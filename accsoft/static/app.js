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
function authBox(title, extra, btn, fn, setup) {
  $('#app').innerHTML = h`<div class="center card"><h2>${title}</h2>${extra}
    ${field('نام کاربری', h`<input id="u" autocomplete="${setup ? 'off' : 'username'}" style="width:100%">`)}
    ${field('رمز عبور', h`<input id="p" type="password" autocomplete="${setup ? 'new-password' : 'current-password'}" style="width:100%">`)}
    <p><button id="go">${btn}</button></p></div>`.s;
  $('#go').onclick = () => run(async () => { await fn($('#u').value, $('#p').value); await boot(); });
  $('#p').onkeydown = e => { if (e.key === 'Enter') $('#go').click(); };
}
const loginView = () => {
  authBox('ورود', '', 'ورود', (u, p) => api('POST', '/api/login', { username: u, password: p }));
  $('.center').insertAdjacentHTML('beforeend', '<p><a id="fg" style="cursor:pointer;color:var(--pri)">رمز عبور را فراموش کرده‌ام</a></p>');
  $('#fg').onclick = () => { S.account_required ? forgotView() : resetView(); };
};
function forgotView() {
  $('#app').innerHTML = h`<div class="center card"><h2>فراموشی رمز</h2>
    <p><b>روش پیشنهادی:</b> رمز را در سایت webakery.ir بازیابی کنید (لینک به ایمیل شما می‌آید). بعد همین‌جا با رمز جدید وارد شوید؛ برنامه رمز را خودش همگام می‌کند (اینترنت لازم است).</p>
    <p><button id="fs">باز کردن صفحهٔ بازیابی رمز در سایت</button></p>
    <p class="mut">اگر اینترنت ندارید یا حساب سایت ندارید:</p><p><button class="sec" id="fl">بازیابی با کد روی همین کامپیوتر</button> <button class="sec" id="fb">بازگشت</button></p></div>`.s;
  $('#fs').onclick = () => run(() => api('POST', '/api/open-url', { to: 'forgot' }), 'صفحهٔ بازیابی در مرورگر باز شد');
  $('#fl').onclick = resetView; $('#fb').onclick = loginView;
}
function resetView() {
  $('#app').innerHTML = h`<div class="center card"><h2>بازیابی رمز عبور</h2>
    <p class="mut">۱) «ساخت کد» را بزنید تا یک فایل کد در پوشهٔ داده‌های برنامه ساخته شود (فقط کسی که به این کامپیوتر دسترسی دارد می‌تواند آن را بخواند).</p>
    <p><button id="rq">۱) ساخت کد بازیابی</button></p><div id="rinfo" class="mut"></div>
    ${field('نام کاربری (خالی = مدیر اصلی)', h`<input id="ru" style="width:100%">`)}${field('کد بازیابی', h`<input id="rc" style="width:100%;direction:ltr" autocomplete="off">`)}
    ${field('رمز جدید (حداقل ۸ نویسه)', h`<input id="rp" type="password" style="width:100%" autocomplete="new-password">`)}
    <p><button id="rg">۲) تغییر رمز</button> <button class="sec" id="rb">بازگشت</button></p></div>`.s;
  $('#rq').onclick = () => run(async () => { const r = await api('POST', '/api/reset/request', {});
    $('#rinfo').innerHTML = h`فایل را باز کنید و کد را بخوانید:<br><b dir="ltr">${r.path}</b>`.s; });
  $('#rg').onclick = () => run(async () => { await api('POST', '/api/reset/confirm', { username: $('#ru').value, code: $('#rc').value, password: $('#rp').value }); toast('رمز تغییر کرد؛ وارد شوید'); loginView(); });
  $('#rb').onclick = loginView;
}
function setupView() {
  if (!S.account_required) {
    authBox('نصب اولیه', field('نام فروشگاه', h`<input id="shop" style="width:100%">`), 'ایجاد حساب مدیر',
      (u, p) => api('POST', '/api/setup', { username: u, password: p, shop_name: $('#shop').value }));
    $('.center').insertAdjacentHTML('beforeend', '<p class="mut">رمز حداقل ۸ نویسه. آن را فراموش نکنید؛ بازیابی ندارد.</p>');
    return;
  }
  let mode = 'login';
  const draw = () => {
    $('#app').innerHTML = h`<div class="center card"><h2>به دفترچی خوش آمدید</h2>
      <p class="mut">برای استفاده از برنامه به یک حساب در webakery.ir نیاز دارید. اگر حساب دارید وارد شوید، وگرنه همین‌جا بسازید (به اینترنت نیاز است).</p>
      <div class="row"><button class="${mode === 'login' ? '' : 'sec'}" id="m1">ورود با حساب</button><button class="${mode === 'register' ? '' : 'sec'}" id="m2">ساخت حساب جدید</button></div>
      ${mode === 'register' ? field('نام شما', h`<input id="nm" style="width:100%">`) : ''}
      ${field('نام فروشگاه', h`<input id="shop" style="width:100%">`)}
      ${field('ایمیل', h`<input id="em" type="email" style="width:100%;direction:ltr" autocomplete="username">`)}
      ${field(mode === 'register' ? 'رمز عبور (حداقل ۸ نویسه)' : 'رمز عبور', h`<input id="pw" type="password" style="width:100%" autocomplete="${mode === 'register' ? 'new-password' : 'current-password'}">`)}
      <p><button id="go">${mode === 'register' ? 'ساخت حساب و ادامه' : 'ورود و ادامه'}</button></p>
      <p><a id="fg" style="cursor:pointer;color:var(--pri)">رمز عبور را فراموش کرده‌ام (بازیابی از سایت)</a></p></div>`.s;
    $('#m1').onclick = () => { mode = 'login'; draw(); }; $('#m2').onclick = () => { mode = 'register'; draw(); };
    $('#fg').onclick = () => run(() => api('POST', '/api/open-url', { to: 'forgot' }), 'صفحهٔ بازیابی رمز در مرورگر باز شد');
    $('#pw').onkeydown = e => { if (e.key === 'Enter') $('#go').click(); };
    $('#go').onclick = () => run(async () => {
      await api('POST', '/api/setup', { mode, email: $('#em').value, password: $('#pw').value, name: $('#nm')?.value || '', shop_name: $('#shop').value }); await boot(); });
  };
  draw();
}

