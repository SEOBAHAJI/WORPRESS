import unittest

from tests.helpers import fresh_db
from accsoft import security, services, woo


class FakeWoo(woo.Woo):
    def __init__(self, db, products=(), orders=(), variations=None):
        self.db, self.rial = db, db.get("woo_unit") == "rial"
        self.products, self.orders, self.calls = list(products), list(orders), []
        self.variations, self.media = variations or {}, []

    def wp_media(self, filename, blob, mime):
        if self.db.get("wp_user", "") == "":
            raise services.AppError("no wp credentials")
        self.media.append((filename, mime, len(blob)))
        return 5000 + len(self.media)

    def request(self, method, path, params=None, body=None):
        self.calls.append((method, path, params, body))
        if method == "GET" and path == "products":
            return self.products if params["page"] == 1 else []
        if method == "GET" and path == "orders":
            return self.orders if params["page"] == 1 else []
        if method == "GET" and path.endswith("/variations"):
            return self.variations.get(int(path.split("/")[1]), []) if params["page"] == 1 else []
        if path == "products/batch" or path.endswith("/variations/batch"):
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
        self.assertEqual(woo.pull_products(self.db, woo=w), {"added": 1, "updated": 0, "variations": 0})
        p = services.list_products(self.db)[0]
        self.assertEqual((p["price"], p["stock"], p["category"], p["woo_id"]), (250000, 8, "لباس", 11))
        services.adjust_stock(self.db, p["id"], -3)  # فروش حضوری
        w.products = [{**WP, "regular_price": "300000"}]
        self.assertEqual(woo.pull_products(self.db, woo=w), {"added": 0, "updated": 1, "variations": 0})
        p = services.list_products(self.db)[0]
        self.assertEqual((p["price"], p["stock"]), (300000, 5))
        woo.pull_products(self.db, update_stock=True, woo=w)
        self.assertEqual(services.list_products(self.db)[0]["stock"], 8)

    def test_push_only_dirty_and_creates_new(self):
        woo.pull_products(self.db, woo=FakeWoo(self.db, [WP]))
        new = services.save_product(self.db, {"name": "جدید", "price": 1000, "stock": 2})
        w = FakeWoo(self.db)
        r = woo.push_products(self.db, woo=w)
        self.assertEqual((r["updated"], r["created"]), (0, 1))
        self.assertEqual(self.db.one("SELECT woo_id FROM products WHERE id=?", (new,))["woo_id"], 900)
        services.bulk_price(self.db, "all", mode="percent", value=10)
        w = FakeWoo(self.db)
        self.assertEqual(woo.push_products(self.db, woo=w)["updated"], 2)
        sent = {u["id"]: u for u in w.calls[0][3]["update"]}
        self.assertEqual(sent[11]["regular_price"], "275000")
        r = woo.push_products(self.db, woo=FakeWoo(self.db))
        self.assertEqual((r["updated"], r["created"]), (0, 0))

    VAR = {"id": 20, "type": "variable", "name": "کفش", "sku": "", "images": [], "categories": [{"name": "کفش"}]}
    VARS = {20: [{"id": 201, "sku": "K-41", "regular_price": "900000", "manage_stock": True, "stock_quantity": 4,
                  "attributes": [{"name": "سایز", "option": "41"}], "image": {}},
                 {"id": 202, "sku": "K-42", "regular_price": "950000", "manage_stock": True, "stock_quantity": 2,
                  "attributes": [{"name": "سایز", "option": "42"}], "image": {}}]}

    def test_variable_product_pull_sell_push(self):
        w = FakeWoo(self.db, [self.VAR], variations=self.VARS)
        r = woo.pull_products(self.db, woo=w)
        self.assertEqual((r["added"], r["variations"]), (1, 2))
        rows = services.list_products(self.db)
        self.assertEqual([p["kind"] for p in rows], ["variable", "variation", "variation"])  # والد سپس تنوع‌ها
        self.assertEqual(rows[1]["name"], "کفش - سایز: 41")
        sellable = services.list_products(self.db, sellable=True)
        self.assertEqual(len(sellable), 2)
        with self.assertRaises(services.AppError):  # فروش والد متغیر ممنوع
            services.create_sale(self.db, [{"product_id": rows[0]["id"], "qty": 1}])
        v41 = sellable[0]["id"] if sellable[0]["sku"] == "K-41" else sellable[1]["id"]
        services.create_sale(self.db, [{"product_id": v41, "qty": 1}])
        w2 = FakeWoo(self.db)
        r = woo.push_products(self.db, woo=w2)
        self.assertEqual(r["updated"], 1)
        method, path, _, body = w2.calls[0]
        self.assertEqual(path, "products/20/variations/batch")
        self.assertEqual(body["update"], [{"id": 201, "regular_price": "900000", "manage_stock": True, "stock_quantity": 3}])
        # ورود مجدد تنوع‌ها تکراری نمی‌سازد
        self.assertEqual(woo.pull_products(self.db, woo=w)["added"], 0)
        # سفارش با variation_id به تنوع درست وصل می‌شود و موجودی همان را کم می‌کند
        order = {"id": 5, "number": "5", "total": "950000", "billing": {},
                 "line_items": [{"product_id": 20, "variation_id": 202, "name": "کفش", "quantity": 1, "price": 950000}]}
        woo.pull_orders(self.db, woo=FakeWoo(self.db, orders=[order]))
        stocks = {p["sku"]: p["stock"] for p in services.list_products(self.db, sellable=True)}
        self.assertEqual(stocks, {"K-41": 3, "K-42": 1})
        services.delete_product(self.db, rows[0]["id"])  # حذف والد = حذف تنوع‌ها
        self.assertEqual(services.list_products(self.db), [])

    def test_image_push_requires_wp_credentials_and_clears_flag(self):
        woo.pull_products(self.db, woo=FakeWoo(self.db, [WP]))
        pid = services.list_products(self.db)[0]["id"]
        name = woo.save_image_bytes(b"\x89PNG\r\n" + b"0" * 10)
        self.db.conn.execute("UPDATE products SET image=?, image_dirty=1 WHERE id=?", (name, pid))
        r = woo.push_products(self.db, woo=FakeWoo(self.db))  # بدون اعتبار وردپرس
        self.assertEqual((r["images"], r["images_failed"]), (0, 1))
        self.assertEqual(r["updated"], 1)  # قیمت/موجودی با وجود خطای تصویر ارسال شد
        self.assertEqual(self.db.one("SELECT image_dirty FROM products WHERE id=?", (pid,))["image_dirty"], 1)
        self.db.set("wp_user", "admin")
        w = FakeWoo(self.db)
        r = woo.push_products(self.db, woo=w)
        self.assertEqual((r["images"], r["images_failed"]), (1, 0))
        self.assertEqual(w.media[0][1], "image/png")
        self.assertEqual(w.calls[0][3]["update"][0]["images"], [{"id": 5001}])
        self.assertEqual(self.db.one("SELECT image_dirty FROM products WHERE id=?", (pid,))["image_dirty"], 0)

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

    def test_normalize_url(self):
        n = woo.normalize_url
        self.assertEqual(n(" shop.ir/ "), "https://shop.ir")
        self.assertEqual(n("https://shop.ir/wp-json/wc/v3/"), "https://shop.ir")
        self.assertEqual(n("http://a.ir/wp-admin/x"), "http://a.ir")
        self.assertEqual(n(""), "")

    def test_sync_all_first_time_pulls_stock_then_keeps_local_stock(self):
        w = FakeWoo(self.db, [WP])
        r = woo.sync_all(self.db, woo=w)
        self.assertEqual((r["products"]["added"], r["orders"]["imported"] if "imported" in r["orders"] else 0), (1, 0))
        p = services.list_products(self.db)[0]
        self.assertEqual(p["stock"], 8)
        services.adjust_stock(self.db, p["id"], -3)  # فروش حضوری → باید به سایت برود، نه برعکس
        w2 = FakeWoo(self.db, [WP])
        r = woo.sync_all(self.db, woo=w2)
        self.assertEqual(services.list_products(self.db)[0]["stock"], 5)
        sent = [c for c in w2.calls if c[1] == "products/batch"]
        self.assertEqual(sent[0][3]["update"][0]["stock_quantity"], 5)
        first_get = next(i for i, c in enumerate(w2.calls) if c[0] == "GET")
        self.assertLess(w2.calls.index(sent[0]), first_get)  # ابتدا ارسال، بعد دریافت
