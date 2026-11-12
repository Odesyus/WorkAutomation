@echo off
title Telekom Otomasyon - Otomatik Kurulum ve Kurucu
color 0B

echo ================================================================
echo         TELEKOM OTOMASYON PLATFORMU - OTOMATIK KURULUM
echo ================================================================
echo.
echo Bu kurulum programi gerekli bilesenleri: Python, Kutuphaneler,
echo Kodlar ve Tarayici Motorunu otomatik olarak yapilandiracaktir.
echo.

set "TARGET_DIR=%USERPROFILE%\TelekomOtomasyon"
if exist "%~dp0app.py" (
    set "TARGET_DIR=%~dp0"
)
if "%TARGET_DIR:~-1%"=="\" set "TARGET_DIR=%TARGET_DIR:~0,-1%"
echo [*] Kurulum Klasoru: "%TARGET_DIR%"

:: -----------------------------------------------------------------
:: ADIM 1: Python Kontrolü ve Otomatik İndirme/Kurulum
:: -----------------------------------------------------------------
echo.
echo [1/6] Python Kontrol Ediliyor...
python --version >nul 2>&1
if not errorlevel 1 goto :python_exists

echo [!] Bilgisayarinizda Python kurulu bulunamadi.
echo [*] Python 3.12 indiriliyor, lutfen bekleyin...

set "PY_INSTALLER=%TEMP%\python_312_setup.exe"
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe', '$env:PY_INSTALLER')"

if not exist "%PY_INSTALLER%" (
    echo [HATA] Python indirilemedi! Lutfen internet baglantinizi kontrol edin.
    pause
    exit /b 1
)

echo [*] Python sessiz modda kuruluyor, PATH otomatik eklenecek...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1
del /f /q "%PY_INSTALLER%" >nul 2>&1

set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"

python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python kuruldu ancak PATH ortam degiskeni bu pencerede henuz aktif degil.
    echo Lutfen bu pencereyi kapatip Kurulum.bat dosyasini tekrar calistirin.
    pause
    exit /b 0
)
echo [+] Python basariyla kuruldu!
goto :python_done

:python_exists
for /f "tokens=*" %%v in ('python --version') do echo [+] Bulundu: %%v

:python_done

:: -----------------------------------------------------------------
:: ADIM 2: Proje Kodlarını Çekme (Git veya Doğrudan ZIP)
:: -----------------------------------------------------------------
echo.
echo [2/6] Proje Kodlari Kontrol Ediliyor...
if exist "%TARGET_DIR%\app.py" (
    echo [+] Kodlar mevcut klasorde hazir.
    goto :code_done
)

echo [*] Kodlar GitHub deposundan indiriliyor...
git --version >nul 2>&1
if errorlevel 1 goto :download_zip

git clone https://github.com/Odesyus/WorkAutomation.git "%TARGET_DIR%"
goto :code_done

:download_zip
echo [*] Git bulunamadi; kaynak kodlar ZIP olarak indiriliyor...
set "ZIP_PATH=%TEMP%\repo.zip"
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://github.com/Odesyus/WorkAutomation/archive/refs/heads/main.zip', '$env:ZIP_PATH')"
powershell -NoProfile -Command "Expand-Archive -Path '$env:ZIP_PATH' -DestinationPath '%TEMP%\repo_extracted' -Force"

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
xcopy /E /Y /Q "%TEMP%\repo_extracted\WorkAutomation-main\*" "%TARGET_DIR%\" >nul
del /f /q "%ZIP_PATH%" >nul 2>&1
rmdir /s /q "%TEMP%\repo_extracted" >nul 2>&1
echo [+] Kodlar hazirlandi.

:code_done
cd /d "%TARGET_DIR%"

:: -----------------------------------------------------------------
:: ADIM 3: Sanal Ortam ve Kütüphaneler (pip & requirements)
:: -----------------------------------------------------------------
echo.
echo [3/6] Sanal Ortam ve Kutuphaneler Yapilandiriliyor...
if exist "venv\Scripts\activate.bat" goto :venv_ready

echo [*] Izole sanal ortam olusturuluyor...
python -m venv venv

:venv_ready
call venv\Scripts\activate.bat

echo [*] Gerekli Python kutuphaneleri kuruluyor: Flask, Playwright, OracleDB, Paramiko...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
echo [+] Kutuphaneler basariyla kuruldu.

:: -----------------------------------------------------------------
:: ADIM 4: Playwright Tarayıcı Motoru Kurulumu
:: -----------------------------------------------------------------
echo.
echo [4/6] Otomasyon Tarayicisi Kontrol Ediliyor...
python -m playwright install chromium
echo [+] Tarayici bilesenleri hazir.

:: -----------------------------------------------------------------
:: ADIM 5: Oracle Veritabanı Sürücüsü (Instant Client)
:: -----------------------------------------------------------------
echo.
echo [5/6] Oracle Veritabani Surucusu Kontrol Ediliyor...
if exist "%TARGET_DIR%\instantclient_19_25\oci.dll" (
    echo [+] Oracle Instant Client surucusu hazir.
    goto :oracle_done
)

echo [*] Oracle Instant Client surucusu indiriliyor, lutfen bekleyin...
set "ORACLE_ZIP=%TEMP%\instantclient.zip"
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { (New-Object System.Net.WebClient).DownloadFile('https://download.oracle.com/otn_software/nt/instantclient/1925000/instantclient-basiclite-windows.x64-19.25.0.0.0dbru.zip', '$env:ORACLE_ZIP'); Expand-Archive -Path '$env:ORACLE_ZIP' -DestinationPath '%TARGET_DIR%' -Force; Remove-Item '$env:ORACLE_ZIP' -Force; Write-Host '[+] Oracle surucusu basariyla kuruldu.' } catch { Write-Host '[-] Surucu otomatik indirilemedi.' }"

:oracle_done

:: -----------------------------------------------------------------
:: ADIM 6: Masaüstü Kısayolu ve Yapılandırma
:: -----------------------------------------------------------------
echo.
echo [6/6] Masaustu Kisayolu ve Yerel Ayarlar Olusturuluyor...

if not exist "local_config.json" (
    if exist "local_config.example.json" (
        copy "local_config.example.json" "local_config.json" >nul
    )
)

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'), 'Telekom Otomasyon.lnk')); $s.TargetPath = [System.IO.Path]::Combine('%TARGET_DIR%', 'Baslat.bat'); $s.WorkingDirectory = '%TARGET_DIR%'; $s.IconLocation = 'shell32.dll,220'; $s.Description = 'Telekom Otomasyon Platformu'; $s.Save()"

echo [+] Masaustunuze 'Telekom Otomasyon' kisayolu eklendi!

echo.
echo ================================================================
echo       KURULUM TAMAMLANDI!
echo ================================================================
echo.
echo Ekip arkadaslariniz artik masaustundeki 'Telekom Otomasyon'
echo simgesine cift tiklayarak sistemi dogrudan calistirabilirler.
echo.
echo Simdi uygulama baslatiliyor...
ping 127.0.0.1 -n 4 >nul

start "" "%TARGET_DIR%\Baslat.bat"
exit /b 0
