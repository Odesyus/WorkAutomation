@echo off
title Telekom Otomasyon - Guncelleme
cd /d "%~dp0"

echo ===================================================
echo       TELEKOM OTOMASYON PLATFORMU GUNCELLEYICI
echo ===================================================
echo.

echo [*] GitHub uzerinden en son kodlar cekiliyor...
git pull origin main
if errorlevel 1 (
    echo [!] Kodlar cekilirken bir sorun olustu. Internet baglantinizi ve VPN durumunuzu kontrol edin.
) else (
    echo [+] Kodlar guncellendi.
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [*] Yeni kutuphaneler kontrol ediliyor...
    python -m pip install -r requirements.txt --quiet
    python -m playwright install chromium
    echo [+] Kutuphaneler ve tarayici bilesenleri guncellendi.
)

echo.
echo ===================================================
echo  Guncelleme Islemi Tamamlandi!
echo  'Baslat.bat' ile uygulamayi calistirabilirsiniz.
echo ===================================================
echo.
pause
