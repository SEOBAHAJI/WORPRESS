<?php
/**
 * کلاینت آمادهٔ افزونه‌های وردپرسی شما برای سرور لایسنس (فعال‌سازی + بررسی + به‌روزرسانی خودکار).
 * استفاده — داخل فایل اصلی افزونه (بعد از کپی‌کردن این فایل کنار افزونه):
 *
 *   require_once __DIR__ . '/wb-license-client.php';
 *   $GLOBALS['my_lic'] = new WB_License_Client([
 *       'product' => 'my-plugin',                       // = نام پوشهٔ افزونه = شناسهٔ محصول در پنل
 *       'api'     => 'https://webakery.ir/license-server/api/',
 *       'buy_url' => 'https://webakery.ir/license-server/pay/?plugin=my-plugin',
 *       'file'    => __FILE__,
 *       'version' => '1.0.0',
 *   ]);
 *   if ( ! $GLOBALS['my_lic']->is_active() ) { return; }   // قابلیت‌های پولی فقط با لایسنس معتبر
 *
 * صفحهٔ وارد کردن کلید: «افزونه‌ها ← لایسنس <product>» (خودکار ساخته می‌شود).
 */
if (!class_exists('WB_License_Client')) {
class WB_License_Client {
    private $c;
    public function __construct($c) {
        $this->c = $c + ['buy_url' => '']; $this->c['slug'] = $c['product'];
        add_action('admin_menu', [$this, 'menu']);
        add_filter('pre_set_site_transient_update_plugins', [$this, 'check_update']);
        add_filter('plugins_api', [$this, 'plugin_info'], 10, 3);
    }
    private function title() { return $this->c['name'] ?? $this->c['product']; }
    private function opt($k) { return $this->c['product'] . '_' . $k; }
    private function domain() { return preg_replace('/^www\./i', '', strtolower((string)parse_url(home_url(), PHP_URL_HOST))); }
    private function call($action, $args = []) {
        $r = wp_remote_post($this->c['api'] . '?action=' . $action, ['timeout' => 15, 'body' => $args]);
        if (is_wp_error($r)) return null;
        return json_decode(wp_remote_retrieve_body($r), true);
    }
    public function key() { return (string)get_option($this->opt('license_key'), ''); }

    /** لایسنس معتبر؟ نتیجه ۱۲ ساعت کش می‌شود؛ اگر سرور در دسترس نبود، آخرین نتیجهٔ معتبر تا ۳ روز پذیرفته می‌شود */
    public function is_active() {
        $k = $this->key(); if ($k === '') return false;
        $c = get_transient($this->opt('lic_ok')); if ($c !== false) return $c === 'yes';
        $r = $this->call('validate', ['license_key' => $k, 'domain' => $this->domain(), 'product' => $this->c['product']]);
        if ($r === null) { $last = (int)get_option($this->opt('last_ok'), 0); return $last && time() - $last < 3 * DAY_IN_SECONDS; }
        $ok = !empty($r['valid']);
        set_transient($this->opt('lic_ok'), $ok ? 'yes' : 'no', 12 * HOUR_IN_SECONDS);
        if ($ok) update_option($this->opt('last_ok'), time());
        return $ok;
    }
    public function activate($key) {
        $r = $this->call('activate', ['license_key' => trim($key), 'domain' => $this->domain()]);
        if (!empty($r['success'])) { update_option($this->opt('license_key'), trim($key)); delete_transient($this->opt('lic_ok')); }
        return $r ?: ['success' => false, 'message' => 'اتصال به سرور لایسنس ممکن نشد'];
    }
    public function deactivate() {
        $this->call('deactivate', ['license_key' => $this->key(), 'domain' => $this->domain()]);
        delete_option($this->opt('license_key')); delete_transient($this->opt('lic_ok'));
    }

    public function menu() { add_submenu_page('plugins.php', 'لایسنس ' . $this->title(), 'لایسنس ' . $this->title(), 'manage_options', $this->opt('license'), [$this, 'page']); }
    public function page() {
        if (!current_user_can('manage_options')) return;
        $msg = '';
        if (!empty($_POST[$this->opt('nonce')]) && wp_verify_nonce($_POST[$this->opt('nonce')], $this->opt('lic'))) {
            if (isset($_POST['deactivate'])) { $this->deactivate(); $msg = 'لایسنس از این سایت برداشته شد.'; }
            else { $r = $this->activate(sanitize_text_field($_POST['key'] ?? '')); $msg = $r['message'] ?? ''; }
        }
        echo '<div class="wrap" dir="rtl"><h1>لایسنس ' . esc_html($this->title()) . '</h1>' . ($msg ? '<div class="notice notice-info"><p>' . esc_html($msg) . '</p></div>' : '');
        echo '<p>وضعیت: <b>' . ($this->is_active() ? '✅ فعال' : '❌ غیرفعال') . '</b></p><form method="post">' . wp_nonce_field($this->opt('lic'), $this->opt('nonce'), true, false);
        echo '<input name="key" value="' . esc_attr($this->key()) . '" style="width:320px;direction:ltr" placeholder="XXXXXX-XXXX-XXXX-XXXX-XXXX"> <button class="button button-primary">فعال‌سازی</button> ';
        if ($this->key()) echo '<button class="button" name="deactivate" value="1">برداشتن از این سایت</button>';
        echo '</form>' . ($this->c['buy_url'] ? '<p><a href="' . esc_url(add_query_arg(['domain' => $this->domain(), 'return' => admin_url('plugins.php?page=' . $this->opt('license'))], $this->c['buy_url'])) . '">خرید لایسنس</a></p>' : '') . '</div>';
    }

    private function remote_update() {
        $r = $this->call('update', ['product' => $this->c['product'], 'version' => $this->c['version'], 'license_key' => $this->key(), 'domain' => $this->domain()]);
        return is_array($r) && !empty($r['success']) ? $r : null;
    }
    public function check_update($t) {
        if (!is_object($t) || empty($t->checked)) return $t;
        $u = $this->remote_update(); if (!$u || empty($u['update_available'])) return $t;
        $base = plugin_basename($this->c['file']);
        $t->response[$base] = (object)['slug' => $this->c['product'], 'plugin' => $base, 'new_version' => $u['version'], 'url' => $u['homepage'] ?? '',
            'package' => $u['package'] ?? '', 'requires' => $u['requires'] ?? '', 'tested' => $u['tested'] ?? '', 'requires_php' => $u['requires_php'] ?? ''];
        return $t;
    }
    public function plugin_info($res, $action, $args) {
        if ($action !== 'plugin_information' || ($args->slug ?? '') !== $this->c['product']) return $res;
        $u = $this->remote_update(); if (!$u) return $res;
        return (object)['name' => $u['name'] ?? $this->c['product'], 'slug' => $this->c['product'], 'version' => $u['version'], 'homepage' => $u['homepage'] ?? '',
            'download_link' => $u['package'] ?? '', 'requires' => $u['requires'] ?? '', 'tested' => $u['tested'] ?? '', 'requires_php' => $u['requires_php'] ?? '',
            'sections' => ['changelog' => nl2br(esc_html($u['changelog'] ?? ''))]];
    }
}
}
