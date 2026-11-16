# -*- coding: utf-8 -*-
"""
Sistem Güncelleme Modülü (Git Tabanlı Otomatik Güncelleyici)
GitHub reposundan güncellemeleri denetler ve uygular.
Kütüphaneleri (requirements.txt) ve Playwright tarayıcısını otomatik günceller.
"""

import sys
import os
import subprocess
import time
import shutil
import tempfile
import zipfile
import threading
import requests

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)
from core import config

ROOT_DIR = config.ROOT_DIR


def _parse_version(tag):
    """'v1.0.2' -> (1, 0, 2) tuple olarak ayrıştırır."""
    clean = str(tag or "").strip().lstrip("vV")
    parts = []
    for p in clean.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _get_latest_release():
    """GitHub Releases API üzerinden en son sürüm bilgisini çeker."""
    url = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest"
    resp = requests.get(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "TelekomOtomasyon"}, timeout=15)
    if resp.status_code == 404:
        return None, "Henüz GitHub Releases üzerinde yayınlanmış bir EXE sürümü bulunmuyor."
    resp.raise_for_status()
    data = resp.json()
    zip_url = None
    for asset in data.get("assets", []):
        name = str(asset.get("name", "")).lower()
        if name.endswith(".zip"):
            zip_url = asset.get("browser_download_url")
            break
    return {
        "tag": data.get("tag_name", ""),
        "name": data.get("name") or data.get("tag_name", ""),
        "published_at": str(data.get("published_at", ""))[:10],
        "body": data.get("body", ""),
        "zip_url": zip_url,
    }, None


def _run_git_command(args, timeout=25):
    """Git komutunu proje kök dizininde çalıştırır ve çıktısını döndürür."""
    try:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            ["git"] + args,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout
        )
        return {
            'success': proc.returncode == 0,
            'stdout': proc.stdout.strip(),
            'stderr': proc.stderr.strip(),
            'returncode': proc.returncode
        }
    except Exception as e:
        return {'success': False, 'stdout': '', 'stderr': str(e), 'returncode': -1}


def _ensure_git_repo():
    """
    Eğer klasör ZIP olarak indirilmişse veya .git klasörü yoksa,
    otomatik olarak bu klasörü GitHub reposuna bağlar.
    """
    dot_git = os.path.join(ROOT_DIR, ".git")
    if os.path.isdir(dot_git):
        return True

    repo_url = "https://github.com/Odesyus/WorkAutomation.git"
    try:
        _run_git_command(["init"])
        _run_git_command(["remote", "add", "origin", repo_url])
        fetch = _run_git_command(["fetch", "origin", "main"], timeout=30)
        if fetch['success']:
            _run_git_command(["checkout", "-B", "main", "origin/main"])
            _run_git_command(["branch", "--set-upstream-to=origin/main", "main"])
            return True
    except Exception as e:
        print(f"[GIT REPO AUTO-INIT ERROR] {e}")
    return False


def get_current_version_info():
    """Mevcut commit ve sürüm özetini döndürür."""
    if config.IS_FROZEN:
        return f"v{config.APP_VERSION} (EXE)"
    _ensure_git_repo()
    res = _run_git_command(["log", "-1", "--format=%h - %s (%cd)", "--date=short"], timeout=5)
    if res['success'] and res['stdout']:
        return res['stdout']
    return f"v{config.APP_VERSION}"


def check_for_updates():
    """
    EXE modunda GitHub Releases API'den, kaynak kod modunda 'origin main' dalından
    yeni güncelleme olup olmadığını denetler.
    """
    if config.IS_FROZEN:
        try:
            rel, err = _get_latest_release()
            if err:
                return {'has_update': False, 'message': err, 'current_version': get_current_version_info()}
            latest_ver = _parse_version(rel['tag'])
            curr_ver = _parse_version(config.APP_VERSION)
            if latest_ver <= curr_ver:
                return {
                    'has_update': False,
                    'message': 'Uygulamanız en güncel sürümde.',
                    'current_version': get_current_version_info()
                }
            return {
                'has_update': True,
                'commits_behind': 1,
                'commits': [{
                    'hash': rel['tag'],
                    'title': rel['name'],
                    'date': rel['published_at']
                }],
                'current_version': get_current_version_info(),
                'remote_hash': rel['tag'],
                'download_url': rel['zip_url'],
                'message': f"Yeni sürüm mevcut: {rel['tag']}"
            }
        except Exception as e:
            return {
                'has_update': False,
                'error': f'Sürüm denetlenirken hata oluştu: {e}',
                'current_version': get_current_version_info()
            }

    # 0. .git klasörü yoksa (ZIP'ten açılmışsa) otomatik bağla
    _ensure_git_repo()

    # 1. Uzak sunucudan en son referansları çek
    fetch_res = _run_git_command(["fetch", "origin", "main"], timeout=20)
    if not fetch_res['success']:
        err = fetch_res['stderr'] or 'GitHub sunucusuna erişilemedi.'
        return {
            'has_update': False,
            'error': f'Güncellemeler denetlenirken bağlantı hatası oluştu: {err}',
            'current_version': get_current_version_info()
        }

    # 2. Yerel ve uzak HEAD karşılaştır
    local_head_res = _run_git_command(["rev-parse", "HEAD"], timeout=5)
    remote_head_res = _run_git_command(["rev-parse", "origin/main"], timeout=5)

    if not local_head_res['success'] or not remote_head_res['success']:
        return {
            'has_update': False,
            'error': 'Git referansları okunamadı.',
            'current_version': get_current_version_info()
        }

    local_hash = local_head_res['stdout']
    remote_hash = remote_head_res['stdout']

    if local_hash == remote_hash:
        return {
            'has_update': False,
            'message': 'Uygulamanız en güncel sürümde.',
            'current_version': get_current_version_info(),
            'local_hash': local_hash[:7]
        }

    # 3. Kaç commit gerideyiz ve hangi değişiklikler var?
    count_res = _run_git_command(["rev-list", "--count", "HEAD..origin/main"], timeout=5)
    commits_behind = int(count_res['stdout']) if count_res['success'] and count_res['stdout'].isdigit() else 1

    log_res = _run_git_command(["log", "HEAD..origin/main", "--pretty=format:%h|||%s|||%cd", "--date=short"], timeout=5)
    commits = []
    if log_res['success'] and log_res['stdout']:
        for line in log_res['stdout'].splitlines():
            parts = line.split("|||")
            if len(parts) >= 2:
                commits.append({
                    'hash': parts[0],
                    'title': parts[1],
                    'date': parts[2] if len(parts) > 2 else ''
                })

    return {
        'has_update': True,
        'commits_behind': commits_behind,
        'commits': commits,
        'current_version': get_current_version_info(),
        'local_hash': local_hash[:7],
        'remote_hash': remote_hash[:7],
        'message': f'{commits_behind} adet yeni güncelleme mevcut.'
    }


