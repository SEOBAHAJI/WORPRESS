'use strict';
// ---------- ابزارها ----------
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
class Raw { constructor(s){ this.s = s; } }
const raw = s => new Raw(s);
// قالب با escape خودکار؛ برای HTML تو در تو از raw() یا آرایه‌ای از raw استفاده کنید
const h = (strs, ...vals) => new Raw(strs.reduce((a, s, i) => a + s + (i < vals.length ? part(vals[i]) : ''), ''));
const part = v => v instanceof Raw ? v.s : Array.isArray(v) ? v.map(part).join('') : esc(v);
const $ = (sel, el = document) => el.querySelector(sel);
const money = n => Number(n || 0).toLocaleString('fa-IR');
const faNum = s => String(s ?? '').replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d)).replace(/[,٬]/g, '');
let S = {};           // وضعیت سراسری
let csrf = null;

async function api(method, url, body) {
  const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf || '' },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401) { await boot(); throw new Error('ورود لازم است'); }
  if (!r.ok) { const e = new Error(data.error || 'خطا'); e.license = data.license; throw e; }
  return data;
}
function toast(msg, err) {
  const d = document.createElement('div'); d.textContent = msg; if (err) d.className = 'err';
  $('#toast').append(d); setTimeout(() => d.remove(), err ? 6000 : 3000);
}
const run = async (fn, okMsg) => { try { const r = await fn(); if (okMsg) toast(okMsg); return r; } catch (e) { toast(e.message, true); if (e.license) go('license'); } };
function modal(content, onClose) {
  const m = document.createElement('div'); m.className = 'modal';
  const box = document.createElement('div'); box.innerHTML = content.s; m.append(box);
  m.addEventListener('click', e => { if (e.target === m) close(); });
  const close = () => { m.remove(); onClose && onClose(); };
  box.querySelectorAll('[data-close]').forEach(b => b.onclick = close);
  document.body.append(m); return { box, close };
}
function showPrint(url) {
  const m = modal(h`<iframe src="${url}"></iframe><div class="row" style="margin-top:8px"><button id="pp">🖨 چاپ / ذخیره PDF</button>
    <button class="sec" data-close>بستن</button></div>`);
  $('#pp', m.box).onclick = () => $('iframe', m.box).contentWindow.print();
}
function showHelp(key) { const [t, body] = HELP[key]; modal(h`<div class="help"><h3>${t}</h3>${raw(body)}<button data-close>متوجه شدم</button></div>`); }
const field = (label, inner) => h`<div><label>${label}</label>${inner}</div>`;
const todayJ = () => S.today;

// ---------- ورود/نصب ----------
async function boot() {
  S = await (await fetch('/api/state')).json(); csrf = S.csrf;
  if (!window._pinger) window._pinger = setInterval(() => fetch('/api/ping', { method: 'POST', body: '{}' }), 15000);
  if (S.setup_needed) return setupView();
  if (!S.logged_in) return loginView();
  go(location.hash.slice(1) || 'dashboard');
}
function authBox(title, extra, btn, fn) {
  $('#app').innerHTML = h`<div class="center card"><h2>${title}</h2>${extra}
    ${field('نام کاربری', h`<input id="u" autocomplete="username" style="width:100%">`)}
    ${field('رمز عبور', h`<input id="p" type="password" autocomplete="current-password" style="width:100%">`)}
    <p><button id="go">${btn}</button></p></div>`.s;
  $('#go').onclick = () => run(async () => { await fn($('#u').value, $('#p').value); await boot(); });
  $('#p').onkeydown = e => e.key === 'Enter' && $('#go').click();
}
const loginView = () => authBox('ورود', '', 'ورود', (u, p) => api('POST', '/api/login', { username: u, password: p }));
function setupView() {
  authBox('نصب اولیه', field('نام فروشگاه', h`<input id="shop" style="width:100%">`) , 'ایجاد حساب مدیر',
    (u, p) => api('POST', '/api/setup', { username: u, password: p, shop_name: $('#shop').value }));
  $('.center').insertAdjacentHTML('beforeend', '<p class="mut">رمز حداقل ۸ نویسه. آن را فراموش نکنید؛ بازیابی ندارد.</p>');
}

// ---------- چارچوب ----------
const PAGES = { dashboard: ['داشبورد', pDashboard], pos: ['فروش حضوری', pPos], sales: ['فاکتورها', pSales],
  products: ['محصولات', pProducts], inventory: ['انبار', pInventory], customers: ['مشتریان', pCustomers],
  reports: ['گزارش‌ها', pReports], expenses: ['هزینه‌ها', pExpenses], woo: ['ووکامرس', pWoo],
  settings: ['تنظیمات', pSettings], license: ['لایسنس', pLicense] };
