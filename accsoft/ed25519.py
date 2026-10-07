"""تأیید امضای Ed25519 (RFC 8032) به‌صورت پایتون خالص؛ برای لایسنس آفلاین.
امضاکردن فقط در tools/license_tool.py استفاده می‌شود و در برنامهٔ نهایی کلید خصوصی وجود ندارد."""
import hashlib

_b = 256
_q = 2 ** 255 - 19
_l = 2 ** 252 + 27742317777372353535851937790883648493


def _H(m):
    return hashlib.sha512(m).digest()


def _inv(x):
    return pow(x, _q - 2, _q)


_d = -121665 * _inv(121666) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _xrecover(y):
    xx = (y * y - 1) * _inv(_d * y * y + 1)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = 4 * _inv(5)
_Bx = _xrecover(_By)
_B = (_Bx % _q, _By % _q)


def _add(P, Q):
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _d * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _d * x1 * x2 * y1 * y2)
    return x3 % _q, y3 % _q


def _mul(P, e):
    Q = (0, 1)
    while e > 0:
        if e & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        e >>= 1
    return Q


def _enc(P):
    x, y = P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decode_point(s):
    if len(s) != 32:
        raise ValueError("bad point")
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    if y >= _q:
        raise ValueError("bad point")
    x = _xrecover(y)
    if x & 1 != (s[31] >> 7):
        x = _q - x
    P = (x, y)
    if (-P[0] * P[0] + P[1] * P[1] - 1 - _d * P[0] ** 2 * P[1] ** 2) % _q != 0:
        raise ValueError("not on curve")
    return P


def _hint(m):
    return int.from_bytes(_H(m), "little")


def publickey(seed: bytes) -> bytes:
    h = _H(seed)
    a = 2 ** 254 + sum(2 ** i * ((h[i // 8] >> (i % 8)) & 1) for i in range(3, 254))
    return _enc(_mul(_B, a))


def sign(msg: bytes, seed: bytes) -> bytes:
    h = _H(seed)
    a = 2 ** 254 + sum(2 ** i * ((h[i // 8] >> (i % 8)) & 1) for i in range(3, 254))
    A = publickey(seed)
    r = _hint(h[32:64] + msg)
    R = _mul(_B, r)
    S = (r + _hint(_enc(R) + A + msg) * a) % _l
    return _enc(R) + S.to_bytes(32, "little")


def verify(sig: bytes, msg: bytes, pk: bytes) -> bool:
    try:
        if len(sig) != 64 or len(pk) != 32:
            return False
        R = _decode_point(sig[:32])
        A = _decode_point(pk)
        S = int.from_bytes(sig[32:], "little")
        if S >= _l:
            return False
        h = _hint(_enc(R) + pk + msg)
        return _mul(_B, S) == _add(R, _mul(A, h))
    except Exception:
        return False
