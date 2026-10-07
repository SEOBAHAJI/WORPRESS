<?php
if (!defined('ABSPATH')) exit;
/* امضای Ed25519 سازگار با برنامهٔ پایتون (libsodium = RFC 8032). کلید خصوصی (seed) فقط در wp-config.php:
   define('ACCSOFT_SEED_HEX', '<۶۴ نویسهٔ هگز>');  — هرگز در پایگاه داده ذخیره نمی‌شود. */

function accsoft_b64u($b) { return rtrim(strtr(base64_encode($b), '+/', '-_'), '='); }

function accsoft_seed() {
    if (!defined('ACCSOFT_SEED_HEX') || !function_exists('sodium_crypto_sign_seed_keypair')) return null;
    $h = ACCSOFT_SEED_HEX;
    if (!is_string($h) || !preg_match('/^[0-9a-fA-F]{64}$/', $h)) return null;
    return hex2bin($h);
}

function accsoft_keypair() {
    $s = accsoft_seed();
    return $s ? sodium_crypto_sign_seed_keypair($s) : null;
}

function accsoft_pubkey_hex() {
    $kp = accsoft_keypair();
    return $kp ? sodium_bin2hex(sodium_crypto_sign_publickey($kp)) : '';
}

function accsoft_sign($msg) {
    $kp = accsoft_keypair();
    if (!$kp) throw new Exception('کلید خصوصی در wp-config.php تنظیم نشده است (ACCSOFT_SEED_HEX).');
    return sodium_crypto_sign_detached($msg, sodium_crypto_sign_secretkey($kp));
}

/** JSON متعارف دقیقاً مثل پایتون: کلیدها مرتب، بدون فاصله، یونیکد خام. لیست‌ها مرتب نمی‌شوند. */
function accsoft_canon($v) {
    return json_encode(accsoft_sorted($v), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_LINE_TERMINATORS);
}
function accsoft_sorted($v) {
    if (!is_array($v)) return $v;
    if (function_exists('array_is_list') ? array_is_list($v) : (array_keys($v) === range(0, count($v) - 1) || !$v)) {
        return array_map('accsoft_sorted', $v);
    }
    ksort($v, SORT_STRING);
    return array_map('accsoft_sorted', $v);
}

function accsoft_add_months($ymd, $n) {
    $d = new DateTime($ymd, new DateTimeZone('UTC'));
    $y = (int)$d->format('Y'); $m = (int)$d->format('n') - 1 + (int)$n; $day = (int)$d->format('j');
    $y += intdiv($m, 12); $m = $m % 12 + 1;
    $last = (int)date('t', gmmktime(0, 0, 0, $m, 1, $y));
    return sprintf('%04d-%02d-%02d', $y, $m, min($day, $last));
}

/** کد لایسنس: base64url(payload).base64url(sig) — همان قالب برنامه */
function accsoft_make_license($product, $plan, $name, $mid, $issued, $expires, $features = []) {
    $features = array_values(array_unique(array_map('strval', $features))); sort($features);
    $lid = bin2hex(random_bytes(4));
    $payload = ['v' => 2, 'lid' => $lid, 'product' => $product, 'plan' => $plan, 'name' => $name, 'issued' => $issued,
                'expires' => $expires ?: null, 'mid' => $mid, 'features' => $features];
    $body = accsoft_canon($payload);
    return [$lid, accsoft_b64u($body) . '.' . accsoft_b64u(accsoft_sign($body))];
}

function accsoft_sign_catalog($data) {
    return ['data' => $data, 'sig' => accsoft_b64u(accsoft_sign(accsoft_canon($data)))];
}

/* تاریخ شمسی برای نمایش */
function accsoft_jdate($ymd) {
    if (!$ymd) return 'مادام‌العمر';
    [$gy, $gm, $gd] = array_map('intval', explode('-', $ymd));
    $gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    $gy2 = $gm > 2 ? $gy + 1 : $gy;
    $days = 355666 + 365 * $gy + intdiv($gy2 + 3, 4) - intdiv($gy2 + 99, 100) + intdiv($gy2 + 399, 400) + $gd + $gdm[$gm - 1];
    $jy = -1595 + 33 * intdiv($days, 12053); $days %= 12053;
    $jy += 4 * intdiv($days, 1461); $days %= 1461;
    if ($days > 365) { $jy += intdiv($days - 1, 365); $days = ($days - 1) % 365; }
    if ($days < 186) { $jm = 1 + intdiv($days, 31); $jd = 1 + $days % 31; }
    else { $jm = 7 + intdiv($days - 186, 30); $jd = 1 + ($days - 186) % 30; }
    return sprintf('%04d/%02d/%02d', $jy, $jm, $jd);
}