function go(page) {
  if (!PAGES[page]) page = 'dashboard';
  location.hash = page;
  const L = S.license, [title, fn] = PAGES[page];
  const banner = L.mode === 'trial' ? h`<div class="banner">دورهٔ آزمایشی: ${L.days_left} روز باقی مانده. <a href="#license" style="color:inherit">تهیهٔ لایسنس</a></div>`
    : L.mode === 'expired' ? h`<div class="banner bad">${L.tampered ? 'ساعت سیستم دستکاری شده است.' : (L.license_error || 'لایسنس معتبر نیست.')} فقط مشاهده و خروجی فعال است. <a href="#license" style="color:inherit">تهیهٔ لایسنس</a></div>` : '';
  $('#app').innerHTML = h`<div class="layout"><nav class="side"><h1>${S.shop_name || 'حسابداری'}</h1>
    ${Object.entries(PAGES).map(([k, [t]]) => h`<a data-p="${k}" class="${k === page ? 'on' : ''}">${t}</a>`)}
    <a id="out">خروج</a></nav><main class="main">${banner}<div class="top"><h2>${title}</h2>
    <button class="sec" id="hlp">؟ راهنما</button></div><div id="page"></div></main></div>`.s;
  document.querySelectorAll('.side a[data-p]').forEach(a => a.onclick = () => go(a.dataset.p));
  $('#out').onclick = async () => { await api('POST', '/api/logout', {}); boot(); };
  $('#hlp').onclick = () => showHelp(page);
  run(() => fn($('#page')));
}
const render = (el, t) => { el.innerHTML = t.s; };
const profitCls = n => n < 0 ? 'neg' : 'pos-n';

// ---------- داشبورد ----------
async function pDashboard(el) {
  const d = await api('GET', '/api/dashboard');
  const card = (t, x) => h`<div class="card stat"><small>${t}</small><b>${money(x.revenue)} تومان</b>
    <small>${x.count} فاکتور · <span class="${profitCls(x.net_profit)}">${x.net_profit < 0 ? 'زیان' : 'سود'} خالص ${money(Math.abs(x.net_profit))}</span></small></div>`;
  render(el, h`<div class="grid">${card('امروز', d.day)}${card('این هفته', d.week)}${card('این ماه', d.month)}</div>
    <div class="grid"><div class="card stat"><small>محصولات</small><b>${d.products}</b></div>
    <div class="card stat"><small>مشتریان</small><b>${d.customers}</b></div>
    <div class="card stat"><small>کمبود موجودی</small><b class="${d.low_stock ? 'neg' : ''}">${d.low_stock}</b></div></div>`);
}

