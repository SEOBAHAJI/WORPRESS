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


@unittest.skipUnless(PHP, "php نصب نیست")
class Upload(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = str(self.tmp / "t.db")
        (self.tmp / "up").mkdir()
        self.opts = {"_up": str(self.tmp / "up"), "accsoft_settings": {"zibal_merchant": "z"}}

    def php(self, cmd, arg):
        r = subprocess.run([PHP, H, self.db, cmd, json.dumps(arg)], capture_output=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.decode("utf-8", "replace")

    def mkzip(self, name, files):
        import zipfile
        p = self.tmp / name
        with zipfile.ZipFile(p, "w") as z:
            for n, c in files.items():
                z.writestr(n, c)
        return str(p)

    PLUG = "<?php\n/**\n * Plugin Name: My Plugin\n * Description: test desc\n * Version: %s\n * Requires PHP: 7.4\n */\n"

    def test_upload_registers_product_and_secure_update(self):
        z = self.mkzip("a.zip", {"my-plugin/my-plugin.php": self.PLUG % "1.2.0", "my-plugin/inc/x.php": "<?php"})
        r = json.loads(self.php("ingest", {"zip": z, "opts": self.opts, "changelog": "اولین"}))
        self.assertEqual((r["slug"], r["version"], r["created"]), ("my-plugin", "1.2.0", True))
        # لایسنس بساز و فعال کن
        self.php("import", {"opts": self.opts, "data": {"licenses": [{"license_key": "MYPLUG-AAAA-BBBB-CCCC-DDDD", "email": "a@b.ir", "product": "my-plugin", "status": "active"}],
                                                      "activations": [{"license_key": "MYPLUG-AAAA-BBBB-CCCC-DDDD", "domain": "shop.ir"}]}})
        q = {"opts": self.opts, "get": {"action": "update", "product": "my-plugin", "version": "1.0.0", "license_key": "MYPLUG-AAAA-BBBB-CCCC-DDDD", "domain": "shop.ir"}}
        u = json.loads(self.php("api", q))
        self.assertTrue(u["success"] and u["update_available"] and "accsoft_dl=my-plugin" in u["package"])
        nolic = json.loads(self.php("api", {"opts": self.opts, "get": {"action": "update", "product": "my-plugin", "version": "1.0.0"}}))
        self.assertEqual(nolic["package"], "")        # بدون لایسنس لینکی داده نمی‌شود
        ok = self.php("dl", {"opts": self.opts, "get": {"accsoft_dl": "my-plugin", "license_key": "MYPLUG-AAAA-BBBB-CCCC-DDDD", "domain": "shop.ir"}})
        self.assertTrue(ok.startswith("PK"))          # zip واقعی
        bad = self.php("dl", {"opts": self.opts, "get": {"accsoft_dl": "my-plugin", "license_key": "MYPLUG-AAAA-BBBB-CCCC-DDDD", "domain": "evil.ir"}})
        self.assertEqual(bad, "Invalid license")
        # نسخهٔ جدید → به‌روزرسانی؛ نسخهٔ قدیمی‌تر رد
        z2 = self.mkzip("b.zip", {"my-plugin/my-plugin.php": self.PLUG % "1.3.0"})
        r2 = json.loads(self.php("ingest", {"zip": z2, "opts": self.opts}))
        self.assertEqual((r2["version"], r2["created"]), ("1.3.0", False))
        z3 = self.mkzip("c.zip", {"my-plugin/my-plugin.php": self.PLUG % "1.0.0"})
        self.assertIn("قدیمی", json.loads(self.php("ingest", {"zip": z3, "opts": self.opts}))["error"])

    def test_bad_zips_rejected(self):
        for files in ({"../evil.php": "x"}, {"a/a.php": "<?php // no header", }, {"a/a.php": self.PLUG % "1", "b/b.php": "x"}, {"a/a.php": "<?php\n/* Plugin Name: X */"}):
            r = json.loads(self.php("ingest", {"zip": self.mkzip("x.zip", files), "opts": self.opts}))
            self.assertIn("error", r, files)

    def test_injected_engine_gate_and_plans(self):
        import zipfile
        src = self.PLUG % "2.0.0" + "namespace My\\Plug;\nadd_action('init', function(){});\n"
        z = self.mkzip("n.zip", {"my-plugin/my-plugin.php": src, "my-plugin/readme.txt": "x"})
        r = json.loads(self.php("ingest", {"zip": z, "opts": self.opts, "o": {"plans_text": "m1|ماهانه|1|150,000\nlife|دائمی|0|2500000"}}))
        self.assertTrue(r["injected"], r)
        zf = zipfile.ZipFile(next((self.tmp / "up" / "accsoft-updates").glob("*.zip")))
        self.assertIn("my-plugin/wb-license-client.php", zf.namelist())
        main = zf.read("my-plugin/my-plugin.php").decode()
        self.assertIn("WB_License_Client", main)
        self.assertIn("is_active()", main)
        self.assertLess(main.index("namespace My"), main.index("WB_License_Client"))   # بعد از namespace، نه قبلش
        out = self.tmp / "x"
        zf.extractall(out)
        lint = subprocess.run([PHP, "-l", str(out / "my-plugin" / "my-plugin.php")], capture_output=True, text=True)
        self.assertIn("No syntax errors", lint.stdout + lint.stderr)
        plans = json.loads(self.php("sql", {"q": "SELECT 1 x"}))   # فقط سالم بودن هارنس
        self.assertTrue(plans)

    def test_no_gate_and_brace_namespace_and_existing_engine(self):
        import zipfile
        r = json.loads(self.php("ingest", {"zip": self.mkzip("a.zip", {"p-a/p-a.php": self.PLUG % "1.0"}), "opts": self.opts, "o": {"gate": False}}))
        main = zipfile.ZipFile(next((self.tmp / "up" / "accsoft-updates").glob("p-a-*.zip"))).read("p-a/p-a.php").decode()
        self.assertTrue(r["injected"] and "is_active()" not in main)
        e = json.loads(self.php("ingest", {"zip": self.mkzip("b.zip", {"p-b/p-b.php": self.PLUG % "1.0" + "namespace X {\n}\n"}), "opts": self.opts}))
        self.assertIn("namespace", e["error"])
        c = json.loads(self.php("ingest", {"zip": self.mkzip("c.zip", {"p-c/p-c.php": self.PLUG % "1.0" + "require 'x'; new WB_License_Client([]);"}), "opts": self.opts}))
        self.assertFalse(c["injected"])
        bad = json.loads(self.php("ingest", {"zip": self.mkzip("d.zip", {"p-d/p-d.php": self.PLUG % "1.0"}), "opts": self.opts, "o": {"plans_text": "bad line"}}))
        self.assertIn("پلن", bad["error"])
