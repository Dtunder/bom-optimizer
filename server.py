import json
import os
import sys
import csv
import tempfile
import html
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import src.db as db

# Add project path to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.bom_parser import BOMParser
from src.distributor_client import DistributorClient
from src.optimizer import BOMOptimizer
from src.alternative_matcher import AlternativeMatcher

# Initialize database
db.init_db()

PORT = 8002
WEB_DIR = Path(__file__).parent / "web"

class BOMRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging to keep terminal clean
        pass

    def do_GET(self):
        # Serve index.html by default
        path = self.path.split('?')[0]
        if path == "/" or path == "/index.html":
            file_path = WEB_DIR / "index.html"
            content_type = "text/html"
        elif path == "/api/history":
            history = db.get_recent_history()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(history).encode('utf-8'))
            return
        else:
            # Prevent directory traversal
            clean_path = path.lstrip("/")
            file_path = (WEB_DIR / clean_path).resolve()
            
            # Security check: Ensure file_path is strictly inside WEB_DIR
            # Using parent check to avoid prefix attacks (e.g. web vs web_secret)
            try:
                # Path.is_relative_to is Python 3.9+
                file_path.relative_to(WEB_DIR.resolve())
            except ValueError:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"403 Forbidden")
                return

            if file_path.suffix == ".css":
                content_type = "text/css"
            elif file_path.suffix == ".js":
                content_type = "application/javascript"
            elif file_path.suffix == ".json":
                content_type = "application/json"
            else:
                content_type = "text/plain"

        if file_path.exists() and file_path.is_file():
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        if self.path == "/api/upload":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                payload = json.loads(post_data.decode('utf-8'))
                csv_data = payload.get("csv_data", "")
                filename = payload.get("filename", "uploaded_bom.csv")
                
                if not csv_data.strip():
                    raise ValueError("Empty CSV content")
                
                # Write to temp file to reuse BOMParser
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as tf:
                    tf.write(csv_data)
                    temp_path = tf.name
                
                try:
                    parser = BOMParser()
                    bom_items = parser.parse_csv(temp_path)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                
                if not bom_items:
                    raise ValueError("No valid parts found in CSV")
                
                # Query prices and run optimizers
                dist_client = DistributorClient()
                part_details = {}
                for item in bom_items:
                    mpn = item["mpn"]
                    part_details[mpn.upper()] = dist_client.query_part(mpn)
                
                opt = BOMOptimizer()
                single_res = opt.optimize_single_source(bom_items, part_details)
                split_res = opt.optimize_split_source(bom_items, part_details)
                
                # Include alternatives for out-of-stock items in the response
                matcher = AlternativeMatcher()
                for item in split_res.get("parts", []):
                    if item.get("unfulfilled"):
                        item["alternatives"] = matcher.find_alternatives(
                            {"mpn": item["mpn"], "footprint": "SMD", "description": ""},
                            dist_client._mock_db
                        )
                
                response_data = {
                    "success": True,
                    "bom_items": bom_items,
                    "single_source": single_res,
                    "split_source": split_res
                }
                
                # Save to database
                bom_id = db.save_bom(filename, len(bom_items))
                db.save_history(bom_id, split_res.get("total_cost", 0.0), response_data)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                # Sanitize error message just in case it's displayed in HTML
                self.wfile.write(json.dumps({"success": False, "error": html.escape(str(e))}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, BOMRequestHandler)
    print(f"\n=======================================================")
    print(f"  Sovereign BOM Optimizer Server Running on Port {PORT}")
    print(f"  Access the dashboard at: http://localhost:{PORT}")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == "__main__":
    # Ensure web folder exists
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    run_server()