// ---------- فروش حضوری ----------
let cart = [];
async function pPos(el) {
  const products = await api('GET', '/api/products');
  render(el, h`<div class="pos"><div class="card"><input id="q" placeholder="جست‌وجوی نام یا کد..." style="width:100%" autofocus>
    <div class="plist" id="pl"></div></div>
    <div class="card"><table id="ct"></table>
    <div class="row">${field('تخفیف (تومان)', h`<input id="disc" value="0" size="10">`)}
      ${field('پرداخت', h`<select id="pm"><option value="cash">نقد</option><option value="card">کارت</option><option value="credit">اعتباری</option></select>`)}</div>
    <div class="row">${field('موبایل مشتری', h`<input id="cph" placeholder="09..." size="12">`)}${field('نام', h`<input id="cfn" size="9">`)}${field('نام خانوادگی', h`<input id="cln" size="11">`)}</div>
    <h3>مبلغ نهایی: <span id="tot"></span> تومان</h3>
    <button class="ok" id="sell">ثبت و چاپ</button> <button class="sec" id="clr">خالی کردن</button></div></div>`);
  const drawList = () => {
    const q = $('#q').value.trim().toLowerCase();
    $('#pl').innerHTML = products.filter(p => !q || p.name.toLowerCase().includes(q) || (p.sku || '').toLowerCase().includes(q)).slice(0, 60)
      .map(p => h`<div class="prod" data-id="${p.id}">${p.image ? h`<img class="thumb" src="/img/${p.image}">` : h`<div class="thumb"></div>`}
      <div class="grow"><b>${p.name}</b><br><small class="mut">موجودی: ${p.stock}</small></div><b>${money(p.price_toman)}</b></div>`.s).join('');
    document.querySelectorAll('.prod').forEach(d => d.onclick = () => {
      const p = products.find(x => x.id == d.dataset.id); const ex = cart.find(c => c.product_id === p.id);
      ex ? ex.qty++ : cart.push({ product_id: p.id, name: p.name, qty: 1, unit_price: p.price_toman }); drawCart();
    });
  };
  const total = () => Math.max(0, cart.reduce((a, c) => a + c.qty * c.unit_price, 0) - (parseInt(faNum($('#disc').value)) || 0));
  const drawCart = () => {
    $('#ct').innerHTML = '<tr><th>کالا</th><th>تعداد</th><th>فی</th><th></th></tr>' + cart.map((c, i) => h`<tr><td>${c.name}</td>
      <td><input type="number" min="1" value="${c.qty}" data-i="${i}" data-f="qty" style="width:60px"></td>
      <td><input value="${c.unit_price}" data-i="${i}" data-f="unit_price" style="width:100px"></td><td><button class="sec" data-del="${i}">✕</button></td></tr>`.s).join('');
    $('#ct').querySelectorAll('input').forEach(inp => inp.onchange = () => {
      cart[inp.dataset.i][inp.dataset.f] = parseInt(faNum(inp.value)) || 0; drawCart(); });
    $('#ct').querySelectorAll('[data-del]').forEach(b => b.onclick = () => { cart.splice(b.dataset.del, 1); drawCart(); });
    $('#tot').textContent = money(total());
  };
  $('#q').oninput = drawList; $('#disc').oninput = drawCart; drawList(); drawCart();
  $('#clr').onclick = () => { cart = []; drawCart(); };
  $('#sell').onclick = () => run(async () => {
    const phone = $('#cph').value.trim();
    const r = await api('POST', '/api/sales', { items: cart.map(({ product_id, qty, unit_price }) => ({ product_id, qty, unit_price })),
      discount: parseInt(faNum($('#disc').value)) || 0, pay_method: $('#pm').value,
      customer: phone ? { phone, first_name: $('#cfn').value, last_name: $('#cln').value } : null });
    cart = []; toast(`فاکتور ${r.number} ثبت شد`); showPrint(`/print/invoice/${r.id}`); pPos(el);
  });
}

// ---------- فاکتورها ----------
async function pSales(el) {
  render(el, h`<div class="card"><div class="row">${field('کانال', h`<select id="ch"><option value="">همه</option><option value="offline">حضوری</option><option value="online">آنلاین</option></select>`)}
    ${field('از (شمسی)', h`<input id="s" size="10" placeholder="۱۴۰۵/۰۷/۰۱">`)}${field('تا', h`<input id="e" size="10" placeholder="۱۴۰۵/۰۷/۳۰">`)}
    <button id="f">نمایش</button><a class="btn sec" id="x">Excel</a></div></div><div class="card" id="t"></div>`);
  const load = () => run(async () => {
    const qs = new URLSearchParams({ channel: $('#ch').value }); const s = faNum($('#s').value), e = faNum($('#e').value);
    if (s && e) { qs.set('start', s); qs.set('end', e); }
    $('#x').href = '/export/sales.xlsx?' + qs;
    const rows = await api('GET', '/api/sales?' + qs);
    $('#t').innerHTML = h`<table><tr><th>شماره</th><th>تاریخ</th><th>کانال</th><th>مشتری</th><th>مبلغ</th><th>سود</th><th></th></tr>
      ${rows.map(r => h`<tr><td>${r.number}</td><td>${r.jdate}</td><td><span class="badge ${r.channel === 'online' ? 'on' : 'off'}">${r.channel === 'online' ? 'آنلاین' : 'حضوری'}</span></td>
      <td>${[r.first_name, r.last_name, r.phone].filter(Boolean).join(' ')}</td><td>${money(r.total)}</td><td class="${profitCls(r.total - r.cogs)}">${money(r.total - r.cogs)}</td>
      <td><button class="sec" data-p="${r.id}">چاپ</button> <button class="bad" data-d="${r.id}">ابطال</button></td></tr>`)}</table>`.s;
    $('#t').querySelectorAll('[data-p]').forEach(b => b.onclick = () => showPrint('/print/invoice/' + b.dataset.p));
    $('#t').querySelectorAll('[data-d]').forEach(b => b.onclick = () => confirm('فاکتور باطل و موجودی برگردانده شود؟') &&
      run(async () => { await api('DELETE', '/api/sales/' + b.dataset.d); load(); }, 'باطل شد'));
  });
  $('#f').onclick = load; load();
}

