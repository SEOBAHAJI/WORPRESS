"""اتصال دوطرفهٔ ووکامرس (REST v3): خواندن/نوشتن محصول، قیمت، موجودی و دریافت سفارش‌های آنلاین."""
import base64
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid

from . import security, services
from .config import data_dir
from .services import AppError, usd_rate

MAX_IMG = 3 * 1024 * 1024


class Woo:
    def __init__(self, db):
        self.db = db
        url = (db.get("woo_url", "") or "").rstrip("/")
        if not url:
            raise AppError("آدرس سایت ووکامرس در تنظیمات وارد نشده است")
        if not url.startswith("https://") and db.get("woo_allow_http", "0") != "1":
            raise AppError("برای امنیت، آدرس سایت باید https باشد")
        self.base = f"{url}/wp-json/wc/v3"
        self.key = security.unseal(db.get("woo_key", ""))
        self.secret = security.unseal(db.get("woo_secret", ""))
        if not (self.key and self.secret):
            raise AppError("کلید API ووکامرس وارد نشده است")
        self.rial = db.get("woo_unit", "toman") == "rial"

    def request(self, method, path, params=None, body=None):
        url = f"{self.base}/{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        data = json.dumps(body).encode() if body is not None else None
        auth = base64.b64encode(f"{self.key}:{self.secret}".encode()).decode()
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Basic {auth}", "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raise AppError(f"خطای ووکامرس {e.code}: {e.read(300).decode('utf-8', 'replace')}")
        except urllib.error.URLError as e:
            raise AppError(f"اتصال به سایت ممکن نشد: {e.reason}")

    def paged(self, path, params=None):
        page, out = 1, []
        while True:
            chunk = self.request("GET", path, {**(params or {}), "per_page": 100, "page": page})
            out += chunk
            if len(chunk) < 100:
                return out
            page += 1

    def price_out(self, toman):
        return str(int(toman) * (10 if self.rial else 1))

    def price_in(self, s):
        try:
            v = float(s or 0)
        except ValueError:
            return 0
        return int(round(v / 10)) if self.rial else int(round(v))

    # ----- دانلود تصویر -----
    def fetch_image(self, src):
        if not src.startswith("https://") and self.db.get("woo_allow_http", "0") != "1":
            return ""
        try:
            with urllib.request.urlopen(urllib.request.Request(src), timeout=20) as r:
                blob = r.read(MAX_IMG + 1)
        except Exception:
            return ""
        return save_image_bytes(blob) if len(blob) <= MAX_IMG else ""


def save_image_bytes(blob: bytes) -> str:
    sig = {b"\xff\xd8\xff": "jpg", b"\x89PNG": "png", b"GIF8": "gif", b"RIFF": "webp"}
    ext = next((e for s, e in sig.items() if blob.startswith(s)), None)
    if not ext or len(blob) > MAX_IMG or (ext == "webp" and blob[8:12] != b"WEBP"):
        raise AppError("فقط تصویر JPG/PNG/GIF/WEBP تا ۳ مگابایت مجاز است")
    name = f"{uuid.uuid4().hex}.{ext}"
    (data_dir() / "images" / name).write_bytes(blob)
    return name


def pull_products(db, update_stock=False, images=True, woo=None):
    w = woo or Woo(db)
    added = updated = 0
    for wp in w.paged("products", {"status": "publish"}):
        if wp.get("type") not in ("simple", None):
            continue  # محصولات متغیر فعلاً پشتیبانی نمی‌شوند
        price = w.price_in(wp.get("regular_price") or wp.get("price"))
        stock = wp.get("stock_quantity") if wp.get("manage_stock") else None
        cat = (wp.get("categories") or [{}])[0].get("name", "")
        row = db.one("SELECT * FROM products WHERE woo_id=?", (wp["id"],)) or \
            (db.one("SELECT * FROM products WHERE sku=?", (wp["sku"],)) if wp.get("sku") else None)
        img = ""
        if images and wp.get("images") and (not row or not row["image"]):
            img = w.fetch_image(wp["images"][0].get("src", ""))
        with db.tx() as c:
            if row:
                sets, args = ["name=?", "category=?", "woo_id=?", "woo_dirty=0"], [wp["name"], cat, wp["id"]]
                if row["currency"] == "IRT":
                    sets.append("price=?")
                    args.append(price)
                if img:
                    sets.append("image=?")
                    args.append(img)
                c.execute(f"UPDATE products SET {','.join(sets)} WHERE id=?", (*args, row["id"]))
                if update_stock and stock is not None and stock != row["stock"]:
                    services.adjust_stock(db, row["id"], stock - row["stock"], "woo_sync",
                                          note="همگام‌سازی از سایت", conn=c, allow_negative=True)
                    c.execute("UPDATE products SET woo_dirty=0 WHERE id=?", (row["id"],))
                updated += 1
            else:
                cur = c.execute("INSERT INTO products(name,sku,category,price,stock,image,woo_id) VALUES(?,?,?,?,?,?,?)",
                                (wp["name"], wp.get("sku") or None, cat, price, max(stock or 0, 0), img, wp["id"]))
                if stock:
                    c.execute("INSERT INTO stock_moves(product_id,qty,reason,note) VALUES(?,?,?,?)",
                              (cur.lastrowid, stock, "woo_sync", "ورود اولیه از سایت"))
                added += 1
    return {"added": added, "updated": updated}


