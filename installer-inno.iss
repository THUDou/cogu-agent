#define APPNAME "COGU Loong"
#define APPVERSION "0.9.1"
#define APPPUBLISHER "COGU Team"
#define APPEXE "COGU-Loong.exe"
#define APPURL "https://github.com/THUDou/cogu-agent"

[Setup]
AppId={{B7E3F2A1-4D5C-6E8F-9A0B-1C2D3E4F5A6B}
AppName={#APPNAME}
AppVersion={#APPVERSION}
AppPublisher={#APPPUBLISHER}
AppPublisherURL={#APPURL}
AppSupportURL={#APPURL}
DefaultDirName={autopf}\{#APPNAME}
DefaultGroupName={#APPNAME}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=COGU-Loong-{#APPVERSION}-Setup-Inno
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#APPEXE}
SetupIconFile=
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]

Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\COGU-Loong.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\COGU AGENT\MINI\openPangu-Embedded-1B\*"; DestDir: "{app}\pangu-model"; Flags: ignoreversion recursesubdirs createallsubdirs nocompression

[Icons]
Name: "{group}\{#APPNAME}"; Filename: "{app}\{#APPEXE}"
Name: "{group}\{cm:UninstallProgram,{#APPNAME}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#APPNAME}"; Filename: "{app}\{#APPEXE}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#APPEXE}"; Description: "{cm:LaunchProgram,{#APPNAME}}"; Flags: nowait postinstall skipifsilent