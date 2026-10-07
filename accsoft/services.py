"""منطق کسب‌وکار: محصولات، قیمت، انبار، مشتری، فروش، گزارش."""
import re
from datetime import date, datetime, timedelta

from . import jalali

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class AppError(Exception):
    """خطایی که پیامش به کاربر نمایش داده می‌شود."""


# ---------- ارز ----------
def usd_rate(db) -> float:
    return float(db.get("usd_rate", "0") or 0)


def to_toman(db, amount: float, currency: str) -> int:
    if currency == "USD":
        rate = usd_rate(db)
        if rate <= 0:
            raise AppError("نرخ دلار در تنظیمات وارد نشده است")
        return int(round(amount * rate))
    return int(round(amount))


def with_toman(db, p: dict) -> dict:
    rate = usd_rate(db)
    f = (lambda v: int(round(v * rate))) if p["currency"] == "USD" else (lambda v: int(round(v)))
    return {**p, "price_toman": f(p["price"]), "cost_toman": f(p["cost"])}


# ---------- محصولات ----------
def _num(v, name, minimum=0):
    try:
        n = float(str(v if v is not None else 0).translate(FA_DIGITS).replace(",", "").strip() or 0)
    except ValueError:
        raise AppError(f"مقدار «{name}» عدد معتبر نیست")
    if n < minimum:
        raise AppError(f"مقدار «{name}» نمی‌تواند منفی باشد")
    return n


def list_products(db, q="", category="", low_only=False, sellable=False):
    sql, args = "SELECT * FROM products WHERE active=1", []
    if sellable:  # والد محصول متغیر خودش فروختنی/انبارشدنی نیست؛ فقط تنوع‌هایش
        sql += " AND kind!='variable'"
    if q:
        sql += " AND (name LIKE ? OR sku LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    if category:
        sql += " AND category=?"
        args.append(category)
    if low_only:
        sql += " AND stock<=min_stock"
    # تنوع‌ها بلافاصله بعد از والدشان می‌آیند
    rows = db.q(sql + " ORDER BY COALESCE(parent_id, id) DESC, parent_id IS NOT NULL, id", args)
    return [with_toman(db, p) for p in rows]


def save_product(db, data: dict, pid=None):
    name = (data.get("name") or "").strip()
    if not name:
        raise AppError("نام محصول الزامی است")
    cur = data.get("currency", "IRT")
    if cur not in ("IRT", "USD"):
        raise AppError("واحد پول نامعتبر است")
    vals = dict(name=name, sku=(data.get("sku") or "").strip() or None,
                category=(data.get("category") or "").strip(), currency=cur,
                price=_num(data.get("price"), "قیمت"), cost=_num(data.get("cost"), "قیمت خرید"),
                min_stock=int(_num(data.get("min_stock"), "حداقل موجودی")),
                image=data.get("image", ""))
    with db.tx() as c:
        try:
            if pid:
                old = c.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
                if not old:
                    raise AppError("محصول پیدا نشد")
                if "image" not in data:
                    vals["image"] = old["image"]
                sets = ",".join(f"{k}=?" for k in vals)
                c.execute(f"UPDATE products SET {sets}, woo_dirty=CASE WHEN woo_id IS NULL THEN 0 ELSE 1 END,"
                          "updated_at=CURRENT_TIMESTAMP WHERE id=?", (*vals.values(), pid))
            else:
                stock = int(_num(data.get("stock"), "موجودی"))
                cols = ",".join(vals)
                cur_ = c.execute(f"INSERT INTO products({cols},stock,woo_dirty) VALUES({','.join('?'*len(vals))},?,0)",
                                 (*vals.values(), stock))
                pid = cur_.lastrowid
                if stock:
                    c.execute("INSERT INTO stock_moves(product_id,qty,reason,note) VALUES(?,?,?,?)",
                              (pid, stock, "initial", "موجودی اولیه"))
        except Exception as e:
            if "UNIQUE" in str(e):
                raise AppError("کد محصول (SKU) تکراری است")
            raise
    return pid


