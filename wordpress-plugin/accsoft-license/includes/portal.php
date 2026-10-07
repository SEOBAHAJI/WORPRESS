<?php
if (!defined('ABSPATH')) exit;
/* پیشخوان مشتری: [accsoft_dashboard] */

function accsoft_flash($uid, $msg, $ok = true) { set_transient('accsoft_msg_' . $uid, ($ok ? '' : '!') . $msg, 600); }

add_shortcode('accsoft_dashboard', function () {
    $uid = get_current_user_id();
    ob_start();
    echo '<style>.acs{direction:rtl;font-family:Tahoma,sans-serif;max-width:900px;margin:auto}.acs .c{border:1px solid #d5dbe5;border-radius:10px;padding:14px;margin:12px 0;background:#fff}
    .acs table{width:100%;border-collapse:collapse}.acs th,.acs td{padding:7px;border-bottom:1px solid #eee;text-align:right;font-size:14px}
    .acs code{direction:ltr;display:block;word-break:break-all;background:#f3f5f9;padding:6px;border-radius:6px;font-size:11px}
    .acs input,.acs select{padding:7px;border:1px solid #bbb;border-radius:6px;margin:3px}.acs button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:8px 14px;cursor:pointer}
    .acs .m{padding:10px;border-radius:8px;background:#e7f5ec}.acs .m.e{background:#fde8e8}.acs .t{display:inline-block;padding:2px 8px;border-radius:10px;background:#eef;font-size:12px}</style><div class="acs">';
    if (!$uid) {
        echo '<div class="c"><h3>ورود به پیشخوان</h3><p>برای خرید یا مدیریت لایسنس وارد حساب خود شوید.</p>';
        wp_login_form(['redirect' => esc_url_raw(add_query_arg(null, null))]);
        if (get_option('users_can_register')) echo '<p><a href="' . esc_url(wp_registration_url()) . '">ثبت‌نام</a></p>';
        echo '</div></div>'; return ob_get_clean();
    }
    $msg = get_transient('accsoft_msg_' . $uid);
    if ($msg) { delete_transient('accsoft_msg_' . $uid); $bad = $msg[0] === '!'; echo '<div class="m' . ($bad ? ' e' : '') . '">' . esc_html(ltrim($msg, '!')) . '</div>'; }

    $qp = isset($_GET['product']) ? sanitize_key($_GET['product']) : 'accsoft';
    $qplan = isset($_GET['plan']) ? sanitize_key($_GET['plan']) : '';
    $qmid = isset($_GET['mid']) ? strtoupper(preg_replace('/[^0-9A-Fa-f]/', '', (string)$_GET['mid'])) : '';
    $post = function ($action, $extra = '') { return '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="' . $action . '">' . wp_nonce_field($action, '_n', true, false) . $extra; };

    // خرید
    echo '<div class="c"><h3>خرید لایسنس جدید</h3>' . $post('accsoft_buy');
    echo '<select name="product">';
    foreach (accsoft_products() as $p) echo '<option value="' . esc_attr($p['id']) . '"' . selected($qp, $p['id'], false) . '>' . esc_html($p['name']) . '</option>';
    echo '</select><select name="plan">';
    foreach (accsoft_products() as $p) foreach ($p['plans'] as $pl)
        echo '<option value="' . esc_attr($pl['id']) . '"' . selected($qplan, $pl['id'], false) . '>' . esc_html($p['name'] . ' — ' . $pl['title'] . ' — ' . number_format_i18n($pl['price']) . ' تومان') . '</option>';
    echo '</select><br><input name="mid" value="' . esc_attr($qmid) . '" placeholder="شناسهٔ سیستم (۱۶ نویسه)" maxlength="16" style="width:230px;direction:ltr">
      <button>پرداخت</button><br><small>شناسهٔ سیستم را از صفحهٔ «لایسنس» داخل برنامه کپی کنید.</small></form></div>';

    // لایسنس‌ها
    global $wpdb;
    $rows = $wpdb->get_results($wpdb->prepare("SELECT * FROM " . accsoft_t('licenses') . " WHERE user_id=%d ORDER BY id DESC", $uid), ARRAY_A);
    echo '<div class="c"><h3>لایسنس‌های من</h3>';
    if (!$rows) echo '<p>هنوز لایسنسی ندارید.</p>';
    foreach ($rows as $l) {
        $st = accsoft_license_state($l); $p = accsoft_product($l['product']);
        echo '<div class="c"><b>' . esc_html($p['name'] ?? $l['product']) . '</b> <span class="t">' . esc_html($l['plan']) . '</span> <span class="t">' . esc_html($st) . '</span>
          <p>انقضا: ' . esc_html(accsoft_jdate($l['expires'])) . ' | سیستم: <span dir="ltr">' . esc_html($l['mid'] ?: '—') . '</span> | شمارهٔ لایسنس: ' . esc_html($l['lid']) . '</p>';
        if ($l['status'] === 'active') {
            echo '<code>' . esc_html($l['license_key']) . '</code><small>کد بالا را در برنامه، صفحهٔ «لایسنس»، بخش فعال‌سازی وارد کنید.</small>';
            if ($l['expires']) {
                echo $post('accsoft_renew', '<input type="hidden" name="lic" value="' . (int)$l['id'] . '">') . 'تمدید: <select name="plan">';
                foreach (($p['plans'] ?? []) as $pl) if ($pl['months']) echo '<option value="' . esc_attr($pl['id']) . '">' . esc_html($pl['title'] . ' — ' . number_format_i18n($pl['price']) . ' تومان') . '</option>';
                echo '</select><button>تمدید و پرداخت</button></form>';
            }
            echo $post('accsoft_transfer', '<input type="hidden" name="lic" value="' . (int)$l['id'] . '">') . 'انتقال به سیستم جدید (' . (int)$l['transfers'] . ' از ' . (int)accsoft_setting('max_transfers', 2) . ' بار):
              <input name="mid" placeholder="شناسهٔ سیستم جدید" maxlength="16" style="direction:ltr"><button onclick="return confirm(\'کد فعلی باطل می‌شود. ادامه؟\')">انتقال</button></form>';
        }
        echo '</div>';
    }
    echo '</div></div>';
    return ob_get_clean();
});

function accsoft_post_guard($action) {
    if (!is_user_logged_in()) wp_die('ابتدا وارد شوید', 403);
    check_admin_referer($action, '_n');
    return get_current_user_id();
}
function accsoft_back() { wp_safe_redirect(accsoft_portal_url()); exit; }
function accsoft_pay_order($uid, $oid) {
    $o = accsoft_order($oid);
    if ((int)$o['amount'] <= 0) { accsoft_fulfil($oid); accsoft_flash($uid, 'لایسنس صادر شد.'); accsoft_back(); }
    wp_redirect(accsoft_zibal_start($o)); exit;
}

add_action('admin_post_accsoft_buy', function () {
    $uid = accsoft_post_guard('accsoft_buy');
    try {
        $oid = accsoft_new_order($uid, sanitize_key($_POST['product'] ?? ''), sanitize_key($_POST['plan'] ?? ''), strtoupper(trim((string)($_POST['mid'] ?? ''))));
        accsoft_pay_order($uid, $oid);
    } catch (Exception $e) { accsoft_flash($uid, $e->getMessage(), false); accsoft_back(); }
});
add_action('admin_post_accsoft_renew', function () {
    $uid = accsoft_post_guard('accsoft_renew');
    try {
        $l = accsoft_license((int)($_POST['lic'] ?? 0));
        if (!$l || (int)$l['user_id'] !== $uid || $l['status'] !== 'active' || !$l['expires']) throw new Exception('این لایسنس قابل تمدید نیست');
        $plan = sanitize_key($_POST['plan'] ?? ''); $pl = accsoft_plan($l['product'], $plan);
        if (!$pl || !$pl['months']) throw new Exception('پلن تمدید نامعتبر');
        accsoft_pay_order($uid, accsoft_new_order($uid, $l['product'], $plan, $l['mid'], (int)$l['id']));
    } catch (Exception $e) { accsoft_flash($uid, $e->getMessage(), false); accsoft_back(); }
});
add_action('admin_post_accsoft_transfer', function () {
    $uid = accsoft_post_guard('accsoft_transfer');
    try { accsoft_transfer($uid, (int)($_POST['lic'] ?? 0), strtoupper(trim((string)($_POST['mid'] ?? '')))); accsoft_flash($uid, 'منتقل شد. کد جدید را در برنامه وارد کنید؛ کد قبلی پس از به‌روزرسانی کاتالوگ برنامه باطل می‌شود.'); }
    catch (Exception $e) { accsoft_flash($uid, $e->getMessage(), false); }
    accsoft_back();
});
