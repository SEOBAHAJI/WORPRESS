; Inno Setup — نصب برای کاربر جاری (بدون نیاز به دسترسی ادمین)
#define AppVer GetEnv("APP_VERSION")
[Setup]
AppName=Daftarchi
AppVersion={#AppVer}
AppPublisher=Daftarchi
DefaultDirName={autopf}\Daftarchi
DefaultGroupName=Daftarchi
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Daftarchi-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Daftarchi.exe

[Files]
Source: "..\dist\Daftarchi.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Daftarchi"; Filename: "{app}\Daftarchi.exe"
Name: "{autodesktop}\Daftarchi"; Filename: "{app}\Daftarchi.exe"

[Run]
Filename: "{app}\Daftarchi.exe"; Description: "Run Daftarchi"; Flags: nowait postinstall skipifsilent

; داده‌های کاربر (%APPDATA%\Daftarchi) هنگام حذف برنامه عمداً پاک نمی‌شود.
