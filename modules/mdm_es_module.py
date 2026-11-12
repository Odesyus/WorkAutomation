# -*- coding: utf-8 -*-
"""
MDM/ES cihaz kayıt modülü.
MDM (https://test-cdp.turktelekom.com.tr/ui/home.html#/deviceAdd) ve
ES (http://10.132.1.11:8080/ui/#/deviceAdd) üzerinde Playwright ile cihaz kaydı gerçekleştirir.
"""

import threading
import uuid
from datetime import datetime
import sys
import os

# Proje kök dizinini path'e ekle
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
import config

# ES için kalıcı tarayıcı profili (reCAPTCHA oturumunu korur)
ES_PROFILE_DIR = os.path.join(ROOT_DIR, 'es_browser_profile')

# Görev takip sözlüğü
tasks = {}


def register_device(imei, imsi, msisdn, target='both', manufacturer=None, model=None):
    """
    MDM ve/veya ES sisteminde cihaz kaydını arka plan iş parçacığında başlatır.

    Args:
        imei (str): 15 haneli IMEI numarası (Device Id)
        imsi (str): 15 haneli IMSI numarası (Network Id)
        msisdn (str): MSISDN numarası (Subscriber Id: MDM için normal 10 hane, ES için 90'lı)
        target (str): 'both' | 'mdm' | 'es'
        manufacturer (str, optional): Cihaz üreticisi (IMEI girildiğinde sistem otomatik çeker)
        model (str, optional): Cihaz modeli (IMEI girildiğinde sistem otomatik çeker)

    Returns:
        dict: {'task_id': '...', 'status': 'running', 'message': '...'}
    """
    task_id = str(uuid.uuid4())

    tasks[task_id] = {
        'id': task_id,
        'status': 'running',
        'message': 'MDM/ES cihaz kaydı başlatılıyor...',
        'progress': 5,
        'started_at': datetime.now().isoformat(),
        'completed_at': None
    }

    thread = threading.Thread(
        target=_run_registration,
        args=(task_id, imei, imsi, msisdn, target, manufacturer, model),
        daemon=True
    )
    thread.start()

    return {
        'task_id': task_id,
        'status': 'running',
        'message': 'MDM/ES cihaz kaydı arka planda başlatıldı.'
    }


