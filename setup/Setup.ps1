# -*- coding: utf-8 -*-
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$RepoUrl = "https://github.com/Odesyus/WorkAutomation.git"
$PythonInstallerUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
$GitFallbackUrl = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe"
$OracleClientUrl = "https://download.oracle.com/otn_software/nt/instantclient/1925000/instantclient-basiclite-windows.x64-19.25.0.0.0dbru.zip"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ParentDir = Split-Path -Parent $ScriptDir
$DefaultTarget = Join-Path $env:USERPROFILE "TelekomOtomasyon"
if (Test-Path (Join-Path $ParentDir "app.py")) {
    $DefaultTarget = $ParentDir
}

# --- Ana Form ---
$form = New-Object System.Windows.Forms.Form
$form.Text = "Telekom Otomasyon - Kurulum Sihirbazi (Setup)"
$form.Size = New-Object System.Drawing.Size(660, 500)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 247, 250)
$form.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)

# Ust Baslik Paneli
$header = New-Object System.Windows.Forms.Panel
$header.Dock = "Top"
$header.Height = 72
$header.BackColor = [System.Drawing.Color]::FromArgb(15, 23, 42)
$form.Controls.Add($header)

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "Telekom Otomasyon Platformu"
$lblTitle.ForeColor = [System.Drawing.Color]::White
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$lblTitle.Location = New-Object System.Drawing.Point(20, 12)
$lblTitle.AutoSize = $true
$header.Controls.Add($lblTitle)

$lblSub = New-Object System.Windows.Forms.Label
$lblSub.Text = "Python, Git, GitHub Proje Kodlari ve Gerekli Kutuphaneler Kurulum Sihirbazi"
$lblSub.ForeColor = [System.Drawing.Color]::FromArgb(148, 163, 184)
$lblSub.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$lblSub.Location = New-Object System.Drawing.Point(22, 42)
$lblSub.AutoSize = $true
$header.Controls.Add($lblSub)

# Klasor Secimi
$lblPath = New-Object System.Windows.Forms.Label
$lblPath.Text = "Kurulum Klasoru (GitHub projesi bu klasore indirilecektir):"
$lblPath.Location = New-Object System.Drawing.Point(22, 88)
$lblPath.AutoSize = $true
$form.Controls.Add($lblPath)

$txtPath = New-Object System.Windows.Forms.TextBox
$txtPath.Text = $DefaultTarget
$txtPath.Location = New-Object System.Drawing.Point(22, 112)
$txtPath.Size = New-Object System.Drawing.Size(505, 26)
$form.Controls.Add($txtPath)

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Text = "Gozat..."
$btnBrowse.Location = New-Object System.Drawing.Point(535, 111)
$btnBrowse.Size = New-Object System.Drawing.Size(90, 27)
$btnBrowse.BackColor = [System.Drawing.Color]::White
$form.Controls.Add($btnBrowse)

$btnBrowse.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = "Telekom Otomasyon kurulum klasorunu secin"
    if (Test-Path $txtPath.Text) { $dlg.SelectedPath = $txtPath.Text }
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $txtPath.Text = $dlg.SelectedPath
    }
})

# Secenekler
$chkShortcut = New-Object System.Windows.Forms.CheckBox
$chkShortcut.Text = "Masaustune 'Telekom Otomasyon' kisayolu olustur"
$chkShortcut.Checked = $true
$chkShortcut.Location = New-Object System.Drawing.Point(22, 148)
$chkShortcut.AutoSize = $true
$form.Controls.Add($chkShortcut)

$chkLaunch = New-Object System.Windows.Forms.CheckBox
$chkLaunch.Text = "Kurulum tamamlandiginda uygulamayi baslat"
$chkLaunch.Checked = $true
$chkLaunch.Location = New-Object System.Drawing.Point(345, 148)
$chkLaunch.AutoSize = $true
$form.Controls.Add($chkLaunch)

# Durum ve Ilerleme
$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "Kuruluma hazir. Klasor secip 'Kurulumu Baslat' butonuna tiklayin."
$lblStatus.Location = New-Object System.Drawing.Point(22, 182)
$lblStatus.Size = New-Object System.Drawing.Size(603, 20)
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($lblStatus)

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(22, 206)
$progressBar.Size = New-Object System.Drawing.Size(603, 22)
$progressBar.Minimum = 0
$progressBar.Maximum = 100
$form.Controls.Add($progressBar)

