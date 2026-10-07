"""کاتالوگ محصولات/افزونه‌ها و پلن‌های لایسنس. دادهٔ عمومی و امضاشده؛ افزودن محصول یا پلن جدید فقط ویرایش
کاتالوگ در «پنل مدیریت لایسنس» است و نیازی به کد ندارد.

قالب فایل:  {"data": {...}, "sig": "<base64url امضای Ed25519 روی JSON متعارف data>"}
data = {"version": N, "revoked": ["<lid>", ...],
        "products": [{"id","name","kind":"app|plugin","description","trial_days",
                      "plans":[{"id","title","months":null|int,"price":تومان}]}]}"""
import base64
import json

from . import ed25519, pubkey
from .config import PLANS, data_dir, resource_dir

APP_PRODUCT = "accsoft"


def canonical(data) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_catalog(seed: bytes, data: dict) -> dict:
    return {"data": data, "sig": _b64(ed25519.sign(canonical(data), seed))}


def verify_doc(doc):
    """→ data یا None. بدون کلید عمومی تنظیم‌شده هیچ سندی معتبر نیست."""
    pk = pubkey.public_key()
    try:
        if pk and ed25519.verify(_unb64(doc["sig"]), canonical(doc["data"]), pk):
            return doc["data"]
    except Exception:
        pass
    return None


def default_data():
    return {"version": 0, "revoked": [], "products": [{
        "id": APP_PRODUCT, "name": "دفترچی", "kind": "app", "description": "", "trial_days": 7,
        "plans": [{"id": k, "title": v["title"], "months": v["months"], "price": v["price"]} for k, v in PLANS.items()]}]}


def _read(path):
    try:
        return verify_doc(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def load() -> dict:
    """جدیدترین کاتالوگ معتبر: فایل کاربر (دریافت‌شده از سایت) یا کاتالوگ همراه برنامه یا پیش‌فرض."""
    cands = [d for d in (_read(data_dir() / "catalog.json"), _read(resource_dir() / "catalog.json")) if d]
    return max(cands, key=lambda d: d.get("version", 0)) if cands else default_data()


def install(doc) -> dict:
    """کاتالوگ جدید را فقط اگر امضا معتبر و نسخه‌اش کمتر از فعلی نباشد (ضد برگرداندن ابطال‌ها) ذخیره می‌کند."""
    data = verify_doc(doc)
    if not data:
        raise ValueError("امضای کاتالوگ نامعتبر است")
    if data.get("version", 0) < load().get("version", 0):
        raise ValueError("کاتالوگ قدیمی‌تر از نسخهٔ فعلی است")
    (data_dir() / "catalog.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return data


def product(cat, pid):
    return next((p for p in cat["products"] if p["id"] == pid), None)


def plan(cat, pid, plan_id):
    p = product(cat, pid)
    return next((x for x in (p or {}).get("plans", []) if x["id"] == plan_id), None)
