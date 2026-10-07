<?php
if (!defined('ABSPATH')) exit;
/* پنل مدیریت و پیشخوان مشتری برای لایسنس‌های افزونه‌های وردپرسی + درون‌ریزی دادهٔ سرور قبلی */

/** درون‌ریزی دادهٔ licenses.json سرور قبلی (لایسنس‌ها، فعال‌سازی‌ها، پرداخت‌ها، کدهای تخفیف). تکراری‌ها رد می‌شوند. */
function accsoft_wl_import($d) {
    global $wpdb; $n = ['licenses' => 0, 'activations' => 0, 'payments' => 0, 'coupons' => 0, 'skipped' => 0];
    $s = function ($v) { return $v === null ? null : (string)$v; };
    $dt = function ($v) { return $v ? gmdate('Y-m-d H:i:s', strtotime((string)$v)) : accsoft_now(); };
    foreach ((array)($d['licenses'] ?? []) as $l) {
        if (empty($l['license_key']) || accsoft_wl_find($l['license_key'])) { $n['skipped']++; continue; }
        $wpdb->insert(accsoft_t('wlic'), ['uid' => $s($l['id'] ?? uniqid()), 'license_key' => $s($l['license_key']), 'email' => strtolower($s($l['email'] ?? '')), 'product' => strtolower($s($l['product'] ?? '')),
            'note' => $s($l['note'] ?? ''), 'status' => $s($l['status'] ?? 'active'), 'expires_at' => !empty($l['expires_at']) ? gmdate('Y-m-d', strtotime($l['expires_at'])) : null, 'created_at' => $dt($l['created_at'] ?? null)]);
        $n['licenses']++;
    }
    foreach ((array)($d['activations'] ?? []) as $a) {
        if (empty($a['license_key']) || empty($a['domain'])) continue;
        $dom = accsoft_wl_clean_domain($a['domain']);
        if ($wpdb->get_var($wpdb->prepare("SELECT id FROM " . accsoft_t('wact') . " WHERE license_key=%s AND domain=%s", $a['license_key'], $dom))) { $n['skipped']++; continue; }
        $wpdb->insert(accsoft_t('wact'), ['license_key' => $s($a['license_key']), 'domain' => $dom, 'ip' => $s($a['ip'] ?? ''), 'activated_at' => $dt($a['activated_at'] ?? null)]);
        $n['activations']++;
    }
    foreach ((array)($d['payments'] ?? []) as $p) {
        if (empty($p['track_id']) || $wpdb->get_var($wpdb->prepare("SELECT id FROM " . accsoft_t('wpay') . " WHERE track_id=%s", (string)$p['track_id']))) { $n['skipped']++; continue; }
        $wpdb->insert(accsoft_t('wpay'), ['track_id' => $s($p['track_id']), 'plugin' => $s($p['plugin'] ?? ''), 'email' => strtolower($s($p['email'] ?? '')), 'domain' => $s($p['domain'] ?? ''),
            'return_url' => $s($p['return_url'] ?? ''), 'amount' => (int)($p['amount'] ?? 0), 'base_amount' => (int)($p['base_amount'] ?? ($p['amount'] ?? 0)), 'plan' => $s($p['plan'] ?? null), 'months' => (int)($p['months'] ?? 0),
            'coupon_id' => $s($p['coupon_id'] ?? null), 'coupon_code' => $s($p['coupon_code'] ?? null), 'coupon_discount' => (int)($p['coupon_discount'] ?? 0), 'status' => $s($p['status'] ?? 'pending'),
            'license_key' => $s($p['license_key'] ?? null), 'created_at' => $dt($p['created_at'] ?? null)]);
        $n['payments']++;
    }
    foreach ((array)($d['coupons'] ?? []) as $c) {
        if (empty($c['code']) || accsoft_wl_coupon($c['code'])) { $n['skipped']++; continue; }
        $wpdb->insert(accsoft_t('wcoupon'), ['uid' => $s($c['id'] ?? uniqid()), 'code' => strtoupper($s($c['code'])), 'type' => ($c['type'] ?? '') === 'fixed' ? 'fixed' : 'percent', 'value' => (int)($c['value'] ?? 0),
            'product' => $s($c['product'] ?? 'all'), 'max_uses' => (int)($c['max_uses'] ?? 0), 'used_count' => (int)($c['used_count'] ?? 0), 'min_amount' => (int)($c['min_amount'] ?? 0),
            'expires_at' => !empty($c['expires_at']) ? gmdate('Y-m-d', strtotime($c['expires_at'])) : null, 'status' => ($c['status'] ?? '') === 'disabled' ? 'disabled' : 'active', 'note' => $s($c['note'] ?? ''), 'created_at' => $dt($c['created_at'] ?? null)]);
        $n['coupons']++;
    }
    return $n;
}

