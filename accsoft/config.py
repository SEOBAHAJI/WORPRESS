import os
import sys
from pathlib import Path

APP_NAME = "Daftarchi"   # دفترچی
OLD_APP_NAME = "AccSoft"  # نام پیشین پوشهٔ داده؛ اگر موجود بود همان استفاده می‌شود
WEBAKERY_BASE = "https://webakery.ir"
LICENSE_PORTAL_PATH = "/accsoft-panel/"   # صفحهٔ پیشخوان ساخته‌شده توسط افزونهٔ وردپرس
TRIAL_DAYS = 7

# قیمت پلن‌ها (تومان)
PLANS = {
    "lifetime": {"title": "مادام‌العمر", "months": None, "price": 14_000_000},
    "3m": {"title": "۳ ماهه", "months": 3, "price": 6_000_000},
    "6m": {"title": "۶ ماهه", "months": 6, "price": 9_000_000},
    "12m": {"title": "۱۲ ماهه", "months": 12, "price": 12_000_000},
}


def data_dir() -> Path:
    override = os.environ.get("ACCSOFT_DATA")
    if override:
        p = Path(override)
    else:
        base = Path(os.environ.get("APPDATA", Path.home())) if sys.platform == "win32" else Path.home() / ".local" / "share"
        p = base / APP_NAME
        if not p.exists() and (base / OLD_APP_NAME).exists():
            p = base / OLD_APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    (p / "images").mkdir(exist_ok=True)
    return p


def resource_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / "accsoft" if base else Path(__file__).parent
