# -*- coding: utf-8 -*-
"""
Opera MTS aktivasyon modülü.
Mevcut Opera.py içindeki run() fonksiyonunu arka plan iş parçacığında çalıştırır
ve ilerlemeyi web arayüzüne aktarır.
"""

import threading
import uuid
import asyncio
import time
from datetime import datetime
import sys
import os

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Görev takip sözlüğü
tasks = {}

# Aynı anda tek Opera aktivasyonu çalışsın (aynı kullanıcı ile MTS'e paralel giriş sorun çıkarabilir)
_opera_lock = threading.Lock()


def _now():
    return datetime.now().strftime('%H:%M:%S')


def _log(task_id, mesaj):
    tasks[task_id]['logs'].append(f"[{_now()}] {mesaj}")


def _resolve_line_info(iccid):
    """Verilen ICCID'ye karşılık gelen MSISDN ve Pos/Pre bilgisini önbellekten bulur."""
    try:
        from modules import iccid_module
        iccid_str = str(iccid).strip()
        for item in iccid_module.load_cached_lines():
            if str(item.get('iccid', '')).strip() == iccid_str:
                return (str(item.get('msisdn') or iccid_str).strip(), item.get('pos_pre') or '-')
    except Exception:
        pass
    return (str(iccid).strip(), '-')


def start_multi_activation(items, options=None):
    """
    Çoklu aktivasyonu arka planda sırayla çalıştırır.
    items: [{'iccid': '...', 'msisdn': '...', 'pos_pre': '...'}, ...]
    Her aktivasyon için MernsDB'den taze rastgele TCKN ve DT çekilir.
    """
    task_id = str(uuid.uuid4())
    opts = dict(options or {})

    tasks[task_id] = {
        'id': task_id,
        'status': 'running',
        'message': f'{len(items)} adet hat için çoklu aktivasyon sıraya alındı...',
        'progress': 0,
        'logs': [],
        'screenshot_url': None,
        'stop_requested': False,
        '_page': None,
        'multi_total': len(items),
        'multi_current': 0,
        'multi_success': 0,
        'multi_failed': 0,
        'dirty_iccids': [],
        'started_at': datetime.now().isoformat(),
        'completed_at': None,
    }
    _log(task_id, f"Çoklu aktivasyon başlatıldı ({len(items)} hat seçildi).")

    thread = threading.Thread(
        target=_run_multi_activation,
        args=(task_id, items, opts),
        daemon=True,
    )
    thread.start()
    return task_id


