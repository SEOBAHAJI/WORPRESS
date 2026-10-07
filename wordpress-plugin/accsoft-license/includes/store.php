<?php
if (!defined('ABSPATH')) exit;

function accsoft_t($n) { global $wpdb; return $wpdb->prefix . 'accsoft_' . $n; }

function accsoft_install_tables() {
    global $wpdb; require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $cs = $wpdb->get_charset_collate();
    dbDelta("CREATE TABLE " . accsoft_t('licenses') . " (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, lid VARCHAR(16) NOT NULL, user_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
      product VARCHAR(40) NOT NULL, plan VARCHAR(40) NOT NULL, name VARCHAR(190) NOT NULL DEFAULT '', mid VARCHAR(16) NOT NULL DEFAULT '',
      issued DATE NOT NULL, expires DATE NULL, license_key TEXT NOT NULL, status VARCHAR(12) NOT NULL DEFAULT 'active',
      order_id BIGINT UNSIGNED NOT NULL DEFAULT 0, parent_id BIGINT UNSIGNED NOT NULL DEFAULT 0, transfers INT NOT NULL DEFAULT 0,
      created DATETIME NOT NULL, PRIMARY KEY (id), UNIQUE KEY lid (lid), KEY user_id (user_id)) $cs;");
    dbDelta("CREATE TABLE " . accsoft_t('orders') . " (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, code VARCHAR(32) NOT NULL, user_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
      product VARCHAR(40) NOT NULL, plan VARCHAR(40) NOT NULL, mid VARCHAR(16) NOT NULL DEFAULT '', amount BIGINT NOT NULL DEFAULT 0,
      status VARCHAR(10) NOT NULL DEFAULT 'pending', track_id VARCHAR(40) NOT NULL DEFAULT '', ref_number VARCHAR(40) NOT NULL DEFAULT '',
      renew_of BIGINT UNSIGNED NOT NULL DEFAULT 0, license_id BIGINT UNSIGNED NOT NULL DEFAULT 0, created DATETIME NOT NULL, paid_at DATETIME NULL,
      PRIMARY KEY (id), UNIQUE KEY code (code), KEY track_id (track_id), KEY user_id (user_id)) $cs;");
    accsoft_wl_install_tables();
    update_option('accsoft_db_ver', ACCSOFT_VER);
}

function accsoft_activate() {
    accsoft_install_tables();
    if (!get_option('accsoft_products')) {
        update_option('accsoft_products', [[
            'id' => 'accsoft', 'name' => 'دفترچی', 'kind' => 'app', 'description' => '', 'trial_days' => 7,
            'plans' => [
                ['id' => 'm3', 'title' => '۳ ماهه', 'months' => 3, 'price' => 6000000],
                ['id' => 'm6', 'title' => '۶ ماهه', 'months' => 6, 'price' => 9000000],
                ['id' => 'm12', 'title' => '۱۲ ماهه', 'months' => 12, 'price' => 12000000],
                ['id' => 'lifetime', 'title' => 'مادام‌العمر', 'months' => null, 'price' => 14000000],
            ]]], false);
    }
    $pid = (int)accsoft_setting('portal_page_id');
    if (!$pid || !get_post($pid)) {
        $pid = wp_insert_post(['post_title' => 'پیشخوان لایسنس', 'post_name' => 'accsoft-panel', 'post_status' => 'publish',
                               'post_type' => 'page', 'post_content' => '[accsoft_dashboard]']);
        if ($pid && !is_wp_error($pid)) accsoft_set_settings(['portal_page_id' => $pid]);
    }
}

function accsoft_setting($k, $d = '') { $s = get_option('accsoft_settings', []); return $s[$k] ?? $d; }
function accsoft_set_settings($new) { update_option('accsoft_settings', array_merge(get_option('accsoft_settings', []), $new), false); }
function accsoft_portal_url($args = []) {
    $u = get_permalink((int)accsoft_setting('portal_page_id')) ?: home_url('/accsoft-panel/');
    return $args ? add_query_arg($args, $u) : $u;
}
function accsoft_today() { return current_time('Y-m-d'); }
function accsoft_now() { return current_time('mysql'); }

