#define APPNAME "COGU AGENT"
#define APPVERSION "1.4.0"
#define APPPUBLISHER "COGU Team"
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
OutputBaseFilename=COGU-AGENT-v{#APPVERSION}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinese"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\COGU-Loong.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "cogu\*"; DestDir: "{app}\cogu"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "skills\*"; DestDir: "{app}\skills"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "pangu-model\*"; DestDir: "{app}\pangu-model"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.safetensors"
Source: "pangu-env\*"; DestDir: "{app}\pangu-env"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "USAGE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "quick-start.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "start-cogu.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "studio-ui\*"; DestDir: "{app}\studio-ui"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "node_modules\"

[Icons]
Name: "{group}\COGU Loong - 桌面版"; Filename: "{app}\COGU-Loong.exe"
Name: "{group}\COGU AGENT - 快速启动"; Filename: "{app}\quick-start.bat"
Name: "{group}\COGU AGENT - Gateway模式"; Filename: "{app}\start-cogu.bat"
Name: "{group}\使用手册"; Filename: "{app}\USAGE.md"
Name: "{group}\{cm:UninstallProgram,{#APPNAME}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\COGU Loong"; Filename: "{app}\COGU-Loong.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\COGU-Loong.exe"; Description: "启动 COGU Loong 桌面版"; Flags: nowait postinstall skipifsilent

[Code]
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
end;