def _run_multi_activation(task_id, items, options=None):
    """Çoklu hat aktivasyonunu sırayla ve her biri için yeni Merns çekerek yürütür."""
    task = tasks[task_id]
    total = len(items)

    def on_screenshot(shot_url):
        task['screenshot_url'] = shot_url
        _log(task_id, f"Ekran görüntüsü alındı: {shot_url}")

    def on_page_ready(page_obj):
        task['_page'] = page_obj

    run_opts = dict(options or {})
    run_opts['on_screenshot'] = on_screenshot
    run_opts['on_page_ready'] = on_page_ready
    run_opts['is_stopped'] = lambda: bool(task.get('stop_requested'))

    with _opera_lock:
        from playwright.sync_api import sync_playwright
        from modules import iccid_module
        import importlib
        import Opera
        importlib.reload(Opera)

        with sync_playwright() as playwright:
            for idx, item in enumerate(items):
                if task.get('stop_requested'):
                    task['status'] = 'stopped'
                    task['message'] = 'Çoklu aktivasyon kullanıcı tarafından durduruldu.'
                    _log(task_id, task['message'])
                    break

                task['multi_current'] = idx + 1
                iccid_no = str(item.get('iccid', '')).strip()
                msisdn, resolved_pos_pre = _resolve_line_info(iccid_no)
                pos_pre = item.get('pos_pre') or resolved_pos_pre
                is_prepaid = str(pos_pre).lower() in ['pre', 'prepaid', 'faturasız', 'faturasiz']
                hat_tipi = 'Faturasız' if is_prepaid else 'Faturalı'

                _log(task_id, f"--------------------------------------------------")
                _log(task_id, f"[{idx + 1}/{total}] MernsDB'den yeni kişi sorgulanıyor...")
                merns_res = fetch_merns()
                if not merns_res.get('success'):
                    _log(task_id, f"[{idx + 1}/{total}] MernsDB hatası: {merns_res.get('error')}. Hat atlanıyor.")
                    task['multi_failed'] += 1
                    continue

                m_data = merns_res['data']
                tckn = m_data['tckn']
                dt = m_data['dt']
                kisi_adi = f"{m_data.get('ad', '')} {m_data.get('soyad', '')}".strip()

                _log(task_id, f"[{idx + 1}/{total}] Hat: {msisdn} ({pos_pre} → {hat_tipi}) | Müşteri: {kisi_adi} (TCKN: {tckn})")

                def progress(yuzde, mesaj):
                    step_progress = (idx / total) * 100 + (yuzde / total)
                    task['progress'] = round(step_progress, 1)
                    task['message'] = f"[{idx + 1}/{total}] {mesaj}"
                    _log(task_id, f"[{idx + 1}/{total}] [%{yuzde}] {mesaj}")

                line_opts = dict(run_opts)
                line_opts['msisdn'] = msisdn
                line_opts['pos_pre'] = pos_pre

                try:
                    sonuc = Opera.run(playwright, tckn, dt, iccid_no, progress=progress, options=line_opts)
                    if task.get('stop_requested'):
                        task['status'] = 'stopped'
                        task['message'] = 'Çoklu aktivasyon kullanıcı tarafından durduruldu.'
                        _log(task_id, task['message'])
                        break
                    elif sonuc == 'ICCID_IN_USE':
                        iccid_module.mark_iccid_dirty_in_cache(iccid_no)
                        task.setdefault('dirty_iccids', []).append(iccid_no)
                        task['multi_failed'] += 1
                        _log(task_id, f"[{idx + 1}/{total}] ICCID kullanımda: {iccid_no} (Kirli olarak işaretlendi)")
                    else:
                        iccid_module.mark_iccid_dirty_in_cache(iccid_no)
                        task.setdefault('dirty_iccids', []).append(iccid_no)
                        task['multi_success'] += 1
                        _log(task_id, f"[{idx + 1}/{total}] Aktivasyon başarıyla tamamlandı: {msisdn}")
                except Exception as e:
                    if task.get('stop_requested'):
                        task['status'] = 'stopped'
                        task['message'] = 'Çoklu aktivasyon kullanıcı tarafından durduruldu.'
                        _log(task_id, task['message'])
                        break
                    task['multi_failed'] += 1
                    ozet = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
                    _log(task_id, f"[{idx + 1}/{total}] HATA: {ozet}")
                    print(f"[OPERA MULTI HATA] {iccid_no}: {e}")

        task['_page'] = None
        task['completed_at'] = datetime.now().isoformat()
        if task['status'] != 'stopped':
            task['status'] = 'completed' if task['multi_success'] > 0 else 'failed'
            task['progress'] = 100
            task['message'] = f"Çoklu aktivasyon bitti: {task['multi_success']} başarılı, {task['multi_failed']} başarısız (Toplam {total})."
            _log(task_id, task['message'])


