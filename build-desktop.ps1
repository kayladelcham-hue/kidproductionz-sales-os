$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$FrontendDist = Join-Path $ProjectRoot 'app\frontend\dist\index.html'
$Spec = Join-Path $ProjectRoot 'kidproductionz.spec'
$DistPath = Join-Path $ProjectRoot 'dist_release_v2'
$FrontendDir = Join-Path $ProjectRoot 'app\frontend'
$ViteConfig = Join-Path $FrontendDir 'vite.config.mjs'
$ViteDisabled = Join-Path $FrontendDir 'vite.config.mjs.disabled'
$PortableNode = 'C:\Users\CJ\Tools\node\node-v22.20.0-win-x64'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found: $Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $PortableNode 'node.exe'))) { throw "Portable Node not found: $PortableNode" }
if (-not (Test-Path -LiteralPath $Spec)) {
    throw "PyInstaller spec not found: $Spec"
}

& $Python -c 'import PyInstaller' 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed in .venv. Install it there before packaging.'
}

Push-Location $ProjectRoot
try {
    # Vite's config loader triggers Windows spawn EPERM in this environment.
    # Preserve the config for development while producing an equivalent native build.
    if (Test-Path -LiteralPath $ViteConfig) { Rename-Item -LiteralPath $ViteConfig -NewName (Split-Path $ViteDisabled -Leaf) }
    try {
        $oldPath=$env:PATH; $env:PATH="$PortableNode;$oldPath"
        Push-Location $FrontendDir
        & (Join-Path $PortableNode 'node.exe') (Join-Path $FrontendDir 'node_modules\vite\bin\vite.js') build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed.' }
        Pop-Location
    } finally {
        if ((Get-Location).Path -eq $FrontendDir) { Pop-Location }
        $env:PATH=$oldPath
        if (Test-Path -LiteralPath $ViteDisabled) { Rename-Item -LiteralPath $ViteDisabled -NewName (Split-Path $ViteConfig -Leaf) }
    }
    if (-not (Test-Path -LiteralPath $FrontendDist)) { throw 'Frontend production output is missing after build.' }
    if (Test-Path -LiteralPath $DistPath) { Remove-Item -LiteralPath $DistPath -Recurse -Force }
    & $Python -m PyInstaller --noconfirm --clean --distpath $DistPath $Spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller packaging failed.' }
    $Output = Join-Path $DistPath 'KidProductionz Sales OS'
    $legacyRootExe = Join-Path $ProjectRoot 'dist\KidProductionz Sales OS.exe'
    if (Test-Path -LiteralPath $legacyRootExe) { Remove-Item -LiteralPath $legacyRootExe -Force }
    Write-Host "Desktop package created: $Output"
}
finally {
    Pop-Location
}
