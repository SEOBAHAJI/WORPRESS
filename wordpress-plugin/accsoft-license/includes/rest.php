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

/* بازگشت از درگاه پرداخت */
add_action('template_redirect', function () {
    if (empty($_GET['accsoft_cb'])) return;
    [$o, $msg] = accsoft_zibal_callback();
    if ($o && !empty($o['user_id'])) set_transient('accsoft_msg_' . (int)$o['user_id'], $msg, 600);
    wp_safe_redirect(accsoft_portal_url()); exit;
});
