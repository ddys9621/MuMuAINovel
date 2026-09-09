; MuMuAINovel 安装包脚本（Inno Setup 6）
; 构建：ISCC.exe installer.iss（需先跑 build_exe.ps1 产出 dist\MuMuAINovel）
; CI 覆盖版本号：ISCC.exe /DMyAppVersion=1.2.3 installer.iss（见 .github/workflows/build-windows.yml）
;
; 设计要点：
; - 每用户安装（PrivilegesRequired=lowest + {userpf}）：免管理员/UAC，
;   且安装目录可写——应用的 data\/config.ini/embedding 模型下载都写在安装目录，
;   装到 Program Files 会因写权限直接不可用，切勿改回 admin 模式
; - 卸载时保留用户数据（data\ 与 config.ini），仅清理可再生的 embedding 缓存与日志

#define MyAppName "MuMuAINovel"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "MuMuAI"
#define MyAppExeName "MuMuAINovel.exe"
#define MyDistDir "dist\\MuMuAINovel"

[Setup]
AppId={{8F1C7A62-3B4E-4D9A-9C21-6E5D0A7B4F13}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={userpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=MuMuAINovel-Setup-v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; 应用含 64 位二进制（torch 等）
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
; 官方包不带简中；若手动放置了 ChineseSimplified.isl 则优先启用
#if FileExists(AddBackslash(CompilerPath) + "Languages\\ChineseSimplified.isl")
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\\ChineseSimplified.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#MyDistDir}\\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 可再生缓存与日志随卸载清理；data\（数据库/向量库）与 config.ini 刻意保留，
; 用户重装后数据仍在；如需彻底清除可手动删除安装目录
Type: filesandordirs; Name: "{app}\embedding"
Type: filesandordirs; Name: "{app}\logs"
