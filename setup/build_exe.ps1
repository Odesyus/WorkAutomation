# -*- coding: utf-8 -*-
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir

$PythonEmbedUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"

$OutDir = Join-Path $RootDir "dist\TelekomOtomasyon"
$RuntimeDir = Join-Path $OutDir "runtime"

Write-Host "[1/5] Eski dist klasoru temizleniyor..."
Remove-Item (Join-Path $RootDir "dist") -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $OutDir, $RuntimeDir -Force | Out-Null

Write-Host "[2/5] Resmi imzali Python 3.12 Embeddable indiriliyor..."
$wc = New-Object System.Net.WebClient
$pyZip = Join-Path $env:TEMP "python-3.12.7-embed-amd64.zip"
$getPip = Join-Path $env:TEMP "get-pip.py"
$wc.DownloadFile($PythonEmbedUrl, $pyZip)
$wc.DownloadFile($GetPipUrl, $getPip)

Expand-Archive -Path $pyZip -DestinationPath $RuntimeDir -Force
Remove-Item $pyZip -Force -ErrorAction SilentlyContinue

# python312._pth dosyasini duzenle: site-packages ve proje kok dizini aktif edilsin
$pthFile = Join-Path $RuntimeDir "python312._pth"
@"
python312.zip
.
..
Lib\site-packages
import site
"@ | Set-Content -Path $pthFile -Encoding ASCII

$RuntimePython = Join-Path $RuntimeDir "python.exe"
Write-Host "[3/5] pip ve requirements.txt kutuphaneleri runtime icine kuruluyor..."
$ErrorActionPreference = "Continue"
& $RuntimePython $getPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "get-pip kurulumu basarisiz oldu!" }
Remove-Item $getPip -Force -ErrorAction SilentlyContinue

& $RuntimePython -m pip install --no-warn-script-location -r (Join-Path $RootDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "requirements.txt kurulumu basarisiz oldu!" }
$ErrorActionPreference = "Stop"

Write-Host "[4/5] Proje dosyalari, Config, Oracle ve Playwright Chromium kopyalaniyor..."
Copy-Item (Join-Path $RootDir "app.py") $OutDir -Force
Copy-Item (Join-Path $RootDir "requirements.txt") $OutDir -Force
Copy-Item (Join-Path $RootDir "Baslat.bat") $OutDir -Force
Copy-Item (Join-Path $RootDir "Guncelle.bat") $OutDir -Force
Copy-Item (Join-Path $RootDir "Setup.bat") $OutDir -Force

foreach ($dirName in @("core", "modules", "templates", "static", "setup")) {
    $src = Join-Path $RootDir $dirName
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $OutDir $dirName) -Recurse -Force
    }
}
# __pycache__ ve eski screenshotlari temizle
Get-ChildItem -Path $OutDir -Directory -Filter "__pycache__" -Recurse | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
$shotsDir = Join-Path $OutDir "static\screenshots"
if (Test-Path $shotsDir) { Remove-Item $shotsDir -Recurse -Force -ErrorAction SilentlyContinue }

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
Write-Host "[+] Tasinabilir paket hazir: $ZipPath"
