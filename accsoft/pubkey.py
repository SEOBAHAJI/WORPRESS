"""کلید عمومی Ed25519 فروشنده (۳۲ بایت، هگز).
با `python tools/license_tool.py genkey` ساخته و اینجا قرار می‌گیرد.
تا زمانی که تنظیم نشود، فعال‌سازی لایسنس غیرممکن است (امن به‌صورت پیش‌فرض)."""
PUBLIC_KEY_HEX = ""


def public_key():
    return bytes.fromhex(PUBLIC_KEY_HEX) if PUBLIC_KEY_HEX else None
