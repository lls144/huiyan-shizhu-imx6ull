[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
$specPath = Join-Path $repoRoot 'HuiyanDemo.spec'
$buildDir = Join-Path $repoRoot 'build'
$distDir = Join-Path $repoRoot 'dist'
$demoDir = Join-Path $distDir 'HuiyanDemo'
$demoExe = Join-Path $demoDir 'HuiyanDemo.exe'
$iconSource = Join-Path $repoRoot 'pc\gui\assets\huiyan_logo.svg'
$iconPath = Join-Path $repoRoot 'pc\gui\assets\huiyan_logo.ico'

function Assert-ChildPath([string]$candidate, [string]$parent) {
    $parentFull = [IO.Path]::GetFullPath($parent).TrimEnd('\') + '\'
    $candidateFull = [IO.Path]::GetFullPath($candidate)
    if (-not $candidateFull.StartsWith($parentFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside repository: $candidateFull"
    }
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python virtual environment not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $specPath)) {
    throw "PyInstaller spec not found: $specPath"
}
if (-not (Test-Path -LiteralPath $iconSource)) {
    throw "Committed SVG icon not found: $iconSource"
}

$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $pythonExe -c "import PyInstaller, PIL" 2>$null
$toolingMissing = $LASTEXITCODE -ne 0
$ErrorActionPreference = $previousErrorAction
if ($toolingMissing) {
    & $pythonExe -m pip install pyinstaller pillow
    if ($LASTEXITCODE -ne 0) { throw 'Could not install required build tooling.' }
}

& $pythonExe (Join-Path $repoRoot 'tools\windows\build_icon.py') $iconSource $iconPath
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }

foreach ($target in @($buildDir, $demoDir)) {
    if (Test-Path -LiteralPath $target) {
        Assert-ChildPath $target $repoRoot
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

& $pythonExe -m PyInstaller --noconfirm --clean $specPath
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
if (-not (Test-Path -LiteralPath $demoExe)) { throw "Expected executable not created: $demoExe" }

$size = (Get-Item -LiteralPath $demoExe).Length
Write-Host "Build PASS: $demoExe ($([Math]::Round($size / 1MB, 2)) MiB)"