// ---------- چارچوب ----------
const PAGES = { dashboard: ['داشبورد', pDashboard, 'reports'], pos: ['فروش حضوری', pPos, 'sell'], sales: ['فاکتورها', pSales, 'sales_view'],
  products: ['محصولات', pProducts, 'products_view'], inventory: ['انبار', pInventory, 'inventory'], customers: ['مشتریان', pCustomers, 'customers'],
  purchases: ['خرید و تأمین‌کنندگان', pPurchases, 'purchases'], accounts: ['حساب‌ها (بدهکار/بستانکار)', pAccounts, 'finance'],
  reports: ['گزارش‌ها', pReports, 'reports'], expenses: ['هزینه‌ها', pExpenses, 'finance'], woo: ['ووکامرس', pWoo, 'woo'],
  users: ['کاربران', pUsers, 'users'], settings: ['تنظیمات', pSettings, 'settings'], license: ['لایسنس و افزونه‌ها', pLicense, 'settings'] };
const can = p => S.user && S.user.perms.includes(p);
const visiblePages = () => Object.entries(PAGES).filter(([, v]) => can(v[2]));
function go(page) {
  const plug = page.startsWith('plugin:') ? S.plugins.find(p => p.id === page.slice(7) && p.menu) : null;
  if (!plug && !(PAGES[page] && can(PAGES[page][2]))) page = (visiblePages()[0] || ['license'])[0];
  location.hash = page;
  const L = S.license, [title, fn] = plug ? [plug.menu.title, el => { el.innerHTML = ''; const f = document.createElement('iframe');
    f.src = `/plugin/${plug.id}/${plug.menu.page}`; f.style.cssText = 'width:100%;height:78vh;border:0;background:#fff'; el.append(f); }] : PAGES[page];
  const unlinked = S.account_required && !S.user.account ? h`<div class="banner">حساب webakery.ir به این کاربر متصل نیست (برای بازیابی رمز و لایسنس لازم است). <a href="#settings" style="color:inherit">اتصال حساب</a></div>` : '';
  const banner = L.mode === 'trial' ? h`<div class="banner">دورهٔ آزمایشی: ${L.days_left} روز باقی مانده. <a href="#license" style="color:inherit">تهیهٔ لایسنس</a></div>`
    : L.mode === 'expired' ? h`<div class="banner bad">${L.tampered ? 'ساعت سیستم دستکاری شده است.' : (L.license_error || 'لایسنس معتبر نیست.')} فقط مشاهده و خروجی فعال است. <a href="#license" style="color:inherit">تهیهٔ لایسنس</a></div>` : '';
  const menu = [...visiblePages().map(([k, [t]]) => [k, t]), ...S.plugins.filter(p => p.menu).map(p => ['plugin:' + p.id, p.menu.title])];
  $('#app').innerHTML = h`<div class="layout"><nav class="side"><h1>${S.shop_name || 'دفترچی'}</h1>
    ${menu.map(([k, t]) => h`<a data-p="${k}" class="${k === page ? 'on' : ''}">${t}</a>`)}
    <a id="out">خروج (${S.user.username})</a></nav><main class="main">${unlinked}${banner}<div class="top"><h2>${title}</h2>
    ${HELP[page] ? h`<button class="sec" id="hlp">؟ راهنما</button>` : ''}</div><div id="page"></div></main></div>`.s;
  document.querySelectorAll('.side a[data-p]').forEach(a => a.onclick = () => go(a.dataset.p));
  $('#out').onclick = async () => { await api('POST', '/api/logout', {}); boot(); };
  if (HELP[page]) $('#hlp').onclick = () => showHelp(page);
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
    <div class="card stat"><small>کمبود موجودی</small><b class="${d.low_stock ? 'neg' : ''}">${d.low_stock}</b></div>
    <div class="card stat"><small>مطالبات از مشتریان</small><b>${money(d.receivable)}</b></div>
    <div class="card stat"><small>بدهی به تأمین‌کنندگان</small><b class="${d.payable ? 'neg' : ''}">${money(d.payable)}</b></div></div>`);
}

// ---------- فروش حضوری ----------
let cart = [];
async function pPos(el) {
  const products = await api('GET', '/api/products?sellable=1');
  render(el, h`<div class="pos"><div class="card"><input id="q" placeholder="جست‌وجوی نام یا کد..." style="width:100%" autofocus>
    <div class="plist" id="pl"></div></div>
    <div class="card"><table id="ct"></table>
    <div class="row">${field('تخفیف (تومان)', h`<input id="disc" value="0" size="10">`)}
      ${field('پرداخت', h`<select id="pm"><option value="cash">نقد</option><option value="card">کارت</option><option value="credit">اعتباری (نسیه)</option></select>`)}
      ${field('پیش‌پرداخت (برای نسیه)', h`<input id="paid" value="0" size="10">`)}</div>
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
      discount: parseInt(faNum($('#disc').value)) || 0, pay_method: $('#pm').value, paid: parseInt(faNum($('#paid').value)) || 0,
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
      <td>${p.kind === 'variable' ? '' : h`<img class="thumb" data-img="${p.id}" style="cursor:pointer" ${p.image ? raw(`src="/img/${esc(p.image)}"`) : ''} title="تغییر تصویر">`}</td>
      <td style="${p.kind === 'variation' ? 'padding-right:26px' : ''}">${p.kind === 'variation' ? '↳ ' : ''}${p.name}${p.woo_id ? h` <span class="badge on">سایت</span>` : ''}${p.kind === 'variable' ? h` <span class="badge off">متغیر</span>` : ''}</td><td>${p.sku}</td>
      <td>${p.kind === 'variable' ? '' : money(p.price_toman)}${p.currency === 'USD' && p.kind !== 'variable' ? h` <small class="mut">($${p.price})</small>` : ''}</td><td>${p.kind === 'variable' ? '' : money(p.cost_toman)}</td>
      <td class="${p.stock <= p.min_stock && p.kind !== 'variable' ? 'neg' : ''}">${p.kind === 'variable' ? '—' : p.stock}</td><td><button class="sec" data-e="${p.id}">ویرایش</button> <button class="bad" data-x="${p.id}">حذف</button></td></tr>`)}</table>`.s;
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
  const [rows, moves] = await Promise.all([api('GET', '/api/products?sellable=1'), api('GET', '/api/stock-moves')]);
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
    $('#t').innerHTML = h`<table><tr><th>نام</th><th>موبایل</th><th>تعداد خرید</th><th>جمع خرید</th><th>مانده بدهی</th><th>خوش‌آمد</th></tr>
      ${rows.map(c => h`<tr><td>${c.first_name} ${c.last_name}</td><td dir="ltr">${c.phone}</td><td>${c.orders}</td><td>${money(c.spent)}</td><td class="${c.balance > 0 ? 'neg' : ''}">${money(c.balance)}</td><td>${c.welcomed ? '✓' : ''}</td></tr>`)}</table>`.s;
  });
  $('#q').oninput = load; load();
  $('#add').onclick = () => { const m = modal(h`<h3>مشتری جدید</h3><div class="row">${field('موبایل', h`<input id="p" placeholder="09...">`)}${field('نام', h`<input id="f">`)}${field('نام خانوادگی', h`<input id="l">`)}</div>
    <p><button id="ok">ثبت</button> <button class="sec" data-close>انصراف</button></p>`);
    $('#ok', m.box).onclick = () => run(async () => { await api('POST', '/api/customers', { phone: $('#p', m.box).value, first_name: $('#f', m.box).value, last_name: $('#l', m.box).value }); m.close(); load(); }, 'ثبت شد'); };
}

