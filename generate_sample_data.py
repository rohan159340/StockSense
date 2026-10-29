"""Generate reproducible realistic sample product and daily sales CSV files."""
import csv
import datetime as dt
import random
from pathlib import Path

PRODUCTS = [
    ("P001", "Whole Milk 1L", "Dairy", "North Dairy", 1.35, 2, 28),
    ("P002", "Free Range Eggs 6pk", "Dairy", "North Dairy", 2.10, 3, 34),
    ("P003", "Sourdough Loaf", "Bakery", "Daily Bread Co", 2.40, 1, 18),
    ("P004", "Bananas", "Produce", "Green Valley Produce", 0.32, 2, 48),
    ("P005", "Avocados", "Produce", "Green Valley Produce", 0.85, 2, 31),
    ("P006", "Baby Spinach 150g", "Fresh Food", "Green Valley Produce", 1.55, 2, 15),
    ("P007", "Chicken Breast 500g", "Meat", "Farmstead Foods", 5.40, 3, 22),
    ("P008", "Ground Coffee 250g", "Grocery", "Roast House Supply", 4.20, 5, 44),
    ("P009", "Pasta 500g", "Grocery", "Market Pantry Ltd", 1.10, 4, 39),
    ("P010", "Tomatoes 500g", "Produce", "Green Valley Produce", 1.70, 2, 19),
    ("P011", "Greek Yogurt 500g", "Dairy", "North Dairy", 2.65, 2, 17),
    ("P012", "Orange Juice 1L", "Grocery", "Market Pantry Ltd", 2.30, 4, 29),
]


def generate(output_dir=None, seed=37, today=None):
    output = Path(output_dir) if output_dir else Path(__file__).resolve().parent / "data"
    output.mkdir(parents=True, exist_ok=True)
    today = today or dt.date.today()
    products_path = output / "products.csv"
    sales_path = output / "sales.csv"
    with products_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["product_id", "name", "category", "supplier", "unit_cost", "lead_time_days", "current_stock"])
        writer.writerows(PRODUCTS)

    rng = random.Random(seed)
    base_rates = [5.5, 3.7, 3.0, 8.0, 3.3, 2.6, 2.4, 2.0, 4.5, 3.8, 2.3, 2.8]
    with sales_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "product_id", "units_sold"])
        for offset in range(60, 0, -1):
            day = today - dt.timedelta(days=offset)
            for i, product in enumerate(PRODUCTS):
                weekday_factor = 1.18 if day.weekday() >= 5 else 0.92
                if product[0] in {"P003", "P004", "P010"} and day.weekday() == 5:
                    weekday_factor *= 1.35
                units = max(0, round(base_rates[i] * weekday_factor + rng.gauss(0, max(0.7, base_rates[i] * 0.22))))
                writer.writerow([day.isoformat(), product[0], units])
    return products_path, sales_path


if __name__ == "__main__":
    for path in generate():
        print(path)
