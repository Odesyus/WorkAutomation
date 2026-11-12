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

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def get_current_version_info():
    """Mevcut commit ve sürüm özetini döndürür."""
    res = _run_git_command(["log", "-1", "--format=%h - %s (%cd)", "--date=short"], timeout=5)
    if res['success'] and res['stdout']:
        return res['stdout']
    return "Bilinmeyen Sürüm"


def check_for_updates():
    """
    GitHub 'origin main' dalından yeni commit olup olmadığını denetler.
    """
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
    GitHub'dan 'git pull' ile en güncel kodu çeker,
    gerekli python paketlerini (requirements.txt) ve Playwright tarayıcısını kurar.
    """
    logs = []

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
