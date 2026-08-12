; Windows installer definition (Inno Setup).
; Expects the onefile build to already exist at <repo-root>\dist\CueTimer.exe
; (produced by: pyinstaller packaging/windows/AVKtimer.spec, run from the repo root).
#define RepoRoot SourcePath + "..\..\"

[Setup]
; AppId mantido igual ao original (não visível ao utilizador) para o Windows
; continuar a tratar isto como uma atualização do mesmo programa em vez de
; instalar uma segunda entrada duplicada no Painel de Controlo.
AppId={{AVKTIMER-STUDIO-V17-WIN}}
AppName=Cue Timer
AppPublisher=AVK Studio
AppVersion=2.1
DefaultDirName={autopf}\Cue Timer
DefaultGroupName=Cue Timer v2.1
AllowNoIcons=yes
Compression=lzma
SolidCompression=yes
WizardStyle=modern

VersionInfoVersion=2.1.0.0
VersionInfoTextVersion=2.1

OutputDir={#RepoRoot}Output
OutputBaseFilename=CueTimer_Setup_v2.1
SetupIconFile={#RepoRoot}assets\app.ico

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#RepoRoot}dist\CueTimer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}assets\app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Cue Timer"; Filename: "{app}\CueTimer.exe"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\Cue Timer"; Filename: "{app}\CueTimer.exe"; Tasks: desktopicon; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\CueTimer.exe"; Description: "{cm:LaunchProgram,Cue Timer}"; Flags: nowait postinstall skipifsilent
