@echo off
rem ساخت فایل اجرایی ویندوز. پیش‌نیاز: Python 3.10+ و  pip install -r requirements.txt pyinstaller
rem ابتدا یک‌بار:  python tools\license_tool.py genkey   (کلید عمومی را در accsoft\pubkey.py می‌نویسد)
findstr /C:"PUBLIC_KEY_HEX = \"\"" accsoft\pubkey.py >nul && (echo خطا: ابتدا genkey را اجرا کنید & exit /b 1)
set EXTRA=
if exist accsoft\catalog.json set EXTRA=--add-data "accsoft\catalog.json;accsoft"
pyinstaller --noconfirm --onefile --windowed --name Daftarchi ^
  --add-data "accsoft\static;accsoft\static" %EXTRA% ^
  --collect-all webview --collect-all pythonnet --collect-all clr_loader ^
  --exclude-module tkinter --exclude-module unittest --exclude-module pydoc ^
  main.py
echo فایل نهایی: dist\Daftarchi.exe
