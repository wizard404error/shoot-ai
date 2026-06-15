; Inno Setup Script for Kawkab AI
; Creates a professional Windows installer

#define MyAppName "Kawkab AI"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Kawkab AI"
#define MyAppURL "https://github.com/yourusername/kawkab-ai"
#define MyAppExeName "KawkabAI.exe"

[Setup]
AppId={{A7F8E9D2-3B4C-4E5F-A1B2-C3D4E5F6A7B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE
InfoBeforeFile=
InfoAfterFile=
OutputDir=dist\installer
OutputBaseFilename=KawkabAI-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoCopyright=Copyright (C) 2024 {#MyAppPublisher}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[CustomMessages]
english.CreateDesktopIcon=Create a &desktop shortcut
english.LaunchAfterInstall=Launch {#MyAppName} after installation completes
english.OllamaRequired={#MyAppName} requires Ollama for AI features. Get it from https://ollama.com/download
arabic.CreateDesktopIcon=إنشاء اختصار على &سطح المكتب
arabic.LaunchAfterInstall=تشغيل {#MyAppName} بعد اكتمال التثبيت
arabic.OllamaRequired={#MyAppName} يتطلب Ollama لميزات الذكاء الاصطناعي. احصل عليه من https://ollama.com/download

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "Additional shortcuts:";
Name: "launchafter"; Description: "{cm:LaunchAfterInstall}"; GroupDescription: "Other tasks:"; Flags: checkedonce

[Files]
Source: "dist\KawkabAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchAfterInstall}"; Flags: nowait postinstall skipifsilent; Tasks: launchafter

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{localappdata}\KawkabAI"
Type: filesandordirs; Name: "{userdocs}\KawkabAI"

[Code]
function InitializeSetup: Boolean;
begin
  Result := True;
  MsgBox(ExpandConstant('{cm:OllamaRequired}'), mbInformation, MB_OK);
end;
