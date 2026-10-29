import datetime as dt
import unittest

from analytics import analyze_inventory, forecast_shortages, build_purchase_orders


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2025, 1, 31)
        self.products = [{
            "product_id": "P1", "name": "Apples", "category": "Fresh",
            "supplier": "Orchard Co", "unit_cost": 1.25,
            "lead_time_days": 2, "current_stock": 5,
        }]
        self.sales = []
        for days_ago in range(1, 31):
            self.sales.append({"date": (self.today - dt.timedelta(days=days_ago)).isoformat(),
                               "product_id": "P1", "units_sold": 2})

    def test_computes_7_and_30_day_averages_and_reorder_metrics(self):
        result = analyze_inventory(self.products, self.sales, today=self.today)[0]
        self.assertAlmostEqual(result["avg_daily_sales_7d"], 2)
        self.assertAlmostEqual(result["avg_daily_sales_30d"], 2)
        self.assertAlmostEqual(result["days_of_cover"], 2.5)
        self.assertEqual(result["predicted_stockout_date"], "2025-02-03")
        self.assertEqual(result["reorder_point"], 10)
        self.assertEqual(result["recommended_reorder_qty"], 37)

    def test_zero_sales_has_infinite_cover_and_no_reorder(self):
        result = analyze_inventory(self.products, [], today=self.today)[0]
        self.assertIsNone(result["days_of_cover"])
        self.assertIsNone(result["predicted_stockout_date"])
        self.assertEqual(result["recommended_reorder_qty"], 0)

    def test_shortages_within_14_days_are_sorted_by_soonest_stockout(self):
        items = [
            {"name": "Later", "days_of_cover": 5, "predicted_stockout_date": "2025-02-05"},
            {"name": "Sooner", "days_of_cover": 1, "predicted_stockout_date": "2025-02-01"},
            {"name": "Safe", "days_of_cover": 20, "predicted_stockout_date": "2025-02-20"},
        ]
        self.assertEqual([p["name"] for p in forecast_shortages(items, today=self.today)], ["Sooner", "Later"])

    def test_purchase_orders_group_recommendations_by_supplier_and_total(self):
        items = [
            {"product_id": "P1", "name": "Apples", "supplier": "Orchard Co", "unit_cost": 1.25, "recommended_reorder_qty": 4},
            {"product_id": "P2", "name": "Pears", "supplier": "Orchard Co", "unit_cost": 2, "recommended_reorder_qty": 3},
            {"product_id": "P3", "name": "Milk", "supplier": "Dairy", "unit_cost": 1, "recommended_reorder_qty": 0},
        ]
        orders = build_purchase_orders(items)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["supplier"], "Orchard Co")
        self.assertEqual(orders[0]["total"], 11)
        self.assertEqual(orders[0]["status"], "draft")
        self.assertEqual(len(orders[0]["line_items"]), 2)


if __name__ == "__main__":
    unittest.main()
