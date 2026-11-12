@echo off
title Telekom Otomasyon - Guncelleme
cd /d "%~dp0"

echo ===================================================
echo       TELEKOM OTOMASYON PLATFORMU GUNCELLEYICI
echo ===================================================
echo.

git --version >nul 2>&1
if not errorlevel 1 goto :git_ok

echo [HATA] Bilgisayarinizda Git bulunamadi.
echo Lutfen https://git-scm.com adresinden Git kurun.
echo.
pause
exit /b 1

:git_ok
if exist ".git" goto :check_remote

echo [*] Proje klasorunde Git baglantisi bulunamadi.
echo [*] ZIP kurulumu tespit edildi. GitHub deposuna baglanti kuruluyor...
git init
git remote add origin https://github.com/Odesyus/WorkAutomation.git
git fetch origin main
git checkout -B main origin/main
git branch --set-upstream-to=origin/main main
echo [+] GitHub baglantisi basariyla kuruldu!
echo.
goto :pull_code

:check_remote
git remote -v >nul 2>&1
if not errorlevel 1 goto :pull_code
git remote add origin https://github.com/Odesyus/WorkAutomation.git

:pull_code
echo [*] GitHub uzerinden en son kodlar cekiliyor...
git pull origin main
if not errorlevel 1 goto :pull_ok
echo.
echo [!] Kodlar cekilirken bir sorun olustu.
echo Internet baglantinizi ve VPN durumunuzu kontrol edin.
echo.
goto :check_venv

:pull_ok
echo [+] Kodlar basariyla guncellendi.

:check_venv
if not exist "venv\Scripts\activate.bat" goto :done

call venv\Scripts\activate.bat
echo [*] Yeni kutuphaneler kontrol ediliyor...
python -m pip install -r requirements.txt --quiet
python -m playwright install chromium
echo [+] Kutuphaneler ve tarayici bilesenleri guncellendi.

:done
echo.
echo ===================================================
echo  Guncelleme Islemi Tamamlandi!
echo  'Baslat.bat' ile uygulamayi calistirabilirsiniz.
echo ===================================================
echo.
pause
