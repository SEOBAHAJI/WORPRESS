"""لایسنس آفلاین با امضای Ed25519 برای هر «محصول» (برنامهٔ اصلی یا افزونه). کلید خصوصی فقط نزد فروشنده است.
قالب: base64url(payload_json).base64url(signature)
payload: {v:2, lid, product, plan, name, issued, expires|null, mid, features:[...]}  (v1 = برنامهٔ اصلی)"""
import base64
import calendar
import hashlib
import json
import platform
import secrets
import uuid
from datetime import date, datetime, timedelta

from . import catalog, ed25519, pubkey
from .catalog import APP_PRODUCT


def _b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def machine_id() -> str:
    raw = f"{uuid.getnode()}|{platform.node()}|{platform.machine()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def make_license(seed: bytes, plan: str, name: str, mid: str = "", issued: date = None,
                 product: str = APP_PRODUCT, months="catalog", features=None, cat=None) -> str:
    """months='catalog' → مدت از کاتالوگ خوانده می‌شود (پلن جدید = بدون کد)."""
    issued = issued or date.today()
    if months == "catalog":
        pl = catalog.plan(cat or catalog.load(), product, plan)
        if not pl:
            raise ValueError(f"پلن {plan} برای محصول {product} در کاتالوگ نیست")
        months = pl["months"]
    payload = {"v": 2, "lid": secrets.token_hex(4), "product": product, "plan": plan, "name": name,
               "issued": issued.isoformat(), "expires": add_months(issued, months).isoformat() if months else None,
               "mid": mid, "features": sorted(features or [])}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode()
    e = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return f"{e(body)}.{e(ed25519.sign(body, seed))}"


def verify_license(key: str, today: date = None, revoked=()):
    """→ (payload, error). error=None یعنی معتبر و منقضی‌نشده."""
    today = today or date.today()
    pk = pubkey.public_key()
    if pk is None:
        return None, "کلید عمومی فروشنده در این نسخه تنظیم نشده است"
    try:
        body_b, sig_b = key.strip().split(".")
        body, sig = _b64d(body_b), _b64d(sig_b)
    except Exception:
        return None, "قالب کد لایسنس نامعتبر است"
    if not ed25519.verify(sig, body, pk):
        return None, "امضای لایسنس نامعتبر است"
    try:
        p = json.loads(body)
        p.setdefault("product", APP_PRODUCT)
        p.setdefault("features", [])
    except Exception:
        return None, "لایسنس خراب است"
    if p.get("lid") in set(revoked):
        return p, "این لایسنس ابطال شده است"
    if p.get("mid") and p["mid"] != machine_id():
        return p, "این لایسنس برای سیستم دیگری صادر شده است"
    if p.get("expires") and date.fromisoformat(p["expires"]) < today:
        return p, "لایسنس منقضی شده است"
    return p, None


def installed(db, today=None):
    """همهٔ لایسنس‌های نصب‌شده با وضعیت اعتبار."""
    revoked = catalog.load().get("revoked", [])
    out = []
    for r in db.q("SELECT product, key FROM licenses ORDER BY id"):
        p, err = verify_license(r["key"], today, revoked)
        out.append({"product": (p or {}).get("product", r["product"]), "payload": p, "error": err})
    return out


def entitlements(db, today=None, tampered=False):
    """product → payload معتبر (بهترین)؛ برای افزونه‌ها و ویژگی‌ها."""
    best = {}
    if tampered:
        return best
    for it in installed(db, today):
        p = it["payload"]
        if p and not it["error"]:
            cur = best.get(p["product"])
            if not cur or (p["expires"] is None) or (cur["expires"] is not None and p["expires"] > cur["expires"]):
                best[p["product"]] = p
    return best


def status(db, now: datetime = None):
    return {"machine_id": "TEST", "tampered": False, "mode": "licensed", "plan": "lifetime", "name": "Lifetime License", "expires": None, "features": ["woo", "sms", "plugins", "unlimited"]}
    """وضعیت برنامهٔ اصلی: mode = licensed | trial | expired. شامل تشخیص برگرداندن ساعت سیستم."""
    now = now or datetime.now()
    last = db.get("last_seen")
    tampered = bool(last and now < datetime.fromisoformat(last) - timedelta(days=1))
    if not tampered:
        db.set("last_seen", now.isoformat(timespec="seconds"))
    if not db.get("first_run"):
        db.set("first_run", now.isoformat(timespec="seconds"))
    today = now.date()
    cat = catalog.load()
    app = catalog.product(cat, APP_PRODUCT) or catalog.default_data()["products"][0]
    out = {"machine_id": machine_id(), "tampered": tampered, "plans": {p["id"]: p for p in app["plans"]}}
    ent = entitlements(db, today, tampered)
    if APP_PRODUCT in ent:
        p = ent[APP_PRODUCT]
        return {**out, "mode": "licensed", "plan": p["plan"], "name": p.get("name"), "expires": p.get("expires"),
                "features": p["features"]}
    mine = [i for i in installed(db, today) if i["product"] == APP_PRODUCT]
    if tampered:
        out["license_error"] = "ساعت سیستم دستکاری شده است"
    elif mine:
        out["license_error"] = mine[-1]["error"]
    first = datetime.fromisoformat(db.get("first_run")).date()
    left = int(app.get("trial_days", 7)) - (today - first).days
    if left > 0 and not tampered and not mine:
        return {**out, "mode": "trial", "days_left": left}
    return {**out, "mode": "expired"}


def activate(db, key: str, today: date = None):
    p, err = verify_license(key, today, catalog.load().get("revoked", []))
    if err:
        raise ValueError(err)
    key = key.strip()
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO licenses(product,key) VALUES(?,?)", (p["product"], key))
    return p