def delete_product(db, pid):
    with db.tx() as c:
        kids = c.execute("UPDATE products SET active=0 WHERE parent_id=?", (pid,)).rowcount
        used = kids or c.execute("SELECT 1 FROM sale_items WHERE product_id=? LIMIT 1", (pid,)).fetchone()
        if used:
            c.execute("UPDATE products SET active=0 WHERE id=?", (pid,))  # حفظ تاریخچهٔ فروش
        else:
            c.execute("DELETE FROM stock_moves WHERE product_id=?", (pid,))
            c.execute("DELETE FROM products WHERE id=?", (pid,))


def bulk_price(db, scope="all", ids=None, category="", target="price", mode="percent",
               value=0, rounding=0):
    """تغییر گروهی قیمت. mode: percent (+/-)، amount (+/-)، set (مقدار ثابت)."""
    if target not in ("price", "cost"):
        raise AppError("هدف نامعتبر")
    if mode not in ("percent", "amount", "set"):
        raise AppError("روش نامعتبر")
    value = _num(value, "مقدار", minimum=-10**12) if mode != "set" else _num(value, "مقدار")
    rounding = int(rounding or 0)
    sql, args = "SELECT * FROM products WHERE active=1", []
    if scope == "ids":
        ids = [int(i) for i in (ids or [])]
        if not ids:
            raise AppError("هیچ محصولی انتخاب نشده است")
        sql += f" AND id IN ({','.join('?'*len(ids))})"
        args += ids
    elif scope == "category":
        sql += " AND category=?"
        args.append(category)
    n = 0
    with db.tx() as c:
        for p in c.execute(sql, args).fetchall():
            old = p[target]
            new = {"percent": old * (1 + value / 100), "amount": old + value, "set": value}[mode]
            if p["currency"] == "IRT" and rounding > 0:
                new = round(new / rounding) * rounding
            new = max(0, round(new, 2) if p["currency"] == "USD" else round(new))
            if new != old:
                c.execute(f"UPDATE products SET {target}=?, woo_dirty=CASE WHEN woo_id IS NULL THEN 0 ELSE 1 END,"
                          "updated_at=CURRENT_TIMESTAMP WHERE id=?", (new, p["id"]))
                n += 1
    return n


# ---------- انبار ----------
def adjust_stock(db, pid, qty, reason="adjust", note="", ref="", conn=None, allow_negative=False):
    def run(c):
        p = c.execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()
        if not p:
            raise AppError("محصول پیدا نشد")
        if p["stock"] + qty < 0 and not allow_negative:
            raise AppError("موجودی کافی نیست")
        c.execute("UPDATE products SET stock=stock+?, woo_dirty=CASE WHEN woo_id IS NULL THEN 0 ELSE 1 END,"
                  "updated_at=CURRENT_TIMESTAMP WHERE id=?", (qty, pid))
        c.execute("INSERT INTO stock_moves(product_id,qty,reason,ref,note) VALUES(?,?,?,?,?)",
                  (pid, qty, reason, str(ref), note))
    if conn:
        run(conn)
    else:
        with db.tx() as c:
            run(c)


def stock_moves(db, pid=None, limit=200):
    sql = ("SELECT m.*, p.name FROM stock_moves m JOIN products p ON p.id=m.product_id "
           + ("WHERE m.product_id=? " if pid else "") + "ORDER BY m.id DESC LIMIT ?")
    return db.q(sql, ((pid, limit) if pid else (limit,)))


# ---------- مشتری ----------
def norm_phone(s: str) -> str:
    s = (s or "").translate(FA_DIGITS)
    s = re.sub(r"[\s\-()]", "", s)
    s = re.sub(r"^(\+98|0098|98)", "0", s)
    if not re.fullmatch(r"09\d{9}", s):
        raise AppError("شمارهٔ موبایل نامعتبر است (مثال: 09123456789)")
    return s


