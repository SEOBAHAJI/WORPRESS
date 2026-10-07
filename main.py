#!/usr/bin/env python3
"""اجرای برنامه: سرور محلی روی 127.0.0.1 + پنجرهٔ بومی (pywebview) یا مرورگر پیش‌فرض."""
import sys
import threading
import time
import webbrowser

from accsoft.db import DB
from accsoft.server import create_server


def main():
    db = DB()
    srv = create_server(db)
    url = f"http://127.0.0.1:{srv.app.port}/"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        if "--browser" in sys.argv:
            raise ImportError
        import webview  # اختیاری
        webview.create_window("نرم‌افزار حسابداری", url, width=1280, height=800)
        webview.start()
    except ImportError:
        print(f"برنامه در مرورگر باز شد: {url}\nبستن تب مرورگر، برنامه را پس از چند ثانیه می‌بندد (یا Ctrl+C).")
        srv.app.last_ping = time.time() + 60  # مهلت اولیه برای بالا آمدن مرورگر
        webbrowser.open(url)
        try:
            while time.time() - srv.app.last_ping < 45:
                time.sleep(2)
        except KeyboardInterrupt:
            pass
    srv.shutdown()


if __name__ == "__main__":
    main()