/* ---------- کاتالوگ ---------- */
function accsoft_products() { $p = get_option('accsoft_products', []); return is_array($p) ? $p : []; }
function accsoft_product($id) { foreach (accsoft_products() as $p) if ($p['id'] === $id) return $p; return null; }
function accsoft_plan($pid, $plan) {
    $p = accsoft_product($pid); if (!$p) return null;
    foreach ($p['plans'] as $pl) if ($pl['id'] === $plan) return $pl;
    return null;
}

/** ساخت و امضای کاتالوگ جدید (نسخه +۱). ابطال‌ها از وضعیت لایسنس‌ها محاسبه می‌شوند. */
function accsoft_publish() {
    global $wpdb;
    $revoked = $wpdb->get_col("SELECT lid FROM " . accsoft_t('licenses') . " WHERE status IN ('revoked','replaced') ORDER BY id");
    $products = [];
    foreach (accsoft_products() as $p) {
        $plans = [];
        foreach ($p['plans'] as $pl) {
            $row = ['id' => $pl['id'], 'title' => $pl['title'], 'months' => $pl['months'] === null ? null : (int)$pl['months'], 'price' => (int)$pl['price']];
            if (!empty($pl['features'])) $row['features'] = array_values($pl['features']);
            $plans[] = $row;
        }
        $products[] = ['id' => $p['id'], 'name' => $p['name'], 'kind' => $p['kind'], 'description' => (string)($p['description'] ?? ''),
                       'trial_days' => (int)($p['trial_days'] ?? 0), 'plans' => $plans];
    }
    $ver = (int)get_option('accsoft_catalog_version', 0) + 1;
    $data = ['version' => $ver, 'revoked' => array_map('strval', $revoked), 'products' => $products];
    try { $doc = accsoft_sign_catalog($data); }
    catch (Exception $e) { return $e->getMessage(); }
    update_option('accsoft_catalog_doc', wp_json_encode($doc, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), false);
    update_option('accsoft_catalog_version', $ver, false);
    return true;
}

/* ---------- لایسنس ---------- */
function accsoft_valid_mid($m) { return $m === '' || (bool)preg_match('/^[0-9A-F]{16}$/', $m); }

/** صدور و ذخیرهٔ لایسنس. $expires=null یعنی مادام‌العمر. */
function accsoft_issue($user_id, $product, $plan, $name, $mid, $expires, $order_id = 0, $parent = 0, $transfers = 0) {
    global $wpdb;
    $pl = accsoft_plan($product, $plan); if (!$pl) throw new Exception('پلن نامعتبر');
    $issued = accsoft_today();
    [$lid, $key] = accsoft_make_license($product, $plan, $name, $mid, $issued, $expires, $pl['features'] ?? []);
    $wpdb->insert(accsoft_t('licenses'), ['lid' => $lid, 'user_id' => $user_id, 'product' => $product, 'plan' => $plan, 'name' => $name,
        'mid' => $mid, 'issued' => $issued, 'expires' => $expires, 'license_key' => $key, 'status' => 'active',
        'order_id' => $order_id, 'parent_id' => $parent, 'transfers' => $transfers, 'created' => accsoft_now()]);
    return (int)$wpdb->insert_id;
}

function accsoft_license($id) { global $wpdb; return $wpdb->get_row($wpdb->prepare("SELECT * FROM " . accsoft_t('licenses') . " WHERE id=%d", $id), ARRAY_A); }
function accsoft_order($id) { global $wpdb; return $wpdb->get_row($wpdb->prepare("SELECT * FROM " . accsoft_t('orders') . " WHERE id=%d", $id), ARRAY_A); }

function accsoft_license_state($l) {
    if ($l['status'] === 'revoked') return 'ابطال‌شده';
    if ($l['status'] === 'replaced') return 'منتقل‌شده';
    if ($l['expires'] && $l['expires'] < accsoft_today()) return 'منقضی';
    return 'فعال';
}