// ---------- محصولات ----------
async function pProducts(el) {
  const sel = new Set();
  render(el, h`<div class="card"><div class="row"><input id="q" class="grow" placeholder="جست‌وجو..."><button id="add">+ محصول جدید</button>
    <button class="sec" id="bulk">تغییر گروهی قیمت</button><a class="btn sec" href="/export/products.xlsx">Excel</a>
    <button class="sec" id="prt">PDF</button></div><p class="mut">نرخ دلار فعلی: ${S.usd_rate ? money(S.usd_rate) + ' تومان' : 'تنظیم نشده'}</p><div id="t"></div></div>`);
  const load = () => run(async () => {
    const rows = await api('GET', '/api/products?q=' + encodeURIComponent($('#q').value));
    $('#t').innerHTML = h`<table><tr><th><input type="checkbox" id="all"></th><th></th><th>نام</th><th>کد</th><th>قیمت (تومان)</th><th>خرید</th><th>موجودی</th><th></th></tr>
      ${rows.map(p => h`<tr><td><input type="checkbox" data-s="${p.id}" ${sel.has(p.id) ? raw('checked') : ''}></td>
      <td><img class="thumb" data-img="${p.id}" style="cursor:pointer" ${p.image ? raw(`src="/img/${esc(p.image)}"`) : ''} title="تغییر تصویر"></td>
      <td>${p.name}${p.woo_id ? h` <span class="badge on">سایت</span>` : ''}</td><td>${p.sku}</td>
      <td>${money(p.price_toman)}${p.currency === 'USD' ? h` <small class="mut">($${p.price})</small>` : ''}</td><td>${money(p.cost_toman)}</td>
      <td class="${p.stock <= p.min_stock ? 'neg' : ''}">${p.stock}</td><td><button class="sec" data-e="${p.id}">ویرایش</button> <button class="bad" data-x="${p.id}">حذف</button></td></tr>`)}</table>`.s;
    const byId = id => rows.find(p => p.id == id);
    $('#all').onchange = e => { rows.forEach(p => e.target.checked ? sel.add(p.id) : sel.delete(p.id)); load(); };
    $('#t').querySelectorAll('[data-s]').forEach(c => c.onchange = () => c.checked ? sel.add(+c.dataset.s) : sel.delete(+c.dataset.s));
    $('#t').querySelectorAll('[data-e]').forEach(b => b.onclick = () => editProduct(byId(b.dataset.e), load));
    $('#t').querySelectorAll('[data-x]').forEach(b => b.onclick = () => confirm('محصول حذف شود؟') && run(async () => { await api('DELETE', '/api/products/' + b.dataset.x); load(); }));
    $('#t').querySelectorAll('[data-img]').forEach(i => i.onclick = () => pickImage(i.dataset.img, load));
  });
  $('#q').oninput = load; $('#add').onclick = () => editProduct(null, load); $('#prt').onclick = () => showPrint('/print/products');
  $('#bulk').onclick = () => bulkPrice([...sel], load); load();
}
function pickImage(id, done) {
  const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/jpeg,image/png,image/webp,image/gif';
  inp.onchange = () => { const f = inp.files[0]; if (!f) return; if (f.size > 3e6) return toast('حداکثر ۳ مگابایت', true);
    const r = new FileReader(); r.onload = () => run(async () => { await api('POST', `/api/products/${id}/image`, { data: r.result }); done(); }, 'تصویر ذخیره شد'); r.readAsDataURL(f); };
  inp.click();
}
function editProduct(p, done) {
  p = p || { name: '', sku: '', category: '', currency: 'IRT', price: 0, cost: 0, stock: 0, min_stock: 0 };
  const m = modal(h`<h3>${p.id ? 'ویرایش' : 'افزودن'} محصول</h3><div class="row">
    ${field('نام', h`<input id="n" value="${p.name}" class="grow">`)}${field('کد (SKU)', h`<input id="k" value="${p.sku}">`)}${field('دسته', h`<input id="c" value="${p.category}">`)}</div>
    <div class="row">${field('واحد قیمت', h`<select id="cur"><option value="IRT" ${p.currency === 'IRT' ? raw('selected') : ''}>تومان</option><option value="USD" ${p.currency === 'USD' ? raw('selected') : ''}>دلار</option></select>`)}
    ${field('قیمت فروش', h`<input id="pr" value="${p.price}">`)}${field('قیمت خرید', h`<input id="co" value="${p.cost}">`)}
    ${p.id ? '' : field('موجودی اولیه', h`<input id="st" value="0" size="6">`)}${field('حداقل موجودی', h`<input id="ms" value="${p.min_stock}" size="6">`)}</div>
    <p><button id="ok">ذخیره</button> <button class="sec" data-close>انصراف</button></p>`);
  $('#ok', m.box).onclick = () => run(async () => {
    const v = id => faNum($('#' + id, m.box)?.value ?? 0);
    const body = { name: $('#n', m.box).value, sku: $('#k', m.box).value, category: $('#c', m.box).value, currency: $('#cur', m.box).value,
      price: v('pr'), cost: v('co'), stock: v('st'), min_stock: v('ms') };
    p.id ? await api('PUT', '/api/products/' + p.id, body) : await api('POST', '/api/products', body); m.close(); done();
  }, 'ذخیره شد');
}
function bulkPrice(ids, done) {
  const m = modal(h`<h3>تغییر گروهی قیمت</h3><div class="row">
    ${field('محصولات', h`<select id="sc"><option value="all">همهٔ محصولات</option><option value="ids" ${ids.length ? raw('selected') : ''}>انتخاب‌شده‌ها (${ids.length})</option><option value="category">یک دسته</option></select>`)}
    ${field('دسته', h`<input id="cat">`)}${field('اعمال روی', h`<select id="tg"><option value="price">قیمت فروش</option><option value="cost">قیمت خرید</option></select>`)}</div>
    <div class="row">${field('روش', h`<select id="md"><option value="percent">درصد (منفی = کاهش)</option><option value="amount">مبلغ ثابت اضافه/کم</option><option value="set">تعیین مقدار ثابت</option></select>`)}
    ${field('مقدار', h`<input id="vl" value="10" size="10">`)}${field('رُند به', h`<select id="rd"><option value="0">بدون رُند</option><option value="100">۱۰۰ تومان</option><option value="1000" selected>۱۰۰۰ تومان</option><option value="10000">۱۰ هزار تومان</option></select>`)}</div>
    <p class="mut">مبلغ ثابت برای محصولات دلاری بر حسب دلار است. محصولات متصل به سایت برای «ارسال به سایت» علامت می‌خورند.</p>
    <p><button id="ok">اعمال</button> <button class="sec" data-close>انصراف</button></p>`);
  $('#ok', m.box).onclick = () => run(async () => {
    const r = await api('POST', '/api/products/bulk-price', { scope: $('#sc', m.box).value, ids, category: $('#cat', m.box).value,
      target: $('#tg', m.box).value, mode: $('#md', m.box).value, value: faNum($('#vl', m.box).value), rounding: $('#rd', m.box).value });
    m.close(); toast(`${r.changed} محصول تغییر کرد`); done();
  });
}

