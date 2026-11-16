@echo off
title Telekom Otomasyon - Kurulum Sihirbazi
cd /d "%~dp0"

set "SETUP_PS1=%~dp0setup\Setup.ps1"
if exist "%SETUP_PS1%" goto :run_setup

echo [*] Kurulum arayuzu GitHub uzerinden hazirlaniyor, lutfen bekleyin...
set "SETUP_PS1=%TEMP%\TelekomOtomasyon_Setup.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://raw.githubusercontent.com/Odesyus/WorkAutomation/main/setup/Setup.ps1', '$env:SETUP_PS1')"

if not exist "%SETUP_PS1%" (
    echo [HATA] Setup.ps1 indirilemedi. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)

:run_setup
powershell -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%SETUP_PS1%"
exit /b 0
