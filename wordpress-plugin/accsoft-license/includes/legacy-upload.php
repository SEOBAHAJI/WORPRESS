<?php
if (!defined('ABSPATH')) exit;
/* آپلود افزونهٔ وردپرس (zip) از پنل → ثبت خودکار به‌عنوان محصول لایسنس‌دار + به‌روزرسانی خودکار برای مشتری‌ها.
   فایل‌ها در uploads/accsoft-updates (ممنوع برای دسترسی مستقیم) نگه‌داری و فقط با لایسنس معتبر و دامنهٔ فعال دانلود می‌شوند. */

function accsoft_wl_store_dir() {
    $u = wp_upload_dir(); $d = rtrim($u['basedir'], '/') . '/accsoft-updates';
    if (!is_dir($d)) { wp_mkdir_p($d); file_put_contents($d . '/.htaccess', "Require all denied\nDeny from all\n"); file_put_contents($d . '/index.php', "<?php // silence\n"); }
    return $d;
}

/** zip را بررسی و مشخصات افزونه را برمی‌گرداند؛ در خطا Exception */
function accsoft_wl_zip_meta($path) {
    if (!class_exists('ZipArchive')) throw new Exception('افزونهٔ zip در PHP هاست فعال نیست');
    $z = new ZipArchive(); if ($z->open($path) !== true) throw new Exception('فایل zip معتبر نیست');
    $top = null; $main = null; $total = 0;
    for ($i = 0; $i < $z->numFiles; $i++) {
        $st = $z->statIndex($i); $n = str_replace('\\', '/', $st['name']); $total += $st['size'];
        if ($n === '' || $n[0] === '/' || preg_match('#(^|/)\.\.(/|$)#', $n) || strpos($n, "\0") !== false) throw new Exception('مسیر نامعتبر داخل zip: ' . $n);
        $t = explode('/', $n)[0]; if ($top === null) $top = $t; elseif ($top !== $t) throw new Exception('همهٔ فایل‌ها باید داخل یک پوشه (نام افزونه) باشند');
        if (!$main && substr_count($n, '/') === 1 && substr($n, -4) === '.php') {
            $head = $z->getFromIndex($i, 8192);
            if ($head !== false && preg_match('/^[ \t\/*#@]*Plugin Name:\s*(.+)$/mi', $head)) $main = [$n, $head];
        }
    }
    $z->close();
    if ($total > 300 * 1024 * 1024) throw new Exception('حجم محتوای zip بیش از حد است');
    if (!$main) throw new Exception('فایل اصلی افزونه (با هدر «Plugin Name:») در ریشهٔ پوشه پیدا نشد');
    $h = function ($k) use ($main) { return preg_match('/^[ \t\/*#@]*' . preg_quote($k, '/') . ':\s*(.+)$/mi', $main[1], $m) ? trim(preg_replace('/\s*\*\/.*$/', '', $m[1])) : ''; };
    $slug = preg_replace('/[^a-z0-9_-]/', '', strtolower($top));
    if ($slug === '' ) throw new Exception('نام پوشهٔ افزونه نامعتبر است');
    if ($h('Version') === '') throw new Exception('هدر «Version:» در فایل اصلی افزونه نیست');
    return ['slug' => $slug, 'file' => $main[0], 'name' => $h('Plugin Name'), 'version' => $h('Version'), 'desc' => $h('Description'),
            'requires' => $h('Requires at least') ?: '5.8', 'tested' => $h('Tested up to') ?: '6.6', 'php' => $h('Requires PHP') ?: '7.4'];
}

/** ثبت/به‌روزرسانی محصول از روی zip آپلودشده. محصول موجود: قیمت/پلن‌ها حفظ و فقط نسخه عوض می‌شود. */
function accsoft_wl_ingest($tmp, $changelog = '') {
    $m = accsoft_wl_zip_meta($tmp); $prods = accsoft_wl_products(); $cur = $prods[$m['slug']] ?? null;
    if ($cur && !empty($cur['update']['version']) && empty($cur['update']['file']) && !empty($cur['update']['package'])) { /* محصول قدیمی با لینک بیرونی؛ با آپلود، به فایل داخلی تبدیل می‌شود */ }
    if ($cur && !empty($cur['update']['version']) && version_compare($m['version'], $cur['update']['version'], '<'))
        throw new Exception("نسخهٔ {$m['version']} از نسخهٔ فعلی ({$cur['update']['version']}) قدیمی‌تر است");
    $dir = accsoft_wl_store_dir(); $fn = $m['slug'] . '-' . preg_replace('/[^0-9A-Za-z._-]/', '', $m['version']) . '-' . bin2hex(random_bytes(6)) . '.zip';
    if (!copy($tmp, $dir . '/' . $fn)) throw new Exception('ذخیرهٔ فایل ممکن نشد');
    if (!empty($cur['update']['file']) && $cur['update']['file'] !== $fn) { /* نسخهٔ قبلی برای بازگشت نگه داشته می‌شود */ $hist = $cur['history'] ?? []; array_unshift($hist, $cur['update']['file']); $cur['history'] = array_slice($hist, 0, 3); }
    $prods[$m['slug']] = array_merge($cur ?: ['label' => $m['name'], 'icon' => '🔌', 'desc' => $m['desc'], 'price' => 0, 'plans' => []], [
        'label' => $cur['label'] ?? $m['name'], 'desc' => ($cur['desc'] ?? '') ?: $m['desc'],
        'update' => ['version' => $m['version'], 'package' => '', 'file' => $fn, 'requires' => $m['requires'], 'tested' => $m['tested'], 'requires_php' => $m['php'],
                     'changelog' => $changelog !== '' ? $changelog : 'نسخهٔ ' . $m['version']]]);
    update_option('accsoft_wl_products', $prods, false);
    return $m + ['created' => !$cur, 'file' => $fn];
}

