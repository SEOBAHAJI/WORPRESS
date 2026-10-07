<?php
if (!defined('ABSPATH')) exit;
/* پنل مدیریت: منوی «لایسنس AccSoft» (فقط manage_options) */

add_action('admin_menu', function () {
    add_menu_page('لایسنس AccSoft', 'لایسنس AccSoft', 'manage_options', 'accsoft', 'accsoft_admin_page', 'dashicons-admin-network', 58);
});
add_action('admin_notices', function () {
    if (!current_user_can('manage_options')) return;
    if (!accsoft_pubkey_hex()) echo '<div class="notice notice-error"><p><b>AccSoft:</b> کلید خصوصی تنظیم نشده؛ لایسنس صادر نمی‌شود. به تب «تنظیمات و کلید» بروید.</p></div>';
});

function accsoft_admin_guard($action) {
    if (!current_user_can('manage_options')) wp_die('دسترسی ندارید', 403);
    check_admin_referer($action, '_n');
}
function accsoft_admin_back($tab, $msg = '', $err = false) {
    if ($msg) set_transient('accsoft_admin_msg', ($err ? '!' : '') . $msg, 120);
    wp_safe_redirect(admin_url('admin.php?page=accsoft&tab=' . $tab)); exit;
}
function accsoft_form($action, $inner, $attrs = '') {
    return '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '" ' . $attrs . '><input type="hidden" name="action" value="' . esc_attr($action) . '">'
        . wp_nonce_field($action, '_n', true, false) . $inner . '</form>';
}
const ACCSOFT_SLUG = '/^[a-z0-9][a-z0-9-]{1,39}$/';

