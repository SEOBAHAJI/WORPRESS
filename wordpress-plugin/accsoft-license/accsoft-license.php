<?php
/**
 * Plugin Name: AccSoft License Server
 * Description: سرور لایسنس نرم‌افزار حسابداری AccSoft: پنل مدیریت، پیشخوان مشتری (خرید/تمدید/انتقال)، پرداخت زیبال و API برای برنامه.
 * Version: 1.0.0
 * Requires PHP: 7.4
 * Text Domain: accsoft-license
 */
if (!defined('ABSPATH')) exit;

define('ACCSOFT_VER', '1.0.0');
define('ACCSOFT_DIR', plugin_dir_path(__FILE__));

require_once ACCSOFT_DIR . 'includes/crypto.php';
require_once ACCSOFT_DIR . 'includes/store.php';
require_once ACCSOFT_DIR . 'includes/zibal.php';
require_once ACCSOFT_DIR . 'includes/rest.php';
require_once ACCSOFT_DIR . 'includes/portal.php';
require_once ACCSOFT_DIR . 'includes/admin.php';

register_activation_hook(__FILE__, 'accsoft_activate');
add_action('plugins_loaded', function () {
    if (get_option('accsoft_db_ver') !== ACCSOFT_VER) accsoft_install_tables();
});
