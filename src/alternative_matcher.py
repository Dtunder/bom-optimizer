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

    def _extract_parameters(self, desc: str) -> Dict[str, str]:
        """Extracts value, voltage, and tolerance from description."""
        params = {"value": "", "voltage": "", "tolerance": ""}
        desc_up = desc.upper()
        
        # Value extraction
        # Resistors (10K, 4.7K, 1M, 100R, 0R)
        res_match = re.search(r"\b\d+(?:\.\d+)?[KMR]\b|\b\d+R\b", desc_up)
        if res_match:
            params["value"] = res_match.group(0)
        
        # Capacitors (100NF, 10UF, 1UF, 22PF)
        cap_match = re.search(r"\b\d+(?:\.\d+)?[NUPF]F\b", desc_up)
        if cap_match:
            params["value"] = cap_match.group(0)
            
        # Voltage (e.g. 50V, 6.3V, 100VDC)
        volt_match = re.search(r"\b\d+(?:\.\d+)?V(?:DC)?\b", desc_up)
        if volt_match:
            params["voltage"] = volt_match.group(0)
            
        # Tolerance (e.g. 1%, 5%, 0.1%)
        tol_match = re.search(r"\b\d+(?:\.\d+)?%", desc_up)
        if tol_match:
            params["tolerance"] = tol_match.group(0)
            
        return params

    def find_alternatives(self, target_part: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Finds matching parts in the catalog with footprint and parameter equivalence."""
        alternatives = []
        target_mpn = target_part.get("mpn", "").upper()
        target_fp = self._normalize_footprint(target_part.get("footprint", ""))
        target_desc = target_part.get("description", "")
        target_params = self._extract_parameters(target_desc or target_mpn)
        
        # Determine component class
        comp_class = None
        if any(x in target_desc.upper() for x in ["RES", "OHM", "R0805", "R0603"]):
            comp_class = "resistor"
        elif any(x in target_desc.upper() for x in ["CAP", "UF", "NF", "PF", "C0805", "C0603"]):
            comp_class = "capacitor"
            
        for mpn, data in catalog.items():
            if mpn.upper() == target_mpn:
                continue
                
            catalog_fp = self._normalize_footprint(data.get("footprint", ""))
            catalog_desc = data.get("description", "")
            catalog_params = self._extract_parameters(catalog_desc)
            
            # Check footprint compatibility (mandatory for generic matching)
            if target_fp and catalog_fp and target_fp != catalog_fp:
                continue
                
            confidence = 0
            
            # Match value (strongest indicator)
            if target_params["value"] and catalog_params["value"] and target_params["value"] == catalog_params["value"]:
                confidence += 70
                
                # Bonus for voltage/tolerance matching
                if target_params["voltage"] and catalog_params["voltage"]:
                    if target_params["voltage"] == catalog_params["voltage"]:
                        confidence += 15
                
                if target_params["tolerance"] and catalog_params["tolerance"]:
                    if target_params["tolerance"] == catalog_params["tolerance"]:
                        confidence += 10
            elif comp_class:
                # Ensure same component type even if value is unknown
                is_res = any(x in catalog_desc.upper() for x in ["RES", "OHM"])
                is_cap = any(x in catalog_desc.upper() for x in ["CAP", "UF", "NF", "PF"])
                if comp_class == "resistor" and is_res:
                    confidence = 20
                elif comp_class == "capacitor" and is_cap:
                    confidence = 20
            
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
