"""خروجی Excel (xlsx) و صفحات چاپی (برای ذخیره به‌صورت PDF از پنجرهٔ چاپ)."""
import html
import io

from openpyxl import Workbook
from openpyxl.styles import Font

from . import jalali, services


def _safe(v):
    """جلوگیری از Excel formula injection (نام محصول از سایت می‌آید و غیرقابل‌اعتماد است)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _wb(title, headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.sheet_view.rightToLeft = True
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append([_safe(v) for v in r])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(40, max(10, max(len(str(c.value or "")) for c in col) + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def products_xlsx(db):
    ps = services.list_products(db)
    return _wb("محصولات", ["کد", "نام", "دسته", "واحد", "قیمت", "قیمت (تومان)", "قیمت خرید (تومان)", "موجودی", "حداقل"],
               [[p["sku"], p["name"], p["category"], p["currency"], p["price"], p["price_toman"],
                 p["cost_toman"], p["stock"], p["min_stock"]] for p in ps])


def sales_xlsx(db, start=None, end=None, channel=""):
    ss = services.list_sales(db, start, end, channel, limit=100000)
    return _wb("فروش", ["شماره", "تاریخ", "کانال", "مشتری", "موبایل", "جمع", "تخفیف", "مبلغ نهایی", "بهای تمام‌شده", "سود"],
               [[s["number"], s["jdate"], "آنلاین" if s["channel"] == "online" else "حضوری",
                 f"{s['first_name'] or ''} {s['last_name'] or ''}".strip(), s["phone"], s["subtotal"],
                 s["discount"], s["total"], s["cogs"], s["total"] - s["cogs"]] for s in ss])


def customers_xlsx(db):
    return _wb("مشتریان", ["نام", "نام خانوادگی", "موبایل", "تعداد خرید", "جمع خرید"],
               [[c["first_name"], c["last_name"], c["phone"], c["orders"], c["spent"]] for c in services.list_customers(db)])


def report_xlsx(db, rep):
    t = rep["totals"]
    rows = [["فروش", t["revenue"]], ["بهای تمام‌شده", t["cogs"]], ["سود ناخالص", t["gross_profit"]],
            ["هزینه‌ها", t["expenses"]], ["سود/زیان خالص", t["net_profit"]], [], ["دوره", "تعداد", "فروش", "سود"]]
    rows += [[r["label"], r["count"], r["revenue"], r["profit"]] for r in rep["series"]]
    rows += [[], ["پرفروش‌ها", "تعداد", "فروش", "سود"]]
    rows += [[p["name"], p["qty"], p["revenue"], p["profit"]] for p in rep["top_products"]]
    return _wb("گزارش", [f"گزارش {rep['start']} تا {rep['end']}", ""], rows)


# ---------- صفحات چاپی ----------
CSS = """body{font-family:Tahoma,'Segoe UI',sans-serif;direction:rtl;margin:16px;color:#111}
table{width:100%;border-collapse:collapse;margin:10px 0}td,th{border:1px solid #999;padding:5px 8px;text-align:right}
th{background:#eee}.c{text-align:center}.n{white-space:nowrap}h1,h2{margin:4px 0}
.thermal{width:76mm;font-size:12px;margin:0}.thermal td,.thermal th{padding:2px 3px}
@media print{.noprint{display:none}}"""


def _page(title, body, thermal=False):
    return (f"<!doctype html><html lang=fa dir=rtl><meta charset=utf-8><title>{html.escape(title)}</title>"
            f"<style>{CSS}</style><body class='{'thermal' if thermal else ''}'>"
            "<button class=noprint onclick='window.print()'>🖨 چاپ / ذخیره PDF</button>" + body + "</body></html>")


def fmt(n):
    return f"{int(n):,}"


def invoice_html(db, sale, thermal=False):
    e = html.escape
    rows = "".join(f"<tr><td>{i+1}</td><td>{e(it['name'])}</td><td class=c>{it['qty']}</td>"
                   f"<td class=n>{fmt(it['unit_price'])}</td><td class=n>{fmt(it['qty']*it['unit_price'])}</td></tr>"
                   for i, it in enumerate(sale["items"]))
    cust = f"{e(sale['first_name'] or '')} {e(sale['last_name'] or '')} — {e(sale['phone'] or '')}" if sale["phone"] else "مشتری حضوری"
    body = (f"<h2>{e(db.get('shop_name', 'فروشگاه'))}</h2><div>{e(db.get('shop_phone', ''))} {e(db.get('shop_address', ''))}</div>"
            f"<h3>فاکتور شمارهٔ {sale['number']}</h3><div>تاریخ: {sale['jdate']} | {'آنلاین' if sale['channel']=='online' else 'حضوری'}</div>"
            f"<div>مشتری: {cust}</div><table><tr><th>#</th><th>کالا</th><th>تعداد</th><th>فی (تومان)</th><th>مبلغ</th></tr>{rows}"
            f"<tr><td colspan=4>جمع</td><td class=n>{fmt(sale['subtotal'])}</td></tr>"
            f"<tr><td colspan=4>تخفیف</td><td class=n>{fmt(sale['discount'])}</td></tr>"
            f"<tr><th colspan=4>مبلغ قابل پرداخت (تومان)</th><th class=n>{fmt(sale['total'])}</th></tr></table>"
            f"<div>{e(db.get('invoice_footer', 'با تشکر از خرید شما'))}</div>")
    return _page(f"فاکتور {sale['number']}", body, thermal)


def report_html(rep):
    t, e = rep["totals"], html.escape
    srows = "".join(f"<tr><td>{e(r['label'])}</td><td class=c>{r['count']}</td><td>{fmt(r['revenue'])}</td><td>{fmt(r['profit'])}</td></tr>" for r in rep["series"])
    prow = "".join(f"<tr><td>{e(p['name'])}</td><td class=c>{p['qty']}</td><td>{fmt(p['revenue'])}</td><td>{fmt(p['profit'])}</td></tr>" for p in rep["top_products"])
    chan = "".join(f"<tr><td>{'آنلاین' if k=='online' else 'حضوری'}</td><td class=c>{v['count']}</td><td>{fmt(v['revenue'])}</td><td>{fmt(v['profit'])}</td></tr>" for k, v in rep["by_channel"].items())
    body = (f"<h2>گزارش فروش {e(rep['start'])} تا {e(rep['end'])}</h2><table>"
            f"<tr><th>تعداد فاکتور</th><td>{t['count']}</td><th>فروش</th><td>{fmt(t['revenue'])}</td></tr>"
            f"<tr><th>بهای تمام‌شده</th><td>{fmt(t['cogs'])}</td><th>سود ناخالص</th><td>{fmt(t['gross_profit'])}</td></tr>"
            f"<tr><th>هزینه‌ها</th><td>{fmt(t['expenses'])}</td><th>{'سود' if t['net_profit']>=0 else 'زیان'} خالص</th><td>{fmt(abs(t['net_profit']))}</td></tr></table>"
            f"<h3>تفکیک کانال</h3><table><tr><th>کانال</th><th>تعداد</th><th>فروش</th><th>سود</th></tr>{chan}</table>"
            f"<h3>روند</h3><table><tr><th>دوره</th><th>تعداد</th><th>فروش</th><th>سود</th></tr>{srows}</table>"
            f"<h3>پرفروش‌ترین محصولات</h3><table><tr><th>کالا</th><th>تعداد</th><th>فروش</th><th>سود</th></tr>{prow}</table>")
    return _page("گزارش فروش", body)


def products_html(db):
    e = html.escape
    rows = "".join(f"<tr><td>{e(p['sku'] or '')}</td><td>{e(p['name'])}</td><td>{fmt(p['price_toman'])}</td><td class=c>{p['stock']}</td></tr>" for p in services.list_products(db))
    return _page("لیست محصولات", f"<h2>لیست محصولات و موجودی</h2><table><tr><th>کد</th><th>نام</th><th>قیمت (تومان)</th><th>موجودی</th></tr>{rows}</table>")


def purchase_html(db, pu):
    e = html.escape
    rows = "".join(f"<tr><td>{i+1}</td><td>{e(it['name'])}</td><td class=c>{it['qty']}</td><td class=n>{fmt(it['unit_cost'])}</td>"
                   f"<td class=n>{fmt(it['qty']*it['unit_cost'])}</td></tr>" for i, it in enumerate(pu["items"]))
    body = (f"<h2>{e(db.get('shop_name', 'فروشگاه'))}</h2><h3>فاکتور خرید شمارهٔ {pu['number']}</h3>"
            f"<div>تاریخ: {pu['jdate']} | تأمین‌کننده: {e(pu['supplier'])} {e(pu['phone'] or '')}</div>"
            f"<table><tr><th>#</th><th>کالا</th><th>تعداد</th><th>فی خرید</th><th>مبلغ</th></tr>{rows}"
            f"<tr><td colspan=4>جمع</td><td class=n>{fmt(pu['total'])}</td></tr>"
            f"<tr><td colspan=4>پرداخت‌شده</td><td class=n>{fmt(pu['paid'])}</td></tr>"
            f"<tr><th colspan=4>مانده بدهی</th><th class=n>{fmt(pu['total']-pu['paid'])}</th></tr></table>")
    return _page(f"خرید {pu['number']}", body)