// ---------- انبار ----------
async function pInventory(el) {
  const [rows, moves] = await Promise.all([api('GET', '/api/products'), api('GET', '/api/stock-moves')]);
  const REASON = { sale: 'فروش', return: 'برگشت', adjust: 'اصلاح', purchase: 'خرید/ورود', initial: 'اولیه', woo_sync: 'همگام‌سازی سایت' };
  render(el, h`<div class="card"><table><tr><th>کالا</th><th>موجودی</th><th>حداقل</th><th>تغییر موجودی</th></tr>
    ${rows.map(p => h`<tr><td>${p.name}</td><td class="${p.stock <= p.min_stock ? 'neg' : ''}">${p.stock}</td><td>${p.min_stock}</td>
    <td><input size="5" placeholder="±تعداد" data-q="${p.id}"> <button class="sec" data-in="${p.id}">ثبت</button></td></tr>`)}</table></div>
    <div class="card"><h3>تاریخچه</h3><table><tr><th>کالا</th><th>تعداد</th><th>علت</th><th>یادداشت</th></tr>
    ${moves.slice(0, 80).map(m => h`<tr><td>${m.name}</td><td class="${profitCls(m.qty)}" dir="ltr">${m.qty}</td><td>${REASON[m.reason] || m.reason} ${m.ref}</td><td>${m.note}</td></tr>`)}</table></div>`);
  el.querySelectorAll('[data-in]').forEach(b => b.onclick = () => run(async () => {
    const q = faNum($(`[data-q="${b.dataset.in}"]`).value); if (!q) return toast('تعداد را وارد کنید', true);
    await api('POST', `/api/products/${b.dataset.in}/stock`, { qty: q, reason: +q > 0 ? 'purchase' : 'adjust' }); pInventory(el);
  }, 'ثبت شد'));
}

