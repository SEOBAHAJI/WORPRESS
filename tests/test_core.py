import unittest
from datetime import date, datetime, timedelta

from tests.helpers import TEST_SEED, fresh_db
from accsoft import jalali, licensing, security, services
from accsoft.services import AppError


def mk(db, **kw):
    d = dict(name="کالا", price=1000, cost=600, stock=10, currency="IRT")
    d.update(kw)
    return services.save_product(db, d)


class Products(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()

    def test_usd_pricing_follows_rate(self):
        pid = mk(self.db, currency="USD", price=10, cost=4)
        with self.assertRaises(AppError):  # نرخ دلار تنظیم نشده: فروش با قیمت صفر ممنوع
            services.create_sale(self.db, [{"product_id": pid, "qty": 1}])
        self.db.set("usd_rate", "60000")
        p = services.list_products(self.db)[0]
        self.assertEqual((p["price_toman"], p["cost_toman"]), (600000, 240000))
        self.db.set("usd_rate", "70000")
        self.assertEqual(services.list_products(self.db)[0]["price_toman"], 700000)

    def test_bulk_price_percent_rounding_and_dirty(self):
        a = mk(self.db, price=1234, name="a")
        b = mk(self.db, price=5000, name="b")
        self.db.conn.execute("UPDATE products SET woo_id=7 WHERE id=?", (b,))
        n = services.bulk_price(self.db, "ids", [b], mode="percent", value=10, rounding=100)
        self.assertEqual(n, 1)
        rows = {p["name"]: p for p in services.list_products(self.db)}
        self.assertEqual(rows["b"]["price"], 5500)
        self.assertEqual(rows["a"]["price"], 1234)
        self.assertEqual(rows["b"]["woo_dirty"], 1)
        self.assertEqual(rows["a"]["woo_dirty"], 0)
        services.bulk_price(self.db, "all", mode="percent", value=-100)  # حداقل صفر
        self.assertTrue(all(p["price"] == 0 for p in services.list_products(self.db)))

    def test_bad_input_rejected(self):
        with self.assertRaises(AppError):
            services.save_product(self.db, {"name": ""})
        with self.assertRaises(AppError):
            services.save_product(self.db, {"name": "x", "price": "abc"})
        with self.assertRaises(AppError):
            services.save_product(self.db, {"name": "x", "price": -5})
        mk(self.db, sku="A1")
        with self.assertRaises(AppError):
            mk(self.db, sku="A1")


class Sales(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.p = mk(self.db)

    def test_sale_updates_stock_and_profit(self):
        r = services.create_sale(self.db, [{"product_id": self.p, "qty": 3}], discount=100)
        s = services.get_sale(self.db, r["id"])
        self.assertEqual((s["subtotal"], s["total"], s["cogs"]), (3000, 2900, 1800))
        self.assertEqual(services.list_products(self.db)[0]["stock"], 7)
        services.delete_sale(self.db, r["id"])
        self.assertEqual(services.list_products(self.db)[0]["stock"], 10)

    def test_insufficient_stock_is_atomic(self):
        q = mk(self.db, name="q", stock=1)
        with self.assertRaises(AppError):
            services.create_sale(self.db, [{"product_id": self.p, "qty": 2}, {"product_id": q, "qty": 5}])
        self.assertEqual({x["name"]: x["stock"] for x in services.list_products(self.db)}, {"کالا": 10, "q": 1})
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM sales")["n"], 0)

    def test_discount_cannot_exceed_total(self):
        with self.assertRaises(AppError):
            services.create_sale(self.db, [{"product_id": self.p, "qty": 1}], discount=5000)

    def test_customer_phone_normalised_and_deduped(self):
        c = {"first_name": "علی", "last_name": "رضایی", "phone": "۰۹۱۲-۳۴۵-۶۷۸۹"}
        a = services.create_sale(self.db, [{"product_id": self.p, "qty": 1}], customer=c)
        b = services.create_sale(self.db, [{"product_id": self.p, "qty": 1}], customer={**c, "phone": "+989123456789"})
        self.assertEqual(a["new_customer"] is not None, True)
        self.assertIsNone(b["new_customer"])
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM customers")["n"], 1)
        with self.assertRaises(AppError):
            services.norm_phone("123")

    def test_unit_price_override_and_free_item(self):
        r = services.create_sale(self.db, [{"product_id": self.p, "qty": 2, "unit_price": 700},
                                           {"name": "خدمات", "qty": 1, "unit_price": 300}])
        self.assertEqual(services.get_sale(self.db, r["id"])["total"], 1700)


class Reports(unittest.TestCase):
    def test_profit_channels_expenses_and_top(self):
        db = fresh_db()
        a, b = mk(db, name="a"), mk(db, name="b", price=2000, cost=500)
        services.create_sale(db, [{"product_id": a, "qty": 2}])                       # 2000-1200
        services.create_sale(db, [{"product_id": b, "qty": 5}], channel="online")      # 10000-2500
        services.add_expense(db, "اجاره", 3000)
        t = date.today()
        r = services.report(db, t, t)
        self.assertEqual(r["totals"], {"count": 2, "revenue": 12000, "cogs": 3700, "gross_profit": 8300,
                                       "expenses": 3000, "net_profit": 5300})
        self.assertEqual(r["by_channel"]["online"]["revenue"], 10000)
        self.assertEqual(r["top_products"][0]["name"], "b")
        self.assertEqual(services.report(db, t, t, channel="offline")["totals"]["revenue"], 2000)
        loss = services.report(db, t - timedelta(days=30), t - timedelta(days=20))["totals"]
        self.assertEqual(loss["revenue"], 0)

    def test_net_loss_negative(self):
        db = fresh_db()
        services.add_expense(db, "x", 500)
        t = date.today()
        self.assertEqual(services.report(db, t, t)["totals"]["net_profit"], -500)

    def test_week_starts_saturday_and_month_buckets(self):
        self.assertEqual(jalali.week_start(date(2026, 10, 7)).weekday(), 5)  # چهارشنبه ← شنبه قبل
        s, e = services.preset_range("month", date(2026, 10, 7))
        self.assertEqual(jalali.to_jalali_str(s), "1405/07/01")
        self.assertEqual(jalali.to_jalali_str(e), "1405/07/30")


class Security(unittest.TestCase):
    def test_password_hash(self):
        h = security.hash_password("secret123")
        self.assertTrue(security.check_password("secret123", h))
        self.assertFalse(security.check_password("secret124", h))
        self.assertFalse(security.check_password("x", "garbage"))

    def test_seal_roundtrip_and_tamper(self):
        blob = security.seal("ck_12345")
        self.assertNotIn("ck_12345", blob)
        self.assertEqual(security.unseal(blob), "ck_12345")
        import base64
        raw = bytearray(base64.urlsafe_b64decode(blob))
        raw[-1] ^= 1
        with self.assertRaises(ValueError):
            security.unseal(base64.urlsafe_b64encode(bytes(raw)).decode())

    def test_lockout(self):
        s = security.Sessions()
        for _ in range(5):
            s.fail("u")
        self.assertGreater(s.locked("u"), 0)


class License(unittest.TestCase):
    def test_plans_and_expiry(self):
        today = date(2026, 1, 31)
        k = licensing.make_license(TEST_SEED, "3m", "x", issued=today)
        p, err = licensing.verify_license(k, today)
        self.assertIsNone(err)
        self.assertEqual(p["expires"], "2026-04-30")
        self.assertEqual(licensing.verify_license(k, date(2026, 5, 1))[1], "لایسنس منقضی شده است")
        life = licensing.make_license(TEST_SEED, "lifetime", "x")
        self.assertIsNone(licensing.verify_license(life, date(2099, 1, 1))[1])

    def test_forgery_and_machine_binding(self):
        k = licensing.make_license(TEST_SEED, "12m", "x")
        body, sig = k.split(".")
        other = licensing.make_license(TEST_SEED, "lifetime", "x")
        self.assertIsNotNone(licensing.verify_license(body + "." + other.split(".")[1])[1])  # امضای دیگر
        self.assertIsNotNone(licensing.verify_license("junk")[1])
        bound = licensing.make_license(TEST_SEED, "12m", "x", mid="DEADBEEF00000000")
        self.assertIn("سیستم دیگری", licensing.verify_license(bound)[1])
        wrong = licensing.make_license(bytes(32), "12m", "x")  # کلید خصوصی دیگر
        self.assertIsNotNone(licensing.verify_license(wrong)[1])

    def test_trial_expiry_and_clock_rollback(self):
        db = fresh_db()
        t0 = datetime(2026, 1, 1, 10)
        self.assertEqual(licensing.status(db, t0)["mode"], "trial")
        self.assertEqual(licensing.status(db, t0 + timedelta(days=3))["days_left"], 4)
        self.assertEqual(licensing.status(db, t0 + timedelta(days=8))["mode"], "expired")
        # برگرداندن ساعت پس از انقضا نباید دوره را زنده کند
        st = licensing.status(db, t0 + timedelta(days=1))
        self.assertEqual((st["mode"], st["tampered"]), ("expired", True))

    def test_activation_unlocks(self):
        db = fresh_db()
        licensing.status(db, datetime(2026, 1, 1))
        late = datetime(2026, 3, 1)
        self.assertEqual(licensing.status(db, late)["mode"], "expired")
        k = licensing.make_license(TEST_SEED, "6m", "x", issued=date(2026, 3, 1))
        licensing.activate(db, k, late.date())
        self.assertEqual(licensing.status(db, late)["mode"], "licensed")
        with self.assertRaises(ValueError):
            licensing.activate(db, "bad.key", late.date())


if __name__ == "__main__":
    unittest.main()
