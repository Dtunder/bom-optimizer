import re
from typing import List, Dict, Any

class AlternativeMatcher:
    def __init__(self):
        # Maps package code variations to normalized footprints
        self.footprint_aliases = {
            "0805": ["0805", "r0805", "c0805", "smd 0805", "0805-metric"],
            "0603": ["0603", "r0603", "c0603", "smd 0603", "0603-metric"],
            "0402": ["0402", "r0402", "c0402", "smd 0402", "0402-metric"],
            "1206": ["1206", "r1206", "c1206", "smd 1206", "1206-metric"],
            "SOIC-8": ["soic-8", "soic8", "so-8", "so8", "soic08"],
            "SOIC-14": ["soic-14", "soic14", "so-14", "so14"],
            "SOIC-16": ["soic-16", "soic16", "so-16", "so16"],
            "SOIC-18": ["soic-18", "soic18", "so-18", "so18"],
            "LQFP-64": ["lqfp-64", "lqfp64", "qfp-64", "tqfp-64"],
            "SOT-23": ["sot-23", "sot23", "sot-23-3", "sot23-3"]
        }

    def _normalize_footprint(self, fp: str) -> str:
        if not fp:
            return ""
        clean = fp.strip().upper()
        for norm, aliases in self.footprint_aliases.items():
            if clean.lower() in aliases or any(alias in clean.lower() for alias in aliases):
                return norm
        return clean

    def _normalize_value(self, val_str: str, comp_class: str) -> float:
        if not val_str:
            return 0.0
        
        val_str = val_str.upper().replace("OHM", "R").replace("\u03a9", "R")
        
        if comp_class == "resistor":
            # 10K, 4.7K, 1M, 100R, 0R, 4R7
            # Handle 4K7 style
            match_inter = re.search(r"(\d+)([KMR])(\d+)", val_str)
            if match_inter:
                num = float(match_inter.group(1) + "." + match_inter.group(3))
                suffix = match_inter.group(2)
            else:
                match = re.search(r"(\d+(?:\.\d+)?)\s*([KMR]?)", val_str)
                if not match: return 0.0
                num = float(match.group(1))
                suffix = match.group(2)
                
            if suffix == "K": return num * 1e3
            if suffix == "M": return num * 1e6
            return num
        
        if comp_class == "capacitor":
            # 100NF, 10UF, 1UF, 22PF
            match = re.search(r"(\d+(?:\.\d+)?)\s*([NUPF]?)F?", val_str)
            if not match: return 0.0
            num = float(match.group(1))
            suffix = match.group(2)
            if suffix == "P": return num * 1e-12
            if suffix == "N": return num * 1e-9
            if suffix == "U": return num * 1e-6
            return num
            
        return 0.0

    def _extract_parameters(self, desc: str) -> Dict[str, Any]:
        """Extracts numeric value, voltage, and tolerance from description."""
        params = {"value": 0.0, "raw_value": "", "voltage": 0.0, "tolerance": 100.0, "class": None}
        desc_up = desc.upper().replace("OHM", "R").replace("\u03a9", "R")
        desc_up = re.sub(r"(\d+)\s*([KMRNUPF]F?)\b", r"\1\2", desc_up)
        
        if any(x in desc_up for x in ["RES", "R0805", "R0603"]) or re.search(r"\b\d+R\b|\bR\b", desc_up):
            params["class"] = "resistor"
        elif any(x in desc_up for x in ["CAP", "UF", "NF", "PF", "C0805", "C0603"]):
            params["class"] = "capacitor"

        # Value extraction
        if params["class"] == "resistor":
            res_match = re.search(r"\b\d+(?:\.\d+)?[KMR]\b|\b\d+R\b|\b\d+[KMR]\d+\b", desc_up)
            if res_match:
                params["raw_value"] = res_match.group(0)
                params["value"] = self._normalize_value(params["raw_value"], "resistor")
        
        if params["class"] == "capacitor":
            cap_match = re.search(r"\b\d+(?:\.\d+)?[NUPF]F?\b", desc_up)
            if cap_match:
                params["raw_value"] = cap_match.group(0)
                params["value"] = self._normalize_value(params["raw_value"], "capacitor")
            
        # Voltage (e.g. 50V, 6.3V, 100VDC)
        volt_match = re.search(r"\b(\d+(?:\.\d+)?)\s*V(?:DC)?\b", desc_up)
        if volt_match:
            params["voltage"] = float(volt_match.group(1))
            
        # Tolerance (e.g. 1%, 5%, 0.1%)
        tol_match = re.search(r"\b(\d+(?:\.\d+)?)\s*%", desc_up)
        if tol_match:
            params["tolerance"] = float(tol_match.group(1))
            
        return params

    def find_alternatives(self, target_part: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Finds matching parts in the catalog with footprint and parameter equivalence."""
        alternatives = []
        target_mpn = target_part.get("mpn", "").upper()
        target_fp = self._normalize_footprint(target_part.get("footprint", ""))
        target_desc = target_part.get("description", "")
        target_params = self._extract_parameters(target_desc or target_mpn)
        
        for mpn, data in catalog.items():
            if mpn.upper() == target_mpn:
                continue
            
            # Filter EOL/Obsolete parts
            lifecycle = str(data.get("lifecycle_status", "")).upper()
            if any(x in lifecycle for x in ["OBSOLETE", "EOL", "DISCONTINUED", "NRND"]):
                continue
                
            catalog_fp = self._normalize_footprint(data.get("footprint", ""))
            catalog_desc = data.get("description", "")
            catalog_params = self._extract_parameters(catalog_desc)
            
            # Ensure same component type
            if target_params["class"] and catalog_params["class"] and target_params["class"] != catalog_params["class"]:
                continue

            # Check footprint compatibility (mandatory for generic matching)
            if target_fp and catalog_fp and target_fp != catalog_fp:
                continue
                
            # SAFETY CONSTRAINTS:
            # 1. Voltage must be >= target voltage
            if target_params["voltage"] > 0 and catalog_params["voltage"] > 0:
                if catalog_params["voltage"] < target_params["voltage"]:
                    continue
            
            # 2. Tolerance must be <= target tolerance
            if target_params["tolerance"] < 100.0 and catalog_params["tolerance"] < 100.0:
                if catalog_params["tolerance"] > target_params["tolerance"]:
                    continue

            confidence = 0
            
            # Match value (strongest indicator) - Use normalized values
            if target_params["value"] > 0 and catalog_params["value"] > 0:
                if abs(target_params["value"] - catalog_params["value"]) < (target_params["value"] * 0.0001):
                    confidence += 70
                else:
                    # If values are explicitly extracted but don't match, this is a bad alternative
                    continue
            
            if confidence > 0:
                # Bonus for voltage/tolerance matching
                if target_params["voltage"] > 0 and catalog_params["voltage"] > 0:
                    if catalog_params["voltage"] == target_params["voltage"]:
                        confidence += 15
                
                if target_params["tolerance"] < 100.0 and catalog_params["tolerance"] < 100.0:
                    if catalog_params["tolerance"] == target_params["tolerance"]:
                        confidence += 10
            
            if confidence > 0:
                total_stock = sum(d.get("stock", 0) for d in data.get("distributors", {}).values() if isinstance(d, dict))
                alternatives.append({
                    "mpn": mpn,
                    "description": catalog_desc,
                    "manufacturer": data.get("manufacturer", ""),
                    "confidence": min(confidence, 100),
                    "total_stock": total_stock,
                    "footprint": catalog_fp or data.get("footprint", ""),
                    "params": catalog_params
                })
                
        return sorted(alternatives, key=lambda x: x["confidence"], reverse=True)