# Log Alani
$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Multiline = $true
$txtLog.ScrollBars = "Vertical"
$txtLog.ReadOnly = $true
$txtLog.BackColor = [System.Drawing.Color]::FromArgb(15, 23, 42)
$txtLog.ForeColor = [System.Drawing.Color]::FromArgb(226, 232, 240)
$txtLog.Font = New-Object System.Drawing.Font("Consolas", 9)
$txtLog.Location = New-Object System.Drawing.Point(22, 238)
$txtLog.Size = New-Object System.Drawing.Size(603, 170)
$form.Controls.Add($txtLog)

# Alt Butonlar
$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = "Kurulumu Baslat"
$btnStart.Location = New-Object System.Drawing.Point(395, 420)
$btnStart.Size = New-Object System.Drawing.Size(135, 32)
$btnStart.BackColor = [System.Drawing.Color]::FromArgb(37, 99, 235)
$btnStart.ForeColor = [System.Drawing.Color]::White
$btnStart.FlatStyle = "Flat"
$btnStart.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($btnStart)

$btnClose = New-Object System.Windows.Forms.Button
$btnClose.Text = "Kapat"
$btnClose.Location = New-Object System.Drawing.Point(538, 420)
$btnClose.Size = New-Object System.Drawing.Size(87, 32)
$btnClose.BackColor = [System.Drawing.Color]::White
$form.Controls.Add($btnClose)
$btnClose.Add_Click({ $form.Close() })

# Thread-safe UI guncelleme yardimcilari
$syncHash = [hashtable]::Synchronized(@{
    Form = $form
    Status = $lblStatus
    Progress = $progressBar
    Log = $txtLog
    BtnStart = $btnStart
    BtnBrowse = $btnBrowse
    TxtPath = $txtPath
    BtnClose = $btnClose
})