/** اگر فایل includes/legacy-import.php (همراه بستهٔ مهاجرت) باشد، یک‌بار خودکار درون‌ریزی و فایل حذف می‌شود */
add_action('admin_init', function () {
    $f = ACCSOFT_DIR . 'includes/legacy-import.php';
    if (!current_user_can('manage_options') || !is_readable($f) || get_option('accsoft_wl_imported')) return;
    $data = include $f; if (!is_array($data)) return;
    $n = accsoft_wl_import($data); update_option('accsoft_wl_imported', gmdate('c'), false);
    @unlink($f); set_transient('accsoft_admin_msg', 'درون‌ریزی خودکار: ' . $n['licenses'] . ' لایسنس، ' . $n['activations'] . ' فعال‌سازی، ' . $n['payments'] . ' پرداخت، ' . $n['coupons'] . ' کد تخفیف', 300);
});

function accsoft_wl_admin_page($sub) {
    global $wpdb; $L = accsoft_t('wlic'); $A = accsoft_t('wact');
    $subs = ['lic' => 'لایسنس‌ها', 'prod' => 'محصولات و قیمت', 'pay' => 'پرداخت‌ها', 'coupon' => 'کد تخفیف', 'set' => 'تنظیمات و درون‌ریزی'];
    echo '<p>';
    foreach ($subs as $k => $t) echo '<a class="button' . ($sub === $k ? ' button-primary' : '') . '" href="' . esc_url(admin_url('admin.php?page=accsoft&tab=legacy&sub=' . $k)) . '">' . esc_html($t) . '</a> ';
    echo '</p>';
    $F = function ($do, $inner, $attrs = '') { return accsoft_form('accsoft_wl', '<input type="hidden" name="do" value="' . esc_attr($do) . '">' . $inner, $attrs); };

    if ($sub === 'lic') {
        $q = sanitize_text_field($_GET['q'] ?? '');
        $rows = $q ? $wpdb->get_results($wpdb->prepare("SELECT * FROM $L WHERE email LIKE %s OR license_key LIKE %s OR product=%s OR license_key IN (SELECT license_key FROM $A WHERE domain LIKE %s) ORDER BY id DESC LIMIT 300",
                    '%' . $wpdb->esc_like($q) . '%', '%' . $wpdb->esc_like($q) . '%', strtolower($q), '%' . $wpdb->esc_like($q) . '%'), ARRAY_A)
                   : $wpdb->get_results("SELECT * FROM $L ORDER BY id DESC LIMIT 300", ARRAY_A);
        echo '<form method="get"><input type="hidden" name="page" value="accsoft"><input type="hidden" name="tab" value="legacy"><input type="hidden" name="sub" value="lic"><input name="q" value="' . esc_attr($q) . '" placeholder="ایمیل / کلید / دامنه / محصول"> <button class="button">جستجو</button></form>';
        $opts = ''; foreach (accsoft_wl_products() as $slug => $p) $opts .= '<option value="' . esc_attr($slug) . '">' . esc_html($p['label'] ?? $slug) . '</option>';
        echo '<h3>ایجاد لایسنس دستی</h3>' . $F('create', '<input name="email" type="email" placeholder="ایمیل" required> <select name="product">' . $opts . '</select> <input name="domain" placeholder="دامنه (اختیاری)" style="direction:ltr">
            <input name="expires_at" placeholder="انقضا YYYY-MM-DD (خالی=دائمی)" style="direction:ltr"> <input name="note" placeholder="یادداشت"> <button class="button button-primary">ایجاد</button>');
        echo '<table class="widefat striped"><tr><th>کلید</th><th>ایمیل</th><th>محصول</th><th>دامنه‌ها</th><th>انقضا</th><th>وضعیت</th><th>عملیات</th></tr>';
        foreach ($rows as $l) {
            $acts = accsoft_wl_acts($l['license_key']); $ds = '';
            foreach ($acts as $a) $ds .= '<div dir="ltr">' . esc_html($a['domain']) . ' ' . $F('unact', '<input type="hidden" name="key" value="' . esc_attr($l['license_key']) . '"><input type="hidden" name="domain" value="' . esc_attr($a['domain']) . '"><button class="button-link" title="حذف فعال‌سازی">✖</button>', 'style="display:inline"') . '</div>';
            $btns = $F($l['status'] === 'active' ? 'revoke' : 'restore', '<input type="hidden" name="key" value="' . esc_attr($l['license_key']) . '"><button class="button">' . ($l['status'] === 'active' ? 'ابطال' : 'بازگردانی') . '</button>', 'style="display:inline"')
                  . $F('delete', '<input type="hidden" name="key" value="' . esc_attr($l['license_key']) . '"><button class="button" onclick="return confirm(\'حذف دائمی؟\')">حذف</button>', 'style="display:inline"');
            echo '<tr><td dir="ltr"><code>' . esc_html($l['license_key']) . '</code></td><td dir="ltr">' . esc_html($l['email']) . '</td><td>' . esc_html($l['product']) . '</td><td>' . ($ds ?: '—') . '</td><td>' . esc_html($l['expires_at'] ? accsoft_jdate($l['expires_at']) : 'دائمی') . '</td><td>' . esc_html($l['status']) . '</td><td>' . $btns . '</td></tr>';
        }
        echo '</table>';
    }

    if ($sub === 'prod') {
        echo '<p>قیمت‌ها به <b>تومان</b> وارد می‌شوند (داخلی ریال ذخیره می‌شود). برای حذف پلن، شناسه‌اش را خالی کنید. افزودن محصول جدید: ردیف خالی انتهای صفحه.</p>';
        $prods = accsoft_wl_products(); $prods[''] = ['label' => '', 'icon' => '', 'desc' => '', 'price' => 0, 'plans' => [], 'update' => []]; $i = 0; $inner = '';
        foreach ($prods as $slug => $p) {
            $u = $p['update'] ?? []; $plans = $p['plans'] ?? []; $plans['' ] = ['label' => '', 'months' => 1, 'price' => 0, 'hint' => '', 'badge' => ''];
            $n = "w[$i]"; $inner .= '<div class="card" style="max-width:none"><input name="' . $n . '[slug]" value="' . esc_attr($slug) . '" placeholder="slug" style="direction:ltr"> <input name="' . $n . '[label]" value="' . esc_attr($p['label'] ?? '') . '" placeholder="نام" style="width:260px">
              <input name="' . $n . '[icon]" value="' . esc_attr($p['icon'] ?? '') . '" style="width:50px"> <input name="' . $n . '[desc]" value="' . esc_attr($p['desc'] ?? '') . '" placeholder="توضیح" style="width:320px">
              قیمت (تومان، برای محصول بدون پلن): <input name="' . $n . '[price]" value="' . (int)(($p['price'] ?? 0) / 10) . '" style="width:110px"> ' . ($slug ? '<label><input type="checkbox" name="' . $n . '[del]" value="1"> حذف محصول</label>' : '') . '<br>
              به‌روزرسانی: نسخه <input name="' . $n . '[u_version]" value="' . esc_attr($u['version'] ?? '') . '" style="width:70px;direction:ltr"> لینک zip <input name="' . $n . '[u_package]" value="' . esc_attr($u['package'] ?? '') . '" style="width:340px;direction:ltr">
              WP≥ <input name="' . $n . '[u_requires]" value="' . esc_attr($u['requires'] ?? '5.8') . '" style="width:50px"> تست‌شده <input name="' . $n . '[u_tested]" value="' . esc_attr($u['tested'] ?? '6.6') . '" style="width:50px"> PHP≥ <input name="' . $n . '[u_php]" value="' . esc_attr($u['requires_php'] ?? '7.4') . '" style="width:50px"><br>
              <input name="' . $n . '[u_changelog]" value="' . esc_attr($u['changelog'] ?? '') . '" placeholder="تغییرات نسخه" style="width:90%">
              <table class="widefat"><tr><th>شناسهٔ پلن</th><th>عنوان</th><th>ماه (۰=دائمی)</th><th>قیمت تومان</th><th>توضیح</th><th>نشان</th></tr>';
            $j = 0; foreach ($plans as $pid => $pl) { $m = $n . "[plans][$j]"; $inner .= '<tr><td><input name="' . $m . '[id]" value="' . esc_attr($pid) . '" style="width:80px;direction:ltr"></td><td><input name="' . $m . '[label]" value="' . esc_attr($pl['label']) . '"></td><td><input name="' . $m . '[months]" value="' . (int)$pl['months'] . '" style="width:60px"></td><td><input name="' . $m . '[price]" value="' . (int)($pl['price'] / 10) . '" style="width:110px"></td><td><input name="' . $m . '[hint]" value="' . esc_attr($pl['hint'] ?? '') . '"></td><td><input name="' . $m . '[badge]" value="' . esc_attr($pl['badge'] ?? '') . '" style="width:80px"></td></tr>'; $j++; }
            $inner .= '</table></div>'; $i++;
        }
        echo $F('save_products', $inner . '<p><button class="button button-primary">ذخیره</button></p>');
    }

    if ($sub === 'pay') {
        $rows = $wpdb->get_results("SELECT * FROM " . accsoft_t('wpay') . " ORDER BY id DESC LIMIT 300", ARRAY_A);
        echo '<table class="widefat striped"><tr><th>پیگیری</th><th>محصول/پلن</th><th>ایمیل</th><th>دامنه</th><th>مبلغ (تومان)</th><th>تخفیف</th><th>وضعیت</th><th>کلید</th><th>تاریخ</th></tr>';
        foreach ($rows as $p) echo '<tr><td>' . esc_html($p['track_id']) . '</td><td>' . esc_html($p['plugin'] . ($p['plan'] ? '/' . $p['plan'] : '')) . '</td><td dir="ltr">' . esc_html($p['email']) . '</td><td dir="ltr">' . esc_html($p['domain']) . '</td><td>' . number_format_i18n($p['amount'] / 10) . '</td><td>' . esc_html($p['coupon_code'] ?: '—') . '</td><td>' . esc_html($p['status']) . '</td><td dir="ltr">' . esc_html($p['license_key'] ?: '—') . '</td><td>' . esc_html($p['created_at']) . '</td></tr>';
        echo '</table>';
    }

    if ($sub === 'coupon') {
        $rows = $wpdb->get_results("SELECT * FROM " . accsoft_t('wcoupon') . " ORDER BY id DESC", ARRAY_A);
        echo '<h3>ساخت کد تخفیف</h3>' . $F('coupon_add', '<input name="code" placeholder="کد (خالی=تصادفی)" style="direction:ltr"> <select name="type"><option value="percent">درصدی</option><option value="fixed">مبلغ ثابت (تومان)</option></select>
            <input name="value" placeholder="مقدار" style="width:90px"> <input name="product" placeholder="محصول (all)" value="all" style="width:120px;direction:ltr"> <input name="max_uses" placeholder="حداکثر استفاده" style="width:100px"> <input name="min_amount" placeholder="حداقل سفارش تومان" style="width:120px">
            <input name="expires_at" placeholder="انقضا YYYY-MM-DD" style="direction:ltr"> <input name="note" placeholder="یادداشت"> <button class="button button-primary">ساخت</button>');
        echo '<table class="widefat striped"><tr><th>کد</th><th>نوع/مقدار</th><th>محصول</th><th>استفاده</th><th>انقضا</th><th>وضعیت</th><th></th></tr>';
        foreach ($rows as $c) echo '<tr><td dir="ltr"><b>' . esc_html($c['code']) . '</b></td><td>' . ($c['type'] === 'percent' ? (int)$c['value'] . '٪' : number_format_i18n($c['value'] / 10) . ' تومان') . '</td><td>' . esc_html($c['product']) . '</td><td>' . (int)$c['used_count'] . '/' . ((int)$c['max_uses'] ?: '∞') . '</td><td>' . esc_html($c['expires_at'] ?: '—') . '</td><td>' . esc_html($c['status']) . '</td><td>'
            . $F('coupon_toggle', '<input type="hidden" name="id" value="' . (int)$c['id'] . '"><button class="button">فعال/غیرفعال</button>', 'style="display:inline"') . $F('coupon_del', '<input type="hidden" name="id" value="' . (int)$c['id'] . '"><button class="button">حذف</button>', 'style="display:inline"') . '</td></tr>';
        echo '</table>';
    }

    if ($sub === 'set') {
        echo '<h3>اتصال افزونه‌های قدیمی</h3><p>آدرس API (همان آدرس قبلی): <code>' . esc_html(home_url('/license-server/api/')) . '</code> — جایگزین: <code>' . esc_html(rest_url('accsoft/v1/legacy')) . '</code><br>
          <b>مهم:</b> این آدرس‌ها فقط وقتی به این افزونه می‌رسند که پوشهٔ فیزیکی قدیمی <code>license-server/</code> روی هاست دیگر پوشه‌های <code>api</code>، <code>pay</code>، <code>portal</code> و فایل index.php نداشته باشد (پوشهٔ <code>updates</code> با فایل‌های zip می‌تواند بماند).</p>';
        echo $F('save_wset', '<p>کلید مخفی API (برای create/revoke/coupon_list): <input name="secret" value="' . esc_attr(accsoft_setting('wl_api_secret')) . '" style="direction:ltr;width:320px"> <small>خالی = این عملیات غیرفعال</small></p>
            <p>آدرس پایهٔ سایت: <input name="base" value="' . esc_attr(accsoft_setting('wl_base', 'https://webakery.ir')) . '" style="direction:ltr;width:260px"></p><p><button class="button button-primary">ذخیره</button></p>');
        echo '<h3>درون‌ریزی از سرور قبلی</h3><p>فایل <code>data/licenses.json</code> سرور قبلی را انتخاب کنید (لایسنس‌ها، دامنه‌های فعال، پرداخت‌ها و کدهای تخفیف؛ تکراری‌ها نادیده گرفته می‌شوند).</p>'
            . '<form method="post" enctype="multipart/form-data" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="accsoft_wl_import">' . wp_nonce_field('accsoft_wl_import', '_n', true, false) . '<input type="file" name="f" accept=".json" required> <button class="button button-primary">درون‌ریزی</button></form>';
    }
}

add_action('admin_post_accsoft_wl', function () {
    accsoft_admin_guard('accsoft_wl'); global $wpdb; $do = $_POST['do'] ?? ''; $sub = 'lic'; $msg = 'انجام شد'; $err = false;
    $L = accsoft_t('wlic'); $key = sanitize_text_field($_POST['key'] ?? '');
    switch ($do) {
        case 'create':
            $email = sanitize_email($_POST['email'] ?? ''); $prod = sanitize_key($_POST['product'] ?? '');
            if (!$email || !accsoft_wl_product($prod)) { $msg = 'ایمیل یا محصول نامعتبر'; $err = true; break; }
            $exp = trim($_POST['expires_at'] ?? ''); if ($exp && !preg_match('/^\d{4}-\d{2}-\d{2}$/', $exp)) { $msg = 'قالب تاریخ نامعتبر'; $err = true; break; }
            $lic = accsoft_wl_create($email, $prod, sanitize_text_field($_POST['note'] ?? ''), $exp ?: null, sanitize_text_field($_POST['domain'] ?? '')); $msg = 'ساخته شد: ' . $lic['license_key']; break;
        case 'revoke': $wpdb->update($L, ['status' => 'revoked'], ['license_key' => $key]); break;
        case 'restore': $wpdb->update($L, ['status' => 'active'], ['license_key' => $key]); break;
        case 'delete': $wpdb->delete(accsoft_t('wact'), ['license_key' => $key]); $wpdb->delete($L, ['license_key' => $key]); break;
        case 'unact': $wpdb->delete(accsoft_t('wact'), ['license_key' => $key, 'domain' => accsoft_wl_clean_domain($_POST['domain'] ?? '')]); break;
        case 'save_products':
            $out = [];
            foreach ((array)($_POST['w'] ?? []) as $w) {
                $slug = sanitize_key($w['slug'] ?? ''); if ($slug === '' || !empty($w['del'])) continue;
                $plans = [];
                foreach ((array)($w['plans'] ?? []) as $pl) { $pid = sanitize_key($pl['id'] ?? ''); if ($pid === '') continue;
                    $plans[$pid] = ['months' => max(0, (int)($pl['months'] ?? 0)), 'price' => max(0, (int)($pl['price'] ?? 0)) * 10, 'label' => sanitize_text_field($pl['label'] ?? $pid), 'hint' => sanitize_text_field($pl['hint'] ?? ''), 'badge' => sanitize_text_field($pl['badge'] ?? '')]; }
                $upd = ($w['u_version'] ?? '') !== '' ? ['version' => sanitize_text_field($w['u_version']), 'package' => esc_url_raw($w['u_package'] ?? ''), 'requires' => sanitize_text_field($w['u_requires'] ?? '5.8'),
                        'tested' => sanitize_text_field($w['u_tested'] ?? '6.6'), 'requires_php' => sanitize_text_field($w['u_php'] ?? '7.4'), 'changelog' => sanitize_text_field($w['u_changelog'] ?? '')] : [];
                $out[$slug] = ['label' => sanitize_text_field($w['label'] ?? $slug), 'icon' => sanitize_text_field($w['icon'] ?? ''), 'desc' => sanitize_text_field($w['desc'] ?? ''), 'price' => max(0, (int)($w['price'] ?? 0)) * 10, 'plans' => $plans, 'update' => $upd];
            }
            update_option('accsoft_wl_products', $out, false); $sub = 'prod'; break;
        case 'coupon_add':
            $sub = 'coupon'; $code = strtoupper(preg_replace('/[^A-Za-z0-9_-]/', '', $_POST['code'] ?? '')) ?: strtoupper(substr(bin2hex(random_bytes(5)), 0, 8));
            $type = ($_POST['type'] ?? '') === 'fixed' ? 'fixed' : 'percent'; $val = (int)($_POST['value'] ?? 0); if ($type === 'fixed') $val *= 10;
            if (accsoft_wl_coupon($code)) { $msg = 'این کد قبلاً هست'; $err = true; break; }
            if (($type === 'percent' && ($val < 1 || $val > 100)) || $val <= 0) { $msg = 'مقدار نامعتبر'; $err = true; break; }
            $exp = trim($_POST['expires_at'] ?? '');
            $wpdb->insert(accsoft_t('wcoupon'), ['uid' => uniqid(), 'code' => $code, 'type' => $type, 'value' => $val, 'product' => sanitize_key($_POST['product'] ?? 'all') ?: 'all', 'max_uses' => max(0, (int)($_POST['max_uses'] ?? 0)),
                'min_amount' => max(0, (int)($_POST['min_amount'] ?? 0)) * 10, 'expires_at' => preg_match('/^\d{4}-\d{2}-\d{2}$/', $exp) ? $exp : null, 'status' => 'active', 'note' => sanitize_text_field($_POST['note'] ?? ''), 'created_at' => accsoft_now()]);
            $msg = 'ساخته شد: ' . $code; break;
        case 'coupon_toggle': $sub = 'coupon'; $wpdb->query($wpdb->prepare("UPDATE " . accsoft_t('wcoupon') . " SET status=IF(status='active','disabled','active') WHERE id=%d", (int)$_POST['id'])); break;
        case 'coupon_del': $sub = 'coupon'; $wpdb->delete(accsoft_t('wcoupon'), ['id' => (int)$_POST['id']]); break;
        case 'save_wset': $sub = 'set'; accsoft_set_settings(['wl_api_secret' => preg_replace('/[^A-Za-z0-9_\-]/', '', $_POST['secret'] ?? ''), 'wl_base' => esc_url_raw($_POST['base'] ?? 'https://webakery.ir')]); break;
    }
    set_transient('accsoft_admin_msg', ($err ? '!' : '') . $msg, 120);
    wp_safe_redirect(admin_url('admin.php?page=accsoft&tab=legacy&sub=' . $sub)); exit;
});

add_action('admin_post_accsoft_wl_import', function () {
    accsoft_admin_guard('accsoft_wl_import');
    $f = $_FILES['f'] ?? null; if (!$f || $f['error'] || $f['size'] > 20 * 1024 * 1024) accsoft_admin_back('legacy&sub=set', 'فایل نامعتبر', true);
    $d = json_decode(file_get_contents($f['tmp_name']), true); if (!is_array($d)) accsoft_admin_back('legacy&sub=set', 'JSON نامعتبر', true);
    $n = accsoft_wl_import($d);
    accsoft_admin_back('legacy&sub=set', "درون‌ریزی شد: {$n['licenses']} لایسنس، {$n['activations']} فعال‌سازی، {$n['payments']} پرداخت، {$n['coupons']} کد تخفیف ({$n['skipped']} تکراری)");
});

/* ---------- پیشخوان مشتری: لایسنس‌های افزونه‌ها (با تأیید مالکیت ایمیل) ---------- */
function accsoft_wl_email_verified($uid) {
    $u = get_userdata($uid); return $u && strtolower((string)get_user_meta($uid, 'accsoft_email_ok', true)) === strtolower($u->user_email);
}
function accsoft_wl_portal_html($uid, $post) {
    global $wpdb; $u = get_userdata($uid); $o = '<div class="c"><h3>لایسنس‌های افزونه‌های وردپرسی</h3>';
    if (!accsoft_wl_email_verified($uid)) {
        $has = (int)$wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM " . accsoft_t('wlic') . " WHERE LOWER(email)=%s", strtolower($u->user_email)));
        return $o . ($has ? '<p>برای ایمیل شما (' . esc_html($u->user_email) . ') لایسنس ثبت شده است. برای امنیت، ابتدا مالکیت ایمیل را تأیید کنید:</p>' . $post('accsoft_wl_verify') . '<button>ارسال لینک تأیید به ایمیل</button></form>' : '<p>لایسنسی برای ایمیل شما ثبت نشده.</p>') . '</div>';
    }
    $rows = $wpdb->get_results($wpdb->prepare("SELECT * FROM " . accsoft_t('wlic') . " WHERE LOWER(email)=%s ORDER BY id DESC", strtolower($u->user_email)), ARRAY_A);
    if (!$rows) $o .= '<p>لایسنسی برای ایمیل شما ثبت نشده.</p>';
    foreach ($rows as $l) {
        $p = accsoft_wl_product($l['product']); $acts = accsoft_wl_acts($l['license_key']);
        $o .= '<div class="c"><b>' . esc_html($p['label'] ?? $l['product']) . '</b> <span class="t">' . esc_html($l['status']) . '</span><p>انقضا: ' . esc_html($l['expires_at'] ? accsoft_jdate($l['expires_at']) : 'مادام‌العمر') . '</p><code>' . esc_html($l['license_key']) . '</code>';
        foreach ($acts as $a) $o .= '<p>دامنه: <span dir="ltr">' . esc_html($a['domain']) . '</span> ' . $post('accsoft_wl_unact', '<input type="hidden" name="key" value="' . esc_attr($l['license_key']) . '"><input type="hidden" name="domain" value="' . esc_attr($a['domain']) . '">') . '<button onclick="return confirm(\'فعال‌سازی از این دامنه برداشته شود؟\')">حذف دامنه (برای انتقال)</button></form></p>';
        $o .= '</div>';
    }
    return $o . '</div>';
}
add_action('admin_post_accsoft_wl_verify', function () {
    $uid = accsoft_post_guard('accsoft_wl_verify'); $u = get_userdata($uid);
    $tok = bin2hex(random_bytes(16)); set_transient('accsoft_ev_' . hash('sha256', $tok), [$uid, strtolower($u->user_email)], DAY_IN_SECONDS);
    wp_mail($u->user_email, 'تأیید ایمیل برای مشاهدهٔ لایسنس‌ها', '<div dir="rtl">برای تأیید ایمیل روی لینک زیر بزنید:<br><a href="' . esc_url(home_url('/?accsoft_verify=' . $tok)) . '">تأیید ایمیل</a></div>', ['Content-Type: text/html; charset=UTF-8']);
    accsoft_flash($uid, 'لینک تأیید به ایمیل شما ارسال شد.'); accsoft_back();
});
add_action('template_redirect', function () {
    if (empty($_GET['accsoft_verify']) || !is_user_logged_in()) return;
    $k = 'accsoft_ev_' . hash('sha256', (string)$_GET['accsoft_verify']); $v = get_transient($k); $uid = get_current_user_id();
    if ($v && (int)$v[0] === $uid && $v[1] === strtolower(get_userdata($uid)->user_email)) { update_user_meta($uid, 'accsoft_email_ok', $v[1]); delete_transient($k); accsoft_flash($uid, 'ایمیل تأیید شد.'); }
    else accsoft_flash($uid, 'لینک نامعتبر یا منقضی است (با همان حساب وارد شده باشید).', false);
    wp_safe_redirect(accsoft_portal_url()); exit;
});
add_action('admin_post_accsoft_wl_unact', function () {
    $uid = accsoft_post_guard('accsoft_wl_unact'); global $wpdb; $u = get_userdata($uid);
    $l = accsoft_wl_find(sanitize_text_field($_POST['key'] ?? ''));
    if ($l && accsoft_wl_email_verified($uid) && strtolower($l['email']) === strtolower($u->user_email)) {
        $wpdb->delete(accsoft_t('wact'), ['license_key' => $l['license_key'], 'domain' => accsoft_wl_clean_domain($_POST['domain'] ?? '')]); accsoft_flash($uid, 'دامنه حذف شد؛ اکنون می‌توانید روی دامنهٔ جدید فعال کنید.');
    } else accsoft_flash($uid, 'مجاز نیست.', false);
    accsoft_back();
});