function accsoft_display_name($user_id) { $u = get_userdata($user_id); return $u ? $u->display_name : ''; }

/** پس از پرداخت موفق: فقط یک‌بار (UPDATE شرطی) و بدون صدور تکراری */
function accsoft_fulfil($order_id, $ref = '') {
    global $wpdb;
    $n = $wpdb->query($wpdb->prepare("UPDATE " . accsoft_t('orders') . " SET status='paid', paid_at=%s, ref_number=%s WHERE id=%d AND status='pending'",
        accsoft_now(), $ref, $order_id));
    if ($n !== 1) return false;
    $o = accsoft_order($order_id);
    $pl = accsoft_plan($o['product'], $o['plan']);
    $name = accsoft_display_name($o['user_id']);
    $base = accsoft_today();
    if ($o['renew_of']) {
        $old = accsoft_license($o['renew_of']);
        if ($old && $old['expires'] && $old['expires'] > $base) $base = $old['expires'];
    }
    $expires = $pl['months'] ? accsoft_add_months($base, (int)$pl['months']) : null;
    $lid = accsoft_issue((int)$o['user_id'], $o['product'], $o['plan'], $name, $o['mid'], $expires, (int)$o['id'], (int)$o['renew_of']);
    $wpdb->update(accsoft_t('orders'), ['license_id' => $lid], ['id' => $order_id]);
    return $lid;
}

function accsoft_new_order($user_id, $product, $plan, $mid, $renew_of = 0) {
    global $wpdb;
    $pl = accsoft_plan($product, $plan); if (!$pl) throw new Exception('پلن نامعتبر');
    if (!accsoft_valid_mid($mid) || $mid === '') throw new Exception('شناسهٔ سیستم باید ۱۶ نویسهٔ هگزادسیمال (حروف بزرگ) باشد؛ از صفحهٔ «لایسنس» داخل برنامه کپی کنید.');
    $code = bin2hex(random_bytes(10));
    $wpdb->insert(accsoft_t('orders'), ['code' => $code, 'user_id' => $user_id, 'product' => $product, 'plan' => $plan, 'mid' => $mid,
        'amount' => (int)$pl['price'], 'status' => 'pending', 'renew_of' => $renew_of, 'created' => accsoft_now()]);
    return (int)$wpdb->insert_id;
}

/** انتقال لایسنس به ماشین جدید: لایسنس قدیم ابطال و کلید جدید با همان انقضا صادر می‌شود */
function accsoft_transfer($user_id, $license_id, $new_mid) {
    global $wpdb;
    $l = accsoft_license($license_id);
    if (!$l || (int)$l['user_id'] !== (int)$user_id) throw new Exception('لایسنس پیدا نشد');
    if ($l['status'] !== 'active') throw new Exception('این لایسنس فعال نیست');
    if ($l['expires'] && $l['expires'] < accsoft_today()) throw new Exception('لایسنس منقضی شده؛ ابتدا تمدید کنید');
    if (!preg_match('/^[0-9A-F]{16}$/', $new_mid)) throw new Exception('شناسهٔ سیستم جدید معتبر نیست');
    if ($new_mid === $l['mid']) throw new Exception('شناسهٔ جدید با قبلی یکی است');
    $max = (int)accsoft_setting('max_transfers', 2);
    if ((int)$l['transfers'] >= $max) throw new Exception("سقف انتقال ($max بار) پر شده؛ با پشتیبانی تماس بگیرید");
    $new = accsoft_issue((int)$user_id, $l['product'], $l['plan'], $l['name'], $new_mid, $l['expires'], (int)$l['order_id'], (int)$l['id'], (int)$l['transfers'] + 1);
    $wpdb->update(accsoft_t('licenses'), ['status' => 'replaced'], ['id' => $l['id']]);
    $r = accsoft_publish(); if ($r !== true) throw new Exception($r);
    return $new;
}