$scriptBlock = {
    param($sync, $TargetDir, $CreateShortcut, $LaunchAfter, $RepoUrl, $PythonUrl, $GitFallbackUrl, $OracleUrl)

    function Add-Log([string]$msg) {
        if ($sync.Form.IsDisposed) { return }
        $ts = (Get-Date).ToString("HH:mm:ss")
        $line = "[$ts] $msg`r`n"
        $sync.Form.Invoke([Action]{
            $sync.Log.AppendText($line)
            $sync.Log.SelectionStart = $sync.Log.TextLength
            $sync.Log.ScrollToCaret()
        })
    }

    function Set-Step([int]$pct, [string]$statusText) {
        if ($sync.Form.IsDisposed) { return }
        $sync.Form.Invoke([Action]{
            $sync.Progress.Value = [Math]::Min(100, [Math]::Max(0, $pct))
            $sync.Status.Text = $statusText
        })
    }

    function Refresh-EnvPath {
        $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $extra = @(
            "$env:LOCALAPPDATA\Programs\Python\Python312",
            "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts",
            "$env:ProgramFiles\Python312",
            "$env:ProgramFiles\Python312\Scripts",
            "$env:ProgramFiles\Git\cmd",
            "$env:LOCALAPPDATA\Programs\Git\cmd"
        ) -join ";"
        $env:Path = "$extra;$userPath;$machinePath"
    }

    function Find-Python {
        Refresh-EnvPath
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) {
            $ver = & $cmd.Source --version 2>&1
            if ($LASTEXITCODE -eq 0 -and "$ver" -match "Python 3") { return $cmd.Source }
        }
        $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($pyLauncher) {
            $pyPath = & $pyLauncher.Source -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $pyPath -and (Test-Path $pyPath.Trim())) { return $pyPath.Trim() }
        }
        $candidates = @(
            Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
            Get-ChildItem -Path "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
        ) | Sort-Object -Descending
        foreach ($c in $candidates) {
            if ($c -and (Test-Path $c)) { return $c }
        }
        return $null
    }

    function Find-Git {
        Refresh-EnvPath
        $cmd = Get-Command git -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        $candidates = @(
            "$env:ProgramFiles\Git\cmd\git.exe",
            "${env:ProgramFiles(x86)}\Git\cmd\git.exe",
            "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
        )
        foreach ($c in $candidates) {
            if ($c -and (Test-Path $c)) { return $c }
        }
        return $null
    }

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $wc = New-Object System.Net.WebClient

        # -----------------------------------------------------------------
        # ADIM 1: PYTHON KONTROLU VE KURULUMU
        # -----------------------------------------------------------------
        Set-Step 10 "[1/6] Python kontrol ediliyor..."
        Add-Log "[1/6] Sistemde Python araniyor..."
        $pythonExe = Find-Python
        if (-not $pythonExe) {
            Add-Log "[!] Python bulunamadi. Python 3.12 indiriliyor..."
            Set-Step 15 "[1/6] Python indiriliyor..."
            $pySetup = Join-Path $env:TEMP "python_312_setup.exe"
            $wc.DownloadFile($PythonUrl, $pySetup)
            Add-Log "[*] Python sessiz modda kuruluyor (PATH otomatik eklenecek)..."
            Set-Step 22 "[1/6] Python kuruluyor..."
            $proc = Start-Process -FilePath $pySetup -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1" -Wait -PassThru
            Remove-Item $pySetup -Force -ErrorAction SilentlyContinue
            if ($proc.ExitCode -ne 0) {
                throw "Python kurulumu basarisiz oldu (ExitCode: $($proc.ExitCode))."
            }
            $pythonExe = Find-Python
            if (-not $pythonExe) {
                throw "Python kuruldu ancak python.exe bulunamadi."
            }
        }
        $pyVer = & $pythonExe --version 2>&1
        Add-Log "[+] Python hazir: $pyVer ($pythonExe)"

        # -----------------------------------------------------------------
        # ADIM 2: GIT KONTROLU VE KURULUMU
        # -----------------------------------------------------------------
        Set-Step 30 "[2/6] Git kontrol ediliyor..."
        Add-Log "[2/6] Sistemde Git araniyor..."
        $gitExe = Find-Git
        if (-not $gitExe) {
            Add-Log "[!] Git bulunamadi. Git for Windows indiriliyor..."
            Set-Step 35 "[2/6] Git indiriliyor..."
            $gitUrl = $GitFallbackUrl
            try {
                $wcApi = New-Object System.Net.WebClient
                $wcApi.Headers.Add("User-Agent", "TelekomOtomasyonSetup")
                $rel = $wcApi.DownloadString("https://api.github.com/repos/git-for-windows/git/releases/latest") | ConvertFrom-Json
                $asset = $rel.assets | Where-Object { $_.name -match "^Git-.*-64-bit\.exe$" } | Select-Object -First 1
                if ($asset -and $asset.browser_download_url) { $gitUrl = $asset.browser_download_url }
            } catch {
                Add-Log "[*] GitHub API erisilemedi, varsayilan Git surumu indiriliyor..."
            }
            $gitSetup = Join-Path $env:TEMP "git_setup.exe"
            $wc.DownloadFile($gitUrl, $gitSetup)
            Add-Log "[*] Git sessiz modda kuruluyor..."
            Set-Step 42 "[2/6] Git kuruluyor..."
            $procGit = Start-Process -FilePath $gitSetup -ArgumentList "/VERYSILENT /NORESTART /NOCANCEL /SP-" -Wait -PassThru
            Remove-Item $gitSetup -Force -ErrorAction SilentlyContinue
            if ($procGit.ExitCode -ne 0) {
                throw "Git kurulumu basarisiz oldu (ExitCode: $($procGit.ExitCode))."
            }
            $gitExe = Find-Git
            if (-not $gitExe) {
                throw "Git kuruldu ancak git.exe bulunamadi."
            }
        }
        $gitVer = & $gitExe --version 2>&1
        Add-Log "[+] Git hazir: $gitVer"

        # -----------------------------------------------------------------
        # ADIM 3: GITHUB PROJESINI SECILEN KLASORE INDIRME
        # -----------------------------------------------------------------
        Set-Step 50 "[3/6] GitHub uzerinden proje indiriliyor..."
        Add-Log "[3/6] Hedef klasor: $TargetDir"
        if (-not (Test-Path $TargetDir)) {
            New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
        }

        $dotGit = Join-Path $TargetDir ".git"
        if (Test-Path $dotGit) {
            Add-Log "[*] Mevcut Git deposu bulundu, son guncellemeler cekiliyor..."
            $out = & $gitExe -C $TargetDir pull origin main 2>&1
            $out | ForEach-Object { Add-Log "    $_" }
        } else {
            $hasFiles = (Get-ChildItem -Path $TargetDir -Force | Measure-Object).Count -gt 0
            if (-not $hasFiles) {
                Add-Log "[*] Proje GitHub'dan klonlaniyor: $RepoUrl"
                $out = & $gitExe clone $RepoUrl $TargetDir 2>&1
                $out | ForEach-Object { Add-Log "    $_" }
                if ($LASTEXITCODE -ne 0) {
                    throw "GitHub klonlama islemi basarisiz oldu."
                }
            } else {
                Add-Log "[*] Klasor bos degil; Git deposu baglaniyor..."
                & $gitExe -C $TargetDir init 2>&1 | Out-Null
                & $gitExe -C $TargetDir remote remove origin 2>&1 | Out-Null
                & $gitExe -C $TargetDir remote add origin $RepoUrl 2>&1 | Out-Null
                & $gitExe -C $TargetDir fetch origin main 2>&1 | ForEach-Object { Add-Log "    $_" }
                if ($LASTEXITCODE -ne 0) {
                    throw "GitHub deposuna baglanilamadi."
                }
                & $gitExe -C $TargetDir checkout -f -B main origin/main 2>&1 | ForEach-Object { Add-Log "    $_" }
                if ($LASTEXITCODE -ne 0) {
                    throw "GitHub dosyalari klasore yerlestirilemedi."
                }
                & $gitExe -C $TargetDir branch --set-upstream-to=origin/main main 2>&1 | Out-Null
            }
        }
        Add-Log "[+] Proje dosyalari hazir."

        # -----------------------------------------------------------------
        # ADIM 4: SANAL ORTAM (VENV) VE REQUIREMENTS.TXT KURULUMU
        # -----------------------------------------------------------------
        Set-Step 65 "[4/6] Sanal ortam ve requirements.txt kutuphaneleri kuruluyor..."
        $venvDir = Join-Path $TargetDir "venv"
        $venvPython = Join-Path $venvDir "Scripts\python.exe"
        if (-not (Test-Path $venvPython)) {
            Add-Log "[*] Izole Python sanal ortami (venv) olusturuluyor..."
            & $pythonExe -m venv $venvDir 2>&1 | ForEach-Object { Add-Log "    $_" }
            if (-not (Test-Path $venvPython)) {
                throw "Sanal ortam (venv) olusturulamadi."
            }
        }

        Add-Log "[*] pip guncelleniyor..."
        & $venvPython -m pip install --upgrade pip --quiet 2>&1 | Out-Null

        $reqFile = Join-Path $TargetDir "requirements.txt"
        if (Test-Path $reqFile) {
            Add-Log "[*] requirements.txt icindeki kutuphaneler indiriliyor ve kuruluyor..."
            $pipOut = & $venvPython -m pip install -r $reqFile 2>&1
            $pipOut | ForEach-Object { Add-Log "    $_" }
            if ($LASTEXITCODE -ne 0) {
                throw "requirements.txt kutuphaneleri kurulurken hata olustu."
            }
            Add-Log "[+] Tum requirements.txt kutuphaneleri kuruldu."
        } else {
            Add-Log "[!] Uyari: requirements.txt bulunamadi!"
        }

        # -----------------------------------------------------------------
        # ADIM 5: PLAYWRIGHT CHROMIUM & ORACLE INSTANT CLIENT
        # -----------------------------------------------------------------
        Set-Step 82 "[5/6] Tarayici motoru ve Oracle surucusu kontrol ediliyor..."
        Add-Log "[5/6] Playwright Chromium kontrol ediliyor..."
        & $venvPython -m playwright install chromium 2>&1 | ForEach-Object { Add-Log "    $_" }

        $driversDir = Join-Path $TargetDir "drivers"
        $ociNew = Join-Path $driversDir "instantclient_19_25\oci.dll"
        $ociLegacy = Join-Path $TargetDir "instantclient_19_25\oci.dll"
        if ((Test-Path $ociNew) -or (Test-Path $ociLegacy)) {
            Add-Log "[+] Oracle Instant Client zaten hazir."
        } else {
            Add-Log "[*] Oracle Instant Client indiriliyor..."
            try {
                if (-not (Test-Path $driversDir)) { New-Item -ItemType Directory -Path $driversDir -Force | Out-Null }
                $oraZip = Join-Path $env:TEMP "instantclient.zip"
                $wc.DownloadFile($OracleUrl, $oraZip)
                Expand-Archive -Path $oraZip -DestinationPath $driversDir -Force
                Remove-Item $oraZip -Force -ErrorAction SilentlyContinue
                Add-Log "[+] Oracle Instant Client kuruldu (drivers\instantclient_19_25)."
            } catch {
                Add-Log "[!] Oracle Instant Client otomatik indirilemedi: $($_.Exception.Message)"
            }
        }

        # -----------------------------------------------------------------
        # ADIM 6: YAPILANDIRMA VE MASAUSTU KISAYOLU
        # -----------------------------------------------------------------
        Set-Step 95 "[6/6] Yapilandirma ve kisayol olusturuluyor..."
        $cfgDir = Join-Path $TargetDir "config"
        if (-not (Test-Path $cfgDir)) { New-Item -ItemType Directory -Path $cfgDir -Force | Out-Null }
        $localCfg = Join-Path $cfgDir "local_config.json"
        $exampleCfg = Join-Path $cfgDir "local_config.example.json"
        if (-not (Test-Path $localCfg) -and (Test-Path $exampleCfg)) {
            Copy-Item $exampleCfg $localCfg -Force
            Add-Log "[+] Varsayilan local_config.json olusturuldu."
        }

        if ($CreateShortcut) {
            $desktop = [Environment]::GetFolderPath("Desktop")
            $lnkPath = Join-Path $desktop "Telekom Otomasyon.lnk"
            $ws = New-Object -ComObject WScript.Shell
            $s = $ws.CreateShortcut($lnkPath)
            $s.TargetPath = Join-Path $TargetDir "Baslat.bat"
            $s.WorkingDirectory = $TargetDir
            $s.IconLocation = "shell32.dll,220"
            $s.Description = "Telekom Otomasyon Platformu"
            $s.Save()
            Add-Log "[+] Masaustune 'Telekom Otomasyon' kisayolu eklendi."
        }

        Set-Step 100 "Kurulum basariyla tamamlandi!"
        Add-Log "============================================================"
        Add-Log "KURULUM TAMAMLANDI! Uygulamayi Baslat.bat ile acabilirsiniz."
        Add-Log "============================================================"

        if ($LaunchAfter) {
            $baslat = Join-Path $TargetDir "Baslat.bat"
            if (Test-Path $baslat) {
                Start-Process -FilePath $baslat -WorkingDirectory $TargetDir
            }
        }

        $sync.Form.Invoke([Action]{
            [System.Windows.Forms.MessageBox]::Show(
                "Telekom Otomasyon kurulumu basariyla tamamlandi!",
                "Kurulum Tamamlandi",
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Information
            ) | Out-Null
            $sync.BtnStart.Enabled = $true
            $sync.BtnBrowse.Enabled = $true
            $sync.TxtPath.Enabled = $true
            $sync.BtnClose.Enabled = $true
        })
    }
    catch {
        $errMsg = $_.Exception.Message
        Add-Log "[HATA] $errMsg"
        Set-Step 0 "Kurulum sirasinda hata olustu!"
        $sync.Form.Invoke([Action]{
            [System.Windows.Forms.MessageBox]::Show(
                "Kurulum sirasinda bir hata olustu:`n$errMsg",
                "Kurulum Hatasi",
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Error
            ) | Out-Null
            $sync.BtnStart.Enabled = $true
            $sync.BtnBrowse.Enabled = $true
            $sync.TxtPath.Enabled = $true
            $sync.BtnClose.Enabled = $true
        })
    }
}

$form.Add_FormClosing({
    if (-not $btnClose.Enabled) {
        $_.Cancel = $true
        [System.Windows.Forms.MessageBox]::Show("Kurulum devam ediyor, lutfen bitmesini bekleyin.", "Uyari", "OK", "Warning") | Out-Null
    }
})

$btnStart.Add_Click({
    $target = $txtPath.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($target)) {
        [System.Windows.Forms.MessageBox]::Show("Lutfen gecerli bir kurulum klasoru secin.", "Uyari", "OK", "Warning") | Out-Null
        return
    }

    $btnStart.Enabled = $false
    $btnBrowse.Enabled = $false
    $btnClose.Enabled = $false
    $txtPath.Enabled = $false
    $txtLog.Clear()

    $ps = [PowerShell]::Create()
    $ps.AddScript($scriptBlock).
        AddArgument($syncHash).
        AddArgument($target).
        AddArgument($chkShortcut.Checked).
        AddArgument($chkLaunch.Checked).
        AddArgument($RepoUrl).
        AddArgument($PythonInstallerUrl).
        AddArgument($GitFallbackUrl).
        AddArgument($OracleClientUrl) | Out-Null
    $ps.BeginInvoke() | Out-Null
})

[void]$form.ShowDialog()