function accsoft_admin_page() {
    if (!current_user_can('manage_options')) return;
    global $wpdb;
    $tab = sanitize_key($_GET['tab'] ?? 'home');
    $tabs = ['home' => 'نمای کلی', 'products' => 'محصولات و پلن‌ها', 'licenses' => 'لایسنس‌ها', 'orders' => 'سفارش‌ها', 'settings' => 'تنظیمات و کلید'];
    echo '<div class="wrap" dir="rtl"><h1>لایسنس AccSoft</h1><h2 class="nav-tab-wrapper">';
    foreach ($tabs as $k => $t) echo '<a class="nav-tab' . ($tab === $k ? ' nav-tab-active' : '') . '" href="' . esc_url(admin_url('admin.php?page=accsoft&tab=' . $k)) . '">' . esc_html($t) . '</a>';
    echo '</h2>';
    $msg = get_transient('accsoft_admin_msg');
    if ($msg) { delete_transient('accsoft_admin_msg'); echo '<div class="notice notice-' . ($msg[0] === '!' ? 'error' : 'success') . '"><p>' . esc_html(ltrim($msg, '!')) . '</p></div>'; }
    $L = accsoft_t('licenses'); $O = accsoft_t('orders');

    if ($tab === 'home') {
        $a = (int)$wpdb->get_var("SELECT COUNT(*) FROM $L WHERE status='active' AND (expires IS NULL OR expires>='" . esc_sql(accsoft_today()) . "')");
        $all = (int)$wpdb->get_var("SELECT COUNT(*) FROM $L"); $rev = (int)$wpdb->get_var("SELECT COUNT(*) FROM $L WHERE status IN ('revoked','replaced')");
        $inc = (int)$wpdb->get_var("SELECT COALESCE(SUM(amount),0) FROM $O WHERE status='paid'");
        $m = (int)$wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(amount),0) FROM $O WHERE status='paid' AND paid_at>=%s", gmdate('Y-m-01')));
        $soon = $wpdb->get_results($wpdb->prepare("SELECT * FROM $L WHERE status='active' AND expires BETWEEN %s AND %s ORDER BY expires", accsoft_today(), accsoft_add_months(accsoft_today(), 1)), ARRAY_A);
        echo '<p>لایسنس فعال: <b>' . $a . '</b> | کل صادرشده: <b>' . $all . '</b> | ابطال/منتقل: <b>' . $rev . '</b> | درآمد کل: <b>' . number_format_i18n($inc) . '</b> تومان | این ماه: <b>' . number_format_i18n($m) . '</b></p>';
        echo '<h3>در یک ماه آینده منقضی می‌شوند</h3><table class="widefat"><tr><th>مشتری</th><th>محصول</th><th>انقضا</th></tr>';
        foreach ($soon as $l) echo '<tr><td>' . esc_html($l['name']) . '</td><td>' . esc_html($l['product'] . '/' . $l['plan']) . '</td><td>' . esc_html(accsoft_jdate($l['expires'])) . '</td></tr>';
        echo '</table>';
        echo '<p>نسخهٔ کاتالوگ منتشرشده: ' . (int)get_option('accsoft_catalog_version', 0) . ' — آدرس‌های برنامه: <code>' . esc_html(rest_url('accsoft/v1/catalog')) . '</code> و <code>' . esc_html(rest_url('accsoft/v1/license')) . '</code></p>';
    }

    if ($tab === 'products') {
        $inner = '';
        $prods = accsoft_products(); $prods[] = ['id' => '', 'name' => '', 'kind' => 'plugin', 'description' => '', 'trial_days' => 0, 'plans' => []];
        foreach ($prods as $i => $p) {
            $plans = $p['plans']; $plans[] = ['id' => '', 'title' => '', 'months' => '', 'price' => '', 'features' => []]; $plans[] = $plans[count($plans) - 1];
            $inner .= '<div class="card" style="max-width:none"><h3>' . ($p['id'] ? esc_html($p['name']) : 'افزودن محصول/افزونهٔ جدید (بدون کدنویسی)') . '</h3>
              <input name="p[' . $i . '][id]" value="' . esc_attr($p['id']) . '" placeholder="شناسه (انگلیسی کوچک)" ' . ($p['id'] ? 'readonly' : '') . ' style="direction:ltr">
              <input name="p[' . $i . '][name]" value="' . esc_attr($p['name']) . '" placeholder="نام">
              <select name="p[' . $i . '][kind]"><option value="app"' . selected($p['kind'], 'app', false) . '>برنامهٔ اصلی</option><option value="plugin"' . selected($p['kind'], 'plugin', false) . '>افزونه</option></select>
              روز آزمایشی <input type="number" min="0" name="p[' . $i . '][trial_days]" value="' . (int)$p['trial_days'] . '" style="width:70px">
              <input name="p[' . $i . '][description]" value="' . esc_attr($p['description'] ?? '') . '" placeholder="توضیح" style="width:260px">';
            if ($p['id']) $inner .= ' <label><input type="checkbox" name="p[' . $i . '][del]" value="1"> حذف محصول</label>';
            $inner .= '<table class="widefat"><tr><th>شناسهٔ پلن</th><th>عنوان</th><th>ماه (خالی=مادام‌العمر)</th><th>قیمت تومان</th><th>ویژگی‌ها (با کاما)</th></tr>';
            foreach (array_slice($plans, 0, count($plans) - 1) as $j => $pl) {
                $n = 'p[' . $i . '][plans][' . $j . ']';
                $inner .= '<tr><td><input name="' . $n . '[id]" value="' . esc_attr($pl['id']) . '" style="direction:ltr;width:100px"></td><td><input name="' . $n . '[title]" value="' . esc_attr($pl['title']) . '"></td>
                  <td><input name="' . $n . '[months]" value="' . esc_attr($pl['months'] ?? '') . '" style="width:70px"></td><td><input name="' . $n . '[price]" value="' . esc_attr($pl['price']) . '"></td>
                  <td><input name="' . $n . '[features]" value="' . esc_attr(implode(',', $pl['features'] ?? [])) . '" style="direction:ltr"></td></tr>';
            }
            $inner .= '</table><small>برای حذف پلن، شناسهٔ آن را خالی کنید.</small></div>';
        }
        echo '<p>تغییرات پس از ذخیره امضا و منتشر می‌شود؛ برنامه‌ها با «به‌روزرسانی کاتالوگ» آن را می‌گیرند.</p>';
        echo accsoft_form('accsoft_save_products', $inner . '<p><button class="button button-primary">ذخیره و انتشار کاتالوگ</button></p>');
    }

    if ($tab === 'licenses') {
        $q = sanitize_text_field($_GET['q'] ?? '');
        $rows = $q ? $wpdb->get_results($wpdb->prepare("SELECT * FROM $L WHERE name LIKE %s OR lid=%s OR mid=%s ORDER BY id DESC LIMIT 200", '%' . $wpdb->esc_like($q) . '%', $q, strtoupper($q)), ARRAY_A)
                   : $wpdb->get_results("SELECT * FROM $L ORDER BY id DESC LIMIT 200", ARRAY_A);
        echo '<form method="get"><input type="hidden" name="page" value="accsoft"><input type="hidden" name="tab" value="licenses"><input name="q" value="' . esc_attr($q) . '" placeholder="جستجو: نام / شمارهٔ لایسنس / شناسهٔ سیستم"> <button class="button">جستجو</button></form>';
        $opts = '';
        foreach (accsoft_products() as $p) foreach ($p['plans'] as $pl) $opts .= '<option value="' . esc_attr($p['id'] . '|' . $pl['id']) . '">' . esc_html($p['name'] . ' — ' . $pl['title']) . '</option>';
        echo '<h3>صدور دستی</h3>' . accsoft_form('accsoft_issue', '<select name="pp">' . $opts . '</select> <input name="name" placeholder="نام مشتری" required>
          <input name="mid" placeholder="شناسهٔ سیستم (اختیاری)" maxlength="16" style="direction:ltr"> <input name="user" placeholder="نام کاربری یا ایمیل سایت (اختیاری)">
          <button class="button button-primary">صدور</button>');
        echo '<table class="widefat striped"><tr><th>#</th><th>مشتری</th><th>محصول/پلن</th><th>سیستم</th><th>انقضا</th><th>وضعیت</th><th>عملیات</th></tr>';
        foreach ($rows as $l) {
            $act = $l['status'] === 'active' ? accsoft_form('accsoft_lic_act', '<input type="hidden" name="id" value="' . (int)$l['id'] . '"><input type="hidden" name="do" value="revoke"><button class="button">ابطال</button>', 'style="display:inline"')
                 : ($l['status'] === 'revoked' ? accsoft_form('accsoft_lic_act', '<input type="hidden" name="id" value="' . (int)$l['id'] . '"><input type="hidden" name="do" value="restore"><button class="button">بازگردانی</button>', 'style="display:inline"') : '');
            echo '<tr><td>' . esc_html($l['lid']) . '</td><td>' . esc_html($l['name']) . ' <small>(' . esc_html(accsoft_display_name($l['user_id'])) . ')</small></td><td>' . esc_html($l['product'] . '/' . $l['plan']) . '</td>
              <td dir="ltr">' . esc_html($l['mid'] ?: '—') . '</td><td>' . esc_html(accsoft_jdate($l['expires'])) . '</td><td>' . esc_html(accsoft_license_state($l)) . '</td>
              <td>' . $act . ' <details><summary>کد</summary><code style="word-break:break-all;display:block;max-width:420px">' . esc_html($l['license_key']) . '</code></details></td></tr>';
        }
        echo '</table>';
    }

    if ($tab === 'orders') {
        $rows = $wpdb->get_results("SELECT * FROM $O ORDER BY id DESC LIMIT 200", ARRAY_A);
        echo '<table class="widefat striped"><tr><th>کد</th><th>مشتری</th><th>محصول/پلن</th><th>مبلغ (تومان)</th><th>وضعیت</th><th>پیگیری زیبال</th><th>تاریخ</th></tr>';
        foreach ($rows as $o) echo '<tr><td>' . esc_html(substr($o['code'], 0, 8)) . '</td><td>' . esc_html(accsoft_display_name($o['user_id'])) . '</td><td>' . esc_html($o['product'] . '/' . $o['plan'] . ($o['renew_of'] ? ' (تمدید)' : '')) . '</td>
          <td>' . number_format_i18n($o['amount']) . '</td><td>' . esc_html($o['status']) . '</td><td>' . esc_html($o['track_id'] . ($o['ref_number'] ? ' / ' . $o['ref_number'] : '')) . '</td><td>' . esc_html($o['created']) . '</td></tr>';
        echo '</table>';
    }

    if ($tab === 'settings') {
        $pub = accsoft_pubkey_hex();
        echo '<h3>کلید امضا</h3>';
        if ($pub) {
            echo '<p>کلید فعال است. <b>کلید عمومی</b> (باید داخل <code>accsoft/pubkey.py</code> برنامه باشد):</p><code dir="ltr" style="display:block;word-break:break-all">' . esc_html($pub) . '</code>';
        } else {
            echo '<p>کلید خصوصی در <code>wp-config.php</code> تعریف نشده. اگر قبلاً با پنل محلی (<code>license_private.key</code>) کلید ساخته‌اید، همان ۶۴ نویسه را استفاده کنید تا لایسنس‌های قبلی معتبر بمانند؛ وگرنه کلید جدید بسازید:</p>'
                . (function_exists('sodium_crypto_sign_seed_keypair') ? accsoft_form('accsoft_newseed', '<button class="button">ساخت کلید جدید (فقط یک‌بار نمایش داده می‌شود)</button>') : '<p style="color:#b00">افزونهٔ sodium در PHP فعال نیست؛ از هاست بخواهید فعالش کنند.</p>');
            $seed = get_transient('accsoft_newseed_' . get_current_user_id());
            if ($seed) { delete_transient('accsoft_newseed_' . get_current_user_id());
                echo '<p>این خط را <b>بالای</b> عبارت «That\'s all, stop editing» در wp-config.php بگذارید و <b>از آن پشتیبان بگیرید</b> (گم شود، همهٔ لایسنس‌ها بی‌اعتبار می‌شوند):</p><code dir="ltr" style="display:block">define(\'ACCSOFT_SEED_HEX\', \'' . esc_html($seed) . '\');</code>'; }
        }
        $s = get_option('accsoft_settings', []);
        echo '<h3>درگاه و محدودیت‌ها</h3>' . accsoft_form('accsoft_save_settings',
            '<p>مرچنت زیبال: <input name="zibal_merchant" value="' . esc_attr($s['zibal_merchant'] ?? '') . '" style="direction:ltr"> <small>(برای آزمایش: zibal)</small></p>
             <p>حداکثر تعداد انتقال هر لایسنس: <input type="number" min="0" name="max_transfers" value="' . (int)($s['max_transfers'] ?? 2) . '" style="width:70px"></p>
             <p><button class="button button-primary">ذخیره</button></p>');
        echo '<p>صفحهٔ پیشخوان مشتری: <a href="' . esc_url(accsoft_portal_url()) . '">' . esc_html(accsoft_portal_url()) . '</a> (شورت‌کد <code>[accsoft_dashboard]</code>)</p>';
        echo '<h3>کاتالوگ</h3><p>' . accsoft_form('accsoft_republish', '<button class="button">انتشار مجدد کاتالوگ</button> ', 'style="display:inline"')
            . accsoft_form('accsoft_dl_catalog', '<button class="button">دانلود catalog.json (برای قرار دادن در بستهٔ برنامه)</button>', 'style="display:inline"') . '</p>';
    }
    echo '</div>';
}

add_action('admin_post_accsoft_save_products', function () {
    accsoft_admin_guard('accsoft_save_products');
    $out = []; $seen = [];
    foreach ((array)($_POST['p'] ?? []) as $p) {
        $id = sanitize_key($p['id'] ?? ''); if ($id === '' || !empty($p['del'])) continue;
        if (!preg_match(ACCSOFT_SLUG, $id) || isset($seen[$id])) accsoft_admin_back('products', "شناسهٔ محصول «$id» نامعتبر یا تکراری است", true);
        $seen[$id] = 1; $plans = []; $pseen = [];
        foreach ((array)($p['plans'] ?? []) as $pl) {
            $pid = sanitize_key($pl['id'] ?? ''); if ($pid === '') continue;
            if (!preg_match(ACCSOFT_SLUG, $pid) || isset($pseen[$pid])) accsoft_admin_back('products', "شناسهٔ پلن «$pid» نامعتبر یا تکراری است", true);
            $pseen[$pid] = 1; $months = trim((string)($pl['months'] ?? ''));
            if ($months !== '' && (!ctype_digit($months) || (int)$months < 1 || (int)$months > 600)) accsoft_admin_back('products', "مدت پلن «$pid» نامعتبر است", true);
            $price = trim((string)($pl['price'] ?? '0')); if (!ctype_digit($price)) accsoft_admin_back('products', "قیمت پلن «$pid» باید عدد صحیح تومان باشد", true);
            $feat = array_values(array_filter(array_map('sanitize_key', explode(',', (string)($pl['features'] ?? '')))));
            $plans[] = ['id' => $pid, 'title' => sanitize_text_field($pl['title'] ?? $pid) ?: $pid, 'months' => $months === '' ? null : (int)$months, 'price' => (int)$price, 'features' => $feat];
        }
        $kind = ($p['kind'] ?? '') === 'app' ? 'app' : 'plugin';
        $out[] = ['id' => $id, 'name' => sanitize_text_field($p['name'] ?? '') ?: $id, 'kind' => $kind, 'description' => sanitize_text_field($p['description'] ?? ''),
                  'trial_days' => max(0, (int)($p['trial_days'] ?? 0)), 'plans' => $plans];
    }
    update_option('accsoft_products', $out, false);
    $r = accsoft_publish();
    accsoft_admin_back('products', $r === true ? 'ذخیره و کاتالوگ منتشر شد' : $r, $r !== true);
});

add_action('admin_post_accsoft_issue', function () {
    accsoft_admin_guard('accsoft_issue');
    try {
        [$prod, $plan] = array_pad(explode('|', (string)($_POST['pp'] ?? '')), 2, '');
        $pl = accsoft_plan($prod, $plan); if (!$pl) throw new Exception('پلن نامعتبر');
        $mid = strtoupper(trim((string)($_POST['mid'] ?? ''))); if (!accsoft_valid_mid($mid)) throw new Exception('شناسهٔ سیستم نامعتبر');
        $u = trim((string)($_POST['user'] ?? '')); $uid = 0;
        if ($u !== '') { $usr = get_user_by('login', $u) ?: get_user_by('email', $u); if (!$usr) throw new Exception('کاربر سایت پیدا نشد'); $uid = $usr->ID; }
        $exp = $pl['months'] ? accsoft_add_months(accsoft_today(), (int)$pl['months']) : null;
        accsoft_issue($uid, $prod, $plan, sanitize_text_field($_POST['name'] ?? ''), $mid, $exp);
        accsoft_admin_back('licenses', 'لایسنس صادر شد');
    } catch (Exception $e) { accsoft_admin_back('licenses', $e->getMessage(), true); }
});

add_action('admin_post_accsoft_lic_act', function () {
    accsoft_admin_guard('accsoft_lic_act'); global $wpdb;
    $l = accsoft_license((int)($_POST['id'] ?? 0)); if (!$l) accsoft_admin_back('licenses', 'پیدا نشد', true);
    $do = $_POST['do'] ?? '';
    if ($do === 'revoke' && $l['status'] === 'active') $wpdb->update(accsoft_t('licenses'), ['status' => 'revoked'], ['id' => $l['id']]);
    elseif ($do === 'restore' && $l['status'] === 'revoked') $wpdb->update(accsoft_t('licenses'), ['status' => 'active'], ['id' => $l['id']]);
    else accsoft_admin_back('licenses', 'عملیات مجاز نیست', true);
    $r = accsoft_publish();
    accsoft_admin_back('licenses', $r === true ? 'انجام شد و کاتالوگ منتشر شد (برنامه‌ها پس از دریافت کاتالوگ اعمال می‌کنند)' : $r, $r !== true);
});

add_action('admin_post_accsoft_save_settings', function () {
    accsoft_admin_guard('accsoft_save_settings');
    accsoft_set_settings(['zibal_merchant' => preg_replace('/[^A-Za-z0-9_-]/', '', (string)($_POST['zibal_merchant'] ?? '')), 'max_transfers' => max(0, (int)($_POST['max_transfers'] ?? 2))]);
    accsoft_admin_back('settings', 'ذخیره شد');
});
add_action('admin_post_accsoft_newseed', function () {
    accsoft_admin_guard('accsoft_newseed');
    if (accsoft_seed()) accsoft_admin_back('settings', 'کلید از قبل تعریف شده است', true);
    set_transient('accsoft_newseed_' . get_current_user_id(), bin2hex(random_bytes(32)), 300);
    accsoft_admin_back('settings');
});
add_action('admin_post_accsoft_republish', function () {
    accsoft_admin_guard('accsoft_republish'); $r = accsoft_publish();
    accsoft_admin_back('settings', $r === true ? 'منتشر شد' : $r, $r !== true);
});
add_action('admin_post_accsoft_dl_catalog', function () {
    accsoft_admin_guard('accsoft_dl_catalog');
    $raw = get_option('accsoft_catalog_doc'); if (!$raw) accsoft_admin_back('settings', 'کاتالوگی منتشر نشده', true);
    nocache_headers(); header('Content-Type: application/json'); header('Content-Disposition: attachment; filename="catalog.json"'); echo $raw; exit;
});
