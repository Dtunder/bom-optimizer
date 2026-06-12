import json
import os
import sys
import csv
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Add project path to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.bom_parser import BOMParser
from src.distributor_client import DistributorClient
from src.optimizer import BOMOptimizer
from src.alternative_matcher import AlternativeMatcher

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
        else:
            # Prevent directory traversal
            clean_path = path.lstrip("/")
            file_path = WEB_DIR / clean_path
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
                
                # Parse in-memory CSV
                lines = csv_data.splitlines()
                if not lines:
                    raise ValueError("Empty CSV content")
                
                # Use BOMParser normalization logic
                parser = BOMParser()
                dialect = csv.Sniffer().sniff(csv_data[:4096]) if csv_data.strip() else csv.excel
                reader = csv.reader(lines, dialect)
                headers = next(reader, None)
                if not headers:
                    raise ValueError("No headers found in CSV")
                
                header_map = parser._normalize_headers(headers)
                if "mpn" not in header_map or "quantity" not in header_map:
                    raise ValueError("Missing critical columns: Part Number (MPN) or Quantity")
                
                bom_items = []
                for idx, row in enumerate(reader, start=2):
                    if not row or all(not cell.strip() for cell in row):
                        continue
                    mpn = row[header_map["mpn"]].strip()
                    raw_qty = row[header_map["quantity"]].strip()
                    qty = int(raw_qty) if raw_qty.isdigit() else 1
                    
                    description = row[header_map["description"]].strip() if "description" in header_map and len(row) > header_map["description"] else ""
                    footprint = row[header_map["footprint"]].strip() if "footprint" in header_map and len(row) > header_map["footprint"] else ""
                    manufacturer = row[header_map["manufacturer"]].strip() if "manufacturer" in header_map and len(row) > header_map["manufacturer"] else ""
                    
                    if mpn:
                        bom_items.append({
                            "mpn": mpn,
                            "quantity": qty,
                            "description": description,
                            "footprint": footprint,
                            "manufacturer": manufacturer,
                            "line": idx
                        })
                
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
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, BOMRequestHandler)
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
