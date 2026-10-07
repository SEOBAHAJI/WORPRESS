"""تبدیل تاریخ میلادی و شمسی (الگوریتم جلالی)."""
from datetime import date, datetime

MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
          "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) \
        + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def j2g(jy, jm, jd):
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    days += (jm - 1) * 31 if jm < 7 else ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    sal = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > sal[gm]:
        gd -= sal[gm]
        gm += 1
    return gy, gm, gd


def to_jalali_str(value) -> str:
    """'2025-03-21' یا datetime → '1404/01/01'."""
    d = parse_date(value)
    jy, jm, jd = g2j(d.year, d.month, d.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:19]).date() if len(str(value)) > 10 \
        else date.fromisoformat(str(value))


def from_jalali_str(s: str) -> date:
    """'1404/01/01' (ارقام فارسی هم مجاز) → date میلادی."""
    s = s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    jy, jm, jd = (int(x) for x in s.replace("-", "/").split("/"))
    return date(*j2g(jy, jm, jd))


def month_range(jy, jm):
    start = date(*j2g(jy, jm, 1))
    ny, nm = (jy + 1, 1) if jm == 12 else (jy, jm + 1)
    end = date(*j2g(ny, nm, 1))
    return start, end  # end انحصاری


def week_start(d: date) -> date:
    """هفتهٔ ایرانی از شنبه شروع می‌شود (Monday=0 ... Saturday=5)."""
    from datetime import timedelta
    return d - timedelta(days=(d.weekday() - 5) % 7)