def _fill_and_save_device_add(page, imei, imsi, msisdn, manufacturer, model, system_label, task_id, base_progress):
    """
    Motive IMPACT #/deviceAdd formunu doldurup kaydeder.
    Alan eşleşmeleri:
      - Device Id (#deviceId)         -> IMEI
      - Subscriber Id (#subscriberId) -> MSISDN (MDM için normal 10 haneli, ES için 90 ile başlayan 12 haneli)
      - Network Id (name=networkId)   -> IMSI
      - Manufacturer & Model          -> IMEI girildiğinde sistem tarafından otomatik çekilir
    """
    tasks[task_id]['progress'] = base_progress + 10
    tasks[task_id]['message'] = f'{system_label}: Cihaz ekleme formu (#/deviceAdd) bekleniyor...'

    page.wait_for_selector('#deviceId', timeout=25000)
    page.wait_for_timeout(1000)

    # Subscriber ID biçimlendirmesi:
    # MDM için normal 10 haneli (ör. 5012631892)
    # ES için 90'lı 12 haneli (ör. 905012631892)
    clean_msisdn = str(msisdn).strip()
    if clean_msisdn.startswith('+90'):
        clean_msisdn = clean_msisdn[3:]
    elif clean_msisdn.startswith('90') and len(clean_msisdn) == 12:
        clean_msisdn = clean_msisdn[2:]
    elif clean_msisdn.startswith('0') and len(clean_msisdn) == 11:
        clean_msisdn = clean_msisdn[1:]

    if str(system_label).upper() == 'ES':
        sub_id = f"90{clean_msisdn}"
    else:
        sub_id = clean_msisdn

    tasks[task_id]['progress'] = base_progress + 20
    tasks[task_id]['message'] = f'{system_label}: IMEI ({imei}), Subscriber Id ({sub_id}) ve IMSI ({imsi}) giriliyor...'

    # Device Id -> IMEI
    page.fill('#deviceId', imei)
    page.locator('#deviceId').dispatch_event('input')
    page.locator('#deviceId').dispatch_event('change')
    page.locator('#deviceId').press('Tab')

    # Subscriber Id -> sub_id (MDM: 501..., ES: 90501...)
    page.fill('#subscriberId', sub_id)
    page.locator('#subscriberId').dispatch_event('change')

    # Network Id -> IMSI
    page.fill('input[name="networkId"]', imsi)
    page.locator('input[name="networkId"]').dispatch_event('change')

    # IMEI girildiğinde sistemin Manufacturer/Model'i otomatik çekmesi beklenir
    page.wait_for_timeout(1500)

    # İsteğe bağlı fallback: Eğer kullanıcı manuel marka/model verdiyse ve sistem boş bıraktıysa
    if manufacturer:
        try:
            brand_text = page.locator('#manufacturer .ui-select-match').inner_text().strip() if page.locator('#manufacturer .ui-select-match').count() > 0 else ''
            if not brand_text or 'select' in brand_text.lower():
                tasks[task_id]['message'] = f'{system_label}: Marka/Model ({manufacturer} / {model}) manuel seçiliyor...'
                page.click('#manufacturer .ui-select-toggle', timeout=4000)
                page.wait_for_timeout(300)
                page.locator('#manufacturer input.ui-select-search').fill(manufacturer)
                page.wait_for_timeout(400)
                brand_row = page.locator('#manufacturer .ui-select-choices-row', has_text=manufacturer).first
                if brand_row.count() > 0:
                    brand_row.click()
                    page.wait_for_timeout(1000)
                    if model:
                        model_toggle = page.locator('#model .ui-select-toggle')
                        if model_toggle.count() > 0:
                            model_toggle.click(timeout=4000)
                            page.wait_for_timeout(300)
                            page.locator('#model input.ui-select-search').fill(model)
                            page.wait_for_timeout(400)
                            model_row = page.locator('#model .ui-select-choices-row', has_text=model).first
                            if model_row.count() > 0:
                                model_row.click()
                                page.wait_for_timeout(400)
        except Exception as e:
            print(f"[{system_label}] Marka/Model seçimi uyarısı: {e}", flush=True)

    tasks[task_id]['progress'] = base_progress + 35
    tasks[task_id]['message'] = f'{system_label}: Kaydet (Save) butonuna tıklanıyor...'

    page.locator('form[name="deviceForm"] button[type="submit"]').click()
    page.wait_for_timeout(3500)

    # Growl / bildirim mesajını kontrol et
    growl_text = ''
    try:
        growl_loc = page.locator('.growl-container .growl-item')
        if growl_loc.count() > 0:
            growl_text = growl_loc.first.inner_text().strip()
    except Exception:
        pass

    if growl_text:
        lower_g = growl_text.lower()
        if 'error' in lower_g or 'fail' in lower_g or 'already exists' in lower_g or 'exception' in lower_g:
            raise RuntimeError(f"{system_label} uyarısı/hatası: {growl_text}")
        return f"{system_label}: Başarılı ({growl_text})"

    return f"{system_label}: Cihaz kaydı tamamlandı"


