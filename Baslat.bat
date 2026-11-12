@echo off
chcp 65001 >nul
title Telekom Otomasyon Platformu
cd /d "%~dp0"

echo ===================================================
echo       TELEKOM OTOMASYON PLATFORMU BASLATICI
echo ===================================================
echo.

:: 1. Python kurulu mu kontrol et
python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Bilgisayarınızda Python kurulu bulunamadı!
    echo Lütfen https://www.python.org adresinden Python kurun
    echo ve kurulum sirasinda "Add python.exe to PATH" kutucugunu isaretleyin.
    echo.
    pause
    exit /b 1
)

:: 2. Sanal Ortam (venv) kontrolü ve oluşturma
if not exist "venv\Scripts\activate.bat" (
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
    echo [*] Gerekli kutuphaneler yukleniyor, bu islem ilk seferde 1-2 dakika surebilir...
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt --quiet
    echo [*] Playwright Chromium tarayicisi kuruluyor...
    python -m playwright install chromium
    echo [+] Kurulum basariyla tamamlandi!
) else (
    call venv\Scripts\activate.bat
)

:: 3. local_config.json yoksa ornek sablondan olustur
if not exist "local_config.json" (
    if exist "local_config.example.json" (
        copy "local_config.example.json" "local_config.json" >nul
        echo [+] local_config.json yapilandirmasi hazirlandi.
    )
)

:: 4. Tarayıcıyı otomatik aç ve uygulamayı başlat
echo.
echo ===================================================
echo  Uygulama Baslatildi! Tarayici aciliyor: http://127.0.0.1:5000
echo  Durdurmak icin bu pencereyi kapatabilirsiniz.
echo ===================================================
echo.

start http://127.0.0.1:5000
python app.py

pause