// ---------- مشتریان ----------
async function pCustomers(el) {
  render(el, h`<div class="card"><div class="row"><input id="q" class="grow" placeholder="جست‌وجو (نام/موبایل)"><button id="add">+ مشتری</button><a class="btn sec" href="/export/customers.xlsx">Excel</a></div><div id="t"></div></div>`);
  const load = () => run(async () => {
    const rows = await api('GET', '/api/customers?q=' + encodeURIComponent($('#q').value));
    $('#t').innerHTML = h`<table><tr><th>نام</th><th>موبایل</th><th>تعداد خرید</th><th>جمع خرید</th><th>خوش‌آمد</th></tr>
      ${rows.map(c => h`<tr><td>${c.first_name} ${c.last_name}</td><td dir="ltr">${c.phone}</td><td>${c.orders}</td><td>${money(c.spent)}</td><td>${c.welcomed ? '✓' : ''}</td></tr>`)}</table>`.s;
  });
  $('#q').oninput = load; load();
  $('#add').onclick = () => { const m = modal(h`<h3>مشتری جدید</h3><div class="row">${field('موبایل', h`<input id="p" placeholder="09...">`)}${field('نام', h`<input id="f">`)}${field('نام خانوادگی', h`<input id="l">`)}</div>
    <p><button id="ok">ثبت</button> <button class="sec" data-close>انصراف</button></p>`);
    $('#ok', m.box).onclick = () => run(async () => { await api('POST', '/api/customers', { phone: $('#p', m.box).value, first_name: $('#f', m.box).value, last_name: $('#l', m.box).value }); m.close(); load(); }, 'ثبت شد'); };
}

// ---------- گزارش‌ها ----------
async function pReports(el) {
  render(el, h`<div class="card"><div class="row"><button data-k="day">امروز</button><button data-k="week">این هفته</button><button data-k="month">این ماه</button>
    ${field('از', h`<input id="s" size="10" value="${todayJ()}">`)}${field('تا', h`<input id="e" size="10" value="${todayJ()}">`)}
    ${field('گروه‌بندی', h`<select id="pd"><option value="day">روزانه</option><option value="week">هفتگی</option><option value="month">ماهانه</option></select>`)}
    ${field('کانال', h`<select id="ch"><option value="">همه</option><option value="offline">حضوری</option><option value="online">آنلاین</option></select>`)}
    <button class="sec" id="go">نمایش</button><a class="btn sec" id="x">Excel</a><button class="sec" id="pdf">PDF</button></div></div><div id="r"></div>`);
  const qs = k => { const q = new URLSearchParams({ channel: $('#ch').value });
    k ? q.set('kind', k) : (q.set('start', faNum($('#s').value)), q.set('end', faNum($('#e').value)), q.set('period', $('#pd').value)); return q; };
  const load = k => run(async () => {
    const q = qs(k); const r = await api('GET', '/api/report?' + q); const t = r.totals;
    $('#x').href = '/export/report.xlsx?' + q; $('#pdf').onclick = () => showPrint('/print/report?' + q);
    const max = Math.max(1, ...r.series.map(s => s.revenue));
    $('#r').innerHTML = h`<div class="grid"><div class="card stat"><small>فروش (${r.start} تا ${r.end})</small><b>${money(t.revenue)}</b><small>${t.count} فاکتور</small></div>
      <div class="card stat"><small>سود ناخالص</small><b>${money(t.gross_profit)}</b></div><div class="card stat"><small>هزینه‌ها</small><b>${money(t.expenses)}</b></div>
      <div class="card stat"><small>${t.net_profit < 0 ? 'زیان' : 'سود'} خالص</small><b class="${profitCls(t.net_profit)}">${money(Math.abs(t.net_profit))}</b></div></div>
      <div class="card"><h3>حضوری در برابر آنلاین</h3><table><tr><th>کانال</th><th>تعداد</th><th>فروش</th><th>سود ناخالص</th></tr>
      ${Object.entries(r.by_channel).map(([k, v]) => h`<tr><td>${k === 'online' ? 'آنلاین' : 'حضوری'}</td><td>${v.count}</td><td>${money(v.revenue)}</td><td>${money(v.profit)}</td></tr>`)}</table></div>
      <div class="card"><h3>روند</h3><table><tr><th>دوره</th><th>تعداد</th><th>فروش</th><th></th><th>سود پس از هزینه</th></tr>
      ${r.series.map(s => h`<tr><td>${s.label}</td><td>${s.count}</td><td>${money(s.revenue)}</td><td style="width:30%"><div class="bar" style="width:${Math.round(100 * s.revenue / max)}%"></div></td><td class="${profitCls(s.profit)}">${money(s.profit)}</td></tr>`)}</table></div>
      <div class="card"><h3>پرفروش‌ترین محصولات</h3><table><tr><th>کالا</th><th>تعداد</th><th>فروش</th><th>سود</th></tr>
      ${r.top_products.map(p => h`<tr><td>${p.name}</td><td>${p.qty}</td><td>${money(p.revenue)}</td><td>${money(p.profit)}</td></tr>`)}</table></div>`.s;
  });
  el.querySelectorAll('[data-k]').forEach(b => b.onclick = () => load(b.dataset.k)); $('#go').onclick = () => load(); load('day');
}

