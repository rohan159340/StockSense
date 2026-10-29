"""StockSense dashboard server; built only on Python's standard library."""
import csv
import datetime as dt
import io
import json
import mimetypes
import os
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from analytics import analyze_inventory, build_purchase_orders, forecast_shortages
import generate_sample_data

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DRAFTS = BASE / "drafts"
STATIC = BASE / "static"
LOCK = threading.RLock()


def load_csv(path):
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_products():
    rows = load_csv(DATA / "products.csv")
    for row in rows:
        row["unit_cost"] = float(row["unit_cost"])
        row["lead_time_days"] = int(row["lead_time_days"])
        row["current_stock"] = float(row["current_stock"])
    return rows


def load_sales():
    rows = load_csv(DATA / "sales.csv")
    for row in rows:
        row["units_sold"] = float(row["units_sold"])
    return rows


def read_orders():
    DRAFTS.mkdir(exist_ok=True)
    orders = []
    for path in sorted(DRAFTS.glob("*.json")):
        try:
            orders.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return orders


def save_order(order):
    DRAFTS.mkdir(exist_ok=True)
    (DRAFTS / f"{order['order_id']}.json").write_text(json.dumps(order, indent=2), encoding="utf-8")


def analytics_payload():
    inventory = analyze_inventory(load_products(), load_sales())
    return {"inventory": inventory, "shortages": forecast_shortages(inventory), "orders": read_orders()}


def parse_uploaded_csv(raw, expected_headers):
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Could not read CSV as UTF-8.") from exc
    if not rows:
        raise ValueError("CSV must contain a header and at least one row.")
    if not set(expected_headers).issubset(rows[0].keys()):
        raise ValueError("Missing required columns: " + ", ".join(expected_headers))
    return rows


class Handler(BaseHTTPRequestHandler):
    server_version = "StockSense/1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/dashboard":
            try:
                with LOCK:
                    self.send_json(analytics_payload())
            except (OSError, ValueError, KeyError) as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/" or path.startswith("/static/"):
            name = "index.html" if path == "/" else path.removeprefix("/static/")
            if "/" in name or name.startswith("."):
                self.send_error(404)
                return
            file_path = STATIC / name
            if not file_path.is_file():
                self.send_error(404)
                return
            body = file_path.read_bytes()
            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        if length > 5_000_000:
            self.send_json({"error": "Upload exceeds 5 MB."}, 413)
            return
        body = self.rfile.read(length)
        if path == "/api/upload":
            boundary_match = re.search(r"boundary=(.+)", self.headers.get("Content-Type", ""))
            if not boundary_match:
                self.send_json({"error": "Expected multipart CSV upload."}, 400)
                return
            try:
                fields = parse_multipart(body, boundary_match.group(1).strip('"'))
                kind = fields.get("kind", b"products").decode("utf-8")
                if kind not in ("products", "sales") or "file" not in fields:
                    raise ValueError("Choose a products or sales CSV file.")
                required = ("product_id", "name", "category", "supplier", "unit_cost", "lead_time_days", "current_stock") if kind == "products" else ("date", "product_id", "units_sold")
                rows = parse_uploaded_csv(fields["file"], required)
                for row in rows:
                    if kind == "products":
                        float(row["unit_cost"]); int(row["lead_time_days"]); float(row["current_stock"])
                    else:
                        dt.date.fromisoformat(row["date"]); float(row["units_sold"])
                destination = DATA / (kind + ".csv")
                with LOCK:
                    destination.write_bytes(fields["file"])
                self.send_json({"ok": True, "message": f"Loaded {len(rows)} {kind} rows."})
            except (ValueError, KeyError, UnicodeDecodeError) as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "Invalid JSON."}, 400)
            return
        if path == "/api/orders/generate":
            try:
                with LOCK:
                    inventory = analyze_inventory(load_products(), load_sales())
                    orders = build_purchase_orders(inventory)
                    for order in orders:
                        order["order_id"] += "-" + uuid.uuid4().hex[:6]
                        save_order(order)
                    self.send_json({"ok": True, "orders": read_orders()})
            except (OSError, ValueError, KeyError) as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        match = re.fullmatch(r"/api/orders/([^/]+)/(approve|reject)", path)
        if match:
            order_id, decision = match.groups()
            with LOCK:
                orders = read_orders()
                order = next((x for x in orders if x.get("order_id") == order_id), None)
                if order is None:
                    self.send_json({"error": "Order not found."}, 404)
                    return
                if order.get("status") != "draft":
                    self.send_json({"error": "Only draft orders can be reviewed."}, 409)
                    return
                order["status"] = "approved" if decision == "approve" else "rejected"
                order["reviewed_at"] = dt.datetime.now().isoformat(timespec="seconds")
                save_order(order)
                self.send_json({"ok": True, "order": order})
            return
        self.send_error(404)


def parse_multipart(body, boundary):
    fields = {}
    marker = ("--" + boundary).encode()
    for part in body.split(marker):
        if not part or part in (b"--\r\n", b"--"):
            continue
        part = part.strip(b"\r\n")
        if part.endswith(b"--"):
            part = part[:-2].rstrip(b"\r\n")
        header, sep, content = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        disposition = header.decode("latin1")
        name_match = re.search(r'name="([^"]+)"', disposition)
        if name_match:
            fields[name_match.group(1)] = content.rstrip(b"\r\n")
    return fields


def main():
    DATA.mkdir(exist_ok=True)
    DRAFTS.mkdir(exist_ok=True)
    if not (DATA / "products.csv").exists() or not (DATA / "sales.csv").exists():
        generate_sample_data.generate(DATA)
    host = os.environ.get("STOCKSENSE_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("STOCKSENSE_PORT", "8000")))
    print(f"StockSense running on http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
