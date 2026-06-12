import itertools
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
        try:
            # Convert keys to int and sort
            sorted_breaks = sorted({int(k): v for k, v in price_breaks.items() if float(v) > 0}.items(), reverse=True)
            if not sorted_breaks:
                return 0.0
                
            for break_qty, price in sorted_breaks:
                if qty >= break_qty:
                    return float(price)
            # Default to the lowest quantity break price if it doesn't match
            return float(sorted_breaks[-1][1])
        except (ValueError, TypeError):
            return 0.0

    def optimize_single_source(self, bom_items: List[Dict[str, Any]], part_details: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates total cost for each distributor if they fulfill the entire BOM."""
        results = {}
        distributors = list(self.shipping_config.keys())
        
        for dist in distributors:
            items_cost = 0.0
            fulfilled_items = []
            unfulfilled_items = []
            
            for item in bom_items:
                mpn = item.get("mpn", "").strip()
                if not mpn: continue
                
                target_qty = max(1, int(item.get("quantity", 1)))
                details = part_details.get(mpn.upper(), {})
                dist_data = details.get("distributors", {}).get(dist, {})
                
                stock = dist_data.get("stock", 0)
                moq = max(1, dist_data.get("moq", 1))
                price_breaks = dist_data.get("price_breaks", {})
                
                order_qty = max(target_qty, moq)
                
                if stock >= order_qty and price_breaks:
                    unit_price = self._get_price_for_qty(price_breaks, order_qty)
                    if unit_price > 0:
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
                        unfulfilled_items.append({"mpn": mpn, "reason": "Price not available"})
                else:
                    unfulfilled_items.append({
                        "mpn": mpn,
                        "reason": "Out of stock" if stock < order_qty else "Not carried"
                    })
            
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

    def find_best_combination(self, bom_items: List[Dict[str, Any]], part_details: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Implements a subset-power-set search to find the optimal combination of distributors.
        This evaluates all combinations of distributors and picks the cheapest.
        """
        distributors = list(self.shipping_config.keys())
        best_overall_result = None
        min_total_cost = float('inf')

        # Iterate through all possible combinations (subsets) of distributors
        for r in range(1, len(distributors) + 1):
            for subset in itertools.combinations(distributors, r):
                current_parts = []
                distributors_used_cost = {d: 0.0 for d in subset}
                feasible_subset = True
                
                for item in bom_items:
                    mpn = item.get("mpn", "").strip()
                    if not mpn: continue
                    
                    target_qty = max(1, int(item.get("quantity", 1)))
                    details = part_details.get(mpn.upper(), {})
                    
                    best_dist_in_subset = None
                    best_price_in_subset = float("inf")
                    best_qty = target_qty
                    best_unit_price = 0.0
                    
                    for dist in subset:
                        dist_data = details.get("distributors", {}).get(dist, {})
                        stock = dist_data.get("stock", 0)
                        moq = max(1, dist_data.get("moq", 1))
                        price_breaks = dist_data.get("price_breaks", {})
                        
                        order_qty = max(target_qty, moq)
                        if stock >= order_qty and price_breaks:
                            unit_price = self._get_price_for_qty(price_breaks, order_qty)
                            if unit_price <= 0: continue
                            
                            total = unit_price * order_qty
                            if total < best_price_in_subset:
                                best_price_in_subset = total
                                best_dist_in_subset = dist
                                best_qty = order_qty
                                best_unit_price = unit_price
                    
                    if best_dist_in_subset:
                        current_parts.append({
                            "mpn": mpn,
                            "distributor": best_dist_in_subset,
                            "qty": best_qty,
                            "unit_price": best_unit_price,
                            "total": best_price_in_subset
                        })
                        distributors_used_cost[best_dist_in_subset] += best_price_in_subset
                    else:
                        # Check if this part is available anywhere in the entire catalog.
                        # If it is available elsewhere, but not in our subset, this subset is unfeasible.
                        available_anywhere = False
                        for d in distributors:
                            d_data = details.get("distributors", {}).get(d, {})
                            d_moq = max(1, d_data.get("moq", 1))
                            if d_data.get("stock", 0) >= max(target_qty, d_moq) and d_data.get("price_breaks"):
                                if self._get_price_for_qty(d_data.get("price_breaks"), max(target_qty, d_moq)) > 0:
                                    available_anywhere = True
                                    break
                        
                        if available_anywhere:
                            feasible_subset = False
                            break
                        else:
                            current_parts.append({
                                "mpn": mpn,
                                "distributor": None,
                                "qty": target_qty,
                                "unit_price": 0.0,
                                "total": 0.0,
                                "unfulfilled": True
                            })
                
                if feasible_subset:
                    total_items_cost = 0.0
                    total_shipping_cost = 0.0
                    dist_summaries = {}
                    
                    # Only consider distributors that were actually assigned parts
                    actually_used = {d: cost for d, cost in distributors_used_cost.items() if cost > 0}
                    
                    for dist, cost in actually_used.items():
                        cfg = self.shipping_config[dist]
                        shipping = 0.0 if cost >= cfg["threshold"] else cfg["rate"]
                        total_items_cost += cost
                        total_shipping_cost += shipping
                        dist_summaries[dist] = {
                            "items_cost": round(cost, 2),
                            "shipping_cost": round(shipping, 2),
                            "total": round(cost + shipping, 2)
                        }
                    
                    total_cost = total_items_cost + total_shipping_cost
                    if total_cost < min_total_cost:
                        min_total_cost = total_cost
                        best_overall_result = {
                            "parts": current_parts,
                            "distributors": dist_summaries,
                            "items_cost": round(total_items_cost, 2),
                            "shipping_cost": round(total_shipping_cost, 2),
                            "total_cost": round(total_cost, 2),
                            "subset": subset
                        }
        
        return best_overall_result or {"error": "No feasible combination found", "is_feasible": False}

    def optimize_split_source(self, bom_items: List[Dict[str, Any]], part_details: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates the overall cheapest split purchase across multiple distributors."""
        # Use the power-set search for better results
        return self.find_best_combination(bom_items, part_details)
