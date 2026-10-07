#!/usr/bin/env python3
"""ابزار فروشنده: ساخت کلید و صدور لایسنس. این فایل و کلید خصوصی را همراه برنامه منتشر نکنید.

  python tools/license_tool.py genkey                       # ساخت جفت‌کلید (یک‌بار)
  python tools/license_tool.py issue --plan 12m --name "علی رضایی" [--mid ABCD...]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from accsoft import ed25519, licensing  # noqa: E402
from accsoft.config import PLANS  # noqa: E402

KEY_FILE = "license_private.key"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("genkey")
    i = sub.add_parser("issue")
    i.add_argument("--plan", required=True, choices=list(PLANS))
    i.add_argument("--name", required=True)
    i.add_argument("--mid", default="", help="شناسهٔ دستگاه مشتری (اختیاری ولی توصیه‌شده)")
    a = ap.parse_args()
    if a.cmd == "genkey":
        if os.path.exists(KEY_FILE):
            sys.exit(f"{KEY_FILE} از قبل وجود دارد؛ برای جلوگیری از ابطال لایسنس‌ها بازنویسی نشد.")
        seed = os.urandom(32)
        fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(seed.hex())
        pub = ed25519.publickey(seed).hex()
        path = os.path.join(os.path.dirname(__file__), "..", "accsoft", "pubkey.py")
        src = open(path, encoding="utf-8").read()
        import re
        open(path, "w", encoding="utf-8").write(
            re.sub(r'PUBLIC_KEY_HEX = ".*"', f'PUBLIC_KEY_HEX = "{pub}"', src))
        print(f"کلید خصوصی در {KEY_FILE} ذخیره شد (جای امن نگه دارید و در گیت نگذارید).")
        print("کلید عمومی در accsoft/pubkey.py نوشته شد. حالا برنامه را بسازید.")
    else:
        seed = bytes.fromhex(open(KEY_FILE).read().strip())
        print(licensing.make_license(seed, a.plan, a.name, a.mid))


if __name__ == "__main__":
    main()
