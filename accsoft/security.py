"""رمزنگاری و احراز هویت: PBKDF2، توکن نشست، قفل موقت پس از تلاش ناموفق، و رمز کردن اسرار در دیسک."""
import base64
import hashlib
import hmac
import os
import secrets
import time

from .config import data_dir

PBKDF2_ITERS = 240_000


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, PBKDF2_ITERS)
    return f"pbkdf2${PBKDF2_ITERS}${salt.hex()}${dk.hex()}"


def check_password(pw: str, stored: str) -> bool:
    try:
        _, iters, salt, dk = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


def _key_path():
    return data_dir() / "secret.key"


def _master_key() -> bytes:
    p = _key_path()
    if not p.exists():
        p.write_bytes(os.urandom(32))
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
    return p.read_bytes()


def _stream(key: bytes, nonce: bytes, n: int) -> bytes:
    out, i = b"", 0
    while len(out) < n:
        out += hmac.new(key, nonce + i.to_bytes(4, "big"), hashlib.sha256).digest()
        i += 1
    return out[:n]


def seal(text: str) -> str:
    """رمز کردن اسرار (کلید ووکامرس، API پیامک) با جریان HMAC-SHA256 + برچسب یکپارچگی."""
    if not text:
        return ""
    key = _master_key()
    nonce = os.urandom(16)
    data = text.encode()
    ct = bytes(a ^ b for a, b in zip(data, _stream(key, nonce, len(data))))
    tag = hmac.new(key, b"tag" + nonce + ct, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(nonce + tag + ct).decode()


def unseal(blob: str) -> str:
    if not blob:
        return ""
    raw = base64.urlsafe_b64decode(blob.encode())
    nonce, tag, ct = raw[:16], raw[16:32], raw[32:]
    key = _master_key()
    if not hmac.compare_digest(tag, hmac.new(key, b"tag" + nonce + ct, hashlib.sha256).digest()[:16]):
        raise ValueError("secret tampered")
    return bytes(a ^ b for a, b in zip(ct, _stream(key, nonce, len(ct)))).decode()


class Sessions:
    TTL = 8 * 3600

    def __init__(self):
        self._s = {}
        self._fails = {}

    def locked(self, user: str) -> int:
        n, until = self._fails.get(user, (0, 0))
        return max(0, int(until - time.time())) if n >= 5 else 0

    def fail(self, user: str):
        n, _ = self._fails.get(user, (0, 0))
        self._fails[user] = (n + 1, time.time() + 300)

    def create(self, user_id: int):
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        self._s[sid] = {"uid": user_id, "csrf": csrf, "exp": time.time() + self.TTL}
        return sid, csrf

    def get(self, sid):
        s = self._s.get(sid or "")
        if s and s["exp"] > time.time():
            return s
        self._s.pop(sid or "", None)
        return None

    def drop(self, sid):
        self._s.pop(sid or "", None)

    def clear_fails(self, user):
        self._fails.pop(user, None)
