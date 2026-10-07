"""لایسنس آفلاین با امضای Ed25519. کلید خصوصی فقط نزد فروشنده است (tools/license_tool.py).
قالب: base64url(payload_json).base64url(signature)"""
import base64
import hashlib
import json
import platform
import uuid
from datetime import date, datetime, timedelta

from . import ed25519
from .config import PLANS, TRIAL_DAYS
from . import pubkey


def _b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def machine_id() -> str:
    raw = f"{uuid.getnode()}|{platform.node()}|{platform.machine()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    import calendar
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def make_license(seed: bytes, plan: str, name: str, mid: str = "", issued: date = None) -> str:
    issued = issued or date.today()
    months = PLANS[plan]["months"]
    payload = {"v": 1, "plan": plan, "name": name, "issued": issued.isoformat(),
               "expires": add_months(issued, months).isoformat() if months else None, "mid": mid}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = ed25519.sign(body, seed)
    e = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return f"{e(body)}.{e(sig)}"


def verify_license(key: str, today: date = None):
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
    except Exception:
        return None, "لایسنس خراب است"
    if p.get("mid") and p["mid"] != machine_id():
        return p, "این لایسنس برای سیستم دیگری صادر شده است"
    if p.get("expires") and date.fromisoformat(p["expires"]) < today:
        return p, "لایسنس منقضی شده است"
    return p, None


def status(db, now: datetime = None):
    """وضعیت فعلی: mode = licensed | trial | expired. شامل تشخیص برگرداندن ساعت سیستم."""
    now = now or datetime.now()
    last = db.get("last_seen")
    tampered = bool(last and now < datetime.fromisoformat(last) - timedelta(days=1))
    if not tampered:
        db.set("last_seen", now.isoformat(timespec="seconds"))
    if not db.get("first_run"):
        db.set("first_run", now.isoformat(timespec="seconds"))
    today = now.date()
    out = {"machine_id": machine_id(), "tampered": tampered, "plans": PLANS}
    key = db.get("license_key")
    if key:
        p, err = verify_license(key, today)
        if p and not err and not tampered:
            return {**out, "mode": "licensed", "plan": p["plan"], "name": p.get("name"),
                    "expires": p.get("expires")}
        out["license_error"] = "ساعت سیستم دستکاری شده است" if tampered else err
    first = datetime.fromisoformat(db.get("first_run")).date()
    left = TRIAL_DAYS - (today - first).days
    if left > 0 and not tampered and not key:
        return {**out, "mode": "trial", "days_left": left}
    return {**out, "mode": "expired"}


def activate(db, key: str, today: date = None):
    p, err = verify_license(key, today)
    if err:
        raise ValueError(err)
    db.set("license_key", key.strip())
    return p
