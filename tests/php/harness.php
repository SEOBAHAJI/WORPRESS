<?php
/* هارنس آزمایشی: موتور legacy افزونه را با wpdb شبیه‌سازی‌شده (SQLite) و stubهای وردپرس اجرا می‌کند.
   php harness.php <db> <cmd> [json]   cmd = api | pay | import | sql */
define('ABSPATH', '/'); define('ARRAY_A', 'ARRAY_A'); define('DAY_IN_SECONDS', 86400); define('HOUR_IN_SECONDS', 3600);
define('ACCSOFT_DIR', dirname(__DIR__, 2) . '/wordpress-plugin/accsoft-license/'); define('ACCSOFT_VER', 'test');
[$_, $dbfile, $cmd] = $argv; $arg = json_decode($argv[3] ?? '{}', true) ?: [];
$GLOBALS['O'] = file_exists("$dbfile.opt") ? unserialize(file_get_contents("$dbfile.opt")) : [];
register_shutdown_function(function () use ($dbfile) { file_put_contents("$dbfile.opt", serialize($GLOBALS['O'])); });
function get_option($k, $d = false) { return $GLOBALS['O'][$k] ?? $d; }
function update_option($k, $v, $a = null) { $GLOBALS['O'][$k] = $v; return true; }
function add_action() {} function add_filter() {} function add_rewrite_rule() {} function register_rest_route() {}
function current_time($f) { return $f === 'mysql' ? gmdate('Y-m-d H:i:s') : gmdate($f); }
function status_header($c) {} function nocache_headers() {} function esc_html($s) { return htmlspecialchars((string)$s, ENT_QUOTES); }
function esc_attr($s) { return esc_html($s); } function esc_url($s) { return esc_html($s); } function esc_url_raw($s) { return (string)$s; }
function wp_json_encode($v, $f = 0) { return json_encode($v, $f); } function number_format_i18n($n) { return number_format($n); }
function wp_nonce_field() { return ''; } function wp_verify_nonce() { return 1; } function home_url($p = '') { return 'https://webakery.test' . $p; }
function add_query_arg($a, $u) { return $u . '?' . http_build_query(array_filter($a, fn($x) => $x !== '' && $x !== null)); }
function checked($a, $b, $e = true) { return $a == $b ? ' checked' : ''; } function get_permalink() { return 'https://webakery.test/accsoft-panel/'; }
function get_query_var() { return ''; } function wp_safe_redirect($u) { echo "REDIRECT $u"; exit; } function wp_redirect($u) { echo "REDIRECT $u"; exit; }
function wp_mail($to, $s, $b) { $GLOBALS['mails'][] = [$to, $s]; return true; } function get_post() { return true; }
function wp_remote_post($url, $a) {
    $b = json_decode($a['body'], true);
    if (str_ends_with($url, '/request')) return ['b' => ['result' => 100, 'trackId' => 777001]];
    return ['b' => ['result' => 100, 'amount' => $GLOBALS['O']['zibal_amount'] ?? 0]];
}
function is_wp_error() { return false; } function wp_remote_retrieve_body($r) { return json_encode($r['b']); }
class WPDB_Mock {
    public $prefix = 'wp_', $insert_id = 0; private $p;
    function __construct($f) { $this->p = new PDO("sqlite:$f"); $this->p->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        foreach ([
          'wlic' => 'id INTEGER PRIMARY KEY AUTOINCREMENT, uid, license_key UNIQUE, email, product, note, status, expires_at, created_at',
          'wact' => 'id INTEGER PRIMARY KEY AUTOINCREMENT, license_key, domain, ip, activated_at',
          'wpay' => 'id INTEGER PRIMARY KEY AUTOINCREMENT, track_id UNIQUE, plugin, email, domain, return_url, amount, base_amount, plan, months, coupon_id, coupon_code, coupon_discount, status, license_key, created_at',
          'wcoupon' => 'id INTEGER PRIMARY KEY AUTOINCREMENT, uid, code UNIQUE, type, value, product, max_uses, used_count, min_amount, expires_at, status, note, created_at'] as $t => $c)
            $this->p->exec("CREATE TABLE IF NOT EXISTS wp_accsoft_$t ($c)"); }
    function prepare($sql, ...$args) { if (count($args) === 1 && is_array($args[0])) $args = $args[0]; $i = 0;
        return preg_replace_callback('/%[sd]/', function ($m) use (&$i, $args) { $v = $args[$i++]; return $m[0] === '%d' ? (int)$v : $this->p->quote((string)$v); }, $sql); }
    function get_row($sql, $o = null) { $r = $this->p->query($sql)->fetch(PDO::FETCH_ASSOC); return $r ?: null; }
    function get_results($sql, $o = null) { return $this->p->query($sql)->fetchAll(PDO::FETCH_ASSOC); }
    function get_var($sql) { $r = $this->p->query($sql)->fetch(PDO::FETCH_NUM); return $r ? $r[0] : null; }
    function query($sql) { return $this->p->exec($sql); }
    function insert($t, $d) { $this->p->prepare("INSERT INTO $t (" . implode(',', array_keys($d)) . ') VALUES (' . implode(',', array_fill(0, count($d), '?')) . ')')->execute(array_values($d)); $this->insert_id = $this->p->lastInsertId(); }
    private function where($w) { return implode(' AND ', array_map(fn($k) => "$k=?", array_keys($w))); }
    function update($t, $d, $w) { $s = $this->p->prepare("UPDATE $t SET " . implode(',', array_map(fn($k) => "$k=?", array_keys($d))) . ' WHERE ' . $this->where($w)); $s->execute([...array_values($d), ...array_values($w)]); return $s->rowCount(); }
    function delete($t, $w) { $s = $this->p->prepare("DELETE FROM $t WHERE " . $this->where($w)); $s->execute(array_values($w)); return $s->rowCount(); }
    function esc_like($s) { return addcslashes($s, '_%\\'); }
}
$wpdb = new WPDB_Mock($dbfile);
require ACCSOFT_DIR . 'includes/crypto.php'; require ACCSOFT_DIR . 'includes/store.php'; require ACCSOFT_DIR . 'includes/legacy.php'; require ACCSOFT_DIR . 'includes/legacy-admin.php';
$_GET = $arg['get'] ?? []; $_POST = $arg['post'] ?? []; $_REQUEST = array_merge($_GET, $_POST);
if (isset($arg['opts'])) foreach ($arg['opts'] as $k => $v) $GLOBALS['O'][$k] = $v;
if ($cmd === 'api') { accsoft_wl_api($_REQUEST['action'] ?? '', $arg['post'] ?? []); }
if ($cmd === 'pay') { $_SERVER['REQUEST_METHOD'] = $arg['method'] ?? 'GET'; accsoft_wl_pay(); }
if ($cmd === 'import') { echo json_encode(accsoft_wl_import($arg['data'])); }
if ($cmd === 'sql') { echo json_encode($wpdb->get_results($arg['q'])); }
