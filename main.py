#!/usr/bin/env python3
"""اجرای برنامه: سرور محلی روی 127.0.0.1 + پنجرهٔ بومی (pywebview) یا مرورگر پیش‌فرض."""
import sys
import threading
import time
import webbrowser

from accsoft.db import DB
from accsoft.server import create_server


def _log(msg):
    """ردی از نحوهٔ اجرا (پنجرهٔ بومی یا مرورگر) برای عیب‌یابی."""
    try:
        from accsoft.config import data_dir
        with open(data_dir() / "startup.log", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def main():
    import os
    # نسخهٔ --windowed (بدون کنسول) stdout/stderr ندارد؛ print و traceback نباید برنامه را بیندازند
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    db = DB()
    srv = create_server(db)
    url = f"http://127.0.0.1:{srv.app.port}/"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    native, why = False, ""
    if "--browser" not in sys.argv:
        try:
            import webview  # پنجرهٔ بومی (ویندوز: Edge WebView2)
            webview.settings["ALLOW_DOWNLOADS"] = True       # خروجی Excel
            webview.create_window("دفترچی", url, width=1280, height=820, min_size=(900, 600))
            _log("native-start")
            webview.start(gui="edgechromium" if sys.platform == "win32" else None)   # با بستن پنجره برمی‌گردد
            native = True
        except Exception as e:                                 # pywebview/WebView2 نیست → مرورگر
            why = f"{type(e).__name__}: {e}"
    if not native:
        _log("browser-fallback " + why)
        print(f"برنامه در مرورگر باز شد: {url}\nبستن تب مرورگر، برنامه را پس از چند دقیقه می‌بندد (یا Ctrl+C).")
        srv.app.last_ping = time.time() + 60  # مهلت اولیه برای بالا آمدن مرورگر
        webbrowser.open(url)
        try:
            while time.time() - srv.app.last_ping < 300:
                time.sleep(2)
        except KeyboardInterrupt:
            pass
    srv.shutdown()


if __name__ == "__main__":
    main()
