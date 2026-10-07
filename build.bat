@echo off
rem ساخت فایل اجرایی ویندوز. پیش‌نیاز: Python 3.10+ و  pip install -r requirements.txt pyinstaller
rem ابتدا یک‌بار:  python tools\license_tool.py genkey   (کلید عمومی را در accsoft\pubkey.py می‌نویسد)
findstr /C:"PUBLIC_KEY_HEX = \"\"" accsoft\pubkey.py >nul && (echo خطا: ابتدا genkey را اجرا کنید & exit /b 1)
pyinstaller --noconfirm --onefile --windowed --name AccSoft ^
  --add-data "accsoft\static;accsoft\static" ^
  --exclude-module tkinter --exclude-module unittest --exclude-module pydoc ^
  main.py
echo فایل نهایی: dist\AccSoft.exe
