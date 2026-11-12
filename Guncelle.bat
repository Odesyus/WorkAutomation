@echo off
title Telekom Otomasyon - Guncelleme
cd /d "%~dp0"

echo ===================================================
echo       TELEKOM OTOMASYON PLATFORMU GUNCELLEYICI
echo ===================================================
echo.

git --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Bilgisayarinizda Git bulunamadi.
    echo Lutfen https://git-scm.com adresinden Git kurun.
    pause
    exit /b 1
)

if not exist ".git" (
    echo [*] Proje klasorunde Git baglantisi bulunamadi (ZIP olarak indirilmis).
    echo [*] GitHub deposuna otomatik baglanti kuruluyor, lutfen bekleyin...
    git init
    git remote add origin https://github.com/Odesyus/WorkAutomation.git
    git fetch origin main
    git checkout -B main origin/main
    git branch --set-upstream-to=origin/main main
    echo [+] GitHub baglantisi basariyla kuruldu!
    echo.
)

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
