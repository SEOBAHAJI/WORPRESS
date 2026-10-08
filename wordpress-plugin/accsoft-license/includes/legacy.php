<?php
if (!defined('ABSPATH')) exit;
/* موتور سازگار با «لایسنس‌سرور» قدیمی وبیکری (افزونه‌های وردپرسی baget/hesabdar/...): کلید متنی + فعال‌سازی روی دامنه.
   آدرس‌های قبلی (/license-server/api/ ، /pay/ ، /portal/) با rewrite همچنان کار می‌کنند. */

function accsoft_wl_install_tables() {
    global $wpdb; $cs = $wpdb->get_charset_collate();
    dbDelta("CREATE TABLE " . accsoft_t('wlic') . " (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, uid VARCHAR(24) NOT NULL DEFAULT '', license_key VARCHAR(60) NOT NULL, email VARCHAR(190) NOT NULL DEFAULT '',
      product VARCHAR(60) NOT NULL, note TEXT NULL, status VARCHAR(12) NOT NULL DEFAULT 'active', expires_at DATE NULL, created_at DATETIME NOT NULL,
      PRIMARY KEY (id), UNIQUE KEY license_key (license_key), KEY email (email)) $cs;");
    dbDelta("CREATE TABLE " . accsoft_t('wact') . " (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, license_key VARCHAR(60) NOT NULL, domain VARCHAR(190) NOT NULL, ip VARCHAR(64) NOT NULL DEFAULT '',
      activated_at DATETIME NOT NULL, PRIMARY KEY (id), KEY license_key (license_key), KEY domain (domain)) $cs;");
    dbDelta("CREATE TABLE " . accsoft_t('wpay') . " (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, track_id VARCHAR(40) NOT NULL, plugin VARCHAR(60) NOT NULL DEFAULT '', email VARCHAR(190) NOT NULL DEFAULT '',
      domain VARCHAR(190) NOT NULL DEFAULT '', return_url TEXT NULL, amount BIGINT NOT NULL DEFAULT 0, base_amount BIGINT NOT NULL DEFAULT 0,
      plan VARCHAR(40) NULL, months INT NOT NULL DEFAULT 0, coupon_id VARCHAR(24) NULL, coupon_code VARCHAR(60) NULL, coupon_discount BIGINT NOT NULL DEFAULT 0,
      status VARCHAR(12) NOT NULL DEFAULT 'pending', license_key VARCHAR(60) NULL, created_at DATETIME NOT NULL, PRIMARY KEY (id), UNIQUE KEY track_id (track_id)) $cs;");
    dbDelta("CREATE TABLE " . accsoft_t('wcoupon') . " (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, uid VARCHAR(24) NOT NULL DEFAULT '', code VARCHAR(60) NOT NULL, type VARCHAR(8) NOT NULL DEFAULT 'percent',
      value BIGINT NOT NULL DEFAULT 0, product VARCHAR(60) NOT NULL DEFAULT 'all', max_uses INT NOT NULL DEFAULT 0, used_count INT NOT NULL DEFAULT 0,
      min_amount BIGINT NOT NULL DEFAULT 0, expires_at DATE NULL, status VARCHAR(10) NOT NULL DEFAULT 'active', note TEXT NULL, created_at DATETIME NOT NULL,
      PRIMARY KEY (id), UNIQUE KEY code (code)) $cs;");
}

/* ---------- محصولات قدیمی (قیمت‌ها ریال‌اند، مثل سرور قبلی) ---------- */
function accsoft_wl_products() {
    $p = get_option('accsoft_wl_products');
    if (!is_array($p)) { $seed = @include ACCSOFT_DIR . 'includes/legacy-seed.php'; $p = is_array($seed) ? $seed : []; }
    return $p;
}
function accsoft_wl_product($slug) { $p = accsoft_wl_products(); return $p[strtolower($slug)] ?? null; }
function accsoft_wl_has_plans($slug) { $p = accsoft_wl_product($slug); return !empty($p['plans']); }
function accsoft_wl_plan($slug, $id) { $p = accsoft_wl_product($slug); return $p['plans'][$id] ?? null; }
function accsoft_wl_default_plan($slug) {
    $p = accsoft_wl_product($slug); foreach (($p['plans'] ?? []) as $id => $pl) if (!empty($pl['badge'])) return (string)$id;
    return (string)(array_key_first($p['plans'] ?? []) ?? '');
}
function accsoft_wl_amount($slug, $plan = '') {
    $p = accsoft_wl_product($slug); if (!$p) return 0;
    if (!empty($p['plans'])) { $pl = accsoft_wl_plan($slug, $plan ?: accsoft_wl_default_plan($slug)); if ($pl && (int)$pl['price'] > 0) return (int)$pl['price']; }
    return (int)($p['price'] ?? 0);
}

