[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$demoExe = Join-Path $repoRoot 'dist\HuiyanDemo\HuiyanDemo.exe'
if (-not (Test-Path -LiteralPath $demoExe)) {
    throw "Build the package first; executable not found: $demoExe"
}

$desktop = [Environment]::GetFolderPath('Desktop')
# Keep this script compatible with Windows PowerShell 5, which may read a
# UTF-8 no-BOM script using the local ANSI code page.
$shortcutName = ([char]0x6167) + ([char]0x773C) + ([char]0x8BC6) + ([char]0x73E0) + '.lnk'
$shortcutPath = Join-Path $desktop $shortcutName
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $demoExe
$shortcut.WorkingDirectory = Split-Path -Parent $demoExe
$shortcut.IconLocation = "$demoExe,0"
$shortcut.Description = 'Huiyan Windows demonstration'
$shortcut.Save()
Write-Host "Shortcut created: $shortcutPath"