def _register_on_mdm(p, imei, imsi, msisdn, manufacturer, model, task_id, base_progress):
    """MDM üzerinde headless olarak giriş yapıp #/deviceAdd sayfasından cihaz kaydeder."""
    user = config.MDM_ES.get('user', 'superadmin')
    password = config.MDM_ES.get('password', 'superadmin')
    device_add_url = config.MDM_ES.get(
        'mdm_device_add_url',
        'https://test-cdp.turktelekom.com.tr/ui/home.html#/deviceAdd'
    )

    tasks[task_id]['progress'] = base_progress
    tasks[task_id]['message'] = 'MDM: Giriş ekranı açılıyor...'

    browser = p.chromium.launch(headless=True, args=['--ignore-certificate-errors'])
    context = browser.new_context(ignore_https_errors=True, viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    try:
        page.goto(device_add_url, timeout=30000)
        page.wait_for_timeout(2000)

        if page.locator('input[name="j_username"]').count() > 0:
            tasks[task_id]['message'] = f'MDM: {user} ile giriş yapılıyor...'
            page.fill('input[name="j_username"]', user)
            page.fill('input[name="j_password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_timeout(4000)

        if '#/deviceAdd' not in page.url:
            page.goto(device_add_url, timeout=30000)
            page.wait_for_timeout(2500)

        return _fill_and_save_device_add(
            page, imei, imsi, msisdn, manufacturer, model, 'MDM', task_id, base_progress
        )
    finally:
        browser.close()


def _bring_chrome_to_foreground():
    """Windows üzerinde açılan ES Chrome penceresini en öne getirir ve maksimize eder."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        def enum_handler(hwnd, extra):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    if any(k in title for k in ['cdp', 'keycloak', 'impact', 'chrome', '10.132', 'device']):
                        # Alt tuşu simülasyonu ile Windows'un SetForegroundWindow kilidini aş
                        user32.keybd_event(0x12, 0, 0, 0)
                        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                        user32.SetForegroundWindow(hwnd)
                        user32.keybd_event(0x12, 0, 2, 0)
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_handler), 0)
    except Exception as e:
        print(f"[FOREGROUND HATA] {e}", flush=True)


def _register_on_es(p, imei, imsi, msisdn, manufacturer, model, task_id, base_progress):
    """
    ES üzerinde kalıcı tarayıcı profili (persistent_context) ile giriş yapıp
    #/deviceAdd sayfasından cihaz kaydeder.
    İlk girişte reCAPTCHA varsa kullanıcı adı/şifreyi otomatik doldurur ve
    kullanıcının reCAPTCHA kutucuğunu işaretlemesini bekler; işaretlendiği an
    otomatik olarak SIGN IN butonuna basıp devam eder.
    """
    user = config.MDM_ES.get('user', 'superadmin')
    password = config.MDM_ES.get('password', 'superadmin')
    device_add_url = config.MDM_ES.get(
        'es_device_add_url',
        'http://10.132.1.11:8080/ui/#/deviceAdd'
    )

    tasks[task_id]['progress'] = base_progress
    tasks[task_id]['message'] = 'ES: Kalıcı tarayıcı oturumu açılıyor...'

    os.makedirs(ES_PROFILE_DIR, exist_ok=True)
    context = p.chromium.launch_persistent_context(
        user_data_dir=ES_PROFILE_DIR,
        channel='chrome',
        headless=False,
        viewport={'width': 1280, 'height': 800},
        ignore_https_errors=True,
        args=['--ignore-certificate-errors', '--window-size=1280,800', '--window-position=0,0']
    )
    page = context.pages[0] if context.pages else context.new_page()
    tasks[task_id]['_page'] = page
    try:
        _bring_chrome_to_foreground()
        page.goto(device_add_url, timeout=30000)
        page.wait_for_timeout(2500)

        # Keycloak giriş ekranındaysak otomatik kullanıcı/şifre doldur ve pencereyi öne getir
        if '/auth/realms/' in page.url or page.locator('#username').count() > 0:
            page.fill('#username', user)
            page.fill('#login-password', password)
            page.bring_to_front()
            _bring_chrome_to_foreground()
            tasks[task_id]['message'] = (
                'ES: Kullanıcı adı ve şifre dolduruldu. '
                'Lütfen aşağıdaki canlı ekranda "I\'m not a robot" (reCAPTCHA) kutucuğuna tıklayın '
                '(tıkladığınız an sistem otomatik olarak giriş yapıp cihazı kaydedecektir)...'
            )

            logged_in = False
            tasks[task_id]['_click_queue'] = []

            for loop_i in range(360):  # 180 saniye bekle
                if loop_i % 6 == 0 and loop_i <= 30:
                    _bring_chrome_to_foreground()

                # 1. Kuyruktaki kullanıcı tıklamalarını uygula
                while tasks[task_id].get('_click_queue'):
                    try:
                        cx, cy = tasks[task_id]['_click_queue'].pop(0)
                        page.mouse.click(cx, cy)
                        page.wait_for_timeout(100)
                    except Exception as ce:
                        print(f"[CLICK HATA] {ce}", flush=True)

                # 2. Canlı ekran görüntüsünü al ve belleğe kaydet
                try:
                    tasks[task_id]['_screenshot_bytes'] = page.screenshot(type='jpeg', quality=75)
                except Exception:
                    pass

                # 3. Giriş yapıldı mı kontrol et
                if '/ui/#/' in page.url and '/auth/realms/' not in page.url:
                    logged_in = True
                    break
                try:
                    btn = page.locator('#sbtbtn')
                    if btn.count() > 0 and not btn.is_disabled():
                        tasks[task_id]['message'] = 'ES: reCAPTCHA doğrulandı, SIGN IN tıklanıyor...'
                        btn.click()
                        page.wait_for_timeout(4000)
                        logged_in = True
                        break
                except Exception:
                    pass
                page.wait_for_timeout(400)

            if not logged_in and ('/auth/realms/' in page.url):
                raise RuntimeError('ES: reCAPTCHA doğrulaması zaman aşımına uğradı (180 sn).')

        page.wait_for_timeout(2500)
        if '#/deviceAdd' not in page.url:
            page.goto(device_add_url, timeout=30000)
            page.wait_for_timeout(2500)

        return _fill_and_save_device_add(
            page, imei, imsi, msisdn, manufacturer, model, 'ES', task_id, base_progress
        )
    finally:
        tasks[task_id]['_page'] = None
        context.close()


def _run_registration(task_id, imei, imsi, msisdn, target, manufacturer, model):
    """
    Arka plan iş parçacığında MDM ve/veya ES cihaz kaydını gerçekleştirir.
    """
    try:
        from playwright.sync_api import sync_playwright

        results = []
        with sync_playwright() as p:
            if target in ('both', 'mdm'):
                mdm_res = _register_on_mdm(
                    p, imei, imsi, msisdn, manufacturer, model, task_id, base_progress=10
                )
                results.append(mdm_res)

            if target in ('both', 'es'):
                es_base = 55 if target == 'both' else 10
                es_res = _register_on_es(
                    p, imei, imsi, msisdn, manufacturer, model, task_id, base_progress=es_base
                )
                results.append(es_res)

        tasks[task_id]['progress'] = 100
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['message'] = ' | '.join(results) + f' (IMEI: {imei}, MSISDN: {msisdn}, IMSI: {imsi})'
        tasks[task_id]['completed_at'] = datetime.now().isoformat()
        print(f"[MDM/ES] Görev {task_id} tamamlandı: {tasks[task_id]['message']}", flush=True)

    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['message'] = f'Hata: {str(e)}'
        tasks[task_id]['completed_at'] = datetime.now().isoformat()
        print(f"[MDM/ES HATA] Görev {task_id}: {str(e)}", flush=True)


def get_task_status(task_id):
    """Verilen görev ID'sine ait durum bilgisini döndürür."""
    return tasks.get(task_id, None)


def get_task_screenshot(task_id):
    """Aktif görevin iş parçacığı tarafından kaydedilen son canlı ekran görüntüsünü döndürür."""
    task = tasks.get(task_id)
    if not task:
        return None
    return task.get('_screenshot_bytes')


def click_task_screen(task_id, x, y):
    """Kullanıcının canlı ekranda tıkladığı koordinatı iş parçacığı kuyruğuna ekler."""
    task = tasks.get(task_id)
    if not task:
        return False
    if '_click_queue' not in task:
        task['_click_queue'] = []
    task['_click_queue'].append((float(x), float(y)))
    return True