def apply_update():
    """
    EXE modunda GitHub Releases'tan yeni paketi indirip yeniden başlatır;
    kaynak kod modunda 'git pull' ile günceller.
    """
    if config.IS_FROZEN:
        try:
            rel, err = _get_latest_release()
            if err:
                return {'success': False, 'error': err}
            if not rel.get('zip_url'):
                return {'success': False, 'error': 'Son sürümde indirilebilir .zip paketi bulunamadı.'}

            tmp_dir = tempfile.mkdtemp(prefix="telekom_upd_")
            zip_path = os.path.join(tmp_dir, "update.zip")
            extract_dir = os.path.join(tmp_dir, "extracted")

            with requests.get(rel['zip_url'], stream=True, timeout=180) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            # ZIP icinde tek bir alt klasor varsa onu kaynak olarak kullan
            src_dir = extract_dir
            entries = os.listdir(extract_dir)
            if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
                src_dir = os.path.join(extract_dir, entries[0])

            exe_path = sys.executable
            bat_path = os.path.join(tempfile.gettempdir(), "apply_telekom_update.bat")
            bat_content = f"""@echo off
timeout /t 2 /nobreak >nul
robocopy "{src_dir}" "{ROOT_DIR}" /E /IS /IT /XD config data /XF local_config.json users.json >nul
rmdir /s /q "{tmp_dir}" >nul 2>&1
start "" "{exe_path}"
del "%~f0"
"""
            with open(bat_path, "w", encoding="utf-8") as bf:
                bf.write(bat_content)

            subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
            threading.Timer(0.8, lambda: os._exit(0)).start()
            return {
                'success': True,
                'message': f"Sürüm {rel['tag']} indirildi, uygulama güncellenip yeniden başlatılıyor...",
                'details': [f"Yeni sürüm: {rel['tag']}"]
            }
        except Exception as e:
            return {'success': False, 'error': f'EXE güncelleme hatası: {e}'}

    logs = []

    # 0. Git repo bağlantısını garantiye al
    _ensure_git_repo()

    # 1. Git Pull
    pull_res = _run_git_command(["pull", "origin", "main"], timeout=30)
    if not pull_res['success']:
        return {
            'success': False,
            'error': f"Git Pull başarısız oldu:\n{pull_res['stderr'] or pull_res['stdout']}"
        }
    logs.append(f"Kod güncellendi: {pull_res['stdout']}")

    # 2. Pip gereksinimlerini kontrol et ve kur
    req_path = os.path.join(ROOT_DIR, "requirements.txt")
    if os.path.exists(req_path):
        try:
            pip_proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_path],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60
            )
            if pip_proc.returncode == 0:
                logs.append("Python kütüphaneleri güncellendi.")
            else:
                logs.append(f"Pip uyarısı: {pip_proc.stderr[:200]}")
        except Exception as pe:
            logs.append(f"Pip hatası: {str(pe)}")

    # 3. Playwright tarayıcı kontrolü
    try:
        pw_proc = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90
        )
        if pw_proc.returncode == 0:
            logs.append("Tarayıcı bileşenleri doğrulandı.")
    except Exception as pwe:
        logs.append(f"Playwright uyarısı: {str(pwe)}")

    # 4. Flask Werkzeug yeniden yükleyicisini tetikle (app.py dosyasının mtime'ını güncelle)
    app_path = os.path.join(ROOT_DIR, "app.py")
    try:
        os.utime(app_path, None)
        logs.append("Sunucu yeniden başlatılıyor.")
    except Exception:
        pass

    return {
        'success': True,
        'message': 'Uygulama başarıyla güncellendi.',
        'details': logs,
        'new_version': get_current_version_info()
    }
