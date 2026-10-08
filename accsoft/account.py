"""حساب کاربری وبیکری: ورود/ثبت‌نام با حساب وردپرس سایت (افزونهٔ سرور لایسنس). رمز فقط روی HTTPS ارسال می‌شود."""
import json
import os
import urllib.error
import urllib.request

from .config import WEBAKERY_BASE
from .services import AppError

REQUIRED = False   # تست‌ها/نسخهٔ آفلاین می‌توانند خاموشش کنند
API = f"{WEBAKERY_BASE}/wp-json/accsoft/v1"
URLS = {"forgot": f"{WEBAKERY_BASE}/wp-login.php?action=lostpassword", "register": f"{WEBAKERY_BASE}/wp-login.php?action=register",
        "panel": f"{WEBAKERY_BASE}/accsoft-panel/"}


def _post(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read(65536) or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read(4096)).get("error")
        except Exception:
            msg = None
        raise AppError(msg or f"خطای سرور ({e.code})")
    except (urllib.error.URLError, OSError):
        raise AppError("اتصال به سرور وبیکری ممکن نشد؛ اینترنت را بررسی کنید")
    except ValueError:
        raise AppError("پاسخ نامعتبر از سرور وبیکری")


def login(email, password):
    """→ {email, name, licenses[]}"""
    r = _post("/auth", {"login": email, "password": password})
    if not r.get("ok"):
        raise AppError(r.get("error") or "ورود ناموفق")
    return r


def register(email, password, name=""):
    r = _post("/register", {"email": email, "password": password, "name": name})
    if not r.get("ok"):
        raise AppError(r.get("error") or "ثبت‌نام ناموفق")
    return r
