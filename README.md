# StockSense

StockSense is a local-first inventory management dashboard for small retailers and food businesses. It analyzes product and daily sales CSVs with deterministic Python analytics, forecasts stockouts, recommends reorder quantities, and creates supplier-grouped purchase-order drafts. It does **not** send orders or contact suppliers; approve/reject actions only update local JSON files.

## Requirements

- Python 3.9 or newer (standard library only)
- No package installation required

## Run

From this directory:

```sh
python3 server.py
```

Open <http://localhost:8000>. The server creates `data/products.csv` and `data/sales.csv` with fictional, deterministic sample data for demonstration if they do not already exist. To use another port, set `PORT`, for example `PORT=8080 python3 server.py`.

Run tests:

```sh
python3 -m unittest discover -s tests -v
```

Regenerate sample data (overwrites both sample CSV files):

```sh
python3 generate_sample_data.py
```

## Analytics

For each product, StockSense calculates 7-day and 30-day average daily sales, days of stock cover at the 7-day rate, predicted stockout date, reorder point (`7-day average × (lead time + 3 safety days)`), and a recommended quantity that targets 21 days of cover. Products predicted to stock out in the next 14 days appear in the shortage forecast, ordered by predicted date. Days with no recorded sales count as zero; products without recent sales have no finite cover estimate and a zero recommended order quantity.

## CSV formats

CSV headers must include the exact field names listed below. UTF-8 (with or without BOM) is accepted. Uploading a file replaces the corresponding local data file; keep product IDs consistent between product and sales records.

### Products (`products.csv`)

| Column | Meaning | Example |
|---|---|---|
| `product_id` | Stable unique product identifier | `P001` |
| `name` | Display name | `Whole Milk 1L` |
| `category` | Product category | `Dairy` |
| `supplier` | Supplier group used for draft POs | `North Dairy` |
| `unit_cost` | Cost per unit, numeric | `1.35` |
| `lead_time_days` | Supplier lead time in days, integer | `2` |
| `current_stock` | Current available units, numeric | `28` |

### Daily sales (`sales.csv`)

| Column | Meaning | Example |
|---|---|---|
| `date` | ISO calendar date (`YYYY-MM-DD`) | `2026-10-28` |
| `product_id` | ID matching a product record | `P001` |
| `units_sold` | Units sold on that date, numeric (zero allowed) | `6` |

Upload the two files independently using the CSV import controls on the Overview page. Upload products first if replacing the catalog.

## Purchase order safety

Draft orders are grouped by supplier and contain item quantities, unit costs, line totals, and an order total. Clicking **Approve locally** or **Reject** changes only the JSON file in `drafts/`; the application has no external order-sending integration.

## Project files

- `server.py` — standard-library HTTP server and local JSON/CSV API
- `analytics.py` — deterministic analytics and purchase-order calculations
- `generate_sample_data.py` — reproducible sample dataset generator
- `static/` — dashboard HTML, CSS, and JavaScript
- `data/` — product and sales CSV data
- `drafts/` — saved purchase-order JSON files
- `tests/` — unittest suite
