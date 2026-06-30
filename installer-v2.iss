#define APPNAME "COGU Loong"
#define APPVERSION "2.0.0"
#define APPPUBLISHER "COGU Team"
#define APPURL "https://github.com/THUDou/cogu-agent"
#define APPEXE "COGU Loong.exe"

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
OutputDir=G:\COGU-Release-v2
OutputBaseFilename=COGU-Loong-v{#APPVERSION}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#APPEXE}
SetupIconFile=D:\COGU AGENT\cogu_agent\loong-desktop\assets\logo.ico
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DiskSpanning=yes
DiskSliceSize=2100000000
SlicesPerDisk=1

[Languages]
Name: "chinese"; MessagesFile: "compiler:Default.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "D:\COGU AGENT\cogu_agent\dist-electron\win-unpacked\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "resources\skills\office-claw\.playwright-browsers\chromium-1200\chrome-win64\locales\*,resources\skills\office-claw\.playwright-browsers\chromium-1200\chrome-win64\MEIPreload\*"
Source: "D:\COGU AGENT\cogu_agent\models\*"; DestDir: "{app}\resources\models"; Flags: ignoreversion recursesubdirs createallsubdirs nocompression
Source: "D:\COGU AGENT\cogu_agent\pangu-model\*"; DestDir: "{app}\resources\pangu-model"; Flags: ignoreversion recursesubdirs createallsubdirs nocompression; Excludes: ".cache\*,*.safetensors.index.json"

[Icons]
Name: "{group}\{#APPNAME}"; Filename: "{app}\{#APPEXE}"
Name: "{group}\{cm:UninstallProgram,{#APPNAME}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#APPNAME}"; Filename: "{app}\{#APPEXE}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#APPEXE}"; Description: "{cm:LaunchProgram,{#APPNAME}}"; Flags: nowait postinstall skipifsilent