!define APPNAME "COGU Loong"
!define APPVERSION "0.9.1"
!define APPPUBLISHER "COGU Team"
!define APPEXE "COGU-Loong.exe"
!define APPURL "https://github.com/cogu-agent/cogu-loong"

Name "${APPNAME} ${APPVERSION}"
OutFile "COGU-Loong-${APPVERSION}-Setup.exe"
InstallDir "$PROGRAMFILES\${APPNAME}"
InstallDirRegKey HKLM "Software\${APPNAME}" "InstallDir"
RequestExecutionLevel admin

SetCompressor /SOLID lzma

!include "MUI2.nsh"

!define MUI_ICON "cogu\web\favicon.ico"
!define MUI_UNICON "cogu\web\favicon.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

LangString APP_DESC ${LANG_SIMPCHINESE} "COGU Loong - 国产认知统一智能体桌面版"
LangString APP_DESC ${LANG_ENGLISH} "COGU Loong - Cognitive Unified Agent Desktop"

VIProductVersion "0.9.1.0"
VIAddVersionKey /LANG=${LANG_SIMPCHINESE} "ProductName" "${APPNAME}"
VIAddVersionKey /LANG=${LANG_SIMPCHINESE} "ProductVersion" "${APPVERSION}"
VIAddVersionKey /LANG=${LANG_SIMPCHINESE} "CompanyName" "${APPPUBLISHER}"
VIAddVersionKey /LANG=${LANG_SIMPCHINESE} "FileDescription" "COGU Loong Desktop Installer"
VIAddVersionKey /LANG=${LANG_SIMPCHINESE} "FileVersion" "${APPVERSION}"

Section "MainSection" SEC01
  SetOutPath "$INSTDIR"
  SetOverwrite on

  File /r "dist\COGU-Loong\*.*"

  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortCut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${APPEXE}" "" "$INSTDIR\${APPEXE}" 0
  CreateShortCut "$SMPROGRAMS\${APPNAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
  CreateShortCut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${APPEXE}" "" "$INSTDIR\${APPEXE}" 0

  WriteRegStr HKLM "Software\${APPNAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${APPVERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${APPPUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "URLInfoAbout" "${APPURL}"
SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section Uninstall
  Delete "$INSTDIR\*.*"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\${APPNAME}\*.*"
  RMDir "$SMPROGRAMS\${APPNAME}"
  Delete "$DESKTOP\${APPNAME}.lnk"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
  DeleteRegKey HKLM "Software\${APPNAME}"
SectionEnd