<?php
if (!defined('ABSPATH')) exit;
/* درگاه زیبال. مبلغ سفارش تومان است و به زیبال به ریال (×۱۰) داده می‌شود. merchant «zibal» = محیط آزمایشی. */

function accsoft_zibal_post($path, $body) {
    $r = wp_remote_post('https://gateway.zibal.ir/v1/' . $path, ['timeout' => 20, 'headers' => ['Content-Type' => 'application/json'],
        'body' => wp_json_encode($body)]);
    if (is_wp_error($r)) throw new Exception('اتصال به زیبال ممکن نشد');
    $j = json_decode(wp_remote_retrieve_body($r), true);
    if (!is_array($j)) throw new Exception('پاسخ نامعتبر از زیبال');
    return $j;
}

/** → آدرس هدایت به درگاه */
function accsoft_zibal_start($order) {
    $m = trim((string)accsoft_setting('zibal_merchant'));
    if ($m === '') throw new Exception('درگاه پرداخت هنوز تنظیم نشده است');
    $j = accsoft_zibal_post('request', ['merchant' => $m, 'amount' => (int)$order['amount'] * 10, 'orderId' => $order['code'],
        'callbackUrl' => home_url('/?accsoft_cb=1'), 'description' => 'AccSoft ' . $order['product'] . '/' . $order['plan']]);
    if ((int)($j['result'] ?? 0) !== 100 || empty($j['trackId'])) throw new Exception('خطای زیبال: ' . ($j['message'] ?? $j['result'] ?? '?'));
    global $wpdb;
    $wpdb->update(accsoft_t('orders'), ['track_id' => (string)$j['trackId']], ['id' => $order['id']]);
    return 'https://gateway.zibal.ir/start/' . rawurlencode((string)$j['trackId']);
}

/** بازگشت از درگاه: تأیید سمت سرور (نه اعتماد به پارامترهای مرورگر) و مطابقت مبلغ */
function accsoft_zibal_callback() {
    global $wpdb;
    $track = preg_replace('/[^0-9A-Za-z]/', '', (string)($_GET['trackId'] ?? ''));
    $o = $track ? $wpdb->get_row($wpdb->prepare("SELECT * FROM " . accsoft_t('orders') . " WHERE track_id=%s", $track), ARRAY_A) : null;
    if (!$o) return [null, 'سفارش پیدا نشد'];
    if ($o['status'] === 'paid') return [$o, 'این پرداخت قبلاً ثبت شده است'];
    $m = trim((string)accsoft_setting('zibal_merchant'));
    try { $j = accsoft_zibal_post('verify', ['merchant' => $m, 'trackId' => (int)$track]); }
    catch (Exception $e) { return [$o, $e->getMessage() . ' — اگر مبلغ کسر شده با پشتیبانی تماس بگیرید']; }
    $ok = in_array((int)($j['result'] ?? 0), [100, 201], true) && (int)($j['amount'] ?? 0) === (int)$o['amount'] * 10;
    if (!$ok) {
        $wpdb->query($wpdb->prepare("UPDATE " . accsoft_t('orders') . " SET status='failed' WHERE id=%d AND status='pending'", $o['id']));
        return [$o, 'پرداخت تأیید نشد'];
    }
    $lid = accsoft_fulfil((int)$o['id'], (string)($j['refNumber'] ?? ''));
    return [accsoft_order((int)$o['id']), $lid ? 'پرداخت موفق بود و لایسنس صادر شد.' : 'پرداخت ثبت شد.'];
}
