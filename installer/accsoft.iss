; Inno Setup — نصب برای کاربر جاری (بدون نیاز به دسترسی ادمین)
#define AppVer GetEnv("APP_VERSION")
[Setup]
AppName=AccSoft
AppVersion={#AppVer}
AppPublisher=AccSoft
DefaultDirName={autopf}\AccSoft
DefaultGroupName=AccSoft
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=AccSoft-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\AccSoft.exe

[Files]
Source: "..\dist\AccSoft.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\AccSoft"; Filename: "{app}\AccSoft.exe"
Name: "{autodesktop}\AccSoft"; Filename: "{app}\AccSoft.exe"

[Run]
Filename: "{app}\AccSoft.exe"; Description: "Run AccSoft"; Flags: nowait postinstall skipifsilent

; داده‌های کاربر (%APPDATA%\AccSoft) هنگام حذف برنامه عمداً پاک نمی‌شود.
