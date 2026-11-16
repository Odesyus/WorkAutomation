@echo off
title Telekom Otomasyon Platformu
cd /d "%~dp0"

echo ===================================================
echo       TELEKOM OTOMASYON PLATFORMU BASLATICI
echo ===================================================
echo.

if exist "runtime\python.exe" goto :runtime_ok
if exist "venv\Scripts\activate.bat" goto :venv_ok

python --version >nul 2>&1
if not errorlevel 1 goto :python_ok

echo [HATA] Bilgisayarinizda Python kurulu bulunamadi!
echo Lutfen once Setup.bat dosyasini calistirin.
echo.
pause
exit /b 1

:runtime_ok
set "PYTHON_CMD=runtime\python.exe"
goto :run_app

:python_ok

echo [*] Ilk calistirma tespit edildi.
echo [*] Sanal ortam olusturuluyor, lutfen bekleyin...
python -m venv venv
if not errorlevel 1 goto :venv_created
echo [HATA] Sanal ortam olusturulamadi!
pause
exit /b 1

:venv_created
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
set "PYTHON_CMD=python"

:run_app
if not defined PYTHON_CMD set "PYTHON_CMD=python"
if not exist "config\local_config.json" if exist "config\local_config.example.json" copy "config\local_config.example.json" "config\local_config.json" >nul

echo.
echo ===================================================
echo  Uygulama Baslatildi! Tarayici aciliyor: http://127.0.0.1:5000
echo  Durdurmak icin bu pencereyi kapatabilirsiniz.
echo ===================================================
echo.

start http://127.0.0.1:5000
"%PYTHON_CMD%" app.py
pause