def upsert_customer(db, first, last, phone, conn=None):
    """→ (customer_id, is_new)"""
    phone = norm_phone(phone)
    def run(c):
        r = c.execute("SELECT id FROM customers WHERE phone=?", (phone,)).fetchone()
        if r:
            c.execute("UPDATE customers SET first_name=COALESCE(NULLIF(?,''),first_name),"
                      "last_name=COALESCE(NULLIF(?,''),last_name) WHERE id=?", (first or "", last or "", r["id"]))
            return r["id"], False
        cur = c.execute("INSERT INTO customers(first_name,last_name,phone) VALUES(?,?,?)",
                        ((first or "").strip(), (last or "").strip(), phone))
        return cur.lastrowid, True
    if conn:
        return run(conn)
    with db.tx() as c:
        return run(c)


# ---------- فروش ----------
def create_sale(db, items, customer=None, discount=0, pay_method="cash", note="",
                channel="offline", created_at=None, woo_order_id=None, decrement_stock=True,
                total_override=None, user_id=None, paid=None):
    if not items:
        raise AppError("فاکتور خالی است")
    allow_neg = db.get("allow_negative_stock", "0") == "1"
    discount = int(_num(discount, "تخفیف"))
    with db.tx() as c:
        cid, is_new = (None, False)
        if customer and (customer.get("phone") or "").strip():
            cid, is_new = upsert_customer(db, customer.get("first_name"), customer.get("last_name"),
                                          customer["phone"], conn=c)
        rows, subtotal, cogs = [], 0, 0
        for it in items:
            qty = int(_num(it.get("qty", 1), "تعداد"))
            if qty <= 0:
                raise AppError("تعداد باید بزرگ‌تر از صفر باشد")
            p = None
            if it.get("product_id"):
                p = c.execute("SELECT * FROM products WHERE id=?", (it["product_id"],)).fetchone()
                if not p:
                    raise AppError("محصول پیدا نشد")
            if p and p["kind"] == "variable":
                raise AppError(f"«{p['name']}» محصول متغیر است؛ یکی از تنوع‌هایش را انتخاب کنید")
            if p:
                if p["currency"] == "USD" and usd_rate(db) <= 0:
                    raise AppError(f"نرخ دلار تنظیم نشده؛ قیمت «{p['name']}» قابل محاسبه نیست")
                pd = with_toman(db, dict(p))
                unit = int(_num(it["unit_price"], "قیمت")) if it.get("unit_price") not in (None, "") else pd["price_toman"]
                cost, name = pd["cost_toman"], p["name"]
            else:
                unit, cost, name = int(_num(it.get("unit_price"), "قیمت")), 0, (it.get("name") or "کالا").strip()
            rows.append((p["id"] if p else None, name, qty, unit, cost))
            subtotal += qty * unit
            cogs += qty * cost
        if discount > subtotal:
            raise AppError("تخفیف بیشتر از جمع فاکتور است")
        total = total_override if total_override is not None else subtotal - discount
        if pay_method == "credit":
            if not cid:
                raise AppError("فروش اعتباری نیاز به مشتری (شمارهٔ موبایل) دارد")
            paid = min(max(int(_num(paid, "پیش‌پرداخت")), 0), total)
        else:
            paid = total
        number = (c.execute("SELECT COALESCE(MAX(number),1000)+1 FROM sales").fetchone()[0])
        cur = c.execute(
            "INSERT INTO sales(number,customer_id,channel,subtotal,discount,total,cogs,pay_method,note,woo_order_id,"
            "user_id,paid,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))",
            (number, cid, channel, subtotal, discount, total, cogs, pay_method, note, woo_order_id, user_id, paid, created_at))
        sid = cur.lastrowid
        for pid, name, qty, unit, cost in rows:
            c.execute("INSERT INTO sale_items(sale_id,product_id,name,qty,unit_price,unit_cost) VALUES(?,?,?,?,?,?)",
                      (sid, pid, name, qty, unit, cost))
            if pid and decrement_stock:
                adjust_stock(db, pid, -qty, "sale", ref=number, conn=c, allow_negative=allow_neg or channel == "online")
    return {"id": sid, "number": number, "new_customer": cid if is_new else None}


