import pathlib

p = pathlib.Path(r'c:\Users\baranit2\Desktop\daftarchi-source\accsoft\static\app.js')
text = p.read_text(encoding='utf-8')

# 1. Add Installments page to PAGES
old_pages = "customers: ['مشتریان', pCustomers, 'customers'],"
new_pages = "customers: ['مشتریان', pCustomers, 'customers'], installments: ['اقساط', pInstallments, 'sales_view'],"
if old_pages in text:
    text = text.replace(old_pages, new_pages)

# 2. Add Bulk SMS to Customers
old_cust = """<a class="btn sec" href="/export/customers.xlsx">Excel</a></div><div id="t"></div></div>`);"""
new_cust = """<a class="btn sec" href="/export/customers.xlsx">Excel</a><button class="sec" id="sms">پیامک گروهی</button></div><div id="t"></div></div>`);"""
if old_cust in text:
    text = text.replace(old_cust, new_cust)

old_cust_logic = "m.close(); load(); }, 'ثبت شد'); };"
new_cust_logic = """m.close(); load(); }, 'ثبت شد'); };
  $('#sms').onclick = () => { const m = modal(h`<h3>ارسال پیامک دسته‌جمعی</h3><textarea id="txt" rows="4" style="width:100%" placeholder="متن پیامک..."></textarea><p><button id="send">ارسال به همه</button> <button class="sec" data-close>انصراف</button></p>`);
    $('#send', m.box).onclick = () => run(async () => {
      const phones = Array.from(document.querySelectorAll('#t td[dir="ltr"]')).map(td => td.textContent).filter(x => x);
      await api('POST', '/api/sms/send-bulk', { text: $('#txt', m.box).value, phones });
      m.close(); toast('ارسال پیامک‌ها در پس‌زمینه شروع شد');
    });
  };"""
if old_cust_logic in text:
    text = text.replace(old_cust_logic, new_cust_logic)

# 3. Add pInstallments definition
inst_func = """
async function pInstallments(el) {
  render(el, h`<div class="card"><div class="row"><h3>مدیریت اقساط سررسید شده/آینده</h3></div><div id="t"></div></div>`);
  const load = () => run(async () => {
    const rows = await api('GET', '/api/installments');
    $('#t').innerHTML = h`<table><tr><th>فاکتور</th><th>مشتری</th><th>موبایل</th><th>تاریخ سررسید</th><th>مبلغ کل</th><th>پرداخت شده</th><th>باقی‌مانده</th><th>عملیات</th></tr>
      ${rows.map(i => h`<tr><td>${i.sale_number}</td><td>${i.first_name} ${i.last_name||''}</td><td dir="ltr">${i.phone}</td>
      <td><span class="badge ${i.due_date < new Date().toLocaleDateString('fa-IR','en-US').replace(/\//g,'/') ? 'off' : 'on'}">${i.due_date}</span></td>
      <td>${money(i.amount)}</td><td>${money(i.paid)}</td><td class="neg">${money(i.amount - i.paid)}</td>
      <td>
        <button class="sec remind-btn" data-id="${i.id}">پیامک یادآوری</button>
        <button class="ok pay-btn" data-id="${i.id}">ثبت پرداخت</button>
      </td></tr>`)}</table>`.s;
    document.querySelectorAll('.remind-btn').forEach(b => b.onclick = () => run(async () => { await api('POST', '/api/installments/'+b.dataset.id+'/remind'); toast('پیامک ارسال شد'); }));
    document.querySelectorAll('.pay-btn').forEach(b => b.onclick = () => {
      const amt = prompt("مبلغ پرداختی (تومان):");
      if(amt) run(async () => { await api('POST', '/api/installments/'+b.dataset.id+'/pay', {amount: parseInt(faNum(amt))}); load(); toast('ثبت شد'); });
    });
  });
  load();
}
"""

if "function pReports(el)" in text and "pInstallments" not in text:
    text = text.replace("function pReports(el)", inst_func + "\nfunction pReports(el)")

p.write_text(text, encoding='utf-8')
print("Successfully patched app.js")
