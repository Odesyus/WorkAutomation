# -*- coding: utf-8 -*-
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir

$VenvPython = Join-Path $RootDir "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "venv bulunamadi: $VenvPython"
}

Write-Host "[1/5] PyInstaller kontrol ediliyor..."
& $VenvPython -m pip show pyinstaller >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] PyInstaller kuruluyor..."
    & $VenvPython -m pip install pyinstaller
}

Write-Host "[2/5] Eski build/dist temizleniyor..."
Remove-Item (Join-Path $RootDir "build") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $RootDir "dist") -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "[3/5] TelekomOtomasyon.exe derleniyor..."
& $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --console `
    --name "TelekomOtomasyon" `
    --paths $RootDir `
    --add-data "templates;templates" `
    --add-data "static;static" `
    --hidden-import "core.config" `
    --hidden-import "core.Opera" `
    --hidden-import "core.ICCID" `
    --hidden-import "core.MernsDB" `
    --hidden-import "core.CMPDB" `
    --hidden-import "core.ssh_log_collector" `
    --hidden-import "modules.auth_module" `
    --hidden-import "modules.db_helper" `
    --hidden-import "modules.iccid_module" `
    --hidden-import "modules.mdm_es_module" `
    --hidden-import "modules.opera_module" `
    --hidden-import "modules.update_module" `
    --hidden-import "oracledb" `
    --hidden-import "paramiko" `
    --hidden-import "playwright" `
    --hidden-import "playwright.sync_api" `
    --hidden-import "playwright.async_api" `
    --collect-all "playwright" `
    app.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller derlemesi basarisiz oldu!"
}

$OutDir = Join-Path $RootDir "dist\TelekomOtomasyon"

Write-Host "[4/5] Config, Oracle Instant Client ve Playwright Chromium paketleniyor..."
$OutConfig = Join-Path $OutDir "config"
$OutData = Join-Path $OutDir "data"
$OutDrivers = Join-Path $OutDir "drivers"
New-Item -ItemType Directory -Path $OutConfig, $OutData, $OutDrivers -Force | Out-Null

Copy-Item (Join-Path $RootDir "config\*.example.json") $OutConfig -Force

$OraSrc = Join-Path $RootDir "drivers\instantclient_19_25"
if (Test-Path $OraSrc) {
    Copy-Item $OraSrc (Join-Path $OutDrivers "instantclient_19_25") -Recurse -Force
}

$PwSrc = Join-Path $env:LOCALAPPDATA "ms-playwright"
$PwDest = Join-Path $OutDrivers "ms-playwright"
New-Item -ItemType Directory -Path $PwDest -Force | Out-Null

$patterns = @("chromium-*", "chromium_headless_shell-*", "ffmpeg-*", "winldd-*")
foreach ($pat in $patterns) {
    $matches = Get-ChildItem -Path $PwSrc -Directory -Filter $pat -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
    if ($matches) {
        Write-Host "    + $($matches.Name)"
        Copy-Item $matches.FullName (Join-Path $PwDest $matches.Name) -Recurse -Force
    }
}

Write-Host "[5/5] ZIP paketi olusturuluyor..."
$ZipPath = Join-Path $RootDir "dist\TelekomOtomasyon-win64.zip"
Compress-Archive -Path $OutDir -DestinationPath $ZipPath -Force
Write-Host "[+] Paket hazir: $ZipPath"
