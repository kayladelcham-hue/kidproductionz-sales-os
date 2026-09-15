param(
    [string]$PackageDirectory = "$(Join-Path $PSScriptRoot 'dist\KidProductionz Sales OS')",
    [string]$ShortcutName = "KidProductionz Sales OS"
)

$ErrorActionPreference = 'Stop'

$packageRoot = [IO.Path]::GetFullPath($PackageDirectory)
$exePath = Join-Path $packageRoot 'KidProductionz Sales OS.exe'
$iconPath = Join-Path $packageRoot 'KidProductionz Sales OS.ico'

if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Packaged executable was not found: $exePath. Build the desktop package first."
}

# Prefer the packaged icon. The desktop package builder may also use the source
# logo as a fallback when an ICO is unavailable.
$shortcutIcon = if (Test-Path -LiteralPath $iconPath -PathType Leaf) { $iconPath } else { "$exePath,0" }
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "$ShortcutName.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $packageRoot
$shortcut.IconLocation = $shortcutIcon
$shortcut.Description = 'Launch KidProductionz Sales OS'
$shortcut.Save()

Write-Host "Created desktop shortcut: $shortcutPath"
Write-Host "Target: $exePath"
