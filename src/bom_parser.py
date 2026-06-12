import csv
import re
import os
from typing import List, Dict, Any

class BOMParser:
    def __init__(self):
        # Maps standard keys to lists of common aliases in BOM files
        self.column_aliases = {
            "mpn": ["mpn", "manufacturer part number", "mfg part number", "part number", "part_number", "partno", "order code", "order_code"],
            "quantity": ["quantity", "qty", "count", "amount", "pcs"],
            "description": ["description", "desc", "value", "comment"],
            "footprint": ["footprint", "package", "case", "package/case", "size"],
            "manufacturer": ["manufacturer", "mfr", "mfg", "make", "brand"]
        }

    def _normalize_headers(self, raw_headers: List[str]) -> Dict[str, int]:
        """Maps column name to header index based on aliases."""
        header_map = {}
        for idx, header in enumerate(raw_headers):
            clean_header = header.strip().lower()
            for std_key, aliases in self.column_aliases.items():
                if clean_header in aliases or any(alias in clean_header for alias in aliases):
                    # Prefer exact matches if multiple columns fit, but store mapping
                    header_map[std_key] = idx
                    break
        return header_map

    def parse_csv(self, filepath: str) -> List[Dict[str, Any]]:
        """Parses a BOM CSV file and returns standardized rows."""
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise ValueError("BOM file is empty or does not exist.")

        parsed_items = []
        with open(filepath, mode="r", encoding="utf-8", errors="replace") as f:
            # Handle possible semicolon or comma separation
            sample = f.read(4096)
            f.seek(0)
            
            try:
                dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
            except Exception:
                dialect = csv.excel
            
            reader = csv.reader(f, dialect)
            try:
                headers = next(reader, None)
            except StopIteration:
                raise ValueError("BOM file is empty or missing headers.")
                
            if not headers:
                raise ValueError("BOM file is empty or missing headers.")
            
            header_map = self._normalize_headers(headers)
            
            # Ensure critical columns are mapped
            if "mpn" not in header_map:
                raise ValueError("Could not find Manufacturer Part Number (MPN) column in BOM headers.")
            if "quantity" not in header_map:
                raise ValueError("Could not find Quantity column in BOM headers.")

            for line_idx, row in enumerate(reader, start=2):
                if not row or all(not cell.strip() for cell in row):
                    continue
                
                try:
                    # Robust index check
                    mpn_idx = header_map["mpn"]
                    qty_idx = header_map["quantity"]
                    
                    if mpn_idx >= len(row) or qty_idx >= len(row):
                        continue

                    mpn = row[mpn_idx].strip()
                    raw_qty = row[qty_idx].strip()
                    
                    # Robust quantity extraction: find first number
                    qty_match = re.search(r"(\d+)", raw_qty)
                    qty = int(qty_match.group(1)) if qty_match else 1
                    if qty <= 0: qty = 1
                    
                    description = row[header_map["description"]].strip() if "description" in header_map and len(row) > header_map["description"] else ""
                    footprint = row[header_map["footprint"]].strip() if "footprint" in header_map and len(row) > header_map["footprint"] else ""
                    manufacturer = row[header_map["manufacturer"]].strip() if "manufacturer" in header_map and len(row) > header_map["manufacturer"] else ""
                    
                    if mpn:
                        parsed_items.append({
                            "mpn": mpn,
                            "quantity": qty,
                            "description": description,
                            "footprint": footprint,
                            "manufacturer": manufacturer,
                            "line": line_idx
                        })
                except Exception:
                    # Skip corrupt rows
                    continue

        return parsed_items
