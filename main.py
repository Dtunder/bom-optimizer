import os
import argparse
import html
from pathlib import Path
from src.bom_parser import BOMParser
from src.distributor_client import DistributorClient
from src.optimizer import BOMOptimizer
from src.alternative_matcher import AlternativeMatcher

def generate_html_report(single_results, split_results, bom_items, client, output_path: Path):
    """Generates a premium glassmorphic dark-mode dashboard for the optimized BOM results."""
    
    # Generate parts table rows for single-source option
    single_feasibility = ""
    for dist, res in single_results.items():
        if res.get("is_feasible"):
            status_badge = '<span class="badge success">FEASIBLE</span>'
            total_str = f"&euro; {res['total_cost']:.2f}"
            shipping_str = f"&euro; {res['shipping_cost']:.2f}"
        else:
            status_badge = '<span class="badge danger">UNFEASIBLE</span>'
            total_str = "N/A"
            shipping_str = "N/A"
            
        single_feasibility += f"""
        <tr>
            <td><strong>{html.escape(dist.upper())}</strong></td>
            <td>{status_badge}</td>
            <td>{shipping_str}</td>
            <td><strong>{total_str}</strong></td>
        </tr>
        """

    # Generate split-source parts table rows
    split_rows = ""
    matcher = AlternativeMatcher()
    for item in split_results["parts"]:
        mpn = html.escape(item["mpn"])
        qty = item["qty"]
        dist_name = item.get("distributor", "").upper() if item.get("distributor") else None
        dist = f'<span class="badge info">{html.escape(dist_name)}</span>' if dist_name else '<span class="badge danger">OUT OF STOCK</span>'
        price = f"&euro; {item['unit_price']:.3f}" if item.get("unit_price") else "-"
        total = f"&euro; {item['total']:.2f}" if item.get("total") else "-"
        
        alt_str = ""
        if item.get("unfulfilled"):
            # Try to match alternatives
            alts = matcher.find_alternatives({"mpn": item["mpn"], "footprint": "SMD", "description": ""}, client._mock_db)
            if alts:
                alt_str = "<br><small class='alt-text'>Suggested Alternative: <strong>" + html.escape(alts[0]["mpn"]) + "</strong> (Confidence: " + str(alts[0]["confidence"]) + "%)</small>"
            else:
                alt_str = "<br><small class='alt-text-none'>No compatible alternatives found.</small>"

        split_rows += f"""
        <tr>
            <td>{mpn}{alt_str}</td>
            <td>{qty}</td>
            <td>{dist}</td>
            <td>{price}</td>
            <td><strong>{total}</strong></td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sovereign BOM Sourcing Optimizer Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0d0e15;
            --panel-bg: rgba(22, 24, 37, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-color: #f3f4f6;
            --accent-glow: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            --badge-success: #10b981;
            --badge-danger: #ef4444;
            --badge-info: #3b82f6;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            min-height: 100vh;
            padding: 3rem 1.5rem;
            background-image: 
                radial-gradient(at 10% 20%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
                radial-gradient(at 90% 80%, rgba(168, 85, 247, 0.15) 0px, transparent 50%);
            background-attachment: fixed;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 3rem;
            text-align: center;
        }}
        header h1 {{
            font-size: 2.8rem;
            font-weight: 800;
            letter-spacing: -1px;
            background: var(--accent-glow);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}
        header p {{
            color: #9ca3af;
            font-size: 1.1rem;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }}
        @media(min-width: 768px) {{
            .grid {{
                grid-template-columns: 2fr 1fr;
            }}
        }}
        .panel {{
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 2rem;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }}
        .panel h2 {{
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.75rem;
            color: #ffffff;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}
        th, td {{
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            font-weight: 600;
            color: #9ca3af;
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 1px;
        }}
        td {{
            font-size: 0.95rem;
        }}
        .badge {{
            display: inline-block;
            padding: 0.3rem 0.6rem;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        .badge.success {{ background-color: rgba(16, 185, 129, 0.15); color: var(--badge-success); border: 1px solid var(--badge-success); }}
        .badge.danger {{ background-color: rgba(239, 68, 68, 0.15); color: var(--badge-danger); border: 1px solid var(--badge-danger); }}
        .badge.info {{ background-color: rgba(59, 130, 246, 0.15); color: var(--badge-info); border: 1px solid var(--badge-info); }}
        
        .summary-card {{
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(168, 85, 247, 0.1) 100%);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 20px;
            padding: 2rem;
            text-align: center;
            margin-bottom: 2rem;
        }}
        .summary-card h3 {{
            font-size: 1.1rem;
            color: #a855f7;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 0.5rem;
        }}
        .summary-card .price {{
            font-size: 3.5rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 1rem;
            text-shadow: 0 0 20px rgba(168, 85, 247, 0.4);
        }}
        .summary-card .meta-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-top: 1rem;
            border-top: 1px solid var(--border-color);
            padding-top: 1rem;
        }}
        .summary-card .meta-item span {{
            display: block;
            font-size: 0.8rem;
            color: #9ca3af;
        }}
        .summary-card .meta-item strong {{
            font-size: 1.2rem;
            color: #ffffff;
        }}
        .alt-text {{
            color: #f59e0b;
        }}
        .alt-text-none {{
            color: #ef4444;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Sovereign BOM Optimizer</h1>
            <p>Premium Sourcing & Purchase Consolidation Dashboard</p>
        </header>

        <div class="grid">
            <div class="panel">
                <h2>Split-Source Purchase Plan (Cheapest Mix)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Part (MPN)</th>
                            <th>Qty</th>
                            <th>Best Distributor</th>
                            <th>Unit Price</th>
                            <th>Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {split_rows}
                    </tbody>
                </table>
            </div>

            <div>
                <div class="summary-card">
                    <h3>Optimal Total Cost</h3>
                    <div class="price">&euro; {split_results["total_cost"]:.2f}</div>
                    <div class="meta-grid">
                        <div class="meta-item">
                            <span>Parts Cost</span>
                            <strong>&euro; {split_results["items_cost"]:.2f}</strong>
                        </div>
                        <div class="meta-item">
                            <span>Shipping Fees</span>
                            <strong>&euro; {split_results["shipping_cost"]:.2f}</strong>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h2>Single-Source Options</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Distributor</th>
                                <th>Status</th>
                                <th>Shipping</th>
                                <th>Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {single_feasibility}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    print(f"[SUCCESS] Beautiful glassmorphism dashboard written to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="BOM Sourcing & Settle-Cost Optimizer")
    parser.add_argument("--bom", type=str, required=True, help="Path to BOM CSV file")
    parser.add_argument("--output", type=str, default="reports/bom_report.html", help="Output path for HTML report")
    args = parser.parse_args()

    bom_path = Path(args.bom)
    if not bom_path.exists():
        print(f"[ERROR] BOM file not found: {bom_path}")
        return

    # Parse BOM
    parser_client = BOMParser()
    try:
        bom_items = parser_client.parse(str(bom_path))
    except Exception as e:
        print(f"[ERROR] Parsing CSV failed: {e}")
        return

    print(f"Loaded {len(bom_items)} parts from BOM.")

    # Fetch Distributor prices/stocks
    dist_client = DistributorClient()
    part_details = {}
    for item in bom_items:
        mpn = item["mpn"]
        part_details[mpn.upper()] = dist_client.query_part(mpn)

    # Run Optimizers
    opt = BOMOptimizer()
    single_res = opt.optimize_single_source(bom_items, part_details)
    split_res = opt.optimize_split_source(bom_items, part_details)

    # Print clean command line summary
    print("\n" + "="*50)
    print("           BOM OPTIMIZATION SUMMARY")
    print("="*50)
    print(f"Optimal Split-Source Cost: EUR {split_res['total_cost']:.2f}")
    print(f"  - Parts Cost: EUR {split_res['items_cost']:.2f}")
    print(f"  - Shipping Cost: EUR {split_res['shipping_cost']:.2f}")
    print("\nConsolidated Single-Source Options:")
    for dist, res in single_res.items():
        if res.get("is_feasible"):
            print(f"  - {dist.upper()}: EUR {res['total_cost']:.2f} (Feasible)")
        else:
            print(f"  - {dist.upper()}: Out of stock / Unfeasible")
    print("="*50 + "\n")

    # Generate html dashboard
    output_report = Path(__file__).parent / args.output
    generate_html_report(single_res, split_res, bom_items, dist_client, output_report)

if __name__ == "__main__":
    main()
