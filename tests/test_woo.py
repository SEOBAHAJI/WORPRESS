import unittest

from tests.helpers import fresh_db
from accsoft import security, services, woo


class FakeWoo(woo.Woo):
    def __init__(self, db, products=(), orders=()):
        self.db, self.rial = db, db.get("woo_unit") == "rial"
        self.products, self.orders, self.calls = list(products), list(orders), []

    def request(self, method, path, params=None, body=None):
        self.calls.append((method, path, params, body))
        if method == "GET" and path == "products":
            return self.products if params["page"] == 1 else []
        if method == "GET" and path == "orders":
            return self.orders if params["page"] == 1 else []
        if path == "products/batch":
            return {"create": [{"id": 900 + i} for i, _ in enumerate(body.get("create", []))]}
        raise AssertionError(path)

    def fetch_image(self, src):
        return ""


WP = {"id": 11, "type": "simple", "name": "پیراهن", "sku": "SH1", "regular_price": "250000",
      "manage_stock": True, "stock_quantity": 8, "categories": [{"name": "لباس"}], "images": []}


class WooTests(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()

    def test_pull_creates_then_updates_without_touching_stock(self):
        w = FakeWoo(self.db, [WP])
        self.assertEqual(woo.pull_products(self.db, woo=w), {"added": 1, "updated": 0})
        p = services.list_products(self.db)[0]
        self.assertEqual((p["price"], p["stock"], p["category"], p["woo_id"]), (250000, 8, "لباس", 11))
        services.adjust_stock(self.db, p["id"], -3)  # فروش حضوری
        w.products = [{**WP, "regular_price": "300000"}]
        self.assertEqual(woo.pull_products(self.db, woo=w), {"added": 0, "updated": 1})
        p = services.list_products(self.db)[0]
        self.assertEqual((p["price"], p["stock"]), (300000, 5))
        woo.pull_products(self.db, update_stock=True, woo=w)
        self.assertEqual(services.list_products(self.db)[0]["stock"], 8)

    def test_push_only_dirty_and_creates_new(self):
        woo.pull_products(self.db, woo=FakeWoo(self.db, [WP]))
        new = services.save_product(self.db, {"name": "جدید", "price": 1000, "stock": 2})
        w = FakeWoo(self.db)
        self.assertEqual(woo.push_products(self.db, woo=w), {"updated": 0, "created": 1})
        self.assertEqual(self.db.one("SELECT woo_id FROM products WHERE id=?", (new,))["woo_id"], 900)
        services.bulk_price(self.db, "all", mode="percent", value=10)
        w = FakeWoo(self.db)
        self.assertEqual(woo.push_products(self.db, woo=w)["updated"], 2)
        sent = {u["id"]: u for u in w.calls[0][3]["update"]}
        self.assertEqual(sent[11]["regular_price"], "275000")
        self.assertEqual(woo.push_products(self.db, woo=FakeWoo(self.db)), {"updated": 0, "created": 0})

    def test_push_refuses_zero_price_for_usd_without_rate(self):
        services.save_product(self.db, {"name": "d", "price": 5, "currency": "USD"})
        with self.assertRaises(services.AppError):
            woo.push_products(self.db, woo=FakeWoo(self.db))

    def test_rial_unit(self):
        self.db.set("woo_unit", "rial")
        w = FakeWoo(self.db, [{**WP, "regular_price": "2500000"}])
        woo.pull_products(self.db, woo=w)
        self.assertEqual(services.list_products(self.db)[0]["price"], 250000)
        self.assertEqual(w.price_out(250000), "2500000")

    def test_orders_import_is_idempotent_and_online(self):
        woo.pull_products(self.db, woo=FakeWoo(self.db, [WP]))
        order = {"id": 77, "number": "77", "date_created": "2026-10-07T10:00:00", "total": "480000",
                 "billing": {"first_name": "سارا", "last_name": "احمدی", "phone": "09121112233"},
                 "line_items": [{"product_id": 11, "name": "پیراهن", "quantity": 2, "price": 250000}]}
        w = FakeWoo(self.db, orders=[order])
        self.assertEqual(woo.pull_orders(self.db, woo=w), {"imported": 1})
        self.assertEqual(woo.pull_orders(self.db, woo=w), {"imported": 0})
        s = services.list_sales(self.db)[0]
        self.assertEqual((s["channel"], s["total"], s["discount"], s["phone"]), ("online", 480000, 20000, "09121112233"))
        self.assertEqual(services.list_products(self.db)[0]["stock"], 6)

    def test_http_url_refused_and_image_validation(self):
        self.db.set("woo_url", "http://shop.example")
        self.db.set("woo_key", security.seal("k"))
        self.db.set("woo_secret", security.seal("s"))
        with self.assertRaises(services.AppError):
            woo.Woo(self.db)
        with self.assertRaises(services.AppError):
            woo.save_image_bytes(b"<?php evil ?>")
        with self.assertRaises(services.AppError):
            woo.save_image_bytes(b"\xff\xd8\xff" + b"0" * (3 * 1024 * 1024))
        self.assertTrue(woo.save_image_bytes(b"\x89PNG\r\n" + b"0" * 10).endswith(".png"))
