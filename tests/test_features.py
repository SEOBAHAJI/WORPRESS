import json
import threading
import unittest
from datetime import date, datetime, timedelta

from tests.helpers import TEST_SEED, fresh_db
from tests.test_server import Client
from accsoft import access, catalog, licensing, services
from accsoft.config import data_dir
from accsoft.server import create_server
from accsoft.services import AppError


def mk(db, **kw):
    d = dict(name="کالا", price=1000, cost=600, stock=10, currency="IRT")
    d.update(kw)
    return services.save_product(db, d)


class PurchasesAndLedger(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.sup = services.save_supplier(self.db, {"name": "تأمین‌کننده"})

    def test_purchase_adds_stock_and_weighted_average_cost(self):
        p = mk(self.db, stock=10, cost=600)
        r = services.create_purchase(self.db, self.sup, [{"product_id": p, "qty": 10, "unit_cost": 1000}], paid=4000)
        self.assertEqual(r["total"], 10000)
        row = services.list_products(self.db)[0]
        self.assertEqual((row["stock"], row["cost"]), (20, 800))  # (10*600+10*1000)/20
        s = services.list_suppliers(self.db)[0]
        self.assertEqual(s["balance"], 6000)  # بدهی ما

    def test_supplier_payment_cannot_exceed_balance_and_ledger(self):
        p = mk(self.db)
        services.create_purchase(self.db, self.sup, [{"product_id": p, "qty": 5, "unit_cost": 100}], paid=100)
        services.add_payment(self.db, "supplier", self.sup, 250)
        with self.assertRaises(AppError):
            services.add_payment(self.db, "supplier", self.sup, 200)  # فقط ۱۵۰ مانده
        self.assertEqual(services.party_balance(self.db, "supplier", self.sup), 150)
        led = services.ledger(self.db, "supplier", self.sup)
        self.assertEqual([r["balance"] for r in led], [400, 150])
        self.assertEqual(services.parties_summary(self.db)["creditors"]["total"], 150)

    def test_delete_purchase_reverses_stock_or_refuses(self):
        p = mk(self.db, stock=0)
        r = services.create_purchase(self.db, self.sup, [{"product_id": p, "qty": 5, "unit_cost": 100}])
        services.create_sale(self.db, [{"product_id": p, "qty": 4}])
        with self.assertRaises(AppError):  # کالا فروخته شده؛ برگشت موجودی منفی می‌شود
            services.delete_purchase(self.db, r["id"])
        self.assertEqual(services.list_products(self.db)[0]["stock"], 1)

    def test_credit_sale_creates_receivable_and_receipt_settles(self):
        p = mk(self.db)
        cust = {"phone": "09120000001", "first_name": "ع"}
        with self.assertRaises(AppError):  # اعتباری بدون مشتری ممنوع
            services.create_sale(self.db, [{"product_id": p, "qty": 1}], pay_method="credit")
        services.create_sale(self.db, [{"product_id": p, "qty": 3}], customer=cust, pay_method="credit", paid=1000)
        c = services.list_customers(self.db)[0]
        self.assertEqual(c["balance"], 2000)
        services.add_payment(self.db, "customer", c["id"], 2000)
        self.assertEqual(services.list_customers(self.db)[0]["balance"], 0)
        self.assertEqual(services.parties_summary(self.db)["debtors"]["rows"], [])
        # فروش نقدی بدهی نمی‌سازد
        services.create_sale(self.db, [{"product_id": p, "qty": 1}], customer=cust, pay_method="cash")
        self.assertEqual(services.list_customers(self.db)[0]["balance"], 0)

    def test_old_sales_migrate_as_fully_paid(self):
        import sqlite3, tempfile, os
        from accsoft.db import DB, SCHEMA
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        con = sqlite3.connect(path)
        con.executescript(SCHEMA)  # دیتابیس نسخهٔ ۱ (قبل از مهاجرت)
        con.execute("INSERT INTO sales(number,channel,subtotal,total) VALUES(1001,'offline',500,500)")
        con.execute("INSERT INTO users(username,pass_hash) VALUES('a','x')")
        con.execute("INSERT INTO settings VALUES('license_key','abc.def')")
        con.commit()
        con.close()
        db = DB(path)
        self.assertEqual(db.one("SELECT paid FROM sales")["paid"], 500)
        self.assertEqual(db.one("SELECT role FROM users")["role"], "admin")
        self.assertEqual(db.one("SELECT product FROM licenses")["product"], "accsoft")
        self.assertIsNone(db.get("license_key"))


class Users(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.admin = access.create_user(self.db, "admin", "password123", "admin")

    def test_last_admin_protected(self):
        with self.assertRaises(AppError):
            access.update_user(self.db, self.admin, 999, role="cashier")
        with self.assertRaises(AppError):
            access.delete_user(self.db, self.admin, 999)
        second = access.create_user(self.db, "boss", "password123", "admin")
        access.update_user(self.db, second, self.admin, active=False)  # حالا اولی تنها مدیر فعال است
        with self.assertRaises(AppError):
            access.update_user(self.db, self.admin, 999, active=False)

    def test_validation(self):
        for bad in (("ab", "password123", "admin"), ("abc", "short", "admin"), ("abc", "password123", "root")):
            with self.assertRaises(AppError):
                access.create_user(self.db, *bad)
        with self.assertRaises(AppError):
            access.create_user(self.db, "admin", "password123", "cashier")

    def test_unknown_routes_admin_only(self):
        self.assertEqual(access.perm_for("GET", "/api/whatever"), "users")
        self.assertFalse(access.allowed("cashier", "users"))
        self.assertTrue(access.allowed("cashier", "sell"))
        self.assertFalse(access.allowed("cashier", "reports"))
        self.assertFalse(access.allowed("warehouse", "sell"))


class Licensing(unittest.TestCase):
    def test_catalog_driven_plan_and_new_product_no_code(self):
        data = {"version": 5, "revoked": [], "products": [
            {"id": "plugin-sms-pro", "name": "افزونه", "kind": "plugin", "plans": [
                {"id": "weekly", "title": "هفتگی", "months": None, "price": 1}]}]}
        catalog.install(catalog.sign_catalog(TEST_SEED, data))
        self.assertEqual(catalog.plan(catalog.load(), "plugin-sms-pro", "weekly")["price"], 1)
        k = licensing.make_license(TEST_SEED, "weekly", "x", product="plugin-sms-pro", features=["b", "a"])
        p, err = licensing.verify_license(k)
        self.assertEqual((err, p["product"], p["features"]), (None, "plugin-sms-pro", ["a", "b"]))
        db = fresh_db()
        licensing.activate(db, k)
        self.assertIn("plugin-sms-pro", licensing.entitlements(db))
        self.assertEqual(licensing.status(db)["mode"], "trial")  # لایسنس افزونه برنامهٔ اصلی را باز نمی‌کند
        with self.assertRaises(ValueError):
            licensing.make_license(TEST_SEED, "nope", "x", product="plugin-sms-pro")

    def test_catalog_forgery_and_rollback_rejected(self):
        cur = catalog.load()["version"]
        doc = catalog.sign_catalog(TEST_SEED, {"version": cur + 10, "revoked": [], "products": []})
        catalog.install(doc)
        with self.assertRaises(ValueError):  # نسخهٔ قدیمی‌تر (ضد حذف ابطال‌ها)
            catalog.install(catalog.sign_catalog(TEST_SEED, {"version": cur + 1, "revoked": [], "products": []}))
        forged = catalog.sign_catalog(bytes(32), {"version": cur + 99, "revoked": [], "products": []})
        with self.assertRaises(ValueError):
            catalog.install(forged)
        forged2 = json.loads(json.dumps(doc))
        forged2["data"]["version"] += 5  # دستکاری بدون امضای مجدد
        with self.assertRaises(ValueError):
            catalog.install(forged2)

    def test_revocation(self):
        k = licensing.make_license(TEST_SEED, "12m", "x", months=12)
        lid = licensing.verify_license(k)[0]["lid"]
        db = fresh_db()
        licensing.activate(db, k)
        self.assertEqual(licensing.status(db)["mode"], "licensed")
        v = catalog.load()["version"]
        catalog.install(catalog.sign_catalog(TEST_SEED, {"version": v + 1, "revoked": [lid], "products": catalog.default_data()["products"]}))
        st = licensing.status(db)
        self.assertEqual(st["mode"], "expired")
        self.assertIn("ابطال", st["license_error"])
        with self.assertRaises(ValueError):
            licensing.activate(fresh_db(), k)

    def test_legacy_v1_license_still_works(self):
        import base64
        from accsoft import ed25519
        body = json.dumps({"v": 1, "plan": "lifetime", "name": "x", "issued": "2026-01-01", "expires": None, "mid": ""},
                          separators=(",", ":"), sort_keys=True).encode()
        e = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
        k = f"{e(body)}.{e(ed25519.sign(body, TEST_SEED))}"
        p, err = licensing.verify_license(k)
        self.assertEqual((err, p["product"]), (None, "accsoft"))


class ServerFeatures(unittest.TestCase):
    def setUp(self):
        import shutil
        shutil.rmtree(data_dir() / "plugins", ignore_errors=True)
        self.plug = data_dir() / "plugins" / "hello"
        (self.plug / "static").mkdir(parents=True)
        (self.plug / "manifest.json").write_text(json.dumps({
            "id": "hello", "name": "سلام", "product": "plugin-hello", "entry": "plugin.py", "perm": "reports",
            "menu": {"title": "سلام", "page": "index.html"}}), encoding="utf-8")
        (self.plug / "plugin.py").write_text(
            "def register(api):\n"
            "    @api.route('GET', '/ping', perm='reports')\n"
            "    def ping(c):\n"
            "        return {'pong': True, 'shop': api.db.get('shop_name', '')}\n", encoding="utf-8")
        (self.plug / "static" / "index.html").write_text("<h1>plugin</h1>", encoding="utf-8")
        self.db = fresh_db()
        self.srv = create_server(self.db)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.app.port
        self.admin = Client(self.port)
        self.admin.login()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def make_user(self, role):
        st, d, _ = self.admin.call("POST", "/api/users", {"username": role + "1", "password": "password123", "role": role})
        self.assertEqual(st, 200, d)
        c = Client(self.port)
        st, d, _ = c.call("POST", "/api/login", {"username": role + "1", "password": "password123"})
        c.csrf = d["csrf"]
        return c

    def test_role_enforcement(self):
        cashier = self.make_user("cashier")
        _, p, _ = self.admin.call("POST", "/api/products", {"name": "x", "price": 1000, "stock": 5})
        pid = p["id"]
        self.assertEqual(cashier.call("GET", "/api/products?sellable=1")[0], 200)
        self.assertEqual(cashier.call("POST", "/api/sales", {"items": [{"product_id": pid, "qty": 1}]})[0], 200)
        for method, path, body in [("GET", "/api/report?kind=day", None), ("GET", "/api/dashboard", None),
                                   ("POST", "/api/products", {"name": "y"}), ("DELETE", f"/api/products/{pid}", None),
                                   ("POST", "/api/products/bulk-price", {"scope": "all", "mode": "percent", "value": 5}),
                                   ("GET", "/api/users", None), ("GET", "/api/settings", None),
                                   ("PUT", "/api/settings", {"usd_rate": "1"}), ("POST", "/api/woo/pull-products", {}),
                                   ("GET", "/api/suppliers", None), ("DELETE", "/api/sales/1", None),
                                   ("POST", "/api/expenses", {"title": "a", "amount": 1}), ("GET", "/api/audit", None),
                                   ("GET", "/export/report.xlsx?kind=day", None),
                                   ("POST", f"/api/products/{pid}/stock", {"qty": 5}), ("POST", "/api/license", {"key": "x"})]:
            self.assertEqual(cashier.call(method, path, body)[0], 403, (method, path))
        self.assertEqual(cashier.call("GET", "/api/nonexistent")[0], 404)  # مسیر ناموجود چیزی لو نمی‌دهد
        self.assertEqual(self.admin.call("GET", "/api/audit")[0], 200)

    def test_accountant_and_warehouse_scopes(self):
        acc, wh = self.make_user("accountant"), self.make_user("warehouse")
        self.assertEqual(acc.call("GET", "/api/report?kind=day")[0], 200)
        self.assertEqual(acc.call("POST", "/api/expenses", {"title": "a", "amount": 5})[0], 200)
        self.assertEqual(acc.call("POST", "/api/sales", {"items": []})[0], 403)
        self.assertEqual(acc.call("POST", "/api/users", {"username": "zzz", "password": "password123", "role": "admin"})[0], 403)
        self.assertEqual(wh.call("POST", "/api/products", {"name": "w", "price": 1})[0], 200)
        self.assertEqual(wh.call("GET", "/api/report?kind=day")[0], 403)
        self.assertEqual(wh.call("POST", "/api/expenses", {"title": "a", "amount": 5})[0], 403)

    def test_deactivated_or_deleted_user_loses_session_immediately(self):
        c = self.make_user("cashier")
        uid = next(u["id"] for u in self.admin.call("GET", "/api/users")[1] if u["username"] == "cashier1")
        self.assertEqual(c.call("GET", "/api/products")[0], 200)
        self.assertEqual(self.admin.call("PUT", f"/api/users/{uid}", {"active": False})[0], 200)
        self.assertEqual(c.call("GET", "/api/products")[0], 401)
        self.assertEqual(c.call("POST", "/api/login", {"username": "cashier1", "password": "password123"})[0], 400)

    def test_user_management_rules_over_http(self):
        me = self.admin.call("GET", "/api/state")[1]["user"]
        self.assertEqual(self.admin.call("DELETE", f"/api/users/{me['id']}")[0], 400)
        self.assertEqual(self.admin.call("PUT", f"/api/users/{me['id']}", {"role": "cashier"})[0], 400)
        st, d, _ = self.admin.call("POST", "/api/users", {"username": "dup", "password": "short", "role": "cashier"})
        self.assertEqual(st, 400)

    def test_credit_sale_and_payment_flow_http(self):
        _, p, _ = self.admin.call("POST", "/api/products", {"name": "x", "price": 1000, "stock": 5})
        st, s, _ = self.admin.call("POST", "/api/sales", {"items": [{"product_id": p["id"], "qty": 2}], "pay_method": "credit",
                                                          "paid": 500, "customer": {"phone": "09121234567"}})
        self.assertEqual(st, 200)
        _, parties, _ = self.admin.call("GET", "/api/parties")
        self.assertEqual(parties["debtors"]["total"], 1500)
        cid = parties["debtors"]["rows"][0]["id"]
        self.assertEqual(self.admin.call("POST", "/api/payments", {"party_type": "customer", "party_id": cid, "amount": 9999})[0], 400)
        self.assertEqual(self.admin.call("POST", "/api/payments", {"party_type": "customer", "party_id": cid, "amount": 1500})[0], 200)
        _, led, _ = self.admin.call("GET", f"/api/ledger?party_type=customer&party_id={cid}")
        self.assertEqual(led[-1]["balance"], 0)
        self.assertEqual(self.admin.call("GET", "/api/dashboard")[1]["receivable"], 0)

    def test_purchase_http_and_print(self):
        _, p, _ = self.admin.call("POST", "/api/products", {"name": "<b>x</b>", "price": 1000, "stock": 0})
        _, sup, _ = self.admin.call("POST", "/api/suppliers", {"name": "تامین"})
        st, r, _ = self.admin.call("POST", "/api/purchases", {"supplier_id": sup["id"], "paid": 0,
                                                              "items": [{"product_id": p["id"], "qty": 3, "unit_cost": 400}]})
        self.assertEqual((st, r["total"]), (200, 1200))
        st, page, _ = self.admin.call("GET", f"/print/purchase/{r['id']}")
        self.assertEqual(st, 200)
        self.assertNotIn(b"<b>x</b>", page)
        self.assertEqual(self.admin.call("DELETE", f"/api/suppliers/{sup['id']}")[0], 400)  # سابقه دارد

    def test_plugin_lifecycle_license_gated(self):
        self.assertEqual(self.admin.call("GET", "/api/plugins/hello/ping")[0], 404)  # هنوز بارگذاری نشده
        pl = self.admin.call("GET", "/api/state")[1]["plugins"]
        self.assertEqual((pl[0]["id"], pl[0]["licensed"], pl[0]["menu"]), ("hello", False, None))
        self.assertEqual(self.admin.call("GET", "/plugin/hello/index.html")[0], 404)
        key = licensing.make_license(TEST_SEED, "12m", "x", product="plugin-hello", months=12)
        self.assertEqual(self.admin.call("POST", "/api/license", {"key": key})[0], 200)
        st, d, _ = self.admin.call("GET", "/api/plugins/hello/ping")
        self.assertEqual((st, d["pong"]), (200, True))
        st, page, _ = self.admin.call("GET", "/plugin/hello/index.html")
        self.assertEqual((st, page), (200, b"<h1>plugin</h1>"))
        self.assertEqual(self.admin.call("GET", "/plugin/hello/..%2fmanifest.json")[0], 404)
        self.assertEqual(self.admin.call("GET", "/plugin/hello/plugin.py")[0], 404)  # فقط پوشهٔ static
        cashier = self.make_user("cashier")
        self.assertEqual(cashier.call("GET", "/api/plugins/hello/ping")[0], 403)  # perm=reports
        self.assertIsNone(cashier.call("GET", "/api/state")[1]["plugins"][0]["menu"])
        self.assertEqual(self.admin.call("GET", "/api/state")[1]["plugins"][0]["menu"]["title"], "سلام")

    def test_plugin_stops_when_license_expires(self):
        key = licensing.make_license(TEST_SEED, "x", "x", product="plugin-hello", months=1, issued=date.today() - timedelta(days=20))
        self.admin.call("POST", "/api/license", {"key": key})
        self.assertEqual(self.admin.call("GET", "/api/plugins/hello/ping")[0], 200)
        self.db.conn.execute("DELETE FROM licenses")
        self.assertEqual(self.admin.call("GET", "/api/plugins/hello/ping")[0], 402)

    def test_license_catalog_endpoints(self):
        st, d, _ = self.admin.call("GET", "/api/license/catalog")
        self.assertEqual(st, 200)
        self.assertEqual(d["products"][0]["id"], "accsoft")
        st, d, _ = self.admin.call("GET", "/api/license/buy-url?product=accsoft&plan=12m")
        self.assertIn("plan=12m", d["url"])
        self.assertEqual(self.admin.call("GET", "/api/license/buy-url?product=accsoft&plan=bogus")[0], 400)


if __name__ == "__main__":
    unittest.main()
