"""موتور سازگار با لایسنس‌سرور قدیمی (افزونهٔ وردپرس) با wpdb شبیه‌سازی‌شده؛ بدون php نادیده گرفته می‌شود."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PHP = shutil.which("php")
H = str(Path(__file__).parent / "php" / "harness.php")


@unittest.skipUnless(PHP, "php نصب نیست")
class Legacy(unittest.TestCase):
    def setUp(self):
        self.db = str(Path(tempfile.mkdtemp()) / "t.db")

    def run_php(self, cmd, arg=None):
        r = subprocess.run([PHP, H, self.db, cmd, json.dumps(arg or {})], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def api(self, action, post=None, opts=None, get=None):
        out = self.run_php("api", {"get": {"action": action, **(get or {})}, "post": post or {}, "opts": opts})
        return json.loads(out)

    SEC = {"accsoft_settings": {"wl_api_secret": "s3cret", "zibal_merchant": "zibal"}}

    def test_import_activate_validate_flow(self):
        data = {"licenses": [{"id": "a1", "license_key": "HESABD-AAAA-BBBB-CCCC-DDDD", "email": "U@x.com", "product": "hesabdar", "status": "active", "expires_at": None, "created_at": "2026-07-06 13:36:24"}],
                "activations": [{"license_key": "HESABD-AAAA-BBBB-CCCC-DDDD", "domain": "https://www.Shop.ir/", "activated_at": "2026-07-06 13:36:24"}],
                "payments": [{"track_id": "4666", "plugin": "hesabdar", "email": "u@x.com", "domain": "shop.ir", "amount": 4990000, "status": "paid", "license_key": "HESABD-AAAA-BBBB-CCCC-DDDD", "created_at": "2026-07-06"}],
                "coupons": []}
        r = json.loads(self.run_php("import", {"data": data}))
        self.assertEqual((r["licenses"], r["activations"], r["payments"]), (1, 1, 1))
        r2 = json.loads(self.run_php("import", {"data": data}))
        self.assertEqual((r2["licenses"], r2["activations"], r2["payments"]), (0, 0, 0))   # تکراری وارد نمی‌شود
        v = self.api("validate", {"license_key": "HESABD-AAAA-BBBB-CCCC-DDDD", "domain": "www.shop.ir", "product": "hesabdar"})
        self.assertTrue(v["success"] and v["valid"] and v["email"] == "u@x.com")
        self.assertFalse(self.api("validate", {"license_key": "HESABD-AAAA-BBBB-CCCC-DDDD", "domain": "other.ir"})["success"])
        self.assertFalse(self.api("validate", {"license_key": "HESABD-AAAA-BBBB-CCCC-DDDD", "domain": "shop.ir", "product": "wccp"})["success"])
        a = self.api("activate", {"license_key": "HESABD-AAAA-BBBB-CCCC-DDDD", "domain": "other.ir"})
        self.assertEqual((a["success"], a["error"]), (False, "already_activated"))
        self.api("deactivate", {"license_key": "HESABD-AAAA-BBBB-CCCC-DDDD", "domain": "shop.ir"})
        self.assertTrue(self.api("activate", {"license_key": "HESABD-AAAA-BBBB-CCCC-DDDD", "domain": "other.ir"})["success"])

    def test_protected_endpoints_need_secret_and_create_with_domain(self):
        self.assertEqual(self.api("create", {"email": "a@b.ir", "product": "wccp"})["message"], "Unauthorized")   # بدون کلید تنظیم‌شده
        out = self.run_php("api", {"get": {"action": "create"}, "post": {"email": "a@b.ir", "product": "wccp", "domain": "x.ir"}, "opts": self.SEC})
        self.assertEqual(json.loads(out)["message"], "Unauthorized")   # هدر ندارد
        _ = self.api("ping")
        self.assertTrue(_["success"])

    def test_update_payload_and_unknown_action(self):
        u = self.api("update", get={"product": "hesabdar", "version": "1.0.0"})
        self.assertTrue(u["success"] and u["update_available"] and u["package"].endswith("hesabdar.zip"))
        self.assertFalse(self.api("update", get={"product": "nope"})["success"])
        self.assertFalse(self.api("bogus")["success"])

    def test_coupon_validate(self):
        self.run_php("import", {"data": {"coupons": [{"id": "c1", "code": "sum20", "type": "percent", "value": 20, "product": "wccp", "max_uses": 1, "used_count": 0, "status": "active"}]}})
        r = self.api("coupon_validate", {"code": "SUM20", "product": "wccp", "amount": 1990000})
        self.assertEqual((r["success"], r["discount"], r["final"]), (True, 398000, 1592000))
        self.assertFalse(self.api("coupon_validate", {"code": "SUM20", "product": "hesabdar", "amount": 100})["success"])

    def test_pay_callback_issues_once_and_checks_amount(self):
        base = {"opts": {**self.SEC, "zibal_amount": 7990000}}
        out = self.run_php("pay", {**base, "method": "POST", "get": {"plugin": "hesabdar"}, "post": {"email": "buyer@x.ir", "domain": "https://Buyer.ir", "return_url": "https://buyer.ir/wp-admin/x"}})
        self.assertIn("REDIRECT https://gateway.zibal.ir/start/777001", out)
        cb = {**base, "get": {"plugin": "hesabdar", "zibal_cb": "1", "trackId": "777001", "success": "1"}}
        page = self.run_php("pay", cb)
        self.assertIn("لایسنس فعال شد", page)
        self.run_php("pay", cb)   # بار دوم: لایسنس تکراری نسازد
        rows = json.loads(self.run_php("sql", {"q": "SELECT license_key,email,product FROM wp_accsoft_wlic"}))
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["license_key"].startswith("HESABD-"))
        self.assertEqual(json.loads(self.run_php("sql", {"q": "SELECT domain FROM wp_accsoft_wact"}))[0]["domain"], "buyer.ir")
        # مبلغ نامطابق → رد
        self.db = str(Path(tempfile.mkdtemp()) / "t2.db")
        self.run_php("pay", {"opts": {**self.SEC, "zibal_amount": 1}, "method": "POST", "get": {"plugin": "hesabdar"}, "post": {"email": "b@x.ir", "domain": "b.ir"}})
        bad = self.run_php("pay", {"opts": {**self.SEC, "zibal_amount": 1}, "get": {"plugin": "hesabdar", "zibal_cb": "1", "trackId": "777001", "success": "1"}})
        self.assertIn("پرداخت تأیید نشد", bad)
        self.assertEqual(json.loads(self.run_php("sql", {"q": "SELECT COUNT(*) c FROM wp_accsoft_wlic"}))[0]["c"], 0)

    def test_subscription_extend(self):
        self.run_php("import", {"data": {"licenses": [{"license_key": "WEBAKE-1111-2222-3333-4444", "email": "c@x.ir", "product": "webakery-chat", "status": "active", "expires_at": "2099-01-15"}]}})
        opts = {**self.SEC, "zibal_amount": 3500000}
        self.run_php("pay", {"opts": opts, "method": "POST", "get": {"plugin": "webakery-chat"}, "post": {"email": "c@x.ir", "domain": "c.ir", "plan": "3m"}})
        self.run_php("pay", {"opts": opts, "get": {"plugin": "webakery-chat", "zibal_cb": "1", "trackId": "777001", "success": "1"}})
        exp = json.loads(self.run_php("sql", {"q": "SELECT expires_at FROM wp_accsoft_wlic"}))[0]["expires_at"]
        self.assertEqual(exp, "2099-04-15")   # از انقضای فعلی ۳ ماه اضافه شد
