"""ارسال پیامک از طریق پنل. پشتیبانی از کاوه‌نگار، ملی‌پیامک و هر پنل HTTP دلخواه."""
import json
import urllib.parse
import urllib.request

from . import security


def welcome_text(db, first, last):
    tpl = db.get("welcome_text") or "{name} عزیز، به فروشگاه {shop} خوش آمدید."
    name = f"{first or ''} {last or ''}".strip() or "مشتری"
    return tpl.replace("{name}", name).replace("{shop}", db.get("shop_name", "ما"))


def _http(url, method="GET", data=None, headers=None):
    if not url.lower().startswith("http"):
        raise ValueError("آدرس پنل پیامک نامعتبر است")
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, r.read(2000).decode("utf-8", "replace")


def send(db, phone, text):
    provider = db.get("sms_provider", "none")
    ok, detail = False, ""
    try:
        key = security.unseal(db.get("sms_apikey", ""))
        sender = db.get("sms_sender", "")
        username = db.get("sms_username", "")

        if provider == "kavenegar":
            q = urllib.parse.urlencode({"receptor": phone, "message": text, "sender": sender})
            code, body = _http(f"https://api.kavenegar.com/v1/{urllib.parse.quote(key)}/sms/send.json?{q}")
            ok, detail = code == 200, body[:200]
            
        elif provider == "melipayamak":
            data = json.dumps({
                "username": username or key,
                "password": key,
                "to": phone,
                "from": sender,
                "text": text,
                "isflash": False
            }).encode("utf-8")
            code, body = _http("https://rest.payamak-panel.com/api/SendSMS/SendSMS", "POST", data, {"Content-Type": "application/json"})
            try:
                resp = json.loads(body)
                ok = str(resp.get("RetStatus")) == "1"
            except:
                ok = False
            detail = body[:200]
            
        elif provider == "custom":
            tpl = db.get("sms_url", "")
            fill = lambda s: (s.replace("{to}", urllib.parse.quote(phone)).replace("{text}", urllib.parse.quote(text))
                              .replace("{key}", urllib.parse.quote(key)).replace("{sender}", urllib.parse.quote(sender))
                              .replace("{user}", urllib.parse.quote(username)))
            if db.get("sms_method", "GET") == "POST":
                url, _, body_tpl = tpl.partition("|")
                is_json = body_tpl.strip().startswith("{")
                content_type = "application/json" if is_json else "application/x-www-form-urlencoded"
                code, resp = _http(fill(url), "POST", fill(body_tpl).encode("utf-8"),
                                   {"Content-Type": content_type})
            else:
                code, resp = _http(fill(tpl))
            ok, detail = 200 <= code < 300, resp[:200]
        else:
            detail = "پنل پیامک تنظیم نشده است"
    except Exception as e:
        detail = str(e)[:200]
    with db.lock:
        db.conn.execute("INSERT INTO sms_log(phone,text,ok,detail) VALUES(?,?,?,?)", (phone, text, int(ok), detail))
    return ok, detail