def start_activation(tckn, dt, iccid, options=None):
    """Opera MTS aktivasyonunu arka planda başlatır ve task_id döndürür."""
    task_id = str(uuid.uuid4())
    opts = dict(options or {})
    msisdn, resolved_pos_pre = _resolve_line_info(iccid)
    pos_pre = opts.get('pos_pre') or resolved_pos_pre
    opts['msisdn'] = msisdn
    opts['pos_pre'] = pos_pre
    is_prepaid = str(pos_pre).lower() in ['pre', 'prepaid', 'faturasız', 'faturasiz']
    hat_tipi = 'Faturasız' if is_prepaid else 'Faturalı'

    tasks[task_id] = {
        'id': task_id,
        'status': 'running',
        'message': 'Opera MTS aktivasyonu sıraya alındı...',
        'progress': 0,
        'logs': [],
        'screenshot_url': None,
        'stop_requested': False,
        '_page': None,
        'dirty_iccids': [],
        'started_at': datetime.now().isoformat(),
        'completed_at': None,
    }
    secilenler = [
        lbl for lbl, key in [
            ('2G', 'gsm'), ('3G', 'wcdma'), ('4.5G', 'lte'), ('5G', 'nr'),
            ('VoLTE', 'volte'), ('VoWifi', 'vowifi')
        ] if opts.get(key)
    ]
    tercih_str = ', '.join(secilenler) if secilenler else '2G, 3G, 4.5G, VoLTE, VoWifi'
    _log(task_id, f"Görev oluşturuldu. TCKN: {tckn}, DT: {dt}, MSISDN: {msisdn} ({pos_pre} → {hat_tipi}) | Tercihler: {tercih_str}")

    thread = threading.Thread(
        target=_run_activation,
        args=(task_id, tckn, dt, iccid, opts),
        daemon=True,
    )
    thread.start()
    return task_id


def _run_activation(task_id, tckn, dt, iccid, options=None):
    """Arka plan iş parçacığında Opera.run() fonksiyonunu çalıştırır."""
    task = tasks[task_id]

    def progress(yuzde, mesaj):
        task['progress'] = yuzde
        task['message'] = mesaj
        _log(task_id, mesaj)

    def on_screenshot(shot_url):
        task['screenshot_url'] = shot_url
        _log(task_id, f"Hata anı ekran görüntüsü alındı: {shot_url}")

    def on_page_ready(page_obj):
        task['_page'] = page_obj

    run_opts = dict(options or {})
    run_opts['on_screenshot'] = on_screenshot
    run_opts['on_page_ready'] = on_page_ready
    run_opts['is_stopped'] = lambda: bool(task.get('stop_requested'))

    with _opera_lock:
        if task.get('stop_requested'):
            task['status'] = 'stopped'
            task['message'] = 'Aktivasyon kullanıcı tarafından durduruldu.'
            _log(task_id, task['message'])
            task['completed_at'] = datetime.now().isoformat()
            return

        try:
            from playwright.sync_api import sync_playwright
            from modules import iccid_module
            import importlib
            import Opera
            importlib.reload(Opera)

            with sync_playwright() as playwright:
                sonuc = Opera.run(playwright, tckn, dt, iccid, progress=progress, options=run_opts)

            if task.get('stop_requested'):
                task['status'] = 'stopped'
                task['message'] = 'Aktivasyon kullanıcı tarafından durduruldu.'
            elif sonuc == 'ICCID_IN_USE':
                iccid_module.mark_iccid_dirty_in_cache(iccid)
                task.setdefault('dirty_iccids', []).append(iccid)
                task['status'] = 'failed'
                task['message'] = f'ICCID kullanımda: {iccid}. Listeden başka bir ICCID seçip tekrar deneyin.'
            else:
                iccid_module.mark_iccid_dirty_in_cache(iccid)
                task.setdefault('dirty_iccids', []).append(iccid)
                task['status'] = 'completed'
                task['progress'] = 100
                task['message'] = 'Opera MTS aktivasyonu başarıyla tamamlandı.'
            _log(task_id, task['message'])

        except Exception as e:
            if task.get('stop_requested'):
                task['status'] = 'stopped'
                task['message'] = 'Aktivasyon kullanıcı tarafından durduruldu.'
                _log(task_id, task['message'])
            else:
                task['status'] = 'failed'
                # Playwright hata mesajları çok uzun olabiliyor; ilk satırı özet olarak göster
                ozet = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
                task['message'] = f'Aktivasyon hatası: {ozet}'
                _log(task_id, f"HATA: {e}")
                print(f"[OPERA HATA] Görev {task_id}: {e}")
        finally:
            task['_page'] = None
            task['completed_at'] = datetime.now().isoformat()