/* ---------- لایسنس‌ها ---------- */
function accsoft_wl_clean_domain($u) {
    $u = preg_replace('#^https?://#i', '', trim((string)$u)); $u = explode('/', $u)[0]; $u = explode(':', $u)[0];
    return strtolower(preg_replace('/^www\./i', '', $u));
}
function accsoft_wl_find($key) { global $wpdb; return $wpdb->get_row($wpdb->prepare("SELECT * FROM " . accsoft_t('wlic') . " WHERE license_key=%s", $key), ARRAY_A); }
function accsoft_wl_acts($key) { global $wpdb; return $wpdb->get_results($wpdb->prepare("SELECT * FROM " . accsoft_t('wact') . " WHERE license_key=%s ORDER BY id", $key), ARRAY_A); }
function accsoft_wl_gen_key($product) {
    $pre = substr(strtoupper(preg_replace('/[^A-Z0-9]/i', '', $product)) ?: 'LIC', 0, 6); $c = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    $seg = function () use ($c) { $s = ''; for ($i = 0; $i < 4; $i++) $s .= $c[random_int(0, 35)]; return $s; };
    return $pre . '-' . $seg() . '-' . $seg() . '-' . $seg() . '-' . $seg();
}
function accsoft_wl_create($email, $product = 'wccp', $note = '', $expires = null, $domain = '') {
    global $wpdb;
    do { $key = accsoft_wl_gen_key($product); } while (accsoft_wl_find($key));
    $wpdb->insert(accsoft_t('wlic'), ['uid' => uniqid(), 'license_key' => $key, 'email' => $email, 'product' => strtolower($product), 'note' => $note,
        'status' => 'active', 'expires_at' => $expires ?: null, 'created_at' => accsoft_now()]);
    if ($domain !== '' && ($d = accsoft_wl_clean_domain($domain)) !== '') accsoft_wl_activate($key, $d, '');
    return accsoft_wl_find($key);
}
function accsoft_wl_activate($key, $domain, $ip = '') {
    global $wpdb; $lic = accsoft_wl_find($key);
    if (!$lic) return ['success' => false, 'error' => 'license_not_found', 'message' => 'کلید لایسنس یافت نشد.'];
    if ($lic['status'] !== 'active') return ['success' => false, 'error' => 'license_revoked', 'message' => 'این لایسنس غیرفعال است.'];
    if ($lic['expires_at'] && strtotime($lic['expires_at']) < time()) return ['success' => false, 'error' => 'license_expired', 'message' => 'اشتراک منقضی شده.'];
    $domain = accsoft_wl_clean_domain($domain); $A = accsoft_t('wact');
    if ($wpdb->get_var($wpdb->prepare("SELECT id FROM $A WHERE license_key=%s AND domain=%s", $key, $domain))) return ['success' => true, 'message' => 'لایسنس قبلاً برای این دامنه فعال بود.', 'domain' => $domain];
    $other = $wpdb->get_var($wpdb->prepare("SELECT domain FROM $A WHERE license_key=%s AND domain<>%s LIMIT 1", $key, $domain));
    if ($other) return ['success' => false, 'error' => 'already_activated', 'message' => 'این لایسنس روی دامنه دیگری فعال است: ' . $other];
    $wpdb->insert($A, ['license_key' => $key, 'domain' => $domain, 'ip' => $ip, 'activated_at' => accsoft_now()]);
    return ['success' => true, 'message' => 'لایسنس با موفقیت فعال شد.', 'domain' => $domain];
}
function accsoft_wl_validate($key, $domain, $product = '') {
    global $wpdb; $lic = accsoft_wl_find($key);
    if (!$lic) return ['valid' => false, 'error' => 'license_not_found'];
    if ($lic['status'] !== 'active') return ['valid' => false, 'error' => 'license_revoked'];
    if ($lic['expires_at'] && strtotime($lic['expires_at'] . ' 23:59:59') < time()) return ['valid' => false, 'error' => 'license_expired'];
    if ($product && strtolower($product) !== strtolower($lic['product'])) return ['valid' => false, 'error' => 'product_mismatch'];
    $domain = accsoft_wl_clean_domain($domain);
    if (!$wpdb->get_var($wpdb->prepare("SELECT id FROM " . accsoft_t('wact') . " WHERE license_key=%s AND domain=%s", $key, $domain))) return ['valid' => false, 'error' => 'domain_not_activated'];
    return ['valid' => true, 'email' => $lic['email'], 'product' => $lic['product'], 'expires_at' => $lic['expires_at']];
}
function accsoft_wl_find_by($email, $domain, $product) {
    global $wpdb; $L = accsoft_t('wlic'); $row = null;
    if ($email) $row = $wpdb->get_row($wpdb->prepare("SELECT * FROM $L WHERE LOWER(email)=%s AND product=%s AND status='active' LIMIT 1", strtolower($email), strtolower($product)), ARRAY_A);
    if (!$row && $domain) $row = $wpdb->get_row($wpdb->prepare("SELECT l.* FROM $L l JOIN " . accsoft_t('wact') . " a ON a.license_key=l.license_key WHERE a.domain=%s AND l.product=%s AND l.status='active' LIMIT 1", $domain, strtolower($product)), ARRAY_A);
    return $row;
}
function accsoft_wl_extend($email, $product, $months, $domain = '', $note = '') {
    global $wpdb; $domain = $domain ? accsoft_wl_clean_domain($domain) : ''; $months = max(1, (int)$months);
    $ex = accsoft_wl_find_by(strtolower(trim($email)), $domain, $product);
    if ($ex) {
        $base = time(); if ($ex['expires_at'] && ($t = strtotime($ex['expires_at'] . ' 23:59:59')) > $base) $base = $t;
        $wpdb->update(accsoft_t('wlic'), ['expires_at' => gmdate('Y-m-d', strtotime("+$months months", $base)), 'status' => 'active',
            'note' => trim(($ex['note'] ?? '') . ' | تمدید ' . $months . 'ماهه ' . gmdate('Y-m-d'))], ['license_key' => $ex['license_key']]);
        if ($domain !== '') accsoft_wl_activate($ex['license_key'], $domain, '');
        return accsoft_wl_find($ex['license_key']);
    }
    return accsoft_wl_create(strtolower(trim($email)), $product, $note ?: "اشتراک $months ماهه", gmdate('Y-m-d', strtotime("+$months months")), $domain);
}
function accsoft_wl_lifetime($email, $product, $domain = '', $note = '') {
    global $wpdb; $domain = $domain ? accsoft_wl_clean_domain($domain) : '';
    $ex = accsoft_wl_find_by(strtolower(trim($email)), $domain, $product);
    if ($ex) {
        $wpdb->update(accsoft_t('wlic'), ['expires_at' => null, 'status' => 'active', 'note' => trim(($ex['note'] ?? '') . ' | ارتقا به دائمی ' . gmdate('Y-m-d'))], ['license_key' => $ex['license_key']]);
        if ($domain !== '') accsoft_wl_activate($ex['license_key'], $domain, '');
        return accsoft_wl_find($ex['license_key']);
    }
    return accsoft_wl_create(strtolower(trim($email)), $product, $note ?: 'لایسنس دائمی', null, $domain);
}