def get_sale(db, sid):
    s = db.one("SELECT s.*, c.first_name, c.last_name, c.phone FROM sales s "
               "LEFT JOIN customers c ON c.id=s.customer_id WHERE s.id=?", (sid,))
    if not s:
        raise AppError("فاکتور پیدا نشد")
    s["items"] = db.q("SELECT * FROM sale_items WHERE sale_id=?", (sid,))
    s["jdate"] = jalali.to_jalali_str(s["created_at"])
    return s


def list_sales(db, start=None, end=None, channel="", limit=300):
    sql, args = ("SELECT s.*, c.first_name, c.last_name, c.phone FROM sales s "
                 "LEFT JOIN customers c ON c.id=s.customer_id WHERE 1=1"), []
    if start:
        sql += " AND date(s.created_at)>=?"
        args.append(str(start))
    if end:
        sql += " AND date(s.created_at)<=?"
        args.append(str(end))
    if channel:
        sql += " AND s.channel=?"
        args.append(channel)
    rows = db.q(sql + " ORDER BY s.id DESC LIMIT ?", (*args, limit))
    for r in rows:
        r["jdate"] = jalali.to_jalali_str(r["created_at"])
    return rows


def delete_sale(db, sid):
    """ابطال فاکتور: موجودی برمی‌گردد."""
    with db.tx() as c:
        s = c.execute("SELECT number FROM sales WHERE id=?", (sid,)).fetchone()
        if not s:
            raise AppError("فاکتور پیدا نشد")
        for it in c.execute("SELECT product_id,qty FROM sale_items WHERE sale_id=?", (sid,)).fetchall():
            if it["product_id"]:
                adjust_stock(db, it["product_id"], it["qty"], "return", ref=s["number"],
                             note="ابطال فاکتور", conn=c)
        c.execute("DELETE FROM sales WHERE id=?", (sid,))


def list_customers(db, q=""):
    sql = ("SELECT c.*, COUNT(s.id) AS orders, COALESCE(SUM(s.total),0) AS spent, "
           "COALESCE(SUM(s.total-s.paid),0) - COALESCE((SELECT SUM(amount) FROM payments "
           "WHERE party_type='customer' AND party_id=c.id),0) AS balance FROM customers c "
           "LEFT JOIN sales s ON s.customer_id=c.id ")
    args = ()
    if q:
        sql += "WHERE c.phone LIKE ? OR c.first_name LIKE ? OR c.last_name LIKE ? "
        args = (f"%{q}%",) * 3
    return db.q(sql + "GROUP BY c.id ORDER BY c.id DESC", args)


# ---------- هزینه‌ها ----------
def add_expense(db, title, amount, created_at=None):
    if not (title or "").strip():
        raise AppError("عنوان هزینه الزامی است")
    amount = int(_num(amount, "مبلغ"))
    with db.tx() as c:
        c.execute("INSERT INTO expenses(title,amount,created_at) VALUES(?,?,COALESCE(?,CURRENT_TIMESTAMP))",
                  (title.strip(), amount, created_at))


# ---------- گزارش ----------
def _bucket(d: date, period: str) -> str:
    if period == "month":
        jy, jm, _ = jalali.g2j(d.year, d.month, d.day)
        return f"{jy:04d}/{jm:02d}"
    if period == "week":
        return jalali.to_jalali_str(jalali.week_start(d))
    return jalali.to_jalali_str(d)