// ---------- هزینه‌ها ----------
async function pExpenses(el) {
  const rows = await api('GET', '/api/expenses');
  render(el, h`<div class="card"><div class="row">${field('عنوان', h`<input id="t" class="grow">`)}${field('مبلغ (تومان)', h`<input id="a" size="12">`)}<button id="ok">ثبت هزینه</button></div></div>
    <div class="card"><table><tr><th>تاریخ</th><th>عنوان</th><th>مبلغ</th><th></th></tr>${rows.map(x => h`<tr><td>${x.jdate}</td><td>${x.title}</td><td>${money(x.amount)}</td><td><button class="bad" data-x="${x.id}">حذف</button></td></tr>`)}</table></div>`);
  $('#ok').onclick = () => run(async () => { await api('POST', '/api/expenses', { title: $('#t').value, amount: faNum($('#a').value) }); pExpenses(el); }, 'ثبت شد');
  el.querySelectorAll('[data-x]').forEach(b => b.onclick = () => run(async () => { await api('DELETE', '/api/expenses/' + b.dataset.x); pExpenses(el); }));
}

// ---------- ووکامرس ----------
async function pWoo(el) {
  render(el, h`<div class="card"><p>ابتدا آدرس و کلیدهای API را در <a href="#settings">تنظیمات</a> وارد کنید.</p>
    <div class="row"><button id="p1">⬇ دریافت محصولات از سایت</button><label><input type="checkbox" id="us"> موجودی هم از سایت بیاید</label></div><br>
    <div class="row"><button id="p2">⬆ ارسال تغییرات (قیمت/موجودی/محصول جدید) به سایت</button><label><input type="checkbox" id="all"> همهٔ محصولات</label></div><br>
    <button id="p3">⬇ دریافت سفارش‌های آنلاین</button></div><div class="card" id="out" class="mut"></div>`);
  const act = (id, fn) => $(id).onclick = () => run(async () => { $('#out').textContent = 'در حال انجام...'; const r = await fn(); $('#out').textContent = JSON.stringify(r); toast('انجام شد'); });
  act('#p1', () => api('POST', '/api/woo/pull-products', { update_stock: $('#us').checked }));
  act('#p2', () => api('POST', '/api/woo/push-products', { all: $('#all').checked }));
  act('#p3', () => api('POST', '/api/woo/pull-orders', {}));
}