/* ---------- کد تخفیف ---------- */
function accsoft_wl_coupon($code) { global $wpdb; return $wpdb->get_row($wpdb->prepare("SELECT * FROM " . accsoft_t('wcoupon') . " WHERE code=%s", strtoupper(trim($code))), ARRAY_A); }
function accsoft_wl_coupon_validate($code, $product, $base) {
    $c = accsoft_wl_coupon($code); $no = function ($m) use ($base, $c) { return ['valid' => false, 'message' => $m, 'discount' => 0, 'final' => $base, 'coupon' => $c]; };
    if (!$c) return $no('کد تخفیف یافت نشد.');
    if ($c['status'] !== 'active') return $no('این کد غیرفعال است.');
    if ($c['expires_at'] && strtotime($c['expires_at'] . ' 23:59:59') < time()) return $no('این کد منقضی شده.');
    if ($c['product'] !== 'all' && strtolower($c['product']) !== strtolower($product)) return $no('این کد برای این محصول قابل استفاده نیست.');
    if ((int)$c['max_uses'] > 0 && (int)$c['used_count'] >= (int)$c['max_uses']) return $no('سقف استفاده از این کد تکمیل شده.');
    if ((int)$c['min_amount'] > 0 && $base < (int)$c['min_amount']) return $no('حداقل مبلغ سفارش برای این کد: ' . number_format($c['min_amount'] / 10) . ' تومان.');
    $d = $c['type'] === 'percent' ? (int)round($base * (int)$c['value'] / 100) : (int)$c['value'];
    $d = min($d, $base);
    return ['valid' => true, 'message' => 'کد تخفیف اعمال شد.', 'coupon' => $c, 'discount' => $d, 'final' => $base - $d];
}

