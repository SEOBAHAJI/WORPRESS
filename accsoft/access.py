"""کاربران، نقش‌ها و مجوزها. قاعدهٔ پیش‌فرض: هر مسیر API که در جدول نیامده باشد فقط برای مدیر است."""
import re

from . import security
from .services import AppError

PERMS = {
    "sell": "ثبت فروش", "sales_view": "مشاهدهٔ فاکتورها", "products_view": "مشاهدهٔ محصولات",
    "products_edit": "ویرایش محصول/قیمت", "inventory": "انبار", "customers": "مشتریان",
    "reports": "گزارش‌ها و داشبورد", "purchases": "فاکتور خرید و تأمین‌کنندگان",
    "finance": "هزینه‌ها، حساب‌ها و ابطال فاکتور", "woo": "ووکامرس", "settings": "تنظیمات و لایسنس", "users": "کاربران",
}
ROLES = {
    "admin": ("مدیر", set(PERMS)),
    "accountant": ("حسابدار", {"sales_view", "products_view", "customers", "reports", "purchases", "finance"}),
    "cashier": ("فروشنده", {"sell", "sales_view", "products_view", "customers"}),
    "warehouse": ("انباردار", {"products_view", "products_edit", "inventory", "purchases"}),
}

# (روش‌ها، الگوی مسیر، مجوز). اولین تطبیق برنده است؛ ترتیب مهم است.
RULES = [
    ("GET", r"/api/(state|ping)", "public"),
    ("POST", r"/api/(login|setup|ping|logout|password)", "any"),
    ("GET", r"/api/license/buy-url", "any"),
    ("GET|POST", r"/api/license(/.*)?", "settings"),
    ("GET", r"/api/(dashboard|report)", "reports"),
    ("POST", r"/api/products/bulk-price", "products_edit"),
    ("POST", r"/api/products/\d+/stock", "inventory"),
    ("GET", r"/api/stock-moves", "inventory"),
    ("GET", r"/api/(products|categories)", "products_view"),
    ("POST|PUT|DELETE", r"/api/products(/.*)?", "products_edit"),
    ("GET|POST", r"/api/customers", "customers"),
    ("GET", r"/api/sms/.*", "settings"),
    ("POST", r"/api/sms/.*", "settings"),
    ("POST", r"/api/sales", "sell"),
    ("GET", r"/api/sales(/\d+)?", "sales_view"),
    ("DELETE", r"/api/sales/\d+", "finance"),
    ("GET|POST|DELETE", r"/api/expenses(/\d+)?", "finance"),
    ("GET|POST|PUT|DELETE", r"/api/(suppliers|purchases)(/\d+)?", "purchases"),
    ("GET|POST|DELETE", r"/api/(payments|ledger|parties)(/\d+)?", "finance"),
    ("GET|PUT", r"/api/settings", "settings"),
    ("POST", r"/api/woo/.*", "woo"),
    ("GET|POST|PUT|DELETE", r"/api/(users|audit)(/\d+)?", "users"),
    ("GET", r"/export/products\.xlsx", "products_view"),
    ("GET", r"/export/sales\.xlsx", "sales_view"),
    ("GET", r"/export/customers\.xlsx", "customers"),
    ("GET", r"/export/report\.xlsx", "reports"),
    ("GET", r"/print/invoice/\d+", "sales_view"),
    ("GET", r"/print/report", "reports"),
    ("GET", r"/print/products", "products_view"),
    ("GET", r"/print/purchase/\d+", "purchases"),
]
_COMPILED = [(set(m.split("|")), re.compile(f"^{p}$"), perm) for m, p, perm in RULES]
_PLUGIN_RULES = []  # افزونه‌ها مجوز مسیر خود را ثبت می‌کنند


def add_rule(methods, pattern, perm):
    _PLUGIN_RULES.append((set(methods.split("|")), re.compile(f"^{pattern}$"), perm))


def perm_for(method, path):
    for ms, rx, perm in _COMPILED + _PLUGIN_RULES:
        if method in ms and rx.match(path):
            return perm
    return "users"  # مسیر ناشناخته ⇒ فقط مدیر


def perms_of(role):
    return sorted(ROLES.get(role, ("", set()))[1])


def allowed(role, perm):
    return perm in ("public", "any") or perm in ROLES.get(role, ("", set()))[1]


# ---------- مدیریت کاربران ----------
def audit(db, user, action, detail=""):
    with db.lock:
        db.conn.execute("INSERT INTO audit(user_id,username,action,detail) VALUES(?,?,?,?)",
                        ((user or {}).get("id"), (user or {}).get("username"), action, detail[:500]))


def list_users(db):
    return db.q("SELECT id,username,full_name,role,active,created_at FROM users ORDER BY id")


def _check(username, password, role, creating):
    if creating and (len((username or "").strip()) < 3):
        raise AppError("نام کاربری حداقل ۳ نویسه باشد")
    if role not in ROLES:
        raise AppError("نقش نامعتبر است")
    if password is not None and password != "" and len(password) < 8:
        raise AppError("رمز حداقل ۸ نویسه باشد")


def create_user(db, username, password, role, full_name=""):
    username = (username or "").strip()
    _check(username, password, role, True)
    if not password:
        raise AppError("رمز الزامی است")
    try:
        with db.tx() as c:
            return c.execute("INSERT INTO users(username,pass_hash,role,full_name) VALUES(?,?,?,?)",
                             (username, security.hash_password(password), role, (full_name or "").strip())).lastrowid
    except Exception as e:
        if "UNIQUE" in str(e):
            raise AppError("این نام کاربری قبلاً وجود دارد")
        raise


def _active_admins(c, excluding=None):
    return c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1 AND id IS NOT ?", (excluding,)).fetchone()[0]


def update_user(db, uid, actor_id, role=None, active=None, password=None, full_name=None):
    with db.tx() as c:
        u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not u:
            raise AppError("کاربر پیدا نشد")
        role = role or u["role"]
        active = u["active"] if active is None else int(bool(active))
        _check(u["username"], password, role, False)
        if u["role"] == "admin" and (role != "admin" or not active) and _active_admins(c, uid) == 0:
            raise AppError("حداقل یک مدیر فعال باید وجود داشته باشد")
        if uid == actor_id and not active:
            raise AppError("نمی‌توانید خودتان را غیرفعال کنید")
        c.execute("UPDATE users SET role=?, active=?, full_name=COALESCE(?,full_name) WHERE id=?",
                  (role, active, full_name, uid))
        if password:
            c.execute("UPDATE users SET pass_hash=? WHERE id=?", (security.hash_password(password), uid))


def delete_user(db, uid, actor_id):
    with db.tx() as c:
        u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not u:
            raise AppError("کاربر پیدا نشد")
        if uid == actor_id:
            raise AppError("نمی‌توانید خودتان را حذف کنید")
        if u["role"] == "admin" and u["active"] and _active_admins(c, uid) == 0:
            raise AppError("حداقل یک مدیر فعال باید وجود داشته باشد")
        c.execute("DELETE FROM users WHERE id=?", (uid,))