def stop_activation(task_id):
    """Çalışmakta olan Opera aktivasyonunu anında durdurur ve tarayıcıyı kapatır."""
    task = tasks.get(task_id)
    if not task:
        return {'success': False, 'error': 'Görev bulunamadı.'}
    if task.get('status') != 'running':
        return {'success': False, 'error': 'Görev zaten tamamlanmış veya durdurulmuş.'}

    task['stop_requested'] = True
    _log(task_id, "Durdurma isteği alındı, tarayıcı kapatılıyor...")
    page_obj = task.get('_page')
    if page_obj is not None:
        try:
            loop = page_obj._impl_obj._loop
            asyncio.run_coroutine_threadsafe(page_obj._impl_obj.close(), loop)
        except Exception as e:
            print(f"[OPERA STOP UYARI] {e}")
    return {'success': True, 'message': 'Aktivasyon durduruldu.'}


def take_task_screenshot(task_id):
    """Çalışmakta olan Opera aktivasyonundan anlık ekran görüntüsü alır."""
    task = tasks.get(task_id)
    if not task:
        return {'success': False, 'error': 'Görev bulunamadı.'}
    page_obj = task.get('_page')
    if page_obj is None or task.get('status') != 'running':
        return {'success': False, 'error': 'Aktif bir tarayıcı sayfası bulunamadı.'}

    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        shots_dir = os.path.join(root_dir, "static", "screenshots")
        os.makedirs(shots_dir, exist_ok=True)
        fname = f"opera_snap_{int(time.time() * 1000)}.png"
        fpath = os.path.join(shots_dir, fname)

        loop = page_obj._impl_obj._loop
        fut = asyncio.run_coroutine_threadsafe(
            page_obj._impl_obj.screenshot(path=fpath, fullPage=True),
            loop
        )
        fut.result(timeout=10)
        shot_url = f"/static/screenshots/{fname}"
        task['screenshot_url'] = shot_url
        _log(task_id, f"Anlık ekran görüntüsü alındı: {shot_url}")
        return {'success': True, 'screenshot_url': shot_url}
    except Exception as e:
        return {'success': False, 'error': f'Ekran görüntüsü alınamadı: {e}'}


def get_task_status(task_id, log_offset=0):
    """
    Görev durumunu döndürür. log_offset'ten sonraki yeni log satırlarını da verir
    (arayüz her sorguda sadece yeni satırları ekler).
    """
    task = tasks.get(task_id)
    if not task:
        return None
    return {
        'status': task['status'],
        'message': task['message'],
        'progress': task['progress'],
        'logs': task['logs'][log_offset:],
        'log_count': len(task['logs']),
        'screenshot_url': task.get('screenshot_url'),
        'dirty_iccids': list(task.get('dirty_iccids', [])),
        'multi_total': task.get('multi_total'),
    }


def fetch_merns():
    """
    MernsDB'den rastgele test kişisi (TCKN, doğum tarihi, ad, soyad) getirir.
    Not: BSCS DB için kullanılan Oracle Thick Mode (init_oracle_client) aktif olduğunda
    MernsDB login trigger'ı (DBMAIN.DB_LOGIN_TR) Thick Client'ı reddettiği için,
    MernsDB sorgusu izole Thin Mode alt sürecinde çalıştırılır.
    """
    try:
        import subprocess
        import json

        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = [
            sys.executable,
            "-c",
            "import json, MernsDB; res = MernsDB.get_Merns(); print('__MERNS_JSON__:' + json.dumps(res, ensure_ascii=False))"
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        proc = subprocess.run(
            cmd,
            cwd=root_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=20
        )

        result = {}
        for line in (proc.stdout or "").splitlines():
            if line.startswith("__MERNS_JSON__:"):
                result = json.loads(line.split("__MERNS_JSON__:", 1)[1])
                break

        if result and result.get('TCKN'):
            return {
                'success': True,
                'data': {
                    'tckn': result.get('TCKN', ''),
                    'dt': result.get('DOĞUM TARİHİ', ''),
                    'ad': result.get('AD', ''),
                    'soyad': result.get('SOYAD', ''),
                },
            }
        err_detail = (proc.stdout or proc.stderr or '').strip()
        return {'success': False, 'error': f'MernsDB veritabanından veri alınamadı. {err_detail}'}
    except Exception as e:
        print(f"[MERNS HATA] {e}")
        return {'success': False, 'error': f'MernsDB bilgileri alınırken hata oluştu: {e}'}