/* ---------- به‌روزرسانی افزونه‌ها ---------- */
function accsoft_wl_update_payload($product, $client_ver, $key, $domain) {
    $product = preg_replace('/[^a-z0-9_\-]/', '', strtolower(trim($product))); $domain = accsoft_wl_clean_domain($domain);
    if ($product === '') return ['success' => false, 'message' => 'پارامتر product الزامی است.'];
    $p = accsoft_wl_product($product);
    if (!$p || empty($p['update']['version'])) return ['success' => false, 'message' => 'به‌روزرسانی برای این محصول تعریف نشده است.'];
    if ($key !== '') {
        if ($domain === '') return ['success' => false, 'message' => 'پارامتر domain الزامی است.'];
        $v = accsoft_wl_validate($key, $domain, $product);
        if (empty($v['valid'])) {
            $m = ['license_not_found' => 'کلید لایسنس یافت نشد.', 'license_revoked' => 'لایسنس غیرفعال شده است.', 'license_expired' => 'اعتبار لایسنس منقضی شده است.',
                  'product_mismatch' => 'این لایسنس برای این افزونه نیست.', 'domain_not_activated' => 'لایسنس روی این دامنه فعال نشده است.'];
            return ['success' => false, 'message' => $m[$v['error'] ?? ''] ?? 'لایسنس نامعتبر است.'];
        }
    }
    $u = $p['update']; $home = $u['homepage'] ?? accsoft_setting('wl_base', 'https://webakery.ir'); $pkg = $u['package'] ?? '';
    if (!empty($u['file'])) $pkg = $key !== '' && $domain !== '' ? accsoft_wl_download_url($product, $key, $domain) : '';
    return ['success' => true, 'message' => 'اطلاعات به‌روزرسانی', 'product' => $product, 'version' => $u['version'], 'package' => $pkg, 'download_url' => $pkg,
        'url' => $home, 'homepage' => $home, 'requires' => $u['requires'] ?? '5.8', 'tested' => $u['tested'] ?? '6.6', 'requires_php' => $u['requires_php'] ?? '7.4',
        'changelog' => $u['changelog'] ?? '', 'name' => $p['label'] ?? $product, 'client_version' => $client_ver,
        'update_available' => $client_ver !== '' && version_compare($u['version'], $client_ver, '>')];
}

/* ---------- ایمیل ---------- */
function accsoft_wl_mail($lic, $domain = '') {
    $p = accsoft_wl_product($lic['product']); $label = $p['label'] ?? $lic['product'];
    $exp = $lic['expires_at'] ? 'تاریخ انقضا: ' . esc_html($lic['expires_at']) : 'مادام‌العمر (بدون انقضا)';
    $body = '<div dir="rtl" style="font-family:Tahoma,Arial;max-width:520px;margin:auto"><h2>🔑 لایسنس شما آماده است</h2><p>' . esc_html($label) . '</p>
      <p style="background:#f5f3ff;border:1px dashed #c4b5fd;padding:10px;font-family:monospace;direction:ltr;text-align:center">' . esc_html($lic['license_key']) . '</p>
      <p>' . $exp . ($domain ? '<br>دامنه: <span dir="ltr">' . esc_html($domain) . '</span>' : '') . '</p>
      <p>این کلید را در افزونهٔ سایت خود وارد کنید. مدیریت لایسنس‌ها: <a href="' . esc_url(accsoft_portal_url()) . '">پیشخوان مشتری</a></p></div>';
    return wp_mail($lic['email'], '🔑 لایسنس شما — ' . $label, $body, ['Content-Type: text/html; charset=UTF-8']);
}

