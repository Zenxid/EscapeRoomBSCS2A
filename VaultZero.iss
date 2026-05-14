[Setup]
AppName=Vault Zero
AppVersion=1.0
DefaultDirName={autopf}\Vault Zero
DefaultGroupName=Vault Zero
OutputDir=.\installer
OutputBaseFilename=VaultZero_Setup
SetupIconFile=assets\icon.png
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Your single .exe (from --onefile build)
Source: "dist\VaultZero.exe"; DestDir: "{app}"; Flags: ignoreversion
; If you have any external files not bundled (e.g., save files, configs)
; Source: "arena.db"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Vault Zero"; Filename: "{app}\VaultZero.exe"
Name: "{autodesktop}\Vault Zero"; Filename: "{app}\VaultZero.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VaultZero.exe"; Description: "Launch Vault Zero"; Flags: nowait postinstall skipifsilent