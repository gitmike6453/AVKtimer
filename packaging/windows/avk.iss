; Windows installer definition (Inno Setup).
; Expects the onefile build to already exist at <repo-root>\dist\AVKtimer.exe
; (produced by: pyinstaller packaging/windows/AVKtimer.spec, run from the repo root).
#define RepoRoot SourcePath + "..\..\"

[Setup]
AppId={{AVKTIMER-STUDIO-V17-WIN}}
AppName=AVKtimer Studio
AppPublisher=AVK Studio
AppVersion=1.7
DefaultDirName={autopf}\AVKtimer Studio
DefaultGroupName=AVKtimer Studio v1.7
AllowNoIcons=yes
Compression=lzma
SolidCompression=yes
WizardStyle=modern

VersionInfoVersion=1.7.0.0
VersionInfoTextVersion=1.7

OutputDir={#RepoRoot}Output
OutputBaseFilename=AVKtimer_Studio_v1.7_Setup
SetupIconFile={#RepoRoot}assets\app.ico

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#RepoRoot}dist\AVKtimer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}assets\app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\AVKtimer Studio v1.7"; Filename: "{app}\AVKtimer.exe"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\AVKtimer Studio v1.7"; Filename: "{app}\AVKtimer.exe"; Tasks: desktopicon; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\AVKtimer.exe"; Description: "{cm:LaunchProgram,AVKtimer Studio}"; Flags: nowait postinstall skipifsilent