/* ---------- API سازگار ---------- */
function accsoft_wl_api($action, $in) {
    global $wpdb;
    $san = function ($v) { return trim(strip_tags((string)$v)); };
    $out = function ($ok, $msg, $extra = [], $code = 200) { status_header($code); echo wp_json_encode(array_merge(['success' => $ok, 'message' => $msg], $extra), JSON_UNESCAPED_UNICODE); exit; };
    if (in_array($action, ['create', 'revoke', 'coupon_list'], true)) {
        $sec = (string)accsoft_setting('wl_api_secret'); $got = (string)($_SERVER['HTTP_X_WBLM_SECRET'] ?? '');
        if ($sec === '' || !hash_equals($sec, $got)) $out(false, 'Unauthorized', [], 401);
    }
    switch ($action) {
        case 'ping': $out(true, 'pong');
        case 'create':
            $email = $san($in['email'] ?? ''); if (!$email) $out(false, 'پارامتر email الزامی است.');
            $lic = accsoft_wl_create($email, $san($in['product'] ?? 'wccp'), $san($in['note'] ?? ''), $san($in['expires_at'] ?? '') ?: null, $san($in['domain'] ?? ''));
            if (!empty($in['domain'])) $lic['activations'] = accsoft_wl_acts($lic['license_key']);
            $out(true, 'لایسنس ساخته شد.', $lic);
        case 'revoke':
            $k = $san($in['license_key'] ?? ''); if (!$k) $out(false, 'پارامتر license_key الزامی است.');
            $wpdb->update(accsoft_t('wlic'), ['status' => 'revoked'], ['license_key' => $k]); $out(true, 'لایسنس باطل شد.');
        case 'activate':
            $k = $san($in['license_key'] ?? ''); $d = $san($in['domain'] ?? ($_SERVER['HTTP_REFERER'] ?? ''));
            if (!$k || !$d) $out(false, 'پارامتر license_key و domain الزامی است.');
            $r = accsoft_wl_activate($k, $d, $_SERVER['REMOTE_ADDR'] ?? ''); $out($r['success'], $r['message'], $r);
        case 'validate':
            $k = $san($in['license_key'] ?? ''); $d = $san($in['domain'] ?? '');
            if (!$k || !$d) $out(false, 'پارامتر license_key و domain الزامی است.');
            $r = accsoft_wl_validate($k, $d, $san($in['product'] ?? '')); $out($r['valid'], $r['valid'] ? 'معتبر' : ($r['error'] ?? 'نامعتبر'), $r);
        case 'deactivate':
            $k = $san($in['license_key'] ?? ''); $d = accsoft_wl_clean_domain($san($in['domain'] ?? ''));
            if (!$k || !$d) $out(false, 'پارامتر license_key و domain الزامی است.');
            $wpdb->delete(accsoft_t('wact'), ['license_key' => $k, 'domain' => $d]); $out(true, 'لایسنس از این دامنه حذف شد.');
        case 'update':
            $req = array_merge($_GET, is_array($in) ? $in : []);
            $r = accsoft_wl_update_payload($san($req['product'] ?? ''), $san($req['version'] ?? ''), $san($req['license_key'] ?? ($req['license'] ?? '')), $san($req['domain'] ?? ''));
            $out(!empty($r['success']), $r['message'] ?? '—', $r);
        case 'coupon_validate':
            $code = $san($in['code'] ?? ''); $prod = $san($in['product'] ?? 'wccp'); $amt = (int)($in['amount'] ?? 0);
            if (!$code) $out(false, 'پارامتر code الزامی است.');
            if ($amt <= 0) $amt = accsoft_wl_amount($prod);
            if ($amt <= 0) $out(false, 'مبلغ برای اعتبارسنجی لازم است.');
            $r = accsoft_wl_coupon_validate($code, $prod, $amt);
            $out($r['valid'], $r['message'], ['discount' => $r['discount'], 'final' => $r['final'],
                'coupon' => $r['coupon'] ? array_intersect_key($r['coupon'], array_flip(['code', 'type', 'value', 'product', 'expires_at'])) : null]);
        case 'coupon_list':
            $out(true, 'لیست کدهای تخفیف', ['coupons' => $wpdb->get_results("SELECT * FROM " . accsoft_t('wcoupon'), ARRAY_A)]);
        default: $out(false, 'action نامعتبر است. مقادیر مجاز: create, activate, validate, deactivate, revoke, ping, update, coupon_validate, coupon_list');
    }
}

