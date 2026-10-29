"""Deterministic inventory forecasting and purchase-order calculations."""
import datetime as dt


def _date(value):
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def analyze_inventory(products, sales, today=None):
    """Return each product with 7/30-day sales rates and reorder metrics.

    Sales dates are calendar dates. Missing sales days count as zero. The stockout
    date is today plus the ceiling of days of cover, with zero cover on today.
    """
    today = _date(today or dt.date.today())
    by_product = {}
    for sale in sales:
        pid = str(sale.get("product_id", ""))
        date = _date(sale["date"])
        if date < today and (today - date).days <= 30:
            by_product.setdefault(pid, []).append((date, float(sale["units_sold"])))

    results = []
    for product in products:
        item = dict(product)
        pid = str(item.get("product_id", ""))
        recent = by_product.get(pid, [])
        avg7 = sum(qty for date, qty in recent if (today - date).days <= 7) / 7
        avg30 = sum(qty for _, qty in recent) / 30
        stock = float(item["current_stock"])
        lead = int(item["lead_time_days"])
        daily = avg7
        cover = stock / daily if daily > 0 else None
        if cover is None:
            stockout = None
        else:
            stockout = (today + dt.timedelta(days=max(0, int(cover + 0.999999)))).isoformat()
        reorder_point = int((daily * (lead + 3)) + 0.999999)
        target_stock = int((daily * 21) + 0.999999)
        qty = max(0, target_stock - int(stock)) if daily > 0 else 0
        item.update({
            "avg_daily_sales_7d": round(avg7, 2),
            "avg_daily_sales_30d": round(avg30, 2),
            "days_of_cover": round(cover, 1) if cover is not None else None,
            "predicted_stockout_date": stockout,
            "reorder_point": reorder_point,
            "recommended_reorder_qty": qty,
        })
        results.append(item)
    return results


def forecast_shortages(inventory, today=None, days=14):
    today = _date(today or dt.date.today())
    found = []
    for item in inventory:
        date = item.get("predicted_stockout_date")
        if date is None:
            continue
        stockout = _date(date)
        delta = (stockout - today).days
        if 0 <= delta <= days:
            found.append(item)
    return sorted(found, key=lambda item: (_date(item["predicted_stockout_date"]), item.get("name", "")))


def build_purchase_orders(inventory):
    grouped = {}
    for item in inventory:
        qty = int(item.get("recommended_reorder_qty", 0))
        if qty <= 0:
            continue
        supplier = str(item.get("supplier", "Unassigned"))
        price = float(item["unit_cost"])
        group = grouped.setdefault(supplier, [])
        group.append({
            "product_id": item.get("product_id"), "name": item["name"],
            "quantity": qty, "unit_cost": round(price, 2),
            "line_total": round(qty * price, 2),
        })
    orders = []
    for idx, supplier in enumerate(sorted(grouped), start=1):
        lines = grouped[supplier]
        orders.append({
            "order_id": "PO-" + dt.datetime.now().strftime("%Y%m%d") + f"-{idx:03d}",
            "supplier": supplier, "created_at": dt.datetime.now().isoformat(timespec="seconds"),
            "status": "draft", "line_items": lines,
            "total": round(sum(line["line_total"] for line in lines), 2),
        })
    return orders