def report(db, start: date, end: date, period="day", channel=""):
    """گزارش بازهٔ [start, end] شامل هر دو سر. سود خالص = فروش − بهای تمام‌شده − هزینه‌ها."""
    args = [start.isoformat(), end.isoformat()]
    ch = ""
    if channel:
        ch, _ = " AND channel=?", args.append(channel)
    sales = db.q(f"SELECT id,channel,total,cogs,created_at FROM sales WHERE date(created_at) BETWEEN ? AND ?{ch}", args)
    expenses = db.q("SELECT amount,created_at FROM expenses WHERE date(created_at) BETWEEN ? AND ?",
                    (args[0], args[1]))
    tot = {"count": len(sales), "revenue": sum(s["total"] for s in sales), "cogs": sum(s["cogs"] for s in sales)}
    tot["gross_profit"] = tot["revenue"] - tot["cogs"]
    tot["expenses"] = sum(e["amount"] for e in expenses)
    tot["net_profit"] = tot["gross_profit"] - tot["expenses"]
    by_channel = {k: {"count": 0, "revenue": 0, "profit": 0} for k in ("offline", "online")}
    series = {}
    for s in sales:
        b = by_channel[s["channel"]]
        b["count"] += 1
        b["revenue"] += s["total"]
        b["profit"] += s["total"] - s["cogs"]
        k = _bucket(jalali.parse_date(s["created_at"]), period)
        row = series.setdefault(k, {"label": k, "count": 0, "revenue": 0, "profit": 0, "expenses": 0})
        row["count"] += 1
        row["revenue"] += s["total"]
        row["profit"] += s["total"] - s["cogs"]
    for e in expenses:
        k = _bucket(jalali.parse_date(e["created_at"]), period)
        row = series.setdefault(k, {"label": k, "count": 0, "revenue": 0, "profit": 0, "expenses": 0})
        row["expenses"] += e["amount"]
        row["profit"] -= e["amount"]
    ch2 = ch.replace("channel", "s.channel")
    top = db.q(
        "SELECT i.name, SUM(i.qty) AS qty, SUM(i.qty*i.unit_price) AS revenue, "
        "SUM(i.qty*(i.unit_price-i.unit_cost)) AS profit FROM sale_items i JOIN sales s ON s.id=i.sale_id "
        f"WHERE date(s.created_at) BETWEEN ? AND ?{ch2} GROUP BY COALESCE(i.product_id, i.name) "
        "ORDER BY qty DESC LIMIT 10", args)
    return {"start": jalali.to_jalali_str(start), "end": jalali.to_jalali_str(end), "totals": tot,
            "by_channel": by_channel, "series": [series[k] for k in sorted(series)], "top_products": top}


def preset_range(kind: str, today: date = None):
    today = today or date.today()
    if kind == "day":
        return today, today
    if kind == "week":
        s = jalali.week_start(today)
        return s, s + timedelta(days=6)
    if kind == "month":
        jy, jm, _ = jalali.g2j(today.year, today.month, today.day)
        s, e = jalali.month_range(jy, jm)
        return s, e - timedelta(days=1)
    raise AppError("بازهٔ نامعتبر")


def dashboard(db):
    out = {}
    for k in ("day", "week", "month"):
        s, e = preset_range(k)
        out[k] = report(db, s, e, k)["totals"]
    out["low_stock"] = len(list_products(db, low_only=True))
    out["products"] = db.one("SELECT COUNT(*) n FROM products WHERE active=1")["n"]
    out["customers"] = db.one("SELECT COUNT(*) n FROM customers")["n"]
    out["receivable"], out["payable"] = (parties_summary(db)[k]["total"] for k in ("debtors", "creditors"))
    return out


# ---------- تأمین‌کنندگان، فاکتور خرید ----------
def save_supplier(db, data, sid=None):
    name = (data.get("name") or "").strip()
    if not name:
        raise AppError("نام تأمین‌کننده الزامی است")
    phone = (data.get("phone") or "").strip()
    with db.tx() as c:
        if sid:
            c.execute("UPDATE suppliers SET name=?, phone=?, note=? WHERE id=?", (name, phone, data.get("note", ""), sid))
            return sid
        return c.execute("INSERT INTO suppliers(name,phone,note) VALUES(?,?,?)", (name, phone, data.get("note", ""))).lastrowid


def list_suppliers(db):
    return db.q("SELECT s.*, COALESCE((SELECT SUM(total-paid) FROM purchases WHERE supplier_id=s.id),0)"
                " - COALESCE((SELECT SUM(amount) FROM payments WHERE party_type='supplier' AND party_id=s.id),0)"
                " AS balance FROM suppliers s ORDER BY s.id DESC")


