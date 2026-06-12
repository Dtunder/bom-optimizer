import time
import json
import random
import os
from pathlib import Path
from typing import Dict, Any, Optional

CACHE_FILE = Path(r"C:\Users\user\.gemini\antigravity-ide\scratch\bom_optimizer\cache\distributor_cache.json")

class DistributorClient:
    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled
        # Seed for reproducibility if needed, or at least initialization
        random.seed(42) 
        self.cache = self._load_cache()
        # Mock database of electronic components with realistic mechatronics parameters
        self._mock_db = {
            "STM32F405RGT6": {
                "description": "MCU 32bit ARM Cortex-M4 1MB Flash LQFP-64",
                "footprint": "LQFP-64",
                "manufacturer": "STMicroelectronics",
                "mouser": {"stock": 420, "price_breaks": {1: 12.50, 10: 10.90, 100: 8.50}, "moq": 1, "shipping_days": 3},
                "digikey": {"stock": 1500, "price_breaks": {1: 11.90, 25: 9.80, 100: 8.20}, "moq": 1, "shipping_days": 2},
                "rs": {"stock": 0, "price_breaks": {1: 14.10, 10: 12.00}, "moq": 1, "shipping_days": 5}
            },
            "ESP32-WROOM-32E": {
                "description": "Wi-Fi + BT + BLE MCU Module, 4MB Flash, PCB Antenna",
                "footprint": "SMD-38",
                "manufacturer": "Espressif Systems",
                "mouser": {"stock": 12000, "price_breaks": {1: 3.80, 50: 3.20, 500: 2.70}, "moq": 1, "shipping_days": 3},
                "digikey": {"stock": 8500, "price_breaks": {1: 3.90, 100: 2.95, 1000: 2.40}, "moq": 1, "shipping_days": 2},
                "rs": {"stock": 500, "price_breaks": {1: 4.50, 10: 3.90}, "moq": 5, "shipping_days": 4}
            },
            "MCP2515-I/SO": {
                "description": "Stand-alone CAN Controller with SPI Interface SOIC-18",
                "footprint": "SOIC-18",
                "manufacturer": "Microchip Technology",
                "mouser": {"stock": 50, "price_breaks": {1: 2.20, 10: 1.95, 100: 1.60}, "moq": 1, "shipping_days": 3},
                "digikey": {"stock": 0, "price_breaks": {1: 2.10, 25: 1.80}, "moq": 1, "shipping_days": 2},
                "rs": {"stock": 1200, "price_breaks": {1: 2.50, 5: 2.10, 100: 1.75}, "moq": 1, "shipping_days": 1}
            },
            "MPU6050": {
                "description": "IMU 3-Axis Gyro & 3-Axis Accel QFN-24",
                "footprint": "QFN-24",
                "manufacturer": "InvenSense",
                "mouser": {"stock": 0, "price_breaks": {1: 5.40}, "moq": 1, "shipping_days": 3},
                "digikey": {"stock": 0, "price_breaks": {1: 5.20}, "moq": 1, "shipping_days": 2},
                "rs": {"stock": 0, "price_breaks": {1: 6.00}, "moq": 1, "shipping_days": 5}
            },
            "R0805-10K-1%": {
                "description": "RES SMD 10K Ohm 1% 1/8W 0805",
                "footprint": "0805",
                "manufacturer": "Yageo",
                "mouser": {"stock": 150000, "price_breaks": {1: 0.10, 100: 0.02, 1000: 0.005}, "moq": 10, "shipping_days": 3},
                "digikey": {"stock": 900000, "price_breaks": {1: 0.08, 100: 0.015, 1000: 0.004}, "moq": 1, "shipping_days": 2},
                "rs": {"stock": 45000, "price_breaks": {1: 0.12, 10: 0.05, 500: 0.008}, "moq": 100, "shipping_days": 1}
            },
            "C0603-100NF-50V": {
                "description": "CAP CER 0.1UF 50V X7R 0603",
                "footprint": "0603",
                "manufacturer": "Murata",
                "mouser": {"stock": 85000, "price_breaks": {1: 0.15, 100: 0.03, 1000: 0.008}, "moq": 10, "shipping_days": 3},
                "digikey": {"stock": 400000, "price_breaks": {1: 0.12, 100: 0.025, 1000: 0.006}, "moq": 1, "shipping_days": 2},
                "rs": {"stock": 0, "price_breaks": {1: 0.18}, "moq": 10, "shipping_days": 4}
            }
        }

    def _load_cache(self) -> Dict[str, Any]:
        if self.cache_enabled and CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_cache(self):
        if self.cache_enabled:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(json.dumps(self.cache, indent=4), encoding="utf-8")

    def query_part(self, mpn: str) -> Dict[str, Any]:
        """Queries pricing and stock info for a given MPN, checking cache first."""
        clean_mpn = mpn.strip().upper()
        if clean_mpn in self.cache:
            return self.cache[clean_mpn]

        # Rate limiting simulation to represent scraper/API delays
        time.sleep(0.1)

        result = {"mpn": mpn, "distributors": {}}
        
        # Look up in mock database or generate realistic details dynamically
        if clean_mpn in self._mock_db:
            result["description"] = self._mock_db[clean_mpn]["description"]
            result["footprint"] = self._mock_db[clean_mpn]["footprint"]
            result["manufacturer"] = self._mock_db[clean_mpn]["manufacturer"]
            
            for dist, data in self._mock_db[clean_mpn].items():
                if dist in ["description", "footprint", "manufacturer"]:
                    continue
                result["distributors"][dist] = data
        else:
            # Generate fallback data for generic parts so the app never fails
            result["description"] = f"Generic component {mpn}"
            result["footprint"] = "SMD"
            result["manufacturer"] = "Generic"
            
            # Add random distributor data
            for dist in ["mouser", "digikey", "rs"]:
                stock = random.choice([0, 100, 500, 10000])
                if stock > 0:
                    base_price = round(random.uniform(0.5, 25.0), 2)
                    result["distributors"][dist] = {
                        "stock": stock,
                        "price_breaks": {
                            1: base_price,
                            10: round(base_price * 0.85, 2),
                            100: round(base_price * 0.70, 2)
                        },
                        "moq": 1,
                        "shipping_days": random.randint(1, 5)
                    }
                else:
                    result["distributors"][dist] = {
                        "stock": 0,
                        "price_breaks": {},
                        "moq": 1,
                        "shipping_days": 5
                    }

        self.cache[clean_mpn] = result
        self._save_cache()
        return result
