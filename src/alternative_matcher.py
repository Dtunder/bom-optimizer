import re
from typing import List, Dict, Any

class AlternativeMatcher:
    def __init__(self):
        # Maps package code variations to normalized footprints
        self.footprint_aliases = {
            "0805": ["0805", "r0805", "c0805", "smd 0805"],
            "0603": ["0603", "r0603", "c0603", "smd 0603"],
            "SOIC-8": ["soic-8", "soic8", "so-8", "so8"],
            "SOIC-18": ["soic-18", "soic18", "so-18", "so18"],
            "LQFP-64": ["lqfp-64", "lqfp64", "qfp-64"]
        }

    def _normalize_footprint(self, fp: str) -> str:
        clean = fp.strip().upper()
        for norm, aliases in self.footprint_aliases.items():
            if clean.lower() in aliases or any(alias in clean.lower() for alias in aliases):
                return norm
        return clean

    def _extract_numeric_value(self, desc: str) -> str:
        """Helper to extract values like 10K, 100NF, 1UF from description."""
        # Find resistor values (e.g. 10K, 4.7K, 1M, 100R)
        res_match = re.search(r"\b\d+(?:\.\d+)?[KMRR]\b", desc, re.IGNORECASE)
        if res_match:
            return res_match.group(0).upper()
        # Find capacitor values (e.g. 100NF, 10UF, 1UF)
        cap_match = re.search(r"\b\d+(?:\.\d+)?[NUPF]F\b", desc, re.IGNORECASE)
        if cap_match:
            return cap_match.group(0).upper()
        return ""

    def find_alternatives(self, target_part: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Finds matching parts in the catalog with footprint and parameter equivalence."""
        alternatives = []
        target_mpn = target_part.get("mpn", "").upper()
        target_fp = self._normalize_footprint(target_part.get("footprint", ""))
        target_desc = target_part.get("description", "")
        target_val = self._extract_numeric_value(target_desc or target_mpn)
        
        # Determine component class (Resistor, Capacitor, etc.)
        comp_class = None
        if "RES" in target_desc.upper() or "OHM" in target_desc.upper():
            comp_class = "resistor"
        elif "CAP" in target_desc.upper() or "UF" in target_desc.upper() or "NF" in target_desc.upper():
            comp_class = "capacitor"
            
        for mpn, data in catalog.items():
            if mpn.upper() == target_mpn:
                continue
                
            catalog_fp = self._normalize_footprint(data.get("footprint", ""))
            catalog_desc = data.get("description", "")
            catalog_val = self._extract_numeric_value(catalog_desc)
            
            # Check footprint compatibility
            if target_fp != catalog_fp:
                continue
                
            confidence = 0
            
            # Check value match
            if target_val and catalog_val and target_val == catalog_val:
                confidence = 90
            elif comp_class:
                # Ensure we are matching within the same component type
                is_res = "RES" in catalog_desc.upper() or "OHM" in catalog_desc.upper()
                is_cap = "CAP" in catalog_desc.upper() or "UF" in catalog_desc.upper() or "NF" in catalog_desc.upper()
                if comp_class == "resistor" and is_res:
                    confidence = 50
                elif comp_class == "capacitor" and is_cap:
                    confidence = 50
            
            if confidence > 0:
                # Calculate simple stock status
                total_stock = sum(d.get("stock", 0) for d in data.get("distributors", {}).values() if isinstance(d, dict))
                alternatives.append({
                    "mpn": mpn,
                    "description": catalog_desc,
                    "manufacturer": data.get("manufacturer", ""),
                    "confidence": confidence,
                    "total_stock": total_stock,
                    "footprint": catalog_fp
                })
                
        return sorted(alternatives, key=lambda x: x["confidence"], reverse=True)