/* ---------- مسیرهای قدیمی ---------- */
add_action('init', function () {
    add_rewrite_rule('^license-server/(api|pay|portal)/?$', 'index.php?accsoft_legacy=$matches[1]', 'top');
    add_rewrite_rule('^license-server/?$', 'index.php?accsoft_legacy=portal', 'top');
});
add_filter('query_vars', function ($v) { $v[] = 'accsoft_legacy'; return $v; });
add_action('template_redirect', function () {
    $w = get_query_var('accsoft_legacy'); if (!$w) return;
    if ($w === 'portal') { wp_safe_redirect(accsoft_portal_url()); exit; }
    if ($w === 'api') {
        nocache_headers(); header('Content-Type: application/json; charset=utf-8'); header('Access-Control-Allow-Origin: *');
        $in = json_decode(file_get_contents('php://input'), true); if (!is_array($in)) $in = $_POST;
        accsoft_wl_api((string)($_REQUEST['action'] ?? ''), $in);
    }
    if ($w === 'pay') accsoft_wl_pay();
}, 1);
add_action('rest_api_init', function () {
    register_rest_route('accsoft/v1', '/legacy', ['methods' => ['GET', 'POST'], 'permission_callback' => '__return_true', 'callback' => function () {
        $in = json_decode(file_get_contents('php://input'), true); if (!is_array($in)) $in = $_POST;
        header('Access-Control-Allow-Origin: *'); accsoft_wl_api((string)($_REQUEST['action'] ?? ''), $in);
    }]);
});

