import os
import sys
from pathlib import Path

APP_NAME = "AccSoft"
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
    elif sys.platform == "win32":
        p = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    else:
        p = Path.home() / ".local" / "share" / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    (p / "images").mkdir(exist_ok=True)
    return p


def resource_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / "accsoft" if base else Path(__file__).parent