def push_products(db, all_products=False, woo=None):
    """ارسال قیمت و موجودی (و ساخت محصول جدید) به سایت. پیش‌فرض: فقط تغییریافته‌ها."""
    w = woo or Woo(db)
    rows = db.q("SELECT * FROM products WHERE active=1" + ("" if all_products else " AND (woo_dirty=1 OR woo_id IS NULL)"))
    updates, creates = [], []
    if usd_rate(db) <= 0 and any(p["currency"] == "USD" for p in rows):
        raise AppError("محصول دلاری دارید ولی نرخ دلار تنظیم نشده؛ از ارسال قیمت صفر به سایت جلوگیری شد")
    for p in rows:
        p = services.with_toman(db, p)
        base = {"regular_price": w.price_out(p["price_toman"]), "manage_stock": True, "stock_quantity": p["stock"]}
        if p["woo_id"]:
            updates.append({"id": p["woo_id"], **base})
        else:
            creates.append((p["id"], {"name": p["name"], "type": "simple", "status": "publish",
                                      **({"sku": p["sku"]} if p["sku"] else {}), **base}))
    for i in range(0, len(updates), 100):
        w.request("POST", "products/batch", body={"update": updates[i:i + 100]})
    for i in range(0, len(creates), 100):
        chunk = creates[i:i + 100]
        res = w.request("POST", "products/batch", body={"create": [b for _, b in chunk]})
        for (pid, _), made in zip(chunk, res.get("create", [])):
            if made.get("id"):
                db.conn.execute("UPDATE products SET woo_id=? WHERE id=?", (made["id"], pid))
    ids = [p["id"] for p in rows]
    if ids:
        db.conn.execute(f"UPDATE products SET woo_dirty=0 WHERE id IN ({','.join('?'*len(ids))})", ids)
    return {"updated": len(updates), "created": len(creates)}


def pull_orders(db, woo=None):
    """سفارش‌های processing/completed را به‌عنوان فروش «آنلاین» وارد می‌کند (تکراری وارد نمی‌شود)."""
    w = woo or Woo(db)
    params = {"status": "processing,completed", "orderby": "date", "order": "asc"}
    after = db.get("woo_orders_after")
    if after:
        params["after"] = after
    decrement = db.get("woo_orders_decrement", "1") == "1"
    imported, last = 0, after
    for o in w.paged("orders", params):
        last = o.get("date_created") or last
        if db.one("SELECT 1 FROM sales WHERE woo_order_id=?", (o["id"],)):
            continue
        items = []
        for li in o.get("line_items", []):
            p = db.one("SELECT id FROM products WHERE woo_id=?", (li.get("product_id"),))
            qty = int(li.get("quantity") or 0)
            if qty <= 0:
                continue
            items.append({"product_id": p["id"] if p else None, "name": li.get("name", "کالا"), "qty": qty,
                          "unit_price": w.price_in(li.get("price"))})
        if not items:
            continue
        b = o.get("billing") or {}
        cust = None
        try:
            if b.get("phone"):
                services.norm_phone(b["phone"])
                cust = {"first_name": b.get("first_name"), "last_name": b.get("last_name"), "phone": b["phone"]}
        except AppError:
            cust = None
        subtotal = sum(i["qty"] * i["unit_price"] for i in items)
        total = w.price_in(o.get("total"))
        discount = max(0, subtotal - total)
        services.create_sale(db, items, customer=cust, discount=discount, pay_method="online",
                                   note=f"سفارش ووکامرس #{o.get('number', o['id'])}", channel="online",
                                   created_at=(o.get("date_created") or "").replace("T", " ") or None,
                                   woo_order_id=o["id"], decrement_stock=decrement, total_override=total)
        imported += 1
    if last:
        db.set("woo_orders_after", last)
    return {"imported": imported}