def delete_supplier(db, sid):
    with db.tx() as c:
        if c.execute("SELECT 1 FROM purchases WHERE supplier_id=? LIMIT 1", (sid,)).fetchone() or \
                c.execute("SELECT 1 FROM payments WHERE party_type='supplier' AND party_id=? LIMIT 1", (sid,)).fetchone():
            raise AppError("این تأمین‌کننده سابقهٔ خرید/پرداخت دارد و قابل حذف نیست")
        c.execute("DELETE FROM suppliers WHERE id=?", (sid,))


def _from_toman(db, toman: float, currency: str) -> float:
    if currency == "USD":
        rate = usd_rate(db)
        if rate <= 0:
            raise AppError("نرخ دلار در تنظیمات وارد نشده است")
        return round(toman / rate, 2)
    return round(toman)


def create_purchase(db, supplier_id, items, paid=0, note="", user_id=None, created_at=None):
    """فاکتور خرید: موجودی زیاد می‌شود و قیمت خرید کالا به‌صورت «میانگین موزون» به‌روز می‌شود."""
    if not items:
        raise AppError("فاکتور خرید خالی است")
    with db.tx() as c:
        if not c.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,)).fetchone():
            raise AppError("تأمین‌کننده پیدا نشد")
        rows, total = [], 0
        for it in items:
            qty, unit = int(_num(it.get("qty"), "تعداد")), int(_num(it.get("unit_cost"), "قیمت خرید"))
            if qty <= 0:
                raise AppError("تعداد باید بزرگ‌تر از صفر باشد")
            p = c.execute("SELECT * FROM products WHERE id=? AND active=1", (it.get("product_id"),)).fetchone()
            if not p or p["kind"] == "variable":
                raise AppError("کالای فاکتور خرید نامعتبر است")
            rows.append((p, qty, unit))
            total += qty * unit
        paid = min(max(int(_num(paid, "پرداختی")), 0), total)
        number = c.execute("SELECT COALESCE(MAX(number),5000)+1 FROM purchases").fetchone()[0]
        pid = c.execute("INSERT INTO purchases(number,supplier_id,total,paid,note,user_id,created_at) "
                        "VALUES(?,?,?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))",
                        (number, supplier_id, total, paid, note, user_id, created_at)).lastrowid
        for p, qty, unit in rows:
            c.execute("INSERT INTO purchase_items(purchase_id,product_id,qty,unit_cost) VALUES(?,?,?,?)", (pid, p["id"], qty, unit))
            old_cost = to_toman(db, p["cost"], p["currency"])
            stock = max(p["stock"], 0)
            new_cost = round((stock * old_cost + qty * unit) / (stock + qty))
            c.execute("UPDATE products SET cost=? WHERE id=?", (_from_toman(db, new_cost, p["currency"]), p["id"]))
            adjust_stock(db, p["id"], qty, "purchase", ref=number, note="فاکتور خرید", conn=c)
    return {"id": pid, "number": number, "total": total}


def get_purchase(db, pid):
    r = db.one("SELECT p.*, s.name AS supplier, s.phone FROM purchases p JOIN suppliers s ON s.id=p.supplier_id WHERE p.id=?", (pid,))
    if not r:
        raise AppError("فاکتور خرید پیدا نشد")
    r["items"] = db.q("SELECT i.*, p.name FROM purchase_items i JOIN products p ON p.id=i.product_id WHERE purchase_id=?", (pid,))
    r["jdate"] = jalali.to_jalali_str(r["created_at"])
    return r


def list_purchases(db, limit=200):
    rows = db.q("SELECT p.*, s.name AS supplier FROM purchases p JOIN suppliers s ON s.id=p.supplier_id ORDER BY p.id DESC LIMIT ?", (limit,))
    for r in rows:
        r["jdate"] = jalali.to_jalali_str(r["created_at"])
    return rows


