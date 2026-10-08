<?php
if (!defined('ABSPATH')) exit;
/* API برنامه: GET /wp-json/accsoft/v1/catalog   و   GET /wp-json/accsoft/v1/license?order=کد&mid=شناسه */

add_action('rest_api_init', function () {
    register_rest_route('accsoft/v1', '/catalog', ['methods' => 'GET', 'permission_callback' => '__return_true', 'callback' => function () {
        $raw = get_option('accsoft_catalog_doc');
        $doc = $raw ? json_decode($raw, true) : null;
        if (!$doc) return new WP_REST_Response(['error' => 'کاتالوگ هنوز منتشر نشده'], 404);
        $r = new WP_REST_Response($doc); $r->header('Cache-Control', 'no-cache'); return $r;
    }]);
    register_rest_route('accsoft/v1', '/license', ['methods' => 'GET', 'permission_callback' => '__return_true', 'callback' => function (WP_REST_Request $req) {
        global $wpdb;
        $ip = md5($_SERVER['REMOTE_ADDR'] ?? '');
        $k = 'accsoft_rl_' . $ip; $n = (int)get_transient($k);
        if ($n >= 30) return new WP_REST_Response(['error' => 'تعداد درخواست زیاد است؛ بعداً تلاش کنید'], 429);
        set_transient($k, $n + 1, HOUR_IN_SECONDS);
        $code = preg_replace('/[^0-9a-f]/', '', strtolower((string)$req->get_param('order')));
        $mid = strtoupper(preg_replace('/[^0-9A-Fa-f]/', '', (string)$req->get_param('mid')));
        $o = $code ? $wpdb->get_row($wpdb->prepare("SELECT * FROM " . accsoft_t('orders') . " WHERE code=%s AND status='paid'", $code), ARRAY_A) : null;
        if (!$o || !$o['license_id'] || !hash_equals((string)$o['mid'], $mid)) return new WP_REST_Response(['error' => 'سفارش پرداخت‌شده‌ای با این مشخصات نیست'], 404);
        $l = accsoft_license((int)$o['license_id']);
        if (!$l || $l['status'] !== 'active') return new WP_REST_Response(['error' => 'لایسنس فعال نیست'], 404);
        return ['license' => $l['license_key'], 'product' => $l['product'], 'plan' => $l['plan'], 'expires' => $l['expires']];
    }]);
});

/* ---------- حساب کاربری برنامهٔ دفترچی: ورود و ثبت‌نام با حساب همین سایت ---------- */
function accsoft_acc_limit($key, $max, $ttl) {
    $k = 'accsoft_al_' . md5($key); $n = (int)get_transient($k);
    if ($n >= $max) return false; set_transient($k, $n + 1, $ttl); return true;
}
function accsoft_acc_reply($user) {
    global $wpdb;
    $keys = $wpdb->get_col($wpdb->prepare("SELECT license_key FROM " . accsoft_t('licenses') . " WHERE user_id=%d AND status='active' ORDER BY id DESC", $user->ID));
    return ['ok' => true, 'email' => $user->user_email, 'name' => $user->display_name, 'licenses' => $keys];
}
add_action('rest_api_init', function () {
    register_rest_route('accsoft/v1', '/auth', ['methods' => 'POST', 'permission_callback' => '__return_true', 'callback' => function (WP_REST_Request $req) {
        $login = trim((string)$req->get_param('login')); $pass = (string)$req->get_param('password');
        $ip = (string)($_SERVER['REMOTE_ADDR'] ?? '');
        if ($login === '' || $pass === '') return new WP_REST_Response(['ok' => false, 'error' => 'ایمیل و رمز را وارد کنید'], 400);
        if (!accsoft_acc_limit('a' . $ip . strtolower($login), 8, 15 * MINUTE_IN_SECONDS)) return new WP_REST_Response(['ok' => false, 'error' => 'تلاش‌های زیاد؛ ۱۵ دقیقه بعد دوباره امتحان کنید'], 429);
        $u = wp_authenticate($login, $pass);
        if (is_wp_error($u)) return new WP_REST_Response(['ok' => false, 'error' => 'ایمیل/نام کاربری یا رمز نادرست است'], 401);
        return accsoft_acc_reply($u);
    }]);
    register_rest_route('accsoft/v1', '/register', ['methods' => 'POST', 'permission_callback' => '__return_true', 'callback' => function (WP_REST_Request $req) {
        if (accsoft_setting('allow_app_register', '1') !== '1') return new WP_REST_Response(['ok' => false, 'error' => 'ثبت‌نام از داخل برنامه غیرفعال است؛ از سایت ثبت‌نام کنید'], 403);
        $email = sanitize_email((string)$req->get_param('email')); $pass = (string)$req->get_param('password'); $name = sanitize_text_field((string)$req->get_param('name'));
        if (!accsoft_acc_limit('r' . ($_SERVER['REMOTE_ADDR'] ?? ''), 5, HOUR_IN_SECONDS)) return new WP_REST_Response(['ok' => false, 'error' => 'تعداد ثبت‌نام زیاد است؛ بعداً تلاش کنید'], 429);
        if (!is_email($email)) return new WP_REST_Response(['ok' => false, 'error' => 'ایمیل معتبر نیست'], 400);
        if (strlen($pass) < 8) return new WP_REST_Response(['ok' => false, 'error' => 'رمز حداقل ۸ نویسه باشد'], 400);
        if (email_exists($email)) return new WP_REST_Response(['ok' => false, 'error' => 'با این ایمیل قبلاً حساب ساخته شده؛ وارد شوید یا رمز را بازیابی کنید'], 409);
        $uname = sanitize_user(strstr($email, '@', true), true) ?: 'user'; $base = $uname; $i = 1;
        while (username_exists($uname)) $uname = $base . (++$i);
        $id = wp_create_user($uname, $pass, $email);
        if (is_wp_error($id)) return new WP_REST_Response(['ok' => false, 'error' => 'ساخت حساب ممکن نشد'], 500);
        if ($name !== '') wp_update_user(['ID' => $id, 'display_name' => $name, 'first_name' => $name]);
        return accsoft_acc_reply(get_userdata($id));
    }]);
});

/* بازگشت از درگاه پرداخت */
add_action('template_redirect', function () {
    if (empty($_GET['accsoft_cb'])) return;
    [$o, $msg] = accsoft_zibal_callback();
    if ($o && !empty($o['user_id'])) set_transient('accsoft_msg_' . (int)$o['user_id'], $msg, 600);
    wp_safe_redirect(accsoft_portal_url()); exit;
});
