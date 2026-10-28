# BOM Optimizer

[![Tests](https://github.com/Dtunder/bom-optimizer/actions/workflows/tests.yml/badge.svg)](https://github.com/Dtunder/bom-optimizer/actions/workflows/tests.yml)

Plan multi-distributor electronic component sourcing from a CSV BOM. The optimizer accounts for minimum order quantities (MOQ), quoted price breaks, available stock, and per-distributor shipping fees to compare a single-source purchase with a split-source plan.

## Demo data

The bundled distributor catalog is **simulated**. The application makes no live Mouser, DigiKey, or RS API calls, does not scrape distributor sites, and does not place orders. Prices, stock, shipping rates, and exchange rates are illustrative mock data, not current quotes.

With the included `sample_bom.csv`, the optimizer finds a feasible split-source plan for **EUR 143.45** in parts and **EUR 0.00** shipping. The least expensive feasible single-source option in the same run is Mouser at **EUR 179.50**, so the split saves EUR 36.05 in the mock scenario. These are reproducible results from the bundled catalog, not live market prices.

## Run the CLI

Python 3.11 or newer is recommended.

```bash
python -m pip install -r requirements.txt
python main.py --bom sample_bom.csv --output reports/report.html
```

The command prints the single-source comparison and split-source total, then writes an HTML report. The cache defaults to `cache/distributor_cache.json` inside the repository. Set `BOM_CACHE_FILE` to use a different cache file.

## Run the local web app

```bash
python server.py
```

Open <http://localhost:8002>. Uploaded BOMs are processed against the same simulated catalog and the local history is stored in SQLite under `cache/`.

## Method and limits

- Each BOM line is assigned to one distributor; a line's requested quantity is not divided across suppliers.
- MOQ and the smallest positive quoted price-break lot are applied before stock checks and pricing. Duplicate MPN lines share the same supplier stock.
- The search minimizes parts cost plus shipping. It exhaustively evaluates up to 50,000 supplier assignments and marks those results as optimal. Larger search spaces use bounded multi-start local search and are reported as not certified optimal.
- Shipping thresholds, prices, stock, and offline currency conversions are fixed illustrative inputs. The tool does not validate lifecycle status, authorized sourcing, taxes, delivery promises, or real purchase terms.

## Tests

```bash
python -m pytest -q
```

GitHub Actions runs the same suite on Python 3.11 for pushes and pull requests.
