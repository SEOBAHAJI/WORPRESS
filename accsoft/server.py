"""سرور HTTP محلی فقط روی 127.0.0.1 با احراز هویت، CSRF، بررسی Host/Origin و قفل لایسنس."""
import base64
import json
import mimetypes
import re
import threading
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, exports, jalali, licensing, security, services, sms, woo
from .config import PLANS, WEBAKERY_BASE, data_dir, resource_dir
from .services import AppError

SECRET_KEYS = {"woo_key", "woo_secret", "sms_apikey"}
PLAIN_KEYS = {"shop_name", "shop_phone", "shop_address", "invoice_footer", "usd_rate", "woo_url", "woo_unit",
              "woo_allow_http", "woo_orders_decrement", "sms_provider", "sms_sender", "sms_url", "sms_method",
              "welcome_enabled", "welcome_text", "allow_negative_stock"}
MAX_BODY = 6 * 1024 * 1024
WRITE_OK_WHEN_LOCKED = ("/api/license", "/api/logout", "/api/password")


class App:
    def __init__(self, db, port=0):
        self.db = db
        self.sessions = security.Sessions()
        self.port = port
        self.last_ping = None
        self.routes = []
        self._register()

    def route(self, method, pattern, public=False):
        def deco(fn):
            self.routes.append((method, re.compile(f"^{pattern}$"), fn, public))
            return fn
        return deco

    # ---------- مسیرها ----------
    def _register(self):
        r, db = self.route, self.db

        @r("GET", "/api/state", public=True)
        def state(c):
            lic = licensing.status(db)
            return {"version": __version__, "setup_needed": db.one("SELECT 1 FROM users") is None,
                    "logged_in": bool(c.session), "csrf": c.session["csrf"] if c.session else None,
                    "license": lic, "shop_name": db.get("shop_name", ""), "usd_rate": services.usd_rate(db),
                    "webakery": WEBAKERY_BASE, "today": jalali.to_jalali_str(date.today())}

        @r("POST", "/api/setup", public=True)
        def setup(c):
            if db.one("SELECT 1 FROM users"):
                raise AppError("نصب قبلاً انجام شده است")
            u, p = (c.body.get("username") or "").strip(), c.body.get("password") or ""
            if len(u) < 3 or len(p) < 8:
                raise AppError("نام کاربری حداقل ۳ و رمز حداقل ۸ نویسه باشد")
            db.conn.execute("INSERT INTO users(username,pass_hash) VALUES(?,?)", (u, security.hash_password(p)))
            db.set("shop_name", (c.body.get("shop_name") or "").strip())
            return self._login(c, u, p)

        @r("POST", "/api/login", public=True)
        def login(c):
            return self._login(c, (c.body.get("username") or "").strip(), c.body.get("password") or "")

        @r("POST", "/api/logout")
        def logout(c):
            self.sessions.drop(c.sid)
            c.cookie = "sid=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict"
            return {}

        @r("POST", "/api/password")
        def password(c):
            u = db.one("SELECT * FROM users WHERE id=?", (c.session["uid"],))
            if not security.check_password(c.body.get("old") or "", u["pass_hash"]):
                raise AppError("رمز فعلی نادرست است")
            if len(c.body.get("new") or "") < 8:
                raise AppError("رمز جدید حداقل ۸ نویسه باشد")
            db.conn.execute("UPDATE users SET pass_hash=? WHERE id=?", (security.hash_password(c.body["new"]), u["id"]))
            return {}

        @r("POST", "/api/ping", public=True)
        def ping(c):
            import time
            self.last_ping = time.time()
            return {}

        # ----- لایسنس -----
        @r("GET", "/api/license/buy-url")
        def buy_url(c):
            plan = c.query.get("plan", "")
            if plan not in PLANS:
                raise AppError("پلن نامعتبر")
            q = urllib.parse.urlencode({"product": "accsoft", "plan": plan, "mid": licensing.machine_id()})
            return {"url": f"{WEBAKERY_BASE}/?{q}"}

        @r("POST", "/api/license")
        def activate(c):
            try:
                licensing.activate(db, c.body.get("key") or "")
            except ValueError as e:
                raise AppError(str(e))
            return licensing.status(db)

        @r("POST", "/api/license/order")
        def activate_order(c):
            """دریافت خودکار لایسنس از وبیکری با کد سفارش (قرارداد در README توضیح داده شده)."""
            import urllib.request
            order = re.sub(r"[^A-Za-z0-9_-]", "", c.body.get("order") or "")[:64]
            if not order:
                raise AppError("کد سفارش را وارد کنید")
            url = f"{WEBAKERY_BASE}/api/accsoft/license?" + urllib.parse.urlencode({"order": order, "mid": licensing.machine_id()})
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    key = json.loads(resp.read(8192)).get("license", "")
            except Exception as e:
                raise AppError(f"دریافت لایسنس از وبیکری ممکن نشد: {e}")
            try:
                licensing.activate(db, key)
            except ValueError as e:
                raise AppError(str(e))
            return licensing.status(db)

        # ----- تنظیمات -----
        @r("GET", "/api/settings")
        def get_settings(c):
            out = {k: db.get(k, "") for k in PLAIN_KEYS}
            out.update({k: ("********" if db.get(k) else "") for k in SECRET_KEYS})
            return out

        @r("PUT", "/api/settings")
        def put_settings(c):
            for k, v in c.body.items():
                if k in PLAIN_KEYS:
                    if k == "usd_rate":
                        v = services._num(v, "نرخ دلار")
                    db.set(k, str(v).strip() if k != "welcome_text" else str(v))
                elif k in SECRET_KEYS and v and v != "********":
                    db.set(k, security.seal(str(v).strip()))
            return {}

        # ----- داشبورد/گزارش -----
        @r("GET", "/api/dashboard")
        def dash(c):
            return services.dashboard(db)

        def _range(c):
            kind = c.query.get("kind", "")
            if kind in ("day", "week", "month") and not c.query.get("start"):
                s, e = services.preset_range(kind)
            else:
                try:
                    s, e = jalali.from_jalali_str(c.query["start"]), jalali.from_jalali_str(c.query["end"])
                except Exception:
                    raise AppError("تاریخ را به شکل ۱۴۰۵/۰۷/۱۵ وارد کنید")
            if e < s:
                raise AppError("تاریخ پایان قبل از شروع است")
            return s, e, (kind if kind in ("day", "week", "month") else c.query.get("period", "day"))

        @r("GET", "/api/report")
        def rep(c):
            s, e, period = _range(c)
            return services.report(db, s, e, period, c.query.get("channel", ""))

        # ----- محصولات -----
        @r("GET", "/api/products")
        def products(c):
            return services.list_products(db, c.query.get("q", ""), c.query.get("category", ""), c.query.get("low") == "1")

        @r("GET", "/api/categories")
        def cats(c):
            return [x["category"] for x in db.q("SELECT DISTINCT category FROM products WHERE active=1 AND category!='' ORDER BY 1")]

        @r("POST", "/api/products")
        def add_p(c):
            return {"id": services.save_product(db, c.body)}

        @r("PUT", r"/api/products/(\d+)")
        def edit_p(c, pid):
            services.save_product(db, c.body, int(pid))
            return {}

        @r("DELETE", r"/api/products/(\d+)")
        def del_p(c, pid):
            services.delete_product(db, int(pid))
            return {}

        @r("POST", r"/api/products/(\d+)/image")
        def img_p(c, pid):
            try:
                blob = base64.b64decode((c.body.get("data") or "").split(",")[-1], validate=True)
            except Exception:
                raise AppError("تصویر نامعتبر است")
            name = woo.save_image_bytes(blob)
            with db.tx() as cx:
                cx.execute("UPDATE products SET image=? WHERE id=?", (name, int(pid)))
            return {"image": name}

        @r("POST", "/api/products/bulk-price")
        def bulk(c):
            return {"changed": services.bulk_price(db, **{k: c.body.get(k) for k in
                    ("scope", "ids", "category", "target", "mode", "value", "rounding") if k in c.body})}

        # ----- انبار -----
        @r("POST", r"/api/products/(\d+)/stock")
        def stock(c, pid):
            q = int(services._num(c.body.get("qty"), "تعداد", minimum=-10**9))
            if q == 0:
                raise AppError("تعداد صفر است")
            services.adjust_stock(db, int(pid), q, c.body.get("reason") or "adjust", c.body.get("note") or "")
            return {}

        @r("GET", "/api/stock-moves")
        def moves(c):
            pid = c.query.get("product")
            return services.stock_moves(db, int(pid) if pid else None)

        # ----- مشتری -----
        @r("GET", "/api/customers")
        def custs(c):
            return services.list_customers(db, c.query.get("q", ""))

        @r("POST", "/api/customers")
        def add_c(c):
            cid, new = services.upsert_customer(db, c.body.get("first_name"), c.body.get("last_name"), c.body.get("phone"))
            if new:
                self._welcome(cid)
            return {"id": cid, "new": new}

        @r("POST", "/api/sms/test")
        def sms_test(c):
            ok, detail = sms.send(db, services.norm_phone(c.body.get("phone")), "پیام آزمایشی نرم‌افزار حسابداری")
            return {"ok": ok, "detail": detail}

        @r("GET", "/api/sms/log")
        def sms_log(c):
            return db.q("SELECT * FROM sms_log ORDER BY id DESC LIMIT 100")

        # ----- فروش -----
        @r("POST", "/api/sales")
        def new_sale(c):
            res = services.create_sale(db, c.body.get("items") or [], c.body.get("customer"), c.body.get("discount", 0),
                                       c.body.get("pay_method", "cash"), c.body.get("note", ""), channel="offline")
            if res["new_customer"]:
                self._welcome(res["new_customer"])
            return res

        @r("GET", "/api/sales")
        def sales(c):
            s = e = None
            if c.query.get("start"):
                s, e = jalali.from_jalali_str(c.query["start"]), jalali.from_jalali_str(c.query["end"])
            return services.list_sales(db, s, e, c.query.get("channel", ""))

        @r("GET", r"/api/sales/(\d+)")
        def sale(c, sid):
            return services.get_sale(db, int(sid))

        @r("DELETE", r"/api/sales/(\d+)")
        def del_sale(c, sid):
            services.delete_sale(db, int(sid))
            return {}

        @r("GET", "/api/expenses")
        def exps(c):
            rows = db.q("SELECT * FROM expenses ORDER BY id DESC LIMIT 200")
            for x in rows:
                x["jdate"] = jalali.to_jalali_str(x["created_at"])
            return rows

        @r("POST", "/api/expenses")
        def add_exp(c):
            services.add_expense(db, c.body.get("title"), c.body.get("amount"))
            return {}

        @r("DELETE", r"/api/expenses/(\d+)")
        def del_exp(c, eid):
            with db.tx() as cx:
                cx.execute("DELETE FROM expenses WHERE id=?", (int(eid),))
            return {}

        # ----- ووکامرس -----
        @r("POST", "/api/woo/pull-products")
        def w1(c):
            return woo.pull_products(db, update_stock=bool(c.body.get("update_stock")), images=c.body.get("images", True))

        @r("POST", "/api/woo/push-products")
        def w2(c):
            return woo.push_products(db, all_products=bool(c.body.get("all")))

        @r("POST", "/api/woo/pull-orders")
        def w3(c):
            return woo.pull_orders(db)

        # ----- خروجی‌ها (GET؛ فایل یا صفحهٔ چاپی) -----
        @r("GET", r"/export/(products|sales|customers|report)\.xlsx")
        def export_x(c, what):
            if what == "products":
                data = exports.products_xlsx(db)
            elif what == "customers":
                data = exports.customers_xlsx(db)
            elif what == "sales":
                s = e = None
                if c.query.get("start"):
                    s, e = jalali.from_jalali_str(c.query["start"]), jalali.from_jalali_str(c.query["end"])
                data = exports.sales_xlsx(db, s, e, c.query.get("channel", ""))
            else:
                s, e, period = _range(c)
                data = exports.report_xlsx(db, services.report(db, s, e, period, c.query.get("channel", "")))
            return Raw(data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       {"Content-Disposition": f'attachment; filename="{what}.xlsx"'})

        @r("GET", r"/print/invoice/(\d+)")
        def p_inv(c, sid):
            return Raw(exports.invoice_html(db, services.get_sale(db, int(sid)), c.query.get("w") == "80").encode(),
                       "text/html; charset=utf-8", printable=True)

        @r("GET", "/print/report")
        def p_rep(c):
            s, e, period = _range(c)
            return Raw(exports.report_html(services.report(db, s, e, period, c.query.get("channel", ""))).encode(),
                       "text/html; charset=utf-8", printable=True)

        @r("GET", "/print/products")
        def p_prod(c):
            return Raw(exports.products_html(db).encode(), "text/html; charset=utf-8", printable=True)

    def _login(self, c, user, pw):
        wait = self.sessions.locked(user)
        if wait:
            raise AppError(f"به‌خاطر تلاش‌های ناموفق، {wait} ثانیه صبر کنید")
        u = self.db.one("SELECT * FROM users WHERE username=?", (user,))
        # حتی اگر کاربر وجود نداشت، هزینهٔ هش را بپردازیم تا زمان‌بندی چیزی لو ندهد
        ok = security.check_password(pw, u["pass_hash"] if u else security.hash_password("x"))
        if not (u and ok):
            self.sessions.fail(user)
            raise AppError("نام کاربری یا رمز عبور نادرست است")
        self.sessions.clear_fails(user)
        sid, csrf = self.sessions.create(u["id"])
        c.cookie = f"sid={sid}; Path=/; HttpOnly; SameSite=Strict"
        return {"csrf": csrf}

    def _welcome(self, cid):
        if self.db.get("welcome_enabled", "0") != "1":
            return
        def job():
            cu = self.db.one("SELECT * FROM customers WHERE id=?", (cid,))
            ok, _ = sms.send(self.db, cu["phone"], sms.welcome_text(self.db, cu["first_name"], cu["last_name"]))
            if ok:
                with self.db.lock:
                    self.db.conn.execute("UPDATE customers SET welcomed=1 WHERE id=?", (cid,))
        threading.Thread(target=job, daemon=True).start()


