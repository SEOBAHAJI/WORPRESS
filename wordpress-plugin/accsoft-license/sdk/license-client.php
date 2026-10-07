<?php
/**
 * کلاینت بررسی لایسنس برای افزونه‌های وردپرس/PHP (فقط تأیید؛ هیچ کلید خصوصی‌ای لازم نیست).
 * استفاده:
 *   require 'license-client.php';
 *   $r = SoftLicense::check($key, 'کلید عمومی هگز', 'my-plugin');   // product = شناسهٔ محصول در پنل
 *   if ($r['ok']) {...} else echo $r['error'];
 * برای افزونه‌هایی که به سیستم/سایت خاصی بسته‌اند، $mid را بدهید (مثلاً hash دامنه؛ هنگام صدور همان را در «شناسهٔ سیستم» بگذارید—
 * در پنل فعلی فقط ۱۶ نویسهٔ هگز بزرگ پذیرفته می‌شود: strtoupper(substr(md5(home_url()),0,16))).
 */
class SoftLicense {
    private static function unb64($s) { return base64_decode(strtr($s, '-_', '+/') . str_repeat('=', (4 - strlen($s) % 4) % 4), true); }

    public static function check($key, $pubHex, $product, $mid = '', $revoked = [], $today = null) {
        $today = $today ?: gmdate('Y-m-d');
        $parts = explode('.', trim((string)$key));
        if (count($parts) !== 2) return ['ok' => false, 'error' => 'قالب کد نامعتبر'];
        $body = self::unb64($parts[0]); $sig = self::unb64($parts[1]);
        if ($body === false || $sig === false || strlen($sig) !== SODIUM_CRYPTO_SIGN_BYTES) return ['ok' => false, 'error' => 'کد خراب است'];
        if (!sodium_crypto_sign_verify_detached($sig, $body, sodium_hex2bin($pubHex))) return ['ok' => false, 'error' => 'امضا نامعتبر'];
        $p = json_decode($body, true);
        if (!is_array($p) || ($p['product'] ?? '') !== $product) return ['ok' => false, 'error' => 'این کد برای محصول دیگری است'];
        if (in_array($p['lid'] ?? '', $revoked, true)) return ['ok' => false, 'error' => 'ابطال شده', 'payload' => $p];
        if (!empty($p['mid']) && $p['mid'] !== $mid) return ['ok' => false, 'error' => 'برای سیستم دیگری صادر شده', 'payload' => $p];
        if (!empty($p['expires']) && $p['expires'] < $today) return ['ok' => false, 'error' => 'منقضی شده', 'payload' => $p];
        return ['ok' => true, 'payload' => $p];
    }

    /** لیست ابطال‌ها از کاتالوگ امضاشدهٔ سرور (آدرس: https://سایت/wp-json/accsoft/v1/catalog) */
    public static function revoked($catalogUrl, $pubHex) {
        $r = wp_remote_get($catalogUrl, ['timeout' => 10]);
        if (is_wp_error($r)) return null;
        $doc = json_decode(wp_remote_retrieve_body($r), true);
        if (!is_array($doc) || !isset($doc['data'], $doc['sig'])) return null;
        $sig = self::unb64($doc['sig']);
        if (!$sig || !sodium_crypto_sign_verify_detached($sig, self::canon($doc['data']), sodium_hex2bin($pubHex))) return null;
        return $doc['data']['revoked'] ?? [];
    }
    private static function canon($v) { return json_encode(self::sorted($v), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_LINE_TERMINATORS); }
    private static function sorted($v) {
        if (!is_array($v)) return $v;
        if (function_exists("array_is_list") ? array_is_list($v) : (!$v || array_keys($v) === range(0, count($v) - 1))) return array_map([self::class, 'sorted'], $v);
        ksort($v, SORT_STRING); return array_map([self::class, 'sorted'], $v);
    }
}
