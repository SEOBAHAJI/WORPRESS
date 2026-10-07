import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from tests.helpers import TEST_SEED, fresh_db
from tests.test_server import Client
from accsoft import catalog, licensing
from tools import license_admin as la


class AdminStore(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "k").write_text(TEST_SEED.hex())
        self.s = la.Store(self.tmp / "d", self.tmp / "k")
        self.s.save_product("plugin-x", "افزونه", "plugin")
        self.s.save_plan("plugin-x", "week", "هفتگی", None, 100)

    def test_seeded_default_product_and_issue_without_code(self):
        self.assertEqual([p["id"] for p in self.s.products()], ["accsoft", "plugin-x"])
        self.assertEqual(len(self.s.products()[0]["plans"]), 4)
        # پلن تازه‌ساخته‌شده بدون هیچ تغییر کدی قابل صدور است
        self.s.save_plan("plugin-x", "3m", "سه‌ماهه", 3, 500)
        key = self.s.issue("plugin-x", "3m", "مشتری", features=["a"])
        p, err = licensing.verify_license(key)
        self.assertEqual((err, p["product"], p["features"]), (None, "plugin-x", ["a"]))
        self.assertIsNotNone(p["expires"])
        self.assertEqual(len(self.s.issued("مشتری")), 1)

    def test_validation(self):
        for bad in (lambda: self.s.save_product("Bad ID", "x", "plugin"), lambda: self.s.save_product("ok1", "", "plugin"),
                    lambda: self.s.save_product("ok1", "x", "weird"), lambda: self.s.save_plan("nope", "p1", "t", 1, 1),
                    lambda: self.s.save_plan("plugin-x", "p1", "t", 999, 1), lambda: self.s.save_plan("plugin-x", "p1", "t", 1, -5),
                    lambda: self.s.issue("plugin-x", "week", " "), lambda: self.s.issue("plugin-x", "bogus", "x"),
                    lambda: self.s.issue("plugin-x", "week", "x", mid="zz")):
            with self.assertRaises(la.AdminError):
                bad()

    def test_cannot_delete_product_with_licenses_and_publish_revocation_flow(self):
        key = self.s.issue("plugin-x", "week", "مشتری")
        lid = licensing.verify_license(key)[0]["lid"]
        with self.assertRaises(la.AdminError):
            self.s.delete_product("plugin-x")
        self.s.revoke(lid)
        import accsoft.catalog as cat
        ver = cat.load()["version"]
        orig = la.ROOT
        la.ROOT = self.tmp  # از نوشتن در accsoft/ واقعی جلوگیری کن
        (self.tmp / "accsoft").mkdir(exist_ok=True)
        try:
            info = self.s.publish()
        finally:
            la.ROOT = orig
        self.assertEqual((info["version"], info["revoked"]), (1, 1))
        doc = json.loads(Path(info["file"]).read_text(encoding="utf-8"))
        data = cat.verify_doc(doc)
        self.assertEqual(data["revoked"], [lid])
        self.assertIn("plugin-x", [p["id"] for p in data["products"]])
        self.assertTrue((self.tmp / "accsoft" / "catalog.json").exists())

    def test_genkey_refuses_overwrite(self):
        with self.assertRaises(la.AdminError):
            self.s.genkey()


class AdminHttp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "k").write_text(TEST_SEED.hex())
        self.srv = la.serve(la.Store(self.tmp / "d", self.tmp / "k"), 0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.c = Client(self.srv.server_address[1])

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_auth_csrf_and_flow(self):
        self.assertEqual(self.c.call("GET", "/api/products")[0], 401)
        self.assertEqual(self.c.call("POST", "/api/setup", {"password": "short"})[0], 400)
        st, d, _ = self.c.call("POST", "/api/setup", {"password": "long-enough-pass"})
        self.assertEqual(st, 200)
        self.c.csrf = d["csrf"]
        self.assertEqual(self.c.call("POST", "/api/setup", {"password": "another-long-pass"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/product", {"id": "p1", "name": "x", "kind": "plugin"}, csrf=False)[0], 403)
        self.assertEqual(self.c.call("GET", "/api/products", host="evil.com")[0], 403)
        self.assertEqual(self.c.call("POST", "/api/product", {"id": "plug-a", "name": "افزونه", "kind": "plugin"})[0], 200)
        self.assertEqual(self.c.call("POST", "/api/plan", {"product": "plug-a", "id": "1y", "title": "سالانه", "months": 12, "price": 7})[0], 200)
        st, r, _ = self.c.call("POST", "/api/issue", {"product": "plug-a", "plan": "1y", "name": "علی", "features": "x,y"})
        self.assertEqual(st, 200)
        self.assertEqual(licensing.verify_license(r["key"])[0]["features"], ["x", "y"])
        self.assertEqual(self.c.call("POST", "/api/issue", {"product": "plug-a", "plan": "zzz", "name": "x"})[0], 400)
        self.assertEqual(len(self.c.call("GET", "/api/issued")[1]), 1)
        st, page, _ = self.c.call("GET", "/")
        self.assertEqual(st, 200)
        # قفل پس از ورود ناموفق
        other = Client(self.srv.server_address[1])
        for _ in range(5):
            other.call("POST", "/api/login", {"password": "wrong-wrong-wrong"})
        self.assertIn("صبر", other.call("POST", "/api/login", {"password": "long-enough-pass"})[1]["error"])


if __name__ == "__main__":
    unittest.main()