/* ---------- صفحهٔ پرداخت قدیمی ---------- */
function accsoft_wl_page($title, $body) {
    nocache_headers(); header('Content-Type: text/html; charset=utf-8');
    echo '<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' . esc_html($title) . '</title>
    <style>body{font-family:Tahoma,Arial,sans-serif;background:#eef2ff;margin:0;padding:24px}.c{max-width:520px;margin:auto;background:#fff;border-radius:14px;padding:26px;box-shadow:0 4px 24px #0001}
    input,select{width:100%;padding:10px;margin:4px 0 12px;border:1px solid #ccd;border-radius:8px;box-sizing:border-box}button,.b{background:#6c63ff;color:#fff;border:0;border-radius:8px;padding:11px 18px;cursor:pointer;text-decoration:none;display:inline-block}
    .e{background:#fee2e2;color:#991b1b;padding:10px;border-radius:8px;margin-bottom:12px}.k{background:#f5f3ff;border:1px dashed #c4b5fd;padding:12px;font-family:monospace;direction:ltr;text-align:center;font-size:16px;margin:12px 0}
    label.p{display:block;border:1px solid #ccd;border-radius:10px;padding:10px;margin:6px 0;cursor:pointer}</style></head><body><div class="c">' . $body . '</div></body></html>'; exit;
}
function accsoft_wl_err($t, $m, $extra = '') { accsoft_wl_page($t, '<h2>' . esc_html($t) . '</h2><p>' . esc_html($m) . '</p>' . $extra); }
function accsoft_wl_return($url, $key, $product) {
    $sep = strpos($url, '?') !== false ? '&' : '?';
    return $url . $sep . http_build_query(['wccp_activate' => '1', 'wccp_key' => $key, 'wbl_product' => $product]);
}

function accsoft_wl_pay() {
    global $wpdb; $P = accsoft_t('wpay'); $self = home_url('/license-server/pay/');
    $plugin = strtolower(preg_replace('/[^a-z0-9_-]/i', '', $_GET['plugin'] ?? 'wccp'));
    $product = accsoft_wl_product($plugin); $merchant = trim((string)accsoft_setting('zibal_merchant'));
    if (!$product) accsoft_wl_err('خطا', 'محصول نامعتبر است.');
    $plan = preg_replace('/[^a-z0-9_-]/i', '', $_GET['plan'] ?? '');

    if (isset($_GET['zibal_cb'])) {                       // بازگشت از زیبال
        $track = preg_replace('/[^0-9]/', '', (string)($_GET['trackId'] ?? ''));
        $pay = $track ? $wpdb->get_row($wpdb->prepare("SELECT * FROM $P WHERE track_id=%s", $track), ARRAY_A) : null;
        if (!$pay) accsoft_wl_err('خطا', 'اطلاعات پرداخت یافت نشد.');
        $lic = null;
        if ($pay['status'] === 'paid' && $pay['license_key']) { $lic = accsoft_wl_find($pay['license_key']); }
        else {
            if ((int)($_GET['success'] ?? 0) !== 1) { $wpdb->update($P, ['status' => 'failed'], ['track_id' => $track, 'status' => 'pending']);
                accsoft_wl_err('پرداخت ناموفق', 'پرداخت لغو شد یا با خطا مواجه شد.', '<a class="b" href="' . esc_url(add_query_arg(['plugin' => $pay['plugin'], 'domain' => $pay['domain'], 'return' => $pay['return_url'], 'plan' => $pay['plan']], $self)) . '">تلاش مجدد</a>'); }
            $r = wp_remote_post('https://gateway.zibal.ir/v1/verify', ['timeout' => 20, 'headers' => ['Content-Type' => 'application/json'], 'body' => wp_json_encode(['merchant' => $merchant, 'trackId' => (int)$track])]);
            $v = is_wp_error($r) ? [] : (json_decode(wp_remote_retrieve_body($r), true) ?: []);
            if (!in_array((int)($v['result'] ?? 0), [100, 201], true) || (int)($v['amount'] ?? 0) !== (int)$pay['amount']) accsoft_wl_err('خطای تأیید', 'پرداخت تأیید نشد. کد: ' . (int)($v['result'] ?? 0));
            if ($wpdb->query($wpdb->prepare("UPDATE $P SET status='processing' WHERE track_id=%s AND status='pending'", $track)) === 1) {
                if ((int)$pay['months'] > 0) $lic = accsoft_wl_extend($pay['email'], $pay['plugin'], (int)$pay['months'], $pay['domain'], 'اشتراک ' . ($pay['plan'] ?: $pay['months'] . 'm'));
                elseif ($pay['plan'] && accsoft_wl_has_plans($pay['plugin'])) $lic = accsoft_wl_lifetime($pay['email'], $pay['plugin'], $pay['domain'], 'لایسنس دائمی (' . $pay['plan'] . ')');
                else { $lic = accsoft_wl_create($pay['email'], $pay['plugin']); accsoft_wl_activate($lic['license_key'], $pay['domain'], ''); }
                $wpdb->update($P, ['status' => 'paid', 'license_key' => $lic['license_key']], ['track_id' => $track]);
                accsoft_wl_mail($lic, $pay['domain']);
                if ($pay['coupon_id']) $wpdb->query($wpdb->prepare("UPDATE " . accsoft_t('wcoupon') . " SET used_count=used_count+1 WHERE uid=%s", $pay['coupon_id']));
            } else { $pay = $wpdb->get_row($wpdb->prepare("SELECT * FROM $P WHERE track_id=%s", $track), ARRAY_A); $lic = $pay['license_key'] ? accsoft_wl_find($pay['license_key']) : null; }
        }
        if (!$lic) accsoft_wl_err('در حال پردازش', 'پرداخت ثبت شد؛ چند لحظه بعد صفحه را دوباره باز کنید یا ایمیل خود را بررسی کنید.');
        $go = $pay['return_url'] ? accsoft_wl_return($pay['return_url'], $lic['license_key'], $pay['plugin']) : '';
        accsoft_wl_page('پرداخت موفق', '<h2>لایسنس فعال شد ✅</h2><div class="k">' . esc_html($lic['license_key']) . '</div><p>' . ($lic['expires_at'] ? 'اعتبار تا: ' . esc_html($lic['expires_at']) : '♾ لایسنس مادام‌العمر') . '</p>
          <p>این کلید را در افزونهٔ سایت خود وارد کنید. <a href="' . esc_url(accsoft_portal_url()) . '">پیشخوان مشتری</a></p>'
          . ($go ? '<p>⏳ در حال انتقال به سایت شما...</p><script>setTimeout(function(){location=' . wp_json_encode($go) . '},4000)</script>' : ''));
    }

    $err = ''; $has = accsoft_wl_has_plans($plugin);
    if ($has && !accsoft_wl_plan($plugin, $plan)) $plan = accsoft_wl_default_plan($plugin);
    if (!$has) $plan = '';
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {          // شروع پرداخت
        if (!wp_verify_nonce($_POST['_n'] ?? '', 'accsoft_wl_pay')) accsoft_wl_err('خطا', 'نشست منقضی شده؛ صفحه را دوباره باز کنید.');
        $email = filter_var(trim($_POST['email'] ?? ''), FILTER_VALIDATE_EMAIL); $dom = trim($_POST['domain'] ?? '');
        $plan = $has ? preg_replace('/[^a-z0-9_-]/i', '', $_POST['plan'] ?? '') : ''; if ($has && !accsoft_wl_plan($plugin, $plan)) $plan = accsoft_wl_default_plan($plugin);
        $cd = accsoft_wl_clean_domain($dom); $base = accsoft_wl_amount($plugin, $plan);
        if (!$email || !$cd) $err = 'ایمیل یا دامنه معتبر نیست.';
        elseif ($base <= 0) $err = 'قیمت این محصول تنظیم نشده است.';
        elseif ($merchant === '') $err = 'درگاه پرداخت تنظیم نشده است.';
        elseif (!$has && accsoft_wl_find_by($email, '', $plugin)) $err = 'این ایمیل قبلاً لایسنس فعال دارد؛ از پیشخوان مشتری یا پشتیبانی کلید را بگیرید.';
        elseif (!$has && accsoft_wl_find_by('', $cd, $plugin)) $err = 'این دامنه قبلاً لایسنس فعال دارد؛ برای انتقال با پشتیبانی تماس بگیرید.';
        else {
            $final = $base; $ci = null; $code = trim($_POST['coupon_code'] ?? '');
            if ($code !== '') { $ci = accsoft_wl_coupon_validate($code, $plugin, $base); if (!$ci['valid']) $err = 'کد تخفیف: ' . $ci['message']; else $final = (int)$ci['final']; }
            if (!$err) {
                $pl = $plan ? accsoft_wl_plan($plugin, $plan) : null; $ret = esc_url_raw(trim($_POST['return_url'] ?? ''));
                $resp = wp_remote_post('https://gateway.zibal.ir/v1/request', ['timeout' => 20, 'headers' => ['Content-Type' => 'application/json'], 'body' => wp_json_encode([
                    'merchant' => $merchant, 'amount' => $final, 'callbackUrl' => add_query_arg(['zibal_cb' => 1, 'plugin' => $plugin, 'domain' => $dom, 'plan' => $plan], $self),
                    'description' => ($has ? 'پلن ' : 'لایسنس ') . $plugin . ' — ' . $dom])]);
                $j = is_wp_error($resp) ? [] : (json_decode(wp_remote_retrieve_body($resp), true) ?: []);
                if ((int)($j['result'] ?? -1) !== 100 || empty($j['trackId'])) $err = 'خطا در اتصال به درگاه. کد: ' . (int)($j['result'] ?? -1);
                else {
                    $wpdb->insert($P, ['track_id' => (string)$j['trackId'], 'plugin' => $plugin, 'email' => $email, 'domain' => $cd, 'return_url' => $ret, 'amount' => $final, 'base_amount' => $base,
                        'plan' => $plan ?: null, 'months' => $pl ? (int)$pl['months'] : 0, 'coupon_id' => $ci ? $ci['coupon']['uid'] : null, 'coupon_code' => $ci ? $ci['coupon']['code'] : null,
                        'coupon_discount' => $ci ? (int)$ci['discount'] : 0, 'status' => 'pending', 'created_at' => accsoft_now()]);
                    wp_redirect('https://gateway.zibal.ir/start/' . rawurlencode((string)$j['trackId'])); exit;
                }
            }
        }
    }
    $form = '<h2>' . esc_html(($product['icon'] ?? '') . ' ' . ($product['label'] ?? $plugin)) . '</h2><p>' . esc_html($product['desc'] ?? '') . '</p>' . ($err ? '<div class="e">' . esc_html($err) . '</div>' : '')
        . '<form method="post">' . wp_nonce_field('accsoft_wl_pay', '_n', true, false) . '<input type="hidden" name="return_url" value="' . esc_attr($_GET['return'] ?? ($_POST['return_url'] ?? '')) . '">';
    if ($has) { foreach ($product['plans'] as $id => $pl) $form .= '<label class="p"><input type="radio" name="plan" value="' . esc_attr($id) . '" style="width:auto"' . checked($plan, $id, false) . '> <b>' . esc_html($pl['label']) . '</b> — ' . number_format($pl['price'] / 10) . ' تومان<br><small>' . esc_html($pl['hint'] ?? '') . '</small></label>'; }
    else $form .= '<p><b>' . number_format(accsoft_wl_amount($plugin) / 10) . ' تومان</b></p>';
    $form .= 'ایمیل<input name="email" type="email" required value="' . esc_attr($_POST['email'] ?? '') . '" style="direction:ltr">دامنهٔ سایت<input name="domain" required placeholder="example.com" value="' . esc_attr($_POST['domain'] ?? ($_GET['domain'] ?? '')) . '" style="direction:ltr">
      🎟️ کد تخفیف (اختیاری)<input name="coupon_code" value="' . esc_attr($_POST['coupon_code'] ?? '') . '" style="direction:ltr;text-transform:uppercase"><button>پرداخت</button></form>';
    accsoft_wl_page('پرداخت', $form);
}