/** آدرس دانلود امن؛ فقط وقتی لایسنس و دامنه موجود باشد */
function accsoft_wl_download_url($product, $key, $domain) {
    return add_query_arg(['accsoft_dl' => $product, 'license_key' => $key, 'domain' => $domain], home_url('/'));
}

function accsoft_wl_serve_download() {
    $prod = preg_replace('/[^a-z0-9_-]/', '', strtolower((string)$_GET['accsoft_dl'])); $p = accsoft_wl_product($prod);
    $key = sanitize_text_field($_GET['license_key'] ?? ''); $dom = sanitize_text_field($_GET['domain'] ?? '');
    $v = $p && $key && $dom ? accsoft_wl_validate($key, $dom, $prod) : ['valid' => false];
    if (empty($v['valid'])) { status_header(403); echo 'Invalid license'; exit; }
    $f = $p['update']['file'] ?? ''; $path = accsoft_wl_store_dir() . '/' . basename($f);
    if ($f === '' || !is_file($path)) { status_header(404); echo 'Package not found'; exit; }
    nocache_headers(); header('Content-Type: application/zip'); header('Content-Disposition: attachment; filename="' . $prod . '.zip"'); header('Content-Length: ' . filesize($path)); readfile($path); exit;
}
add_action('template_redirect', function () { if (!empty($_GET['accsoft_dl'])) accsoft_wl_serve_download(); }, 1);

add_action('admin_post_accsoft_wl_upload', function () {
    accsoft_admin_guard('accsoft_wl_upload'); $f = $_FILES['f'] ?? null;
    if (!$f || $f['error'] || !is_uploaded_file($f['tmp_name']) || $f['size'] > 100 * 1024 * 1024) accsoft_admin_back('legacy&sub=upload', 'فایل نامعتبر یا بزرگ‌تر از ۱۰۰ مگابایت', true);
    try { $r = accsoft_wl_ingest($f['tmp_name'], sanitize_text_field($_POST['changelog'] ?? '')); }
    catch (Exception $e) { accsoft_admin_back('legacy&sub=upload', $e->getMessage(), true); }
    accsoft_admin_back('legacy&sub=upload', ($r['created'] ? 'محصول جدید ثبت شد: ' : 'نسخهٔ جدید منتشر شد: ') . $r['name'] . ' ' . $r['version'] . ($r['created'] ? ' — قیمت/پلن را در «محصولات و قیمت» تنظیم کنید' : ''));
});

function accsoft_wl_upload_page() {
    echo '<h3>آپلود افزونه از سیستم</h3><p>فایل zip افزونه را انتخاب کنید (پوشهٔ افزونه در ریشهٔ zip و فایل اصلی با هدر <code>Plugin Name</code> و <code>Version</code>). نام پوشه همان شناسهٔ محصول می‌شود.
      اگر محصول تازه باشد ثبت می‌شود؛ اگر موجود باشد نسخهٔ جدید منتشر و مشتری‌های دارای لایسنس در وردپرس خودشان «به‌روزرسانی» می‌بینند.</p>
      <form method="post" enctype="multipart/form-data" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="accsoft_wl_upload">' . wp_nonce_field('accsoft_wl_upload', '_n', true, false) . '
      <input type="file" name="f" accept=".zip" required> <input name="changelog" placeholder="توضیح تغییرات (اختیاری)" style="width:320px"> <button class="button button-primary">آپلود و انتشار</button></form>';
    echo '<h3>محصولات</h3><table class="widefat striped"><tr><th>شناسه</th><th>نام</th><th>نسخه</th><th>فایل</th><th>قیمت (تومان)</th></tr>';
    foreach (accsoft_wl_products() as $s => $p) echo '<tr><td dir="ltr">' . esc_html($s) . '</td><td>' . esc_html($p['label'] ?? '') . '</td><td>' . esc_html($p['update']['version'] ?? '—') . '</td><td>' . (!empty($p['update']['file']) ? '✔ آپلودشده' : (!empty($p['update']['package']) ? 'لینک بیرونی' : '—')) . '</td><td>' . ($p['plans'] ? 'پلنی' : number_format_i18n(($p['price'] ?? 0) / 10)) . '</td></tr>';
    echo '</table>';
}