// ---------- گزارش‌ها ----------
const JM = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
const short = n => { const a = Math.abs(n), f = x => x.toLocaleString('fa-IR', { maximumFractionDigits: 1 });
  return (n < 0 ? '-' : '') + (a >= 1e9 ? f(a / 1e9) + ' م‌ر' : a >= 1e6 ? f(a / 1e6) + ' م' : a >= 1e3 ? f(a / 1e3) + ' هـ' : f(a)); };
// نمودار میله‌ای دوتایی (فروش و سود)؛ ماه اول سمت راست (RTL)
function barChart(rows) {
  const W = 760, H = 270, L = 8, R = 48, T = 14, B = 34, n = rows.length || 1;
  const hi = Math.max(1, ...rows.map(r => Math.max(r.revenue, r.profit))), lo = Math.min(0, ...rows.map(r => r.profit));
  const span = hi - lo, y = v => T + (H - T - B) * (1 - (v - lo) / span), step = (W - L - R) / n, bw = Math.max(4, Math.min(22, step / 2.6));
  const grid = [0, .25, .5, .75, 1].map(f => { const v = lo + span * f; return `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${W - R + 6}" y="${y(v) + 4}" font-size="10" fill="var(--mut)">${esc(short(v))}</text>`; }).join('');
  const bars = rows.map((r, i) => { const cx = W - R - step * (i + .5), z = y(0);
    const bar = (x, v, col) => `<rect x="${x}" y="${Math.min(y(v), z)}" width="${bw}" height="${Math.max(1, Math.abs(y(v) - z))}" rx="3" fill="${col}"/>`;
    return `<g><title>${esc(r.label)}\nفروش: ${money(r.revenue)}\nسود: ${money(r.profit)}</title>${bar(cx - bw - 1, r.revenue, 'var(--pri)')}${bar(cx + 1, r.profit, r.profit < 0 ? 'var(--bad)' : 'var(--ok)')}
      <text x="${cx}" y="${H - 14}" text-anchor="middle" font-size="${n > 14 ? 8 : 10}" fill="var(--mut)">${esc(r.short || r.label)}</text></g>`; }).join('');
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto" role="img" aria-label="نمودار فروش و سود">${grid}${bars}</svg>
    <div class="mut" style="font-size:12px"><span style="color:var(--pri)">■</span> فروش &nbsp; <span style="color:var(--ok)">■</span> سود پس از هزینه &nbsp; <span style="color:var(--bad)">■</span> زیان</div>`;
}
function donut(parts) {
  const tot = parts.reduce((a, p) => a + p.v, 0), r = 52, c = 2 * Math.PI * r; let off = 0;
  const arcs = tot ? parts.map(p => { const len = c * p.v / tot, o = `<circle r="${r}" cx="70" cy="70" fill="none" stroke="${p.col}" stroke-width="22" stroke-dasharray="${len} ${c - len}" stroke-dashoffset="${-off}" transform="rotate(-90 70 70)"><title>${esc(p.t)}: ${money(p.v)}</title></circle>`; off += len; return o; }).join('')
    : `<circle r="${r}" cx="70" cy="70" fill="none" stroke="var(--line)" stroke-width="22"/>`;
  return `<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap"><svg viewBox="0 0 140 140" width="150" role="img" aria-label="سهم کانال‌ها">${arcs}<text x="70" y="74" text-anchor="middle" font-size="14" fill="var(--ink)">${tot ? '' : '—'}</text></svg>
    <div>${parts.map(p => `<div style="margin:6px 0"><span style="color:${p.col}">●</span> ${esc(p.t)}: <b>${money(p.v)}</b> <span class="mut">(${tot ? Math.round(100 * p.v / tot).toLocaleString('fa-IR') : '۰'}٪)</span></div>`).join('')}</div></div>`;
}
const hbars = (rows, key) => { const m = Math.max(1, ...rows.map(r => r[key])); return rows.map(r => `<div style="margin:7px 0"><div style="display:flex;justify-content:space-between;gap:8px"><span>${esc(r.name)}</span><b>${money(r[key])}</b></div>
  <div style="background:var(--line);border-radius:5px;height:9px"><div style="width:${Math.max(2, Math.round(100 * r[key] / m))}%;background:var(--pri);height:9px;border-radius:5px"></div></div></div>`).join(''); };

async function pReports(el) {
  const jy0 = +S.today.split('/')[0]; let year = jy0, mode = 'year';
  render(el, h`<div class="card"><div class="row">
    <button class="sec" data-m="year" id="my">📅 سالانه / ماهانه</button><button class="sec" data-m="range" id="mr">📆 بازهٔ دلخواه</button>
    <span id="yr" class="row"><button class="sec" id="py">◀</button><b id="yl" style="min-width:60px;text-align:center"></b><button class="sec" id="ny">▶</button></span>
    <span id="rg" class="row" style="display:none">${field('از', h`<input id="s" size="10" value="${todayJ()}">`)}${field('تا', h`<input id="e" size="10" value="${todayJ()}">`)}
    ${field('گروه‌بندی', h`<select id="pd"><option value="day">روزانه</option><option value="week">هفتگی</option><option value="month">ماهانه</option></select>`)}
    <button class="sec" data-k="day">امروز</button><button class="sec" data-k="week">این هفته</button><button class="sec" data-k="month">این ماه</button></span>
    ${field('کانال', h`<select id="ch"><option value="">همه</option><option value="offline">حضوری</option><option value="online">آنلاین</option></select>`)}
    <button id="go">نمایش</button><a class="btn sec" id="x">Excel</a><button class="sec" id="pdf">PDF</button></div></div><div id="r"></div>`);
  const qs = k => { const q = new URLSearchParams({ channel: $('#ch').value });
    if (mode === 'year') { q.set('kind', 'year'); q.set('year', year); }
    else if (k) q.set('kind', k); else { q.set('start', faNum($('#s').value)); q.set('end', faNum($('#e').value)); q.set('period', $('#pd').value); }
    return q; };
  const load = k => run(async () => {
    $('#yl').textContent = year.toLocaleString('fa-IR', { useGrouping: false });
    $('#yr').style.display = mode === 'year' ? '' : 'none'; $('#rg').style.display = mode === 'year' ? 'none' : '';
    $('#my').className = mode === 'year' ? '' : 'sec'; $('#mr').className = mode === 'range' ? '' : 'sec';
    const q = qs(k); const r = await api('GET', '/api/report?' + q); const t = r.totals;
    $('#x').href = '/export/report.xlsx?' + q; $('#pdf').onclick = () => showPrint('/print/report?' + q);
    let rows = r.series.map(s => ({ ...s, gross: s.profit + s.expenses }));
    if (mode === 'year') rows = JM.map((nm, i) => { const k2 = `${year}/${String(i + 1).padStart(2, '0')}`, f = r.series.find(s => s.label === k2) || { count: 0, revenue: 0, profit: 0, expenses: 0 };
      return { ...f, label: nm, short: nm, month: i + 1, gross: f.profit + f.expenses }; });
    const ch = Object.entries(r.by_channel);
    $('#r').innerHTML = h`<div class="grid"><div class="card stat"><small>فروش (${r.start} تا ${r.end})</small><b>${money(t.revenue)}</b><small>${t.count.toLocaleString('fa-IR')} فاکتور</small></div>
      <div class="card stat"><small>سود ناخالص</small><b>${money(t.gross_profit)}</b></div><div class="card stat"><small>هزینه‌ها</small><b>${money(t.expenses)}</b></div>
      <div class="card stat"><small>${t.net_profit < 0 ? 'زیان' : 'سود'} خالص</small><b class="${profitCls(t.net_profit)}">${money(Math.abs(t.net_profit))}</b></div></div>
      <div class="card"><h3>${mode === 'year' ? 'روند ماهانه' : 'روند'}</h3>${raw(barChart(rows))}</div>
      <div class="card"><h3>جدول ${mode === 'year' ? 'ماهانه' : 'دوره‌ای'}</h3><div style="overflow:auto"><table><tr><th>${mode === 'year' ? 'ماه' : 'دوره'}</th><th>فاکتور</th><th>فروش</th><th>سود ناخالص</th><th>هزینه</th><th>سود خالص</th></tr>
      ${rows.map(s => h`<tr ${mode === 'year' ? raw(`data-mo="${s.month}" style="cursor:pointer"`) : ''}><td>${s.label}</td><td>${s.count.toLocaleString('fa-IR')}</td><td>${money(s.revenue)}</td><td>${money(s.gross)}</td><td>${money(s.expenses)}</td><td class="${profitCls(s.profit)}"><b>${money(s.profit)}</b></td></tr>`)}
      <tr style="font-weight:700;background:var(--bg)"><td>جمع</td><td>${t.count.toLocaleString('fa-IR')}</td><td>${money(t.revenue)}</td><td>${money(t.gross_profit)}</td><td>${money(t.expenses)}</td><td class="${profitCls(t.net_profit)}">${money(t.net_profit)}</td></tr></table></div>
      ${mode === 'year' ? h`<small class="mut">برای دیدن جزئیات روزانهٔ هر ماه روی ردیف آن کلیک کنید.</small>` : ''}</div>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))"><div class="card"><h3>حضوری در برابر آنلاین (فروش)</h3>${raw(donut([{ t: 'حضوری', v: r.by_channel.offline.revenue, col: 'var(--pri)' }, { t: 'آنلاین', v: r.by_channel.online.revenue, col: '#f59e0b' }]))}
      <table style="margin-top:8px"><tr><th>کانال</th><th>تعداد</th><th>سود ناخالص</th></tr>${ch.map(([k, v]) => h`<tr><td>${k === 'online' ? 'آنلاین' : 'حضوری'}</td><td>${v.count.toLocaleString('fa-IR')}</td><td>${money(v.profit)}</td></tr>`)}</table></div>
      <div class="card"><h3>پرفروش‌ترین محصولات</h3>${r.top_products.length ? raw(hbars(r.top_products.map(p => ({ ...p, name: `${p.name} (${p.qty.toLocaleString('fa-IR')} عدد)` })), 'revenue')) : h`<p class="mut">فروشی ثبت نشده.</p>`}</div></div>`.s;
    $('#r').querySelectorAll('[data-mo]').forEach(tr => tr.onclick = () => { const m = String(tr.dataset.mo).padStart(2, '0'); mode = 'range';
      $('#s').value = `${year}/${m}/01`; $('#e').value = `${year}/${m}/${m <= 6 ? 31 : m <= 11 ? 30 : 29}`; $('#pd').value = 'day'; load(); });
  });
  el.querySelectorAll('[data-k]').forEach(b => b.onclick = () => load(b.dataset.k)); $('#go').onclick = () => load();
  $('#my').onclick = () => { mode = 'year'; load(); }; $('#mr').onclick = () => { mode = 'range'; load(); };
  $('#py').onclick = () => { year--; load(); }; $('#ny').onclick = () => { year++; load(); };
  $('#ch').onchange = () => load(); load();
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
const WOO_LBL = { added: 'جدید', updated: 'به‌روز شد', variations: 'تنوع', created: 'ساخته شد', images: 'تصویر ارسال شد', images_failed: 'تصویر ناموفق', errors: 'خطاها', imported: 'سفارش وارد شد' };
const wooLine = r => Object.entries(r || {}).filter(([, v]) => !Array.isArray(v) || v.length).map(([k, v]) => `${WOO_LBL[k] || k}: ${Array.isArray(v) ? v.join(' | ') : v}`).join('  ·  ') || 'تغییری نبود';
async function pWoo(el) {
  const s = await api('GET', '/api/settings');
  const connected = !!(s.woo_url && s.woo_key && s.woo_secret);
  const f = (k, label, extra = '') => field(label, h`<input data-k="${k}" value="${s[k]}" ${raw(extra)} style="width:100%;direction:ltr;text-align:left">`);
  render(el, h`<div class="card"><h3>۱) اتصال به سایت ${connected ? h`<span class="pos-n">✔ تنظیم شده</span>` : ''}</h3>
    <details ${connected ? '' : raw('open')}><summary class="mut" style="cursor:pointer">${connected ? 'ویرایش اطلاعات اتصال' : 'اطلاعات اتصال را وارد کنید'}</summary>
    <div class="grid">${f('woo_url', 'آدرس سایت', 'placeholder="example.ir"')}${f('woo_key', 'Consumer Key', 'type="password" autocomplete="off"')}${f('woo_secret', 'Consumer Secret', 'type="password" autocomplete="off"')}</div>
    <p class="mut">کلید را از وردپرس بسازید: ووکامرس ← تنظیمات ← پیشرفته ← REST API ← افزودن کلید (دسترسی «خواندن/نوشتن»).</p>
    <button id="cn">ذخیره و آزمایش اتصال</button> <span id="cs"></span></details></div>
    <div class="card" style="text-align:center"><h3>۲) همگام‌سازی</h3>
    <p class="mut">تغییرات برنامه (قیمت، موجودی، محصول جدید) را به سایت می‌فرستد و محصولات و سفارش‌های جدید سایت را می‌گیرد.</p>
    <button id="sync" style="font-size:18px;padding:14px 40px" ${connected ? '' : raw('disabled')}>🔄 همگام‌سازی همه‌چیز</button><div id="out" style="margin-top:12px"></div></div>
    <details class="card"><summary style="cursor:pointer">گزینه‌های پیشرفته</summary>
    <div class="row" style="margin:10px 0"><button class="sec" id="p1">⬇ فقط دریافت محصولات</button><label><input type="checkbox" id="us"> موجودی هم از سایت بیاید</label></div>
    <div class="row" style="margin:10px 0"><button class="sec" id="p2">⬆ فقط ارسال تغییرات</button><label><input type="checkbox" id="all"> همهٔ محصولات (نه فقط تغییرکرده‌ها)</label></div>
    <div class="row" style="margin:10px 0"><button class="sec" id="p3">⬇ فقط دریافت سفارش‌های آنلاین</button></div>
    <div class="grid">${field('واحد قیمت در سایت', h`<select data-k="woo_unit"><option value="toman" ${s.woo_unit !== 'rial' ? raw('selected') : ''}>تومان</option><option value="rial" ${s.woo_unit === 'rial' ? raw('selected') : ''}>ریال</option></select>`)}
    ${f('wp_user', 'نام کاربری وردپرس (فقط برای ارسال تصویر)')}${f('wp_app_password', 'رمز برنامهٔ وردپرس (Application Password)', 'type="password" autocomplete="off"')}</div>
    <label><input type="checkbox" data-k="woo_orders_decrement" ${s.woo_orders_decrement === '1' ? raw('checked') : ''}> با دریافت سفارش آنلاین، موجودی برنامه کم شود</label>
    <p><button class="sec" id="sv">ذخیره</button></p></details>`);
  const save = () => { const b = {}; el.querySelectorAll('[data-k]').forEach(i => b[i.dataset.k] = i.type === 'checkbox' ? (i.checked ? '1' : '0') : i.value); return api('PUT', '/api/settings', b); };
  $('#sv').onclick = () => run(save, 'ذخیره شد');
  $('#cn').onclick = () => run(async () => {
    $('#cs').textContent = 'در حال آزمایش...'; await save(); const r = await api('POST', '/api/woo/test', {});
    $('#cs').innerHTML = h`<b class="${r.ok ? 'pos-n' : 'neg'}">${r.ok ? '✔ ' : '✖ '}${r.detail}</b>`.s; if (r.ok) { $('#sync').disabled = false; }
  });
  const act = (id, fn) => $(id).onclick = () => run(async () => { $('#out').textContent = 'در حال انجام...'; const r = await fn(); $('#out').innerHTML = h`<b>نتیجه:</b> ${wooLine(r)}`.s; toast('انجام شد'); });
  $('#sync').onclick = () => run(async () => {
    $('#out').textContent = 'در حال همگام‌سازی... (برای فروشگاه‌های بزرگ ممکن است چند دقیقه طول بکشد)';
    const r = await api('POST', '/api/woo/sync', {});
    $('#out').innerHTML = h`<div>⬆ ارسال به سایت: ${wooLine(r.sent)}</div><div>⬇ محصولات: ${r.products ? wooLine(r.products) : 'انجام نشد (ابتدا خطای ارسال را رفع کنید)'}</div><div>🛒 سفارش‌ها: ${r.orders ? wooLine(r.orders) : '—'}</div>`.s;
    toast('همگام‌سازی انجام شد');
  });
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
    ${S.account_required ? h`<div class="card"><h3>حساب webakery.ir</h3>${S.user.account ? h`<p>متصل به: <b dir="ltr">${S.user.account}</b></p>` : h`<p>این کاربر به حساب سایت متصل نیست. با اتصال، می‌توانید رمز را از سایت بازیابی کنید و لایسنس‌های حساب خودکار فعال می‌شوند.</p><div class="row">${field('ایمیل حساب', h`<input id="lk_e" style="direction:ltr">`)}${field('رمز حساب', h`<input id="lk_p" type="password">`)}<button id="lk">اتصال حساب</button></div>`}</div>` : ''}
    <div class="card"><h3>ووکامرس</h3><p>اتصال و همگام‌سازی از صفحهٔ <a href="#woo">ووکامرس</a> انجام می‌شود.</p></div>
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
  if ($('#lk')) $('#lk').onclick = () => run(async () => { await api('POST', '/api/account/link', { email: $('#lk_e').value, password: $('#lk_p').value }); S = await (await fetch('/api/state')).json(); csrf = S.csrf; pSettings(el); }, 'حساب متصل شد');
  $('#tst').onclick = () => run(async () => { const r = await api('POST', '/api/sms/test', { phone: $('#tp').value }); toast(r.ok ? 'ارسال شد' : 'ناموفق: ' + r.detail, !r.ok); });
  $('#pc').onclick = () => run(() => api('POST', '/api/password', { old: $('#po').value, new: $('#pn').value }), 'رمز تغییر کرد');
}

// ---------- خرید و تأمین‌کنندگان ----------
let pcart = [];
async function pPurchases(el) {
  const [sups, products, list] = await Promise.all([api('GET', '/api/suppliers'), api('GET', '/api/products?sellable=1'), api('GET', '/api/purchases')]);
  render(el, h`<div class="card"><h3>تأمین‌کنندگان</h3><div class="row">${field('نام', h`<input id="sn">`)}${field('تلفن', h`<input id="sp">`)}<button id="sa">+ افزودن</button></div>
    <table><tr><th>نام</th><th>تلفن</th><th>مانده بدهی ما</th><th></th></tr>${sups.map(x => h`<tr><td>${x.name}</td><td dir="ltr">${x.phone}</td>
    <td class="${x.balance > 0 ? 'neg' : ''}">${money(x.balance)}</td><td><button class="bad" data-ds="${x.id}">حذف</button></td></tr>`)}</table></div>
    <div class="card"><h3>فاکتور خرید جدید</h3><div class="row">${field('تأمین‌کننده', h`<select id="sup">${sups.map(x => h`<option value="${x.id}">${x.name}</option>`)}</select>`)}
    ${field('افزودن کالا', h`<select id="pp"><option value="">— انتخاب —</option>${products.map(x => h`<option value="${x.id}">${x.name} (موجودی ${x.stock})</option>`)}</select>`)}</div>
    <table id="pc"></table><div class="row">${field('پرداخت‌شده الان (تومان)', h`<input id="pd" value="0" size="12">`)}${field('یادداشت', h`<input id="pn">`)}</div>
    <h3>جمع: <span id="pt"></span> تومان</h3><button class="ok" id="pok">ثبت فاکتور خرید</button></div>
    <div class="card"><h3>فاکتورهای خرید</h3><table><tr><th>شماره</th><th>تاریخ</th><th>تأمین‌کننده</th><th>جمع</th><th>پرداخت‌شده</th><th></th></tr>
    ${list.map(x => h`<tr><td>${x.number}</td><td>${x.jdate}</td><td>${x.supplier}</td><td>${money(x.total)}</td><td>${money(x.paid)}</td>
    <td><button class="sec" data-pp="${x.id}">چاپ</button> <button class="bad" data-dp="${x.id}">ابطال</button></td></tr>`)}</table></div>`);
  const draw = () => {
    $('#pc').innerHTML = '<tr><th>کالا</th><th>تعداد</th><th>قیمت خرید (تومان)</th><th></th></tr>' + pcart.map((c, i) => h`<tr><td>${c.name}</td>
      <td><input type="number" min="1" value="${c.qty}" data-i="${i}" data-f="qty" style="width:70px"></td>
      <td><input value="${c.unit_cost}" data-i="${i}" data-f="unit_cost" style="width:110px"></td><td><button class="sec" data-del="${i}">✕</button></td></tr>`.s).join('');
    $('#pc').querySelectorAll('input').forEach(i => i.onchange = () => { pcart[i.dataset.i][i.dataset.f] = parseInt(faNum(i.value)) || 0; draw(); });
    $('#pc').querySelectorAll('[data-del]').forEach(b => b.onclick = () => { pcart.splice(b.dataset.del, 1); draw(); });
    $('#pt').textContent = money(pcart.reduce((a, c) => a + c.qty * c.unit_cost, 0));
  };
  draw();
  $('#pp').onchange = () => { const p = products.find(x => x.id == $('#pp').value); if (p) { pcart.push({ product_id: p.id, name: p.name, qty: 1, unit_cost: p.cost_toman }); draw(); } $('#pp').value = ''; };
  $('#sa').onclick = () => run(async () => { await api('POST', '/api/suppliers', { name: $('#sn').value, phone: $('#sp').value }); pPurchases(el); }, 'ثبت شد');
  el.querySelectorAll('[data-ds]').forEach(b => b.onclick = () => confirm('حذف شود؟') && run(async () => { await api('DELETE', '/api/suppliers/' + b.dataset.ds); pPurchases(el); }));
  $('#pok').onclick = () => run(async () => {
    const r = await api('POST', '/api/purchases', { supplier_id: $('#sup').value, items: pcart.map(({ product_id, qty, unit_cost }) => ({ product_id, qty, unit_cost })),
      paid: parseInt(faNum($('#pd').value)) || 0, note: $('#pn').value });
    pcart = []; toast(`فاکتور خرید ${r.number} ثبت شد`); pPurchases(el);
  });
  el.querySelectorAll('[data-pp]').forEach(b => b.onclick = () => showPrint('/print/purchase/' + b.dataset.pp));
  el.querySelectorAll('[data-dp]').forEach(b => b.onclick = () => confirm('فاکتور خرید باطل و موجودی کم شود؟') && run(async () => { await api('DELETE', '/api/purchases/' + b.dataset.dp); pPurchases(el); }));
}

// ---------- حساب‌ها ----------
async function pAccounts(el) {
  const d = await api('GET', '/api/parties');
  const tbl = (title, rows, type, cls) => h`<div class="card"><h3>${title}: <span class="${cls}">${money(d[type === 'customer' ? 'debtors' : 'creditors'].total)}</span> تومان</h3>
    <table><tr><th>نام</th><th>موبایل/تلفن</th><th>مانده</th><th></th></tr>${rows.map(x => h`<tr><td>${x.name || [x.first_name, x.last_name].join(' ')}</td><td dir="ltr">${x.phone}</td>
    <td class="${cls}">${money(x.balance)}</td><td><button data-pay="${type}|${x.id}|${x.balance}">${type === 'customer' ? 'ثبت دریافت' : 'ثبت پرداخت'}</button>
    <button class="sec" data-led="${type}|${x.id}">صورت‌حساب</button></td></tr>`)}</table></div>`;
  render(el, h`${tbl('بدهکاران (مشتریانی که باید بپردازند)', d.debtors.rows, 'customer', 'neg')}${tbl('بستانکاران (تأمین‌کنندگانی که باید به آن‌ها بپردازیم)', d.creditors.rows, 'supplier', 'neg')}`);
  el.querySelectorAll('[data-pay]').forEach(b => b.onclick = () => {
    const [t, id, bal] = b.dataset.pay.split('|');
    const m = modal(h`<h3>${t === 'customer' ? 'ثبت دریافت از مشتری' : 'ثبت پرداخت به تأمین‌کننده'}</h3><p class="mut">مانده: ${money(bal)} تومان</p>
      <div class="row">${field('مبلغ', h`<input id="am" value="${bal}">`)}${field('روش', h`<select id="me"><option value="cash">نقد</option><option value="card">کارت</option><option value="transfer">واریز</option></select>`)}${field('یادداشت', h`<input id="no">`)}</div>
      <p><button id="ok">ثبت</button> <button class="sec" data-close>انصراف</button></p>`);
    $('#ok', m.box).onclick = () => run(async () => { await api('POST', '/api/payments', { party_type: t, party_id: id, amount: faNum($('#am', m.box).value), method: $('#me', m.box).value, note: $('#no', m.box).value }); m.close(); pAccounts(el); }, 'ثبت شد');
  });
  el.querySelectorAll('[data-led]').forEach(b => b.onclick = () => run(async () => {
    const [t, id] = b.dataset.led.split('|'); const rows = await api('GET', `/api/ledger?party_type=${t}&party_id=${id}`);
    const m = modal(h`<h3>صورت‌حساب</h3><table><tr><th>تاریخ</th><th>شرح</th><th>بدهکار</th><th>پرداخت</th><th>مانده</th><th></th></tr>
      ${rows.map(r => h`<tr><td>${r.date}</td><td>${r.title}</td><td>${r.debit ? money(r.debit) : ''}</td><td>${r.credit ? money(r.credit) : ''}</td><td>${money(r.balance)}</td>
      <td>${r.payment_id ? h`<button class="bad" data-dpay="${r.payment_id}">حذف</button>` : ''}</td></tr>`)}</table><p><button data-close>بستن</button></p>`);
    m.box.querySelectorAll('[data-dpay]').forEach(x => x.onclick = () => confirm('این پرداخت حذف شود؟') && run(async () => { await api('DELETE', '/api/payments/' + x.dataset.dpay); m.close(); pAccounts(el); }));
  }));
}

// ---------- کاربران ----------
async function pUsers(el) {
  const [users, audit] = await Promise.all([api('GET', '/api/users'), api('GET', '/api/audit')]);
  const roleSel = (id, cur) => h`<select data-role="${id}">${Object.entries(S.roles).map(([k, t]) => h`<option value="${k}" ${k === cur ? raw('selected') : ''}>${t}</option>`)}</select>`;
  render(el, h`<div class="card"><h3>کاربر جدید</h3><div class="row">${field('نام کاربری', h`<input id="nu" autocomplete="off">`)}${field('نام نمایشی', h`<input id="nf">`)}
    ${field('رمز (حداقل ۸)', h`<input id="np" type="password" autocomplete="new-password">`)}${field('نقش', h`<select id="nr">${Object.entries(S.roles).map(([k, t]) => h`<option value="${k}" ${k === 'cashier' ? raw('selected') : ''}>${t}</option>`)}</select>`)}
    <button id="na">افزودن</button></div></div>
    <div class="card"><table><tr><th>کاربر</th><th>نقش</th><th>وضعیت</th><th></th></tr>${users.map(u => h`<tr><td>${u.username} <small class="mut">${u.full_name}</small></td><td>${roleSel(u.id, u.role)}</td>
    <td>${u.active ? h`<span class="badge on">فعال</span>` : h`<span class="badge off">غیرفعال</span>`}</td><td><button class="sec" data-tg="${u.id}|${u.active ? 0 : 1}">${u.active ? 'غیرفعال' : 'فعال'}</button>
    <button class="sec" data-pw="${u.id}">رمز جدید</button> <button class="bad" data-du="${u.id}">حذف</button></td></tr>`)}</table>
    <details><summary>دسترسی هر نقش</summary><table>${Object.entries(S.roles).map(([k, t]) => h`<tr><td><b>${t}</b></td><td class="mut">${(S.role_perms[k] || []).join('، ')}</td></tr>`)}</table></details></div>
    <div class="card"><h3>گزارش رویدادها (۲۰۰ مورد آخر)</h3><table><tr><th>زمان</th><th>کاربر</th><th>رویداد</th><th>جزئیات</th></tr>${audit.map(a => h`<tr><td dir="ltr">${a.created_at}</td><td>${a.username || ''}</td><td>${a.action}</td><td>${a.detail}</td></tr>`)}</table></div>`);
  $('#na').onclick = () => run(async () => { await api('POST', '/api/users', { username: $('#nu').value, full_name: $('#nf').value, password: $('#np').value, role: $('#nr').value }); pUsers(el); }, 'کاربر ساخته شد');
  el.querySelectorAll('[data-role]').forEach(x => x.onchange = () => run(async () => { await api('PUT', '/api/users/' + x.dataset.role, { role: x.value }); pUsers(el); }, 'ذخیره شد'));
  el.querySelectorAll('[data-tg]').forEach(b => b.onclick = () => { const [id, a] = b.dataset.tg.split('|'); run(async () => { await api('PUT', '/api/users/' + id, { active: a === '1' }); pUsers(el); }); });
  el.querySelectorAll('[data-pw]').forEach(b => b.onclick = () => { const pw = prompt('رمز جدید (حداقل ۸ نویسه):'); if (pw) run(async () => { await api('PUT', '/api/users/' + b.dataset.pw, { password: pw }); }, 'رمز تغییر کرد'); });
  el.querySelectorAll('[data-du]').forEach(b => b.onclick = () => confirm('کاربر حذف شود؟') && run(async () => { await api('DELETE', '/api/users/' + b.dataset.du); pUsers(el); }));
}

// ---------- لایسنس و افزونه‌ها ----------
async function pLicense(el) {
  S = { ...S, ...(await (await fetch('/api/state')).json()) }; csrf = S.csrf; const L = S.license;
  const cat = await api('GET', '/api/license/catalog');
  const cur = L.mode === 'licensed' ? h`<div class="banner" style="background:#dcfce7;color:#166534">لایسنس برنامه فعال: ${L.plans[L.plan]?.title || L.plan} — ${L.expires ? 'تا ' + L.expires : 'بدون انقضا'}</div>` : '';
  const pname = id => cat.products.find(p => p.id === id)?.name || id;
  render(el, h`${cur}<div class="card"><p>شناسهٔ دستگاه شما: <b dir="ltr">${L.machine_id}</b> <small class="mut">(هنگام خرید به فروشنده بدهید تا لایسنس به این سیستم وصل شود)</small></p>
    <h3>لایسنس‌های نصب‌شده</h3><table><tr><th>محصول</th><th>پلن</th><th>انقضا</th><th>وضعیت</th></tr>${cat.installed.length ? cat.installed.map(i => h`<tr><td>${pname(i.product)}</td><td>${i.plan || ''}</td><td>${i.expires || 'بدون انقضا'}</td>
    <td>${i.error ? h`<span class="neg">${i.error}</span>` : h`<span class="pos-n">معتبر</span>`}</td></tr>`) : h`<tr><td colspan="4" class="mut">هنوز لایسنسی نصب نشده</td></tr>`}</table></div>
    ${cat.products.map(p => h`<div class="card"><h3>${p.name} <span class="badge">${p.kind === 'app' ? 'برنامه' : 'افزونه'}</span></h3><p class="mut">${p.description}</p>
    <div class="plans">${p.plans.map(x => h`<div class="plan"><div>${x.title}</div><b>${money(x.price)}</b><small class="mut">تومان</small><br><br>
    <button data-buy="${p.id}|${x.id}">پرداخت در وبیکری</button></div>`)}</div></div>`)}
    <div class="card"><h3>فعال‌سازی</h3>${field('کد لایسنس', h`<textarea id="k" rows="3" style="width:100%" dir="ltr"></textarea>`)}<button id="act">فعال‌سازی</button>
    <hr><div class="row">${field('یا کد سفارش وبیکری', h`<input id="od" dir="ltr">`)}<button class="sec" id="ord">دریافت خودکار لایسنس</button>
    <button class="sec" id="rc">به‌روزرسانی کاتالوگ محصولات (اینترنت)</button></div><p class="mut">نسخهٔ کاتالوگ: ${cat.version}</p></div>
    <div class="card"><h3>افزونه‌های نصب‌شده</h3>${S.plugins.length ? h`<table><tr><th>نام</th><th>نسخه</th><th>وضعیت</th></tr>${S.plugins.map(p => h`<tr><td>${p.name}</td><td>${p.version}</td>
    <td>${p.error ? h`<span class="neg">${p.error}</span>` : p.loaded ? 'فعال' : p.licensed ? 'نیاز به راه‌اندازی مجدد برنامه' : 'نیاز به لایسنس: ' + pname(p.product)}</td></tr>`)}</table>` : h`<p class="mut">افزونه‌ای نصب نشده. پوشهٔ افزونه را در plugins داخل پوشهٔ داده کپی کنید.</p>`}</div>`);
  el.querySelectorAll('[data-buy]').forEach(b => b.onclick = () => run(async () => {
    const [pr, pl] = b.dataset.buy.split('|'); const r = await api('GET', `/api/license/buy-url?product=${encodeURIComponent(pr)}&plan=${encodeURIComponent(pl)}`); window.open(r.url, '_blank', 'noopener');
  }));
  const done = async () => { S = { ...S, ...(await (await fetch('/api/state')).json()) }; go('license'); };
  $('#act').onclick = () => run(async () => { await api('POST', '/api/license', { key: $('#k').value }); await done(); }, 'لایسنس فعال شد');
  $('#ord').onclick = () => run(async () => { await api('POST', '/api/license/order', { order: $('#od').value }); await done(); }, 'لایسنس فعال شد');
  $('#rc').onclick = () => run(async () => { await api('POST', '/api/license/catalog-refresh', {}); await done(); }, 'کاتالوگ به‌روز شد');
}

boot();