def delete_purchase(db, pid):
    """ابطال خرید: موجودی کم می‌شود (اگر کالا فروخته شده و موجودی کافی نباشد، رد می‌شود)."""
    with db.tx() as c:
        pu = c.execute("SELECT number FROM purchases WHERE id=?", (pid,)).fetchone()
        if not pu:
            raise AppError("فاکتور خرید پیدا نشد")
        for it in c.execute("SELECT product_id, qty FROM purchase_items WHERE purchase_id=?", (pid,)).fetchall():
            adjust_stock(db, it["product_id"], -it["qty"], "adjust", ref=pu["number"], note="ابطال فاکتور خرید", conn=c)
        c.execute("DELETE FROM purchases WHERE id=?", (pid,))


# ---------- حساب‌ها: بدهکار / بستانکار ----------
def party_balance(db, party_type, pid) -> int:
    """مثبت = طرف حساب بدهکار است (مشتری به ما) / ما بدهکاریم (تأمین‌کننده)."""
    if party_type == "customer":
        a = db.one("SELECT COALESCE(SUM(total-paid),0) v FROM sales WHERE customer_id=?", (pid,))["v"]
    else:
        a = db.one("SELECT COALESCE(SUM(total-paid),0) v FROM purchases WHERE supplier_id=?", (pid,))["v"]
    b = db.one("SELECT COALESCE(SUM(amount),0) v FROM payments WHERE party_type=? AND party_id=?", (party_type, pid))["v"]
    return a - b


def add_payment(db, party_type, pid, amount, method="cash", note="", user_id=None):
    if party_type not in ("customer", "supplier"):
        raise AppError("نوع طرف حساب نامعتبر است")
    amount = int(_num(amount, "مبلغ"))
    if amount <= 0:
        raise AppError("مبلغ باید بزرگ‌تر از صفر باشد")
    with db.tx() as c:
        tbl = "customers" if party_type == "customer" else "suppliers"
        if not c.execute(f"SELECT 1 FROM {tbl} WHERE id=?", (pid,)).fetchone():
            raise AppError("طرف حساب پیدا نشد")
    bal = party_balance(db, party_type, pid)
    if amount > bal:
        raise AppError(f"مبلغ بیشتر از مانده حساب ({bal:,}) است")
    with db.tx() as c:
        c.execute("INSERT INTO payments(party_type,party_id,amount,method,note,user_id) VALUES(?,?,?,?,?,?)",
                  (party_type, pid, amount, method, note, user_id))


def delete_payment(db, payment_id):
    with db.tx() as c:
        c.execute("DELETE FROM payments WHERE id=?", (payment_id,))


def ledger(db, party_type, pid):
    """صورت‌حساب با مانده تجمعی."""
    if party_type == "customer":
        rows = [(r["created_at"], f"فاکتور فروش {r['number']}", r["total"] - r["paid"], 0, None)
                for r in db.q("SELECT number,total,paid,created_at FROM sales WHERE customer_id=?", (pid,)) if r["total"] - r["paid"]]
    else:
        rows = [(r["created_at"], f"فاکتور خرید {r['number']}", r["total"] - r["paid"], 0, None)
                for r in db.q("SELECT number,total,paid,created_at FROM purchases WHERE supplier_id=?", (pid,)) if r["total"] - r["paid"]]
    rows += [(r["created_at"], "پرداخت" + (f" — {r['note']}" if r["note"] else ""), 0, r["amount"], r["id"])
             for r in db.q("SELECT * FROM payments WHERE party_type=? AND party_id=?", (party_type, pid))]
    out, bal = [], 0
    for when, title, debit, credit, payment_id in sorted(rows, key=lambda r: r[0]):
        bal += debit - credit
        out.append({"date": jalali.to_jalali_str(when), "title": title, "debit": debit, "credit": credit,
                    "balance": bal, "payment_id": payment_id})
    return out


def parties_summary(db):
    debtors = [c for c in list_customers(db) if c["balance"] > 0]
    creditors = [s for s in list_suppliers(db) if s["balance"] > 0]
    return {"debtors": {"rows": debtors, "total": sum(c["balance"] for c in debtors)},
            "creditors": {"rows": creditors, "total": sum(s["balance"] for s in creditors)}}
