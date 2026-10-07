"""سازگاری امضا بین افزونهٔ وردپرس (PHP/libsodium) و برنامه (پایتون). بدون php یا sodium نادیده گرفته می‌شود."""
import json
import shutil
import subprocess
import unittest
from datetime import date
from unittest import mock
from pathlib import Path

from accsoft import catalog, ed25519, licensing, pubkey
from .helpers import TEST_SEED

PLUGIN = Path(__file__).resolve().parent.parent / "wordpress-plugin" / "accsoft-license"
PHP = shutil.which("php")

SCRIPT = r"""<?php
define('ABSPATH', '/'); define('ACCSOFT_SEED_HEX', '%s');
require '%s/includes/crypto.php';
[$lid, $key] = accsoft_make_license('accsoft', 'm3', 'علی/رضایی "x"', 'ABCDEF0123456789', '2026-01-31', accsoft_add_months('2026-01-31', 1), ['b', 'a']);
$data = ['version' => 7, 'revoked' => [$lid], 'products' => [['id' => 'accsoft', 'name' => 'حسابداری', 'kind' => 'app', 'description' => 'a/b',
   'trial_days' => 7, 'plans' => [['id' => 'life', 'title' => 'م', 'months' => null, 'price' => 14000000], ['id' => 'm3', 'title' => 'x', 'months' => 3, 'price' => 6000000, 'features' => ['z', 'a']]]]]];
echo json_encode(['key' => $key, 'lid' => $lid, 'pub' => accsoft_pubkey_hex(), 'doc' => accsoft_sign_catalog($data), 'j' => accsoft_jdate('2026-03-21'), 'am' => accsoft_add_months('2026-01-31', 1)]);
"""


@unittest.skipUnless(PHP, "php نصب نیست")
class WpPluginCompat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run([PHP, "-r", "echo function_exists('sodium_crypto_sign_seed_keypair') ? 1 : 0;"], capture_output=True, text=True).stdout
        if out != "1":
            raise unittest.SkipTest("sodium در php نیست")
        code = SCRIPT % (TEST_SEED.hex(), PLUGIN)
        r = subprocess.run([PHP], input=code, capture_output=True, text=True, timeout=60)
        if r.returncode:
            raise AssertionError(r.stdout + r.stderr)
        cls.o = json.loads(r.stdout)

    def test_same_public_key(self):
        self.assertEqual(self.o["pub"], ed25519.publickey(TEST_SEED).hex())

    def test_license_verifies_in_python(self):
        old = pubkey.PUBLIC_KEY_HEX
        pubkey.PUBLIC_KEY_HEX = self.o["pub"]
        mid = mock.patch.object(licensing, "machine_id", lambda: "ABCDEF0123456789")
        mid.start()
        try:
            p, err = licensing.verify_license(self.o["key"], today=date(2026, 2, 1), revoked=())
            self.assertIsNone(err)
            self.assertEqual((p["plan"], p["mid"], p["expires"], p["features"], p["name"]), ("m3", "ABCDEF0123456789", "2026-02-28", ["a", "b"], 'علی/رضایی "x"'))
            _, err = licensing.verify_license(self.o["key"], today=date(2026, 2, 1), revoked=[self.o["lid"]])
            self.assertIn("ابطال", err)
            self.assertTrue(catalog.verify_doc(self.o["doc"]))     # امضای کاتالوگ روی JSON متعارف
            d = json.loads(json.dumps(self.o["doc"])); d["data"]["version"] = 8
            self.assertIsNone(catalog.verify_doc(d))
        finally:
            mid.stop()
            pubkey.PUBLIC_KEY_HEX = old

    def test_helpers(self):
        self.assertEqual(self.o["am"], "2026-02-28")
        from accsoft import jalali
        self.assertEqual(self.o["j"], "%04d/%02d/%02d" % jalali.g2j(2026, 3, 21))


@unittest.skipUnless(PHP, "php نصب نیست")
class PhpClient(unittest.TestCase):
    def test_php_client_verifies_python_license(self):
        out = subprocess.run([PHP, "-r", "echo function_exists('sodium_crypto_sign_seed_keypair') ? 1 : 0;"], capture_output=True, text=True).stdout
        if out != "1":
            self.skipTest("sodium در php نیست")
        cat = {"products": [{"id": "my-plugin", "plans": [{"id": "y", "months": 12}]}]}
        key = licensing.make_license(TEST_SEED, "y", "x", "AAAA111122223333", date(2026, 1, 1), product="my-plugin", cat=cat, features=["pro"])
        pub = ed25519.publickey(TEST_SEED).hex()
        code = ("<?php require '%s/sdk/license-client.php'; $k=%s; $p=%s;"
                "echo json_encode([SoftLicense::check($k,$p,'my-plugin','AAAA111122223333',[],'2026-06-01')['ok'],"
                "SoftLicense::check($k,$p,'other','AAAA111122223333',[],'2026-06-01')['ok'],"
                "SoftLicense::check($k,$p,'my-plugin','BBBB111122223333',[],'2026-06-01')['ok'],"
                "SoftLicense::check($k,$p,'my-plugin','AAAA111122223333',[],'2027-06-01')['ok']]);") % (PLUGIN, json.dumps(key), json.dumps(pub))
        r = subprocess.run([PHP], input=code, capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(r.stdout), [True, False, False, False], r.stdout + r.stderr)
