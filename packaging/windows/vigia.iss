; Instalador Windows (Inno Setup) do Vigia de Slides.
; Espera que o onefile já exista em dist\VigiaSlides.exe
; (produzido por: pyinstaller packaging/windows/VigiaSlides.spec, correr a partir da raiz do repo).
#define RepoRoot SourcePath + "..\..\"

[Setup]
AppId={{AVKTIMER-VIGIA-SLIDES-WIN}}
AppName=Cue Timer Vigia de Slides
AppPublisher=AVK Studio
AppVersion=1.0.1
DefaultDirName={autopf}\Cue Timer Vigia de Slides
DefaultGroupName=Cue Timer Vigia de Slides
AllowNoIcons=yes
Compression=lzma
SolidCompression=yes
WizardStyle=modern

VersionInfoVersion=1.0.1.0
VersionInfoTextVersion=1.0.1

OutputDir={#RepoRoot}Output
OutputBaseFilename=CueTimer_VigiaSlides_v1.0.1_Setup
SetupIconFile={#RepoRoot}assets\app.ico

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#RepoRoot}dist\VigiaSlides.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}assets\app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Cue Timer Vigia de Slides"; Filename: "{app}\VigiaSlides.exe"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\Cue Timer Vigia de Slides"; Filename: "{app}\VigiaSlides.exe"; Tasks: desktopicon; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\VigiaSlides.exe"; Description: "{cm:LaunchProgram,Cue Timer Vigia de Slides}"; Flags: nowait postinstall skipifsilent
