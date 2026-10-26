import itertools
from typing import List, Dict, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP

class BOMOptimizer:
    def __init__(self):
        # Shipping config: (Free threshold, Standard rate)
        self.shipping_config = {
            "mouser": {"threshold": Decimal("50.0"), "rate": Decimal("15.0")},
            "digikey": {"threshold": Decimal("50.0"), "rate": Decimal("18.0")},
            "rs": {"threshold": Decimal("75.0"), "rate": Decimal("12.0")}
        }
        # Offline exchange rate fallback (to EUR)
        self.exchange_rates = {
            "USD": Decimal("0.92"),
            "GBP": Decimal("1.17"),
            "JPY": Decimal("0.006"),
            "CHF": Decimal("1.03"),
            "EUR": Decimal("1.0")
        }

    def _convert_to_eur(self, value: Decimal, currency: str) -> Decimal:
        """Converts a given value to EUR using fallback rates."""
        rate = self.exchange_rates.get(currency.upper(), Decimal("1.0"))
        return (value * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def _get_price_for_qty(self, price_breaks: Dict[int, Any], qty: int, currency: str = "EUR") -> Decimal:
        """Returns the unit price for a given quantity based on price breaks, converted to EUR."""
        if not price_breaks:
            return Decimal("0.0")
        try:
            # Convert keys to int and values to Decimal and sort
            sorted_breaks = sorted({int(k): Decimal(str(v)) for k, v in price_breaks.items() if Decimal(str(v)) > 0}.items(), reverse=True)
            if not sorted_breaks:
                return Decimal("0.0")
                
            unit_price = Decimal("0.0")
            for break_qty, price in sorted_breaks:
                if qty >= break_qty:
                    unit_price = price
                    break
            else:
                # Default to the lowest quantity break price if it doesn't match
                unit_price = sorted_breaks[-1][1]
            
            return self._convert_to_eur(unit_price, currency)
        except (ValueError, TypeError):
            return Decimal("0.0")

    @staticmethod
    def _order_qty_with_price_break(requested_qty: int, moq: int, price_breaks: Dict[int, Any]) -> int:
        """The first quoted price tier is also the smallest purchasable lot.

        Never price an order below its minimum quoted break: doing so
        understates purchase cost and can falsely claim stock sufficiency.
        """
        valid_breaks = []
        for raw_qty, raw_price in price_breaks.items():
            try:
                break_qty = int(raw_qty)
                price = Decimal(str(raw_price))
                if break_qty > 0 and price.is_finite() and price > 0:
                    valid_breaks.append(break_qty)
            except (ValueError, TypeError, ArithmeticError):
                continue
        return max(requested_qty, int(moq), min(valid_breaks)) if valid_breaks else max(requested_qty, int(moq))

    def optimize_single_source(self, bom_items: List[Dict[str, Any]], part_details: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates total cost for each distributor if they fulfill the entire BOM."""
        results = {}
        distributors = list(self.shipping_config.keys())
        
        for dist in distributors:
            items_cost = Decimal("0.0")
            fulfilled_items = []
            unfulfilled_items = []
            stock_used = {}

            # A distributor places one order per part number, not one minimum
            # lot per BOM row. Consolidate repeated MPNs only when the whole
            # requested quantity is purchasable. Otherwise retain the original
            # rows to preserve partial-fulfillment reporting.
            grouped = {}
            for item in bom_items:
                mpn = item.get("mpn", "").strip()
                if mpn:
                    grouped.setdefault(mpn.upper(), []).append(item)
            consolidated = {}
            for key, rows in grouped.items():
                if len(rows) < 2:
                    continue
                requested = sum(max(1, int(row.get("quantity", 1))) for row in rows)
                offer = part_details.get(key, {}).get("distributors", {}).get(dist, {})
                breaks = offer.get("price_breaks", {})
                order_qty = self._order_qty_with_price_break(
                    requested, max(1, offer.get("moq", 1)), breaks
                )
                if (breaks and offer.get("stock", 0) >= order_qty
                        and self._get_price_for_qty(breaks, order_qty, offer.get("currency", "EUR")) > 0):
                    consolidated[key] = requested

            effective_items = []
            seen = set()
            for item in bom_items:
                key = item.get("mpn", "").strip().upper()
                if key in consolidated:
                    if key not in seen:
                        effective_items.append({"mpn": item["mpn"], "quantity": consolidated[key]})
                        seen.add(key)
                else:
                    effective_items.append(item)

            for item in effective_items:
                mpn = item.get("mpn", "").strip()
                if not mpn: continue
                
                target_qty = max(1, int(item.get("quantity", 1)))
                details = part_details.get(mpn.upper(), {})
                dist_data = details.get("distributors", {}).get(dist, {})
                
                stock = dist_data.get("stock", 0)
                moq = max(1, dist_data.get("moq", 1))
                price_breaks = dist_data.get("price_breaks", {})
                currency = dist_data.get("currency", "EUR")
                
                order_qty = self._order_qty_with_price_break(target_qty, moq, price_breaks)
                
                available_stock = stock - stock_used.get(mpn.upper(), 0)
                if available_stock >= order_qty and price_breaks:
                    unit_price = self._get_price_for_qty(price_breaks, order_qty, currency)
                    if unit_price > 0:
                        item_total = unit_price * order_qty
                        items_cost += item_total
                        stock_used[mpn.upper()] = stock_used.get(mpn.upper(), 0) + order_qty
                        fulfilled_items.append({
                            "mpn": mpn,
                            "qty": order_qty,
                            "unit_price": float(unit_price),
                            "total": float(item_total),
                            "shipping_days": dist_data.get("shipping_days", 3)
                        })
                    else:
                        unfulfilled_items.append({"mpn": mpn, "reason": "Price not available"})
                else:
                    unfulfilled_items.append({
                        "mpn": mpn,
                        "reason": "Out of stock" if available_stock < order_qty else "Not carried"
                    })
            
            if not unfulfilled_items:
                shipping_cfg = self.shipping_config[dist]
                shipping_cost = Decimal("0.0") if items_cost >= shipping_cfg["threshold"] else shipping_cfg["rate"]
                results[dist] = {
                    "distributor": dist,
                    "items_cost": float(items_cost.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)),
                    "shipping_cost": float(shipping_cost.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)),
                    "total_cost": float((items_cost + shipping_cost).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)),
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
        """Minimize purchase costs INCLUDING shipping across per-line assignments.

        For up to 50,000 feasible assignments, search exhaustively and certify
        the optimum under the one-distributor-per-BOM-line model. For larger
        search spaces, use bounded local search and disclose that the answer
        is heuristic. No purchase orders are placed.
        """
        distributors = list(self.shipping_config)
        lines = []
        for item in bom_items:
            mpn = item.get("mpn", "").strip()
            if not mpn:
                continue
            target_qty = max(1, int(item.get("quantity", 1)))
            details = part_details.get(mpn.upper(), {})
            options = []
            for dist in distributors:
                dist_data = details.get("distributors", {}).get(dist, {})
                breaks = dist_data.get("price_breaks", {})
                qty = self._order_qty_with_price_break(
                    target_qty, max(1, dist_data.get("moq", 1)), breaks
                )
                if dist_data.get("stock", 0) < qty or not breaks:
                    continue
                unit = self._get_price_for_qty(breaks, qty, dist_data.get("currency", "EUR"))
                if unit > 0 and unit.is_finite():
                    options.append((dist, qty, unit, unit * qty))
            # Retain an explicit unfulfilled row if no supplier can supply it.
            if not options:
                options = [(None, target_qty, Decimal("0"), Decimal("0"))]
            lines.append((mpn, options))

        if not lines:
            return {"error": "No BOM lines to optimize", "is_feasible": False}

        search_space = 1
        for _, options in lines:
            search_space *= len(options)

        evaluations = 0

        def evaluate(assignment):
            nonlocal evaluations
            evaluations += 1
            subtotals = {}
            used = {}
            unfulfilled = 0
            for (mpn, _), (dist, qty, _, cost) in zip(lines, assignment):
                if dist is None:
                    unfulfilled += 1
                    continue
                key = (mpn.upper(), dist)
                stock = part_details.get(mpn.upper(), {}).get("distributors", {}).get(dist, {}).get("stock", 0)
                if used.get(key, 0) + qty > stock:
                    unfulfilled += 1
                    continue
                used[key] = used.get(key, 0) + qty
                subtotals[dist] = subtotals.get(dist, Decimal("0")) + cost
            shipping = sum(
                (Decimal("0") if subtotal >= self.shipping_config[dist]["threshold"]
                 else self.shipping_config[dist]["rate"])
                for dist, subtotal in subtotals.items()
            )
            return (unfulfilled, sum(subtotals.values(), Decimal("0")) + shipping)

        exact = search_space <= 50000
        if exact:
            best_score = (len(lines) + 1, Decimal("Infinity"))
            best_assignment = None
            for assignment in itertools.product(*(opts for _, opts in lines)):
                cost = evaluate(assignment)
                if cost < best_score:
                    best_score = cost
                    best_assignment = assignment
        else:
            # Deterministic bounded multi-start coordinate descent. Evaluate
            # shipping-inclusive cost on EVERY candidate reassignment.
            cheapest = [min(opts, key=lambda opt: opt[3]) for _, opts in lines]
            starts = [cheapest]
            for preferred in distributors:
                starts.append([
                    next((opt for opt in opts if opt[0] == preferred), cheapest[i])
                    for i, (_, opts) in enumerate(lines)
                ])
            best_score = (len(lines) + 1, Decimal("Infinity"))
            best_assignment = None
            for seed in starts:
                current = list(seed)
                current_cost = evaluate(current)
                for _ in range(8):
                    improved = False
                    for i, (_, options) in enumerate(lines):
                        best_local = current[i]
                        best_local_cost = current_cost
                        for option in options:
                            if option == current[i]:
                                continue
                            trial = list(current)
                            trial[i] = option
                            cost = evaluate(trial)
                            if cost < best_local_cost:
                                best_local, best_local_cost = option, cost
                        if best_local != current[i]:
                            current[i] = best_local
                            current_cost = best_local_cost
                            improved = True
                    if not improved:
                        break
                if current_cost < best_score:
                    best_score = current_cost
                    best_assignment = tuple(current)

        parts = []
        subtotals = {}
        stock_used = {}
        for (mpn, _), (dist, qty, unit, cost) in zip(lines, best_assignment):
            key = (mpn.upper(), dist)
            if dist is not None:
                stock = part_details.get(mpn.upper(), {}).get("distributors", {}).get(dist, {}).get("stock", 0)
                if stock_used.get(key, 0) + qty > stock:
                    dist = None
            if dist is None:
                parts.append({
                    "mpn": mpn, "distributor": None, "qty": qty,
                    "unit_price": 0.0, "total": 0.0, "unfulfilled": True
                })
            else:
                stock_used[key] = stock_used.get(key, 0) + qty
                subtotals[dist] = subtotals.get(dist, Decimal("0")) + cost
                parts.append({
                    "mpn": mpn, "distributor": dist, "qty": qty,
                    "unit_price": float(unit), "total": float(cost)
                })

        summaries = {}
        total_shipping = Decimal("0")
        for dist, subtotal in subtotals.items():
            cfg = self.shipping_config[dist]
            shipping = Decimal("0") if subtotal >= cfg["threshold"] else cfg["rate"]
            total_shipping += shipping
            summaries[dist] = {
                "items_cost": float(subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "shipping_cost": float(shipping.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "total": float((subtotal + shipping).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            }
        items_cost = sum(subtotals.values(), Decimal("0"))
        return {
            "parts": parts, "distributors": summaries,
            "items_cost": float(items_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "shipping_cost": float(total_shipping.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "total_cost": float((items_cost + total_shipping).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "subset": tuple(d for d in distributors if d in subtotals),
            "is_feasible": all(p["distributor"] is not None for p in parts),
            "is_optimal": exact and all(p["distributor"] is not None for p in parts),
            "optimization_method": "exact_enumeration" if exact else "bounded_local_search",
            "search_space": search_space,
            "evaluated_assignments": evaluations
        }

    def optimize_split_source(self, bom_items: List[Dict[str, Any]], part_details: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Finds a shipping-aware assignment; check is_optimal for certification."""
        # Search per-line supplier assignments with shipping-inclusive costs.
        return self.find_best_combination(bom_items, part_details)
