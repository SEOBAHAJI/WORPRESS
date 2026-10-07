#!/usr/bin/env python3
"""پنل مدیریت لایسنس (فقط برای فروشنده؛ همراه برنامه منتشر نشود).

  python tools/license_admin.py            # باز شدن پنل روی http://127.0.0.1:8750
  python tools/license_admin.py issue --product accsoft --plan 12m --name "علی" [--mid XXXX]

افزودن محصول/افزونه/پلن جدید = فقط فرم‌های پنل (بدون کدنویسی). «انتشار کاتالوگ» فایل امضاشدهٔ catalog.json می‌سازد
که روی سایت (webakery.ir/api/accsoft/catalog) قرار می‌گیرد و در برنامه‌ها با «به‌روزرسانی کاتالوگ» می‌آید.
داده‌ها در پوشهٔ license_admin/ (در گیت نیست؛ از آن پشتیبان بگیرید) و کلید خصوصی license_private.key."""
import argparse
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from accsoft import catalog, ed25519, licensing, security  # noqa: E402
from accsoft.config import PLANS  # noqa: E402

SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")
KEY_FILE = ROOT / "license_private.key"


class AdminError(Exception):
    pass


class Store:
    def __init__(self, folder=None, key_file=None):
        self.dir = Path(folder or ROOT / "license_admin")
        self.dir.mkdir(exist_ok=True)
        self.key_file = Path(key_file or KEY_FILE)
        self.db = sqlite3.connect(self.dir / "admin.db", check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
          CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'plugin',
            description TEXT DEFAULT '', trial_days INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS plans(product TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE, id TEXT NOT NULL,
            title TEXT NOT NULL, months INTEGER, price INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(product,id));
          CREATE TABLE IF NOT EXISTS issued(id INTEGER PRIMARY KEY, lid TEXT UNIQUE, product TEXT, plan TEXT, customer TEXT,
            mid TEXT, features TEXT, issued TEXT, expires TEXT, key TEXT, revoked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);""")
        if not self.q("SELECT 1 FROM products"):
            d = catalog.default_data()["products"][0]
            self.save_product(d["id"], d["name"], "app", d["description"], d["trial_days"])
            for p in d["plans"]:
                self.save_plan(d["id"], p["id"], p["title"], p["months"], p["price"])

    # --- ابزار ---
    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def x(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args)

    def meta(self, k, default=None):
        r = self.q("SELECT v FROM meta WHERE k=?", (k,))
        return r[0]["v"] if r else default

    def set_meta(self, k, v):
        self.x("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))

    # --- رمز پنل ---
    def has_password(self):
        return bool(self.meta("pw"))

    def set_password(self, pw):
        if len(pw) < 10:
            raise AdminError("رمز پنل حداقل ۱۰ نویسه باشد")
        self.set_meta("pw", security.hash_password(pw))

    def check_password(self, pw):
        return security.check_password(pw, self.meta("pw", ""))

    # --- کلید ---
    def seed(self):
        if not self.key_file.exists():
            raise AdminError("کلید خصوصی ساخته نشده است (دکمهٔ «ساخت کلید»)")
        return bytes.fromhex(self.key_file.read_text().strip())

    def pubkey_hex(self):
        return ed25519.publickey(self.seed()).hex() if self.key_file.exists() else None

    def genkey(self):
        if self.key_file.exists():
            raise AdminError("کلید از قبل وجود دارد؛ بازنویسی همهٔ لایسنس‌های صادرشده را باطل می‌کرد")
        seed = os.urandom(32)
        fd = os.open(self.key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(seed.hex())
        pub = ed25519.publickey(seed).hex()
        path = ROOT / "accsoft" / "pubkey.py"
        if path.exists():
            src = path.read_text(encoding="utf-8")
            path.write_text(re.sub(r'PUBLIC_KEY_HEX = ".*"', f'PUBLIC_KEY_HEX = "{pub}"', src), encoding="utf-8")
        return pub

    # --- محصولات و پلن‌ها ---
    def products(self):
        ps = self.q("SELECT * FROM products ORDER BY kind, name")
        for p in ps:
            p["plans"] = self.q("SELECT id,title,months,price FROM plans WHERE product=? ORDER BY COALESCE(months,9999)", (p["id"],))
        return ps

    def save_product(self, pid, name, kind, description="", trial_days=0):
        if not SLUG.match(pid or ""):
            raise AdminError("شناسه فقط حروف کوچک انگلیسی/عدد/خط‌تیره، ۲ تا ۴۰ نویسه")
        if not (name or "").strip() or kind not in ("app", "plugin"):
            raise AdminError("نام و نوع (برنامه/افزونه) الزامی است")
        self.x("INSERT INTO products(id,name,kind,description,trial_days) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
               "name=excluded.name, kind=excluded.kind, description=excluded.description, trial_days=excluded.trial_days",
               (pid, name.strip(), kind, description or "", max(0, int(trial_days or 0))))

    def delete_product(self, pid):
        if self.q("SELECT 1 FROM issued WHERE product=? LIMIT 1", (pid,)):
            raise AdminError("برای این محصول لایسنس صادر شده؛ قابل حذف نیست")
        self.x("DELETE FROM plans WHERE product=?", (pid,))
        self.x("DELETE FROM products WHERE id=?", (pid,))

    def save_plan(self, product, plan_id, title, months, price):
        if not self.q("SELECT 1 FROM products WHERE id=?", (product,)):
            raise AdminError("محصول پیدا نشد")
        if not SLUG.match(plan_id or ""):
            raise AdminError("شناسهٔ پلن نامعتبر است (مثلاً 12m یا lifetime)")
        months = None if months in (None, "", 0, "0") else int(months)
        if months is not None and not 1 <= months <= 240:
            raise AdminError("مدت باید ۱ تا ۲۴۰ ماه باشد (خالی = مادام‌العمر)")
        price = int(price or 0)
        if price < 0 or not (title or "").strip():
            raise AdminError("عنوان و قیمت معتبر لازم است")
        self.x("INSERT INTO plans(product,id,title,months,price) VALUES(?,?,?,?,?) ON CONFLICT(product,id) DO UPDATE SET "
               "title=excluded.title, months=excluded.months, price=excluded.price", (product, plan_id, title.strip(), months, price))

    def delete_plan(self, product, plan_id):
        self.x("DELETE FROM plans WHERE product=? AND id=?", (product, plan_id))  # لایسنس‌های صادرشده معتبر می‌مانند

    # --- صدور / ابطال ---
    def catalog_cat(self):
        return {"products": [{"id": p["id"], "plans": p["plans"]} for p in self.products()]}

    def issue(self, product, plan, name, mid="", features=()):
        name = (name or "").strip()
        if not name:
            raise AdminError("نام مشتری الزامی است")
        mid = (mid or "").strip().upper()
        if mid and not re.fullmatch(r"[0-9A-F]{16}", mid):
            raise AdminError("شناسهٔ دستگاه باید ۱۶ نویسهٔ هگز باشد (از صفحهٔ لایسنس برنامه کپی شود)")
        feats = sorted({f.strip() for f in features if f.strip()})
        try:
            key = licensing.make_license(self.seed(), plan, name, mid, product=product, features=feats, cat=self.catalog_cat())
        except ValueError as e:
            raise AdminError(str(e))
        p, _ = licensing.verify_license(key)
        if p is None:
            raise AdminError("کلید عمومی داخل accsoft/pubkey.py با کلید خصوصی نمی‌خواند؛ برنامه با کلید دیگری ساخته شده")
        self.x("INSERT INTO issued(lid,product,plan,customer,mid,features,issued,expires,key) VALUES(?,?,?,?,?,?,?,?,?)",
               (p["lid"], product, plan, name, mid, ",".join(feats), p["issued"], p["expires"], key))
        return key

    def issued(self, q=""):
        like = f"%{q}%"
        return self.q("SELECT id,lid,product,plan,customer,mid,features,issued,expires,key,revoked FROM issued "
                      "WHERE customer LIKE ? OR product LIKE ? OR lid LIKE ? ORDER BY id DESC LIMIT 500", (like, like, like))

    def revoke(self, lid, flag=True):
        self.x("UPDATE issued SET revoked=? WHERE lid=?", (int(bool(flag)), lid))

    # --- انتشار ---
    def publish(self):
        ver = int(self.meta("catalog_version", "0")) + 1
        data = {"version": ver, "revoked": [r["lid"] for r in self.q("SELECT lid FROM issued WHERE revoked=1")],
                "products": [{k: p[k] for k in ("id", "name", "kind", "description", "trial_days", "plans")} for p in self.products()]}
        doc = catalog.sign_catalog(self.seed(), data)
        text = json.dumps(doc, ensure_ascii=False, indent=1)
        out = self.dir / "out"
        out.mkdir(exist_ok=True)
        (out / "catalog.json").write_text(text, encoding="utf-8")
        (ROOT / "accsoft" / "catalog.json").write_text(text, encoding="utf-8")  # همراه نسخهٔ بعدی برنامه
        self.set_meta("catalog_version", ver)
        return {"version": ver, "file": str(out / "catalog.json"), "products": len(data["products"]), "revoked": len(data["revoked"])}


PAGE = (Path(__file__).parent / "license_admin.html")


class Handler(BaseHTTPRequestHandler):
    store: Store = None
    sessions = {}
    fails = [0, 0.0]
    port = 0
    server_version = "LicAdmin"
    sys_version = ""

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8", cookie=None):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        for k, v in (("Content-Type", ctype), ("Content-Length", str(len(b))), ("Cache-Control", "no-store"),
                     ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"),
                     ("Content-Security-Policy", "default-src 'self'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'")):
            self.send_header(k, v)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(b)

    def handle_any(self, method):
        import time
        if (self.headers.get("Host") or "") not in (f"127.0.0.1:{self.port}", f"localhost:{self.port}"):
            return self.send(403, {"error": "forbidden"})
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"):
            return self.send(403, {"error": "forbidden"})
        url = urllib.parse.urlsplit(self.path)
        path, q = url.path, {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if method == "GET" and path == "/":
            return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        cookies = dict(p.strip().split("=", 1) for p in (self.headers.get("Cookie") or "").split(";") if "=" in p)
        sess = self.sessions.get(cookies.get("sid"))
        body = {}
        if method != "GET":
            raw = self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 1_000_000))
            try:
                body = json.loads(raw) if raw else {}
            except ValueError:
                return self.send(400, {"error": "JSON نامعتبر"})
        st = self.store
        try:
            if method == "GET" and path == "/api/state":
                return self.send(200, {"setup_needed": not st.has_password(), "logged_in": bool(sess),
                                       "csrf": sess["csrf"] if sess else None, "has_key": st.key_file.exists(),
                                       "pubkey": st.pubkey_hex() if sess else None})
            if method == "POST" and path in ("/api/setup", "/api/login"):
                if path == "/api/setup":
                    if st.has_password():
                        raise AdminError("قبلاً تنظیم شده است")
                    st.set_password(body.get("password") or "")
                elif self.fails[0] >= 5 and time.time() < self.fails[1]:
                    raise AdminError("چند دقیقه صبر کنید")
                elif not st.check_password(body.get("password") or ""):
                    self.fails[:] = [self.fails[0] + 1, time.time() + 300]
                    raise AdminError("رمز نادرست است")
                self.fails[:] = [0, 0.0]
                sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
                self.sessions[sid] = {"csrf": csrf}
                return self.send(200, {"csrf": csrf}, cookie=f"sid={sid}; Path=/; HttpOnly; SameSite=Strict")
            if not sess:
                return self.send(401, {"error": "ورود لازم است"})
            if method != "GET" and not secrets.compare_digest(self.headers.get("X-CSRF-Token") or "", sess["csrf"]):
                return self.send(403, {"error": "CSRF"})
            if method == "GET" and path == "/api/products":
                return self.send(200, st.products())
            if method == "GET" and path == "/api/issued":
                return self.send(200, st.issued(q.get("q", "")))
            if method == "POST" and path == "/api/product":
                st.save_product(body.get("id"), body.get("name"), body.get("kind"), body.get("description", ""), body.get("trial_days", 0))
            elif method == "DELETE" and path.startswith("/api/product/"):
                st.delete_product(path.rsplit("/", 1)[1])
            elif method == "POST" and path == "/api/plan":
                st.save_plan(body.get("product"), body.get("id"), body.get("title"), body.get("months"), body.get("price"))
            elif method == "DELETE" and path.startswith("/api/plan/"):
                _, _, _, prod, pid = path.split("/")
                st.delete_plan(prod, pid)
            elif method == "POST" and path == "/api/issue":
                feats = body.get("features") or []
                if isinstance(feats, str):
                    feats = feats.split(",")
                return self.send(200, {"key": st.issue(body.get("product"), body.get("plan"), body.get("name"), body.get("mid", ""), feats)})
            elif method == "POST" and path == "/api/revoke":
                st.revoke(body.get("lid"), body.get("revoked", True))
            elif method == "POST" and path == "/api/publish":
                return self.send(200, st.publish())
            elif method == "POST" and path == "/api/genkey":
                return self.send(200, {"pubkey": st.genkey()})
            else:
                return self.send(404, {"error": "not found"})
            return self.send(200, {})
        except (AdminError, ValueError) as e:
            self.send(400, {"error": str(e)})
        except Exception:
            import traceback
            traceback.print_exc()
            self.send(500, {"error": "خطای داخلی"})

    def do_GET(self): self.handle_any("GET")
    def do_POST(self): self.handle_any("POST")
    def do_DELETE(self): self.handle_any("DELETE")


def serve(store, port=8750):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    Handler.store, Handler.port = store, srv.server_address[1]
    Handler.sessions, Handler.fails = {}, [0, 0.0]
    return srv


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    i = sub.add_parser("issue")
    i.add_argument("--product", default="accsoft")
    i.add_argument("--plan", required=True)
    i.add_argument("--name", required=True)
    i.add_argument("--mid", default="")
    i.add_argument("--features", default="")
    ap.add_argument("--port", type=int, default=8750)
    a = ap.parse_args()
    store = Store()
    if a.cmd == "issue":
        print(store.issue(a.product, a.plan, a.name, a.mid, a.features.split(",")))
        return
    srv = serve(store, a.port)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"پنل مدیریت لایسنس: {url}  (Ctrl+C برای خروج)")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
