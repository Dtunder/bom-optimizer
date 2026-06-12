from typing import List, Dict, Any, Tuple

class BOMOptimizer:
    def __init__(self):
        # Shipping config: (Free threshold, Standard rate)
        self.shipping_config = {
            "mouser": {"threshold": 50.0, "rate": 15.0},
            "digikey": {"threshold": 50.0, "rate": 18.0},
            "rs": {"threshold": 75.0, "rate": 12.0}
        }

    def _get_price_for_qty(self, price_breaks: Dict[int, float], qty: int) -> float:
        """Returns the unit price for a given quantity based on price breaks."""
        if not price_breaks:
            return 0.0
        sorted_breaks = sorted(price_breaks.items(), reverse=True)
        for break_qty, price in sorted_breaks:
            if qty >= break_qty:
                return price
        # Default to the lowest quantity break price if it doesn't match
        return sorted_breaks[-1][1]

    def optimize_single_source(self, bom_items: List[Dict[str, Any]], part_details: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates total cost for each distributor if they fulfill the entire BOM."""
        results = {}
        distributors = ["mouser", "digikey", "rs"]
        
        for dist in distributors:
            items_cost = 0.0
            fulfilled_items = []
            unfulfilled_items = []
            
            for item in bom_items:
                mpn = item["mpn"]
                target_qty = item["quantity"]
                details = part_details.get(mpn.upper(), {})
                dist_data = details.get("distributors", {}).get(dist, {})
                
                stock = dist_data.get("stock", 0)
                moq = dist_data.get("moq", 1)
                price_breaks = dist_data.get("price_breaks", {})
                
                # Check stock and capacity
                order_qty = max(target_qty, moq)
                
                if stock >= order_qty and price_breaks:
                    unit_price = self._get_price_for_qty(price_breaks, order_qty)
                    item_total = unit_price * order_qty
                    items_cost += item_total
                    fulfilled_items.append({
                        "mpn": mpn,
                        "qty": order_qty,
                        "unit_price": unit_price,
                        "total": item_total,
                        "shipping_days": dist_data.get("shipping_days", 3)
                    })
                else:
                    unfulfilled_items.append({
                        "mpn": mpn,
                        "reason": "Out of stock" if stock < order_qty else "Not carried"
                    })
            
            # If all items are fulfilled, calculate shipping and total
            if not unfulfilled_items:
                shipping_cfg = self.shipping_config[dist]
                shipping_cost = 0.0 if items_cost >= shipping_cfg["threshold"] else shipping_cfg["rate"]
                results[dist] = {
                    "distributor": dist,
                    "items_cost": round(items_cost, 2),
                    "shipping_cost": round(shipping_cost, 2),
                    "total_cost": round(items_cost + shipping_cost, 2),
                    "parts": fulfilled_items,
                    "is_feasible": True
                }
            else:
                results[dist] = {
                    "distributor": dist,
                    "is_feasible": False,
                    "unfulfilled": unfulfilled_items
                }
                
        return results

    def optimize_split_source(self, bom_items: List[Dict[str, Any]], part_details: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates the overall cheapest split purchase across multiple distributors."""
        cheapest_parts = []
        distributors_used = {}
        
        for item in bom_items:
            mpn = item["mpn"]
            target_qty = item["quantity"]
            details = part_details.get(mpn.upper(), {})
            
            best_dist = None
            best_price = float("inf")
            best_qty = target_qty
            best_unit_price = 0.0
            
            # Find the cheapest feasible distributor for this part
            for dist, dist_data in details.get("distributors", {}).items():
                stock = dist_data.get("stock", 0)
                moq = dist_data.get("moq", 1)
                price_breaks = dist_data.get("price_breaks", {})
                
                order_qty = max(target_qty, moq)
                if stock >= order_qty and price_breaks:
                    unit_price = self._get_price_for_qty(price_breaks, order_qty)
                    total = unit_price * order_qty
                    if total < best_price:
                        best_price = total
                        best_dist = dist
                        best_qty = order_qty
                        best_unit_price = unit_price
            
            if best_dist:
                cheapest_parts.append({
                    "mpn": mpn,
                    "distributor": best_dist,
                    "qty": best_qty,
                    "unit_price": best_unit_price,
                    "total": best_price,
                    "shipping_days": details["distributors"][best_dist].get("shipping_days", 3)
                })
                distributors_used[best_dist] = distributors_used.get(best_dist, 0.0) + best_price
            else:
                # Part could not be fulfilled at all (completely out of stock)
                cheapest_parts.append({
                    "mpn": mpn,
                    "distributor": None,
                    "qty": target_qty,
                    "unit_price": 0.0,
                    "total": 0.0,
                    "unfulfilled": True
                })

        # Calculate shipping for each used distributor
        total_items_cost = 0.0
        total_shipping_cost = 0.0
        distributor_summaries = {}
        
        for dist, cost in distributors_used.items():
            shipping_cfg = self.shipping_config[dist]
            shipping = 0.0 if cost >= shipping_cfg["threshold"] else shipping_cfg["rate"]
            total_items_cost += cost
            total_shipping_cost += shipping
            distributor_summaries[dist] = {
                "items_cost": round(cost, 2),
                "shipping_cost": round(shipping, 2),
                "total": round(cost + shipping, 2)
            }

        return {
            "parts": cheapest_parts,
            "distributors": distributor_summaries,
            "items_cost": round(total_items_cost, 2),
            "shipping_cost": round(total_shipping_cost, 2),
            "total_cost": round(total_items_cost + total_shipping_cost, 2)
        }