// ---------- تنظیمات ----------
async function pSettings(el) {
  const s = await api('GET', '/api/settings');
  const inp = (k, label, extra = '') => field(label, h`<input data-k="${k}" value="${s[k]}" ${raw(extra)} style="width:100%">`);
  const sw = (k, label) => h`<label style="display:flex;gap:6px;align-items:center;color:var(--ink)"><input type="checkbox" data-k="${k}" ${s[k] === '1' ? raw('checked') : ''}> ${label}</label>`;
  const sel = (k, label, opts) => field(label, h`<select data-k="${k}">${opts.map(([v, t]) => h`<option value="${v}" ${s[k] === v ? raw('selected') : ''}>${t}</option>`)}</select>`);
  render(el, h`<div class="card"><h3>فروشگاه و ارز</h3><div class="grid">${inp('shop_name', 'نام فروشگاه')}${inp('shop_phone', 'تلفن')}${inp('shop_address', 'آدرس')}
    ${inp('invoice_footer', 'متن پایین فاکتور')}${inp('usd_rate', 'نرخ دلار (تومان)')}</div>${sw('allow_negative_stock', 'اجازهٔ فروش با موجودی صفر')}</div>
    <div class="card"><h3>ووکامرس</h3><div class="grid">${inp('woo_url', 'آدرس سایت (https://...)')}${inp('woo_key', 'Consumer Key', 'type="password" autocomplete="off"')}
    ${inp('woo_secret', 'Consumer Secret', 'type="password" autocomplete="off"')}${sel('woo_unit', 'واحد قیمت سایت', [['toman', 'تومان'], ['rial', 'ریال']])}</div>
    ${sw('woo_orders_decrement', 'با دریافت سفارش آنلاین، موجودی برنامه کم شود')}</div>
    <div class="card"><h3>پیامک خوش‌آمدگویی</h3>${sw('welcome_enabled', 'ارسال پیام به مشتری جدید')}<div class="grid">
    ${sel('sms_provider', 'پنل', [['none', 'غیرفعال'], ['kavenegar', 'کاوه‌نگار'], ['custom', 'سفارشی (URL)']])}${inp('sms_apikey', 'کلید API', 'type="password" autocomplete="off"')}${inp('sms_sender', 'شمارهٔ فرستنده')}
    ${inp('sms_url', 'آدرس سفارشی (https://..?to={to}&text={text}&key={key})')}${sel('sms_method', 'روش', [['GET', 'GET'], ['POST', 'POST (آدرس|بدنه)']])}</div>
    ${field('متن پیام ({name} و {shop})', h`<textarea data-k="welcome_text" rows="2" style="width:100%">${s.welcome_text}</textarea>`)}
    <div class="row"><input id="tp" placeholder="موبایل آزمایشی"><button class="sec" id="tst">ارسال آزمایشی</button></div></div>
    <button id="save">ذخیره تنظیمات</button>
    <div class="card" style="margin-top:14px"><h3>تغییر رمز</h3><div class="row"><input id="po" type="password" placeholder="رمز فعلی"><input id="pn" type="password" placeholder="رمز جدید"><button class="sec" id="pc">تغییر</button></div></div>`);
  $('#save').onclick = () => run(async () => {
    const b = {}; el.querySelectorAll('[data-k]').forEach(i => b[i.dataset.k] = i.type === 'checkbox' ? (i.checked ? '1' : '0') : i.value);
    await api('PUT', '/api/settings', b); S = await (await fetch('/api/state')).json(); csrf = S.csrf;
  }, 'ذخیره شد');
  $('#tst').onclick = () => run(async () => { const r = await api('POST', '/api/sms/test', { phone: $('#tp').value }); toast(r.ok ? 'ارسال شد' : 'ناموفق: ' + r.detail, !r.ok); });
  $('#pc').onclick = () => run(() => api('POST', '/api/password', { old: $('#po').value, new: $('#pn').value }), 'رمز تغییر کرد');
}

// ---------- لایسنس ----------
async function pLicense(el) {
  S = await (await fetch('/api/state')).json(); csrf = S.csrf; const L = S.license;
  const cur = L.mode === 'licensed' ? h`<div class="banner" style="background:#dcfce7;color:#166534">لایسنس فعال: ${L.plans[L.plan].title} — ${L.expires ? 'تا ' + L.expires : 'بدون انقضا'}</div>` : '';
  render(el, h`${cur}<div class="card"><p>شناسهٔ دستگاه شما: <b dir="ltr">${L.machine_id}</b></p>
    <div class="plans">${Object.entries(L.plans).map(([k, p]) => h`<div class="plan"><div>${p.title}</div><b>${money(p.price)}</b><small class="mut">تومان</small><br><br>
    <button data-buy="${k}">پرداخت در وبیکری</button></div>`)}</div></div>
    <div class="card"><h3>فعال‌سازی</h3>${field('کد لایسنس', h`<textarea id="k" rows="3" style="width:100%" dir="ltr"></textarea>`)}<button id="act">فعال‌سازی</button>
    <hr><div class="row">${field('یا کد سفارش وبیکری', h`<input id="od" dir="ltr">`)}<button class="sec" id="ord">دریافت خودکار لایسنس</button></div></div>`);
  el.querySelectorAll('[data-buy]').forEach(b => b.onclick = () => run(async () => {
    const r = await api('GET', '/api/license/buy-url?plan=' + b.dataset.buy); window.open(r.url, '_blank', 'noopener');
  }));
  const done = async () => { S = await (await fetch('/api/state')).json(); go('license'); };
  $('#act').onclick = () => run(async () => { await api('POST', '/api/license', { key: $('#k').value }); await done(); }, 'لایسنس فعال شد');
  $('#ord').onclick = () => run(async () => { await api('POST', '/api/license/order', { order: $('#od').value }); await done(); }, 'لایسنس فعال شد');
}

boot();