class Raw:
    def __init__(self, data, ctype, headers=None, printable=False):
        self.data, self.ctype, self.headers, self.printable = data, ctype, headers or {}, printable


class Ctx:
    cookie = None
    session = None
    sid = None
    body = {}
    query = {}


def make_handler(app: App):
    static_root = resource_dir() / "static"

    class H(BaseHTTPRequestHandler):
        server_version = "AccSoft"
        sys_version = ""

        def log_message(self, *a):
            pass

        # --- کمکی‌ها ---
        def _send(self, code, body: bytes, ctype, extra=None, csp=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", csp or
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; form-action 'self'")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj, cookie=None):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8",
                       {"Set-Cookie": cookie} if cookie else None)

        def _host_ok(self):
            host = (self.headers.get("Host") or "").lower()
            if host not in (f"127.0.0.1:{app.port}", f"localhost:{app.port}"):
                return False  # جلوگیری از DNS rebinding
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{app.port}", f"http://localhost:{app.port}"):
                return False
            return True

        def _handle(self, method):
            if not self._host_ok():
                return self._json(403, {"error": "forbidden"})
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            if method == "GET" and not path.startswith(("/api/", "/export/", "/print/", "/img/")):
                return self._static(path)
            ctx = Ctx()
            ctx.query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            cookies = dict(p.strip().split("=", 1) for p in (self.headers.get("Cookie") or "").split(";") if "=" in p)
            ctx.sid = cookies.get("sid")
            ctx.session = app.sessions.get(ctx.sid)
            if method == "GET" and path.startswith("/img/"):
                if not ctx.session:
                    return self._json(401, {"error": "login"})
                m = re.fullmatch(r"/img/([0-9a-f]{32}\.(jpg|png|gif|webp))", path)
                f = data_dir() / "images" / m.group(1) if m else None
                if not f or not f.exists():
                    return self._json(404, {"error": "not found"})
                return self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream",
                                  {"Cache-Control": "private, max-age=3600"})
            for m_, rx, fn, public in app.routes:
                mm = rx.match(path)
                if m_ == method and mm:
                    break
            else:
                return self._json(404, {"error": "not found"})
            try:
                if not public and not ctx.session:
                    return self._json(401, {"error": "ورود لازم است"})
                if method != "GET":
                    if not public and not hmac_eq(self.headers.get("X-CSRF-Token"), ctx.session["csrf"]):
                        return self._json(403, {"error": "نشست نامعتبر؛ صفحه را تازه کنید"})
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > MAX_BODY:
                        return self._json(413, {"error": "حجم درخواست زیاد است"})
                    raw = self.rfile.read(n) if n else b""
                    try:
                        ctx.body = json.loads(raw) if raw else {}
                    except ValueError:
                        return self._json(400, {"error": "JSON نامعتبر"})
                    if not isinstance(ctx.body, dict):
                        return self._json(400, {"error": "JSON نامعتبر"})
                    if not path.startswith(WRITE_OK_WHEN_LOCKED) and not public \
                            and licensing.status(app.db)["mode"] == "expired":
                        return self._json(402, {"error": "لایسنس منقضی است؛ برای ادامه لایسنس تهیه کنید", "license": True})
                res = fn(ctx, *mm.groups())
                if isinstance(res, Raw):
                    csp = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self'"
                           if res.printable else None)
                    return self._send(200, res.data, res.ctype, res.headers, csp)
                return self._json(200, res, ctx.cookie)
            except AppError as e:
                self._json(400, {"error": str(e)}, ctx.cookie)
            except Exception as e:  # جزئیات داخلی به کاربر نشت نکند
                import traceback
                traceback.print_exc()
                self._json(500, {"error": "خطای داخلی برنامه"})

        def _static(self, path):
            name = "index.html" if path in ("/", "") else path.lstrip("/")
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or not (static_root / name).is_file():
                return self._json(404, {"error": "not found"})
            f = static_root / name
            self._send(200, f.read_bytes(), (mimetypes.guess_type(name)[0] or "text/plain") + "; charset=utf-8")

        def do_GET(self): self._handle("GET")
        def do_POST(self): self._handle("POST")
        def do_PUT(self): self._handle("PUT")
        def do_DELETE(self): self._handle("DELETE")

    return H


def hmac_eq(a, b):
    import hmac
    return bool(a) and hmac.compare_digest(a, b)


def create_server(db, port=0):
    app = App(db)
    srv = ThreadingHTTPServer(("127.0.0.1", port), None)
    app.port = srv.server_address[1]
    srv.RequestHandlerClass = make_handler(app)
    srv.app = app
    return srv
