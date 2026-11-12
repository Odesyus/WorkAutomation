@echo off
title Telekom Otomasyon Platformu
cd /d "%~dp0"

echo ===================================================
echo       TELEKOM OTOMASYON PLATFORMU BASLATICI
echo ===================================================
echo.

python --version >nul 2>&1
if not errorlevel 1 goto :python_ok

echo [HATA] Bilgisayarinizda Python kurulu bulunamadi!
echo Lutfen once Kurulum.bat dosyasini calistirin.
echo.
pause
exit /b 1

:python_ok
if exist "venv\Scripts\activate.bat" goto :venv_ok

echo [*] Ilk calistirma tespit edildi.
echo [*] Sanal ortam olusturuluyor, lutfen bekleyin...
python -m venv venv
if errorlevel 1 (
    echo [HATA] Sanal ortam olusturulamadi!
    pause
    exit /b 1
)
echo [+] Sanal ortam olusturuldu.

call venv\Scripts\activate.bat
echo [*] Gerekli kutuphaneler yukleniyor, lutfen bekleyin...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
echo [*] Playwright Chromium tarayicisi kuruluyor...
python -m playwright install chromium
echo [+] Kurulum basariyla tamamlandi!
goto :run_app

:venv_ok
call venv\Scripts\activate.bat

:run_app
if not exist "local_config.json" (
    if exist "local_config.example.json" copy "local_config.example.json" "local_config.json" >nul
)

echo.
echo ===================================================
echo  Uygulama Baslatildi! Tarayici aciliyor: http://127.0.0.1:5000
echo  Durdurmak icin bu pencereyi kapatabilirsiniz.
echo ===================================================
echo.

start http://127.0.0.1:5000
python app.py
pause
