<?php
if (!defined('ABSPATH')) exit;
// محصولات افزونه‌های وردپرسی وبیکری (قیمت‌ها ریال) — از config.php سرور قبلی؛ بعداً از پنل قابل ویرایش است
return array (
  'wccp' => 
  array (
    'label' => 'baget ادیت فیلدهای پرداخت',
    'icon' => '🛒',
    'desc' => 'ویرایش و سفارشی‌سازی فیلدهای صفحه پرداخت ووکامرس',
    'price' => 1990000,
    'plans' => 
    array (
    ),
    'update' => 
    array (
      'version' => '1.3.3',
      'package' => 'https://webakery.ir/license-server/updates/wccp.zip',
      'requires' => '5.8',
      'tested' => '6.6',
      'requires_php' => '7.4',
      'changelog' => 'نسخه ۱.۳.۳: تست سیستم آپدیت خودکار.',
    ),
  ),
  'access-levels' => 
  array (
    'label' => 'Barbari — مدیریت دسترسی کاربران',
    'icon' => '🔐',
    'desc' => 'کنترل دسترسی کاربران به افزونه‌ها و بخش‌های وردپرس',
    'price' => 999990,
    'plans' => 
    array (
    ),
    'update' => 
    array (
      'version' => '1.5.8',
      'package' => 'https://webakery.ir/license-server/updates/access-levels.zip',
      'requires' => '5.0',
      'tested' => '6.6',
      'requires_php' => '7.4',
      'changelog' => 'نسخه ۱.۵.۸: اصلاح قیمت، رفع باگ کلیک دسترسی افزونه‌ها، جدول کاربران جمع‌وجورتر.',
    ),
  ),
  'sokhte-jet' => 
  array (
    'label' => 'Sokhte Jet — تحلیل و بهینه‌سازی عملکرد',
    'icon' => '⚡',
    'desc' => 'تحلیل سرعت سایت و پیشنهاد بهینه‌سازی عملکرد',
    'price' => 0,
    'plans' => 
    array (
    ),
    'update' => 
    array (
      'version' => '1.0.0',
      'package' => 'https://webakery.ir/license-server/updates/sokhte-jet.zip',
      'requires' => '5.0',
      'tested' => '6.6',
      'requires_php' => '7.4',
      'changelog' => 'نسخه اولیه.',
    ),
  ),
  'hesabdar' => 
  array (
    'label' => 'Hesabdar — پرتال حسابدار',
    'icon' => '📊',
    'desc' => 'پرتال حسابدار، فاکتور و گزارش‌گیری برای فروشگاه',
    'price' => 7990000,
    'plans' => 
    array (
    ),
    'update' => 
    array (
      'version' => '1.10.1',
      'package' => 'https://webakery.ir/license-server/updates/hesabdar.zip',
      'requires' => '5.8',
      'tested' => '6.6',
      'requires_php' => '7.4',
      'changelog' => 'نسخه ۱.۹.۱: کارهای دسته‌جمعی تغییر وضعیت، لیست سفارش با ستون محصول، ویرایش/ایجاد سفارش.',
    ),
  ),
  'nobat-man' => 
  array (
    'label' => 'نوبت من — رزرو نوبت مشاوره',
    'icon' => '📅',
    'desc' => 'رزرو نوبت مشاوره با تقویم شمسی، پرداخت و نسخه پرو',
    'price' => 5990000,
    'plans' => 
    array (
    ),
    'update' => 
    array (
      'version' => '1.0.5',
      'package' => 'https://webakery.ir/license-server/updates/nobat-man.zip',
      'requires' => '5.8',
      'tested' => '6.7',
      'requires_php' => '7.4',
      'changelog' => 'نسخه ۱.۰.۴: بازه رزرو، ماه‌های فعال، درگاه زیبال، رفع تقویم.',
    ),
  ),
  'webakery-chat' => 
  array (
    'label' => 'چت باکس — پشتیبانی آنلاین سایت',
    'icon' => '💬',
    'desc' => 'چت باکس — ماهانه، ۳ ماهه یا دائمی + اعلان تلگرام/واتساپ',
    'price' => 1500000,
    'plans' => 
    array (
      '1m' => 
      array (
        'months' => 1,
        'price' => 1500000,
        'label' => 'ماهانه',
        'hint' => '۱ ماه دسترسی + آپدیت و پشتیبانی',
      ),
      '3m' => 
      array (
        'months' => 3,
        'price' => 3500000,
        'label' => '۳ ماهه',
        'hint' => '۳ ماه — به‌صرفه‌تر از ۳× ماهانه',
        'badge' => 'پیشنهادی',
      ),
      'life' => 
      array (
        'months' => 0,
        'price' => 7990000,
        'label' => 'دائمی',
        'hint' => 'مادام‌العمر — یک‌بار پرداخت',
      ),
    ),
    'update' => 
    array (
      'version' => '1.4.2',
      'package' => 'https://webakery.ir/license-server/updates/webakery-chat-box.zip',
      'requires' => '5.8',
      'tested' => '6.7',
      'requires_php' => '7.4',
      'changelog' => 'نسخه ۱.۴.۲: قیمت ماهانه ۱۵۰، ۳ ماهه ۳۵۰ و دائمی ۷۹۹ هزار تومان.',
    ),
  ),
  'webakery-discount-pages' => 
  array (
    'label' => 'صفحات تخفیف — ساخت صفحه تخفیف ووکامرس',
    'icon' => '🏷️',
    'desc' => 'ساخت و مدیریت صفحات تخفیف برای فروشگاه ووکامرس',
    'price' => 2990000,
    'plans' => 
    array (
    ),
    'update' => 
    array (
      'version' => '1.0.0',
      'package' => 'https://webakery.ir/license-server/updates/webakery-discount-pages.zip',
      'requires' => '5.8',
      'tested' => '6.7',
      'requires_php' => '7.4',
      'changelog' => 'نسخه ۱.۰.۰: انتشار اولیه صفحات تخفیف.',
    ),
  ),
);
