# -*- coding: utf-8 -*-
"""
ICCID modülü.
- load_cached_lines(): iccid_cache.json dosyasından kalıcı hat ve kontrol sonuçlarını yükler.
- fetch_iccids(): TestPortal'daki seçili kullanıcıların hatlarını çeker ve iccid_cache.json'a kaydeder.
- check_iccid_status(msisdn): MusteriBilgisi.aspx sayfasında MSISDN sorgular ve sonucu iccid_cache.json'a yazar.
"""

import sys
import os
import json
import threading
import time
from datetime import datetime, timedelta

# Proje kök dizinini path'e ekle
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config

TIMEOUT = 60000
MUSTERI_BILGISI_URL = f"{config.TESTPORTAL['url']}/Otomasyon/Ortak/MusteriBilgisi.aspx"
CACHE_FILE = os.path.join(ROOT, "iccid_cache.json")
CLEANING_QUEUE_FILE = os.path.join(ROOT, "cleaning_queue.json")
_cache_lock = threading.Lock()
_queue_lock = threading.Lock()
_monitor_thread = None

# Alan içinde bu metinlerden biri varsa veya hata/boş ise "bilgi yok (temiz)" kabul edilir
BOS_DEGERLER = {
    '', '-', 'yok', 'kayıt yok', 'kayit yok', 'kayıt bulunamadı',
    'bulunamadı', 'veri yok', 'no data', 'null', 'none'
}


def load_cached_lines():
    """iccid_cache.json dosyasından kayıtlı hatları ve kontrol durumlarını yükler."""
    with _cache_lock:
        if not os.path.exists(CACHE_FILE):
            initial = [dict(item) for item in getattr(config, 'TEST_LINES', [])]
            _save_cached_lines_unlocked(initial)
            return initial
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[ICCID CACHE OKUMA HATASI] {e}")
        return [dict(item) for item in getattr(config, 'TEST_LINES', [])]


def _save_cached_lines_unlocked(lines):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(lines, f, ensure_ascii=False, indent=2)


def save_cached_lines(lines):
    """Hat listesini thread-safe olarak iccid_cache.json dosyasına kaydeder."""
    with _cache_lock:
        _save_cached_lines_unlocked(lines)


def update_line_status_in_cache(msisdn, status, details):
    """Kontrol edilen bir MSISDN'in Temiz/Kirli sonucunu iccid_cache.json içinde kalıcı olarak günceller."""
    msisdn_str = str(msisdn).strip()
    with _cache_lock:
        lines = []
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    lines = json.load(f)
            except Exception:
                lines = [dict(item) for item in getattr(config, 'TEST_LINES', [])]
        else:
            lines = [dict(item) for item in getattr(config, 'TEST_LINES', [])]

        updated = False
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in lines:
            if str(item.get('msisdn', '')).strip() == msisdn_str:
                item['status'] = status
                item['details'] = details
                item['checked_at'] = now_str
                if status == 'clean':
                    item.pop('next_check_at', None)
                updated = True

        if updated:
            _save_cached_lines_unlocked(lines)


def mark_iccid_dirty_in_cache(iccid):
    """Opera aktivasyonu tamamlanan veya kullanımda olduğu tespit edilen ICCID'yi iccid_cache.json içinde 'dirty' olarak işaretler."""
    iccid_str = str(iccid).strip()
    if not iccid_str:
        return
    with _cache_lock:
        if not os.path.exists(CACHE_FILE):
            return
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                lines = json.load(f)
            updated = False
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for item in lines:
                if str(item.get('iccid', '')).strip() == iccid_str:
                    item['status'] = 'dirty'
                    details = item.get('details') if isinstance(item.get('details'), dict) else {}
                    details['OPERA'] = True
                    item['details'] = details
                    item['checked_at'] = now_str
                    updated = True
            if updated:
                _save_cached_lines_unlocked(lines)
        except Exception as e:
            print(f"[ICCID DIRTY İŞARETLEME HATASI] {e}")


def remove_owner_lines_from_cache(owner_name):
    """Silinen bir kullanıcının hatlarını önbellekten temizler."""
    if not owner_name:
        return
    with _cache_lock:
        if not os.path.exists(CACHE_FILE):
            return
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                lines = json.load(f)
            lines = [item for item in lines if item.get('owner') != owner_name]
            _save_cached_lines_unlocked(lines)
        except Exception:
            pass


def _login(page):
    """TestPortal girişi (ICCID.py ve Test.py ile aynı seçiciler)."""
    page.goto(f"{config.TESTPORTAL['url']}/Login.aspx", timeout=TIMEOUT)
    page.get_by_role("textbox", name="Domain ID").click()
    page.get_by_role("textbox", name="Domain ID").fill(config.TESTPORTAL['user'])
    page.get_by_role("textbox", name="Domain ID").press("Tab")
    page.get_by_role("textbox", name="******").fill(config.TESTPORTAL['password'])
    page.get_by_role("textbox", name="******").press("Enter")


def _has_real_data(text):
    """Dönen metin boş değilse ve anlamlı müşteri/hat verisi içeriyorsa True döner."""
    if not text:
        return False
    cleaned = text.strip().lower()
    if cleaned in BOS_DEGERLER:
        return False
    # Sadece hata/boş mesajı ("bulunamadı", "kayıt yok", "cudb de profil yok" vb.) dönmüşse temiz say
    if any(k in cleaned for k in (
        'bulunamadı', 'bulunamadi', 'kayıt yok', 'kayit yok',
        'not found', 'no record', 'cudb de profil yok', 'profil yok'
    )):
        return False
    return True


def _check_hlr_data(text):
    """
    HLR (EMA) sekmesini kontrol eder:
    - 'RESP 1001;' veya 'RESP\t1001;' gelmişse HLR kirli değil, HLR DB'de sıkıntı var demektir -> 'db_error'
    - Gerçek veri varsa -> True
    - Boşsa -> False
    """
    if not text:
        return False
    cleaned = text.strip()
    if re_match_resp_1001(cleaned):
        return 'db_error'
    return _has_real_data(cleaned)


def re_match_resp_1001(text):
    import re
    return bool(re.search(r'RESP\s+1001\s*;', text, re.IGNORECASE))


def fetch_iccids(user_ids=None):
    """
    ICCID.py'deki get_ICCID() ile seçilen kullanıcıların (tekil veya çoklu liste)
    üzerindeki MSISDN'i olan dataların ICCID'lerini ve Sanal/Fiziksel tiplerini çeker.
    Daha önce kontrol edilmiş hatların Temiz/Kirli durumlarını koruyarak iccid_cache.json'a kaydeder.
    """
    try:
        from playwright.sync_api import sync_playwright
        import ICCID as ICCID_Func

        fetched_data = []
        fetched_owners = set()
        users_map = ICCID_Func.load_users()

        with sync_playwright() as p:
            if not user_ids or user_ids == 'all':
                target_ids = [
                    uid for uid, u in users_map.items()
                    if u.get('User') and u.get('Password')
                ]
            elif isinstance(user_ids, (list, tuple)):
                target_ids = [int(uid) for uid in user_ids if int(uid) in users_map]
            else:
                target_ids = [int(user_ids)]

            for uid in target_ids:
                owner_name = users_map[uid]['Name']
                fetched_owners.add(owner_name)
                raw = ICCID_Func.get_ICCID(p, user_id=uid)
                for r in raw:
                    if r.get('MSISDN') and r.get('ICCID'):
                        fetched_data.append({
                            'msisdn': r['MSISDN'],
                            'imsi': r['IMSI'],
                            'iccid': r['ICCID'],
                            'owner': r.get('OWNER', owner_name),
                            'type': r.get('TYPE', '-'),
                            'pos_pre': r.get('POS_PRE', '-'),
                        })

        # Mevcut önbellekle birleştir (daha önce kontrol edilmiş MSISDN'lerin status/details bilgisini koru)
        with _cache_lock:
            existing_lines = []
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        existing_lines = json.load(f)
                except Exception:
                    existing_lines = [dict(item) for item in getattr(config, 'TEST_LINES', [])]
            else:
                existing_lines = [dict(item) for item in getattr(config, 'TEST_LINES', [])]

            status_map = {
                str(item.get('msisdn', '')).strip(): {
                    'status': item.get('status'),
                    'details': item.get('details'),
                    'checked_at': item.get('checked_at'),
                }
                for item in existing_lines
                if item.get('status')
            }

            # Çekilen hatlara varsa eski kontrol durumlarını ekle
            for item in fetched_data:
                m = str(item['msisdn']).strip()
                if m in status_map:
                    item['status'] = status_map[m]['status']
                    item['details'] = status_map[m]['details']
                    item['checked_at'] = status_map[m].get('checked_at')

            # Çekilmeyen diğer kullanıcıların hatlarını koru, çekilen kullanıcıların hatlarını yenileriyle değiştir
            other_lines = [item for item in existing_lines if item.get('owner') not in fetched_owners]
            merged_lines = other_lines + fetched_data
            merged_lines.sort(key=lambda x: str(x.get('msisdn', '')).strip())
            _save_cached_lines_unlocked(merged_lines)

        print(f"[ICCID] {len(fetched_data)} hat çekildi ve önbelleğe kaydedildi (user_ids={target_ids}).")
        return {'success': True, 'data': fetched_data, 'all_lines': merged_lines}
    except Exception as e:
        print(f"[ICCID HATA] {e}")
        return {'success': False, 'error': f'ICCID listesi çekilemedi: {str(e).splitlines()[0] if str(e) else e}'}


def check_iccid_status(msisdn):
    """
    MSISDN'i MusteriBilgisi.aspx'te sorgular (Test.py'deki gerçek seçicilerle).
    Dönüş data.status: 'clean' | 'dirty'
    data.details: {'BSCS': True/False, 'OCS': ..., 'OPERA': ..., 'HLR': ..., 'CUDB': ..., 'SIEBEL': ...}
    Sonucu iccid_cache.json dosyasına kalıcı olarak kaydeder.
    """
    msisdn = str(msisdn or '').strip()
    if not msisdn:
        return {'success': False, 'error': 'MSISDN boş olamaz.'}

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            try:
                _login(page)
                page.goto(MUSTERI_BILGISI_URL, timeout=TIMEOUT)

                # BSCS Server seçimi ve MSISDN sorgulama (Test.py satır 26-29)
                if page.locator("#BodyCenter_ddlBSCSServer").count() > 0:
                    page.locator("#BodyCenter_ddlBSCSServer").select_option("1")
                page.locator("#BodyCenter_txtMSISDN").click()
                page.locator("#BodyCenter_txtMSISDN").fill(msisdn)
                page.locator("#BodyCenter_txtMSISDN").press("Enter")
                page.wait_for_load_state('networkidle', timeout=TIMEOUT)

                main_div = "#BodyCenter_tcMusteriBilgisi_tab"
                details = {
                    'BSCS': False,
                    'OCS': False,
                    'OPERA': False,
                    'HLR': False,
                    'CUDB': False,
                    'SIEBEL': False,
                }

                # 1. BSCS
                if page.is_visible(main_div + "BSCS_pBSCS"):
                    txt = page.locator(main_div + "BSCS_pBSCS").inner_text()
                    details['BSCS'] = _has_real_data(txt)

                # 2. OCS
                page.get_by_role("link", name="OCS").click()
                if page.is_visible(main_div + "OCS_pOCS"):
                    txt = page.locator(main_div + "OCS_pOCS").inner_text()
                    details['OCS'] = _has_real_data(txt)

                # 3. OPERA
                page.get_by_role("link", name="OPERA").click()
                if page.is_visible(main_div + "OPERA_pOPERA"):
                    loc = page.locator(main_div + "OPERA_pOPERA")
                    txt = loc.inner_text()
                    details['OPERA'] = _has_real_data(txt)

                # 4. HLR (EMA)
                page.get_by_role("link", name="HLR").click()
                if page.is_visible(main_div + "EMA_pEMA"):
                    txt = page.locator(main_div + "EMA_pEMA").inner_text()
                    details['HLR'] = _check_hlr_data(txt)

                # 5. CUDB
                page.get_by_role("link", name="CUDB").click()
                if page.is_visible(main_div + "CUDB_pCUDB") or page.is_visible(main_div + "CUDB_CUDBErrorDiv"):
                    txt = page.locator(main_div + "CUDB_pCUDB," + main_div + "CUDB_CUDBErrorDiv").first.inner_text()
                    details['CUDB'] = _has_real_data(txt)

                # 6. SIEBEL
                page.get_by_role("link", name="SIEBEL").click()
                if page.is_visible(main_div + "SIEBEL_pSIEBEL"):
                    txt = page.locator(main_div + "SIEBEL_pSIEBEL").inner_text()
                    details['SIEBEL'] = _has_real_data(txt)

                # Sadece True olanlar kirli sayılır ('db_error' veya False kirli yapmaz)
                status = 'dirty' if any(v is True for v in details.values()) else 'clean'
            finally:
                context.close()
                browser.close()

        # Kalıcı önbelleğe yaz
        update_line_status_in_cache(msisdn, status, details)

        print(f"[ICCID] {msisdn}: {status} {details}")
        return {'success': True, 'data': {'msisdn': msisdn, 'status': status, 'details': details}}

    except Exception as e:
        print(f"[ICCID HATA] {msisdn}: {e}")
        return {'success': False, 'error': f'Kontrol hatası: {str(e).splitlines()[0] if str(e) else e}'}


def get_next_cleaning_check_time(from_dt=None):
    """
    TestPortal temizlik sistemi her saatin 00, 15, 30 ve 45. dakikalarında job olarak çalışır.
    Bu fonksiyon, job çalışmasından 5 dakika sonrasını (05, 20, 35, 50) hesaplar:
    - 00:00 - 14:59 arası: sonraki job 15'te -> kontrol 20'de
    - 15:00 - 29:59 arası: sonraki job 30'da -> kontrol 35'te
    - 30:00 - 44:59 arası: sonraki job 45'te -> kontrol 50'de
    - 45:00 - 59:59 arası: sonraki job sonraki saat 00'da -> kontrol sonraki saat 05'te
    """
    if from_dt is None:
        from_dt = datetime.now()
    m = from_dt.minute
    if m < 15:
        target = from_dt.replace(minute=20, second=0, microsecond=0)
    elif m < 30:
        target = from_dt.replace(minute=35, second=0, microsecond=0)
    elif m < 45:
        target = from_dt.replace(minute=50, second=0, microsecond=0)
    else:
        next_hour = from_dt + timedelta(hours=1)
        target = next_hour.replace(minute=5, second=0, microsecond=0)
    return target


def load_cleaning_queue():
    """Temizlik kontrol kuyruğunu cleaning_queue.json dosyasından okur."""
    with _queue_lock:
        if not os.path.exists(CLEANING_QUEUE_FILE):
            return []
        try:
            with open(CLEANING_QUEUE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[CLEANING QUEUE OKUMA HATASI] {e}")
        return []


def save_cleaning_queue(queue):
    """Temizlik kontrol kuyruğunu cleaning_queue.json dosyasına kaydeder."""
    with _queue_lock:
        try:
            with open(CLEANING_QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(queue, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CLEANING QUEUE YAZMA HATASI] {e}")


def add_to_cleaning_queue(msisdns):
    """
    Temizliğe gönderilen hatları kuyruğa ekler ve en yakın job'dan 5 dk sonraya kontrol zamanı atar.
    Ayrıca iccid_cache.json dosyasını da günceller.
    """
    if not msisdns:
        return
    queue = load_cleaning_queue()
    existing_map = {str(item.get('msisdn', '')).strip(): item for item in queue}

    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    next_check = get_next_cleaning_check_time(now)
    next_check_str = next_check.strftime("%Y-%m-%d %H:%M:%S")

    for m in msisdns:
        m_str = str(m).strip()
        if not m_str:
            continue
        if m_str in existing_map:
            existing_map[m_str]['next_check_at'] = next_check_str
            existing_map[m_str]['updated_at'] = now_str
        else:
            existing_map[m_str] = {
                'msisdn': m_str,
                'added_at': now_str,
                'next_check_at': next_check_str,
                'retry_count': 0
            }

    save_cleaning_queue(list(existing_map.values()))

    # iccid_cache.json dosyasını güncelle
    with _cache_lock:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    lines = json.load(f)
                updated = False
                for item in lines:
                    m = str(item.get('msisdn', '')).strip()
                    if m in existing_map:
                        item['next_check_at'] = next_check_str
                        item['cleaned_at'] = now_str
                        updated = True
                if updated:
                    _save_cached_lines_unlocked(lines)
            except Exception as e:
                print(f"[CACHE NEXT_CHECK GÜNCELLEME HATASI] {e}")

    start_cleaning_monitor_if_needed()


def _process_pending_cleaning_checks():
    """
    Zamanı gelmiş hatların temizlik durumunu kontrol eder:
    - Temizlenmişse ('clean') kuyruktan çıkarır ve kontrolü sonlandırır.
    - Temizlenmemişse ('dirty') bir sonraki job'dan 5 dakika sonraya öteler.
    """
    queue = load_cleaning_queue()
    if not queue:
        return

    now = datetime.now()
    due_items = []
    remaining_items = []

    for item in queue:
        chk_str = item.get('next_check_at', '')
        try:
            chk_dt = datetime.strptime(chk_str, "%Y-%m-%d %H:%M:%S")
            if now >= chk_dt:
                due_items.append(item)
            else:
                remaining_items.append(item)
        except Exception:
            due_items.append(item)

    if not due_items:
        return

    print(f"[TEMIZLIK MONITORU] {len(due_items)} hat icin kontrol zamani geldi ({now.strftime('%H:%M:%S')}). Kontroller yapiliyor...")

    for item in due_items:
        msisdn = item.get('msisdn')
        if not msisdn:
            continue
        try:
            print(f"[TEMIZLIK MONITORU] Otomatik kontrol: {msisdn}")
            res = check_iccid_status(msisdn)
            st = res.get('data', {}).get('status') if res.get('success') else None

            if st == 'clean':
                print(f"[TEMIZLIK MONITORU] >>> {msisdn} TEMIZLENDI! Kuyruktan cikarildi.")
                with _cache_lock:
                    try:
                        with open(CACHE_FILE, "r", encoding="utf-8") as f:
                            lines = json.load(f)
                        for it in lines:
                            if str(it.get('msisdn', '')).strip() == str(msisdn):
                                it.pop('next_check_at', None)
                        _save_cached_lines_unlocked(lines)
                    except Exception:
                        pass
            else:
                # Temizlenmemişse bir sonraki job'dan 5 dk sonraya planla
                next_chk = get_next_cleaning_check_time(datetime.now())
                next_chk_str = next_chk.strftime("%Y-%m-%d %H:%M:%S")
                item['next_check_at'] = next_chk_str
                item['retry_count'] = item.get('retry_count', 0) + 1
                item['last_status'] = st or 'error'
                remaining_items.append(item)
                print(f"[TEMIZLIK MONITORU] >>> {msisdn} henuz temizlenmemis ({st}). Bir sonraki kontrol zamani: {next_chk_str}")

                with _cache_lock:
                    try:
                        with open(CACHE_FILE, "r", encoding="utf-8") as f:
                            lines = json.load(f)
                        for it in lines:
                            if str(it.get('msisdn', '')).strip() == str(msisdn):
                                it['next_check_at'] = next_chk_str
                        _save_cached_lines_unlocked(lines)
                    except Exception:
                        pass
        except Exception as err:
            print(f"[TEMIZLIK MONITORU HATA] {msisdn}: {err}")
            next_chk = get_next_cleaning_check_time(datetime.now())
            item['next_check_at'] = next_chk.strftime("%Y-%m-%d %H:%M:%S")
            remaining_items.append(item)

    save_cleaning_queue(remaining_items)


def _cleaning_monitor_loop():
    while True:
        try:
            _process_pending_cleaning_checks()
        except Exception as e:
            print(f"[TEMIZLIK DONGUSU HATASI] {e}")
        time.sleep(20)


def start_cleaning_monitor_if_needed():
    global _monitor_thread
    if _monitor_thread is None or not _monitor_thread.is_alive():
        _monitor_thread = threading.Thread(target=_cleaning_monitor_loop, daemon=True, name="CleaningMonitorThread")
        _monitor_thread.start()
        print("[TEMIZLIK MONITORU] Arka plan kontrol thread'i baslatildi.")


def clean_iccids(msisdn_list):
    """
    Seçilen MSISDN listesini sahiplerine (owner) göre gruplayarak
    ilgili kullanıcının TestPortal hesabı ile TestHattiTemizleme.aspx sayfasına girer,
    ilgili hatların kutucuklarını işaretler ve 'Temizleme Talebini Gönder' (#BodyCenter_temizleme) butonuna basar.
    """
    if not msisdn_list or not isinstance(msisdn_list, (list, tuple)):
        return {'success': False, 'error': 'Temizliğe gönderilecek en az bir hat seçilmelidir.'}

    target_msisdns = [str(m).strip() for m in msisdn_list if str(m).strip()]
    if not target_msisdns:
        return {'success': False, 'error': 'Geçerli MSISDN bulunamadı.'}

    try:
        from playwright.sync_api import sync_playwright, expect
        import ICCID as ICCID_Func

        cached_lines = load_cached_lines()
        msisdn_to_owner = {
            str(item.get('msisdn', '')).strip(): item.get('owner', '')
            for item in cached_lines
        }

        users_map = ICCID_Func.load_users()
        name_to_user = {u['Name']: u for u in users_map.values()}
        default_user = {
            'Name': 'Varsayılan',
            'User': config.TESTPORTAL['user'],
            'Password': config.TESTPORTAL['password']
        }

        # MSISDN'leri sahibine göre grupla
        owner_groups = {}
        for m in target_msisdns:
            owner_name = msisdn_to_owner.get(m, '')
            owner_groups.setdefault(owner_name, []).append(m)

        cleaned_msisdns = []
        not_found_msisdns = []
        portal_messages = []

        with sync_playwright() as p:
            for owner_name, owner_msisdns in owner_groups.items():
                u_info = name_to_user.get(owner_name)
                if not u_info or not u_info.get('User') or not u_info.get('Password'):
                    u_info = default_user

                browser = p.chromium.launch(headless=True)
                context = browser.new_context(ignore_https_errors=True)
                page = context.new_page()
                try:
                    page.goto(f"{config.TESTPORTAL['url']}/Login.aspx", timeout=TIMEOUT)
                    page.get_by_role("textbox", name="Domain ID").click()
                    page.get_by_role("textbox", name="Domain ID").fill(u_info['User'])
                    page.get_by_role("textbox", name="Domain ID").press("Tab")
                    page.get_by_role("textbox", name="******").fill(u_info['Password'])
                    page.get_by_role("textbox", name="******").press("Enter")
                    expect(page.locator("[id=bilgilendirme]")).to_be_visible(timeout=TIMEOUT)

                    page.goto(f"{config.TESTPORTAL['url']}/Talepler/TestHattiTemizleme.aspx", timeout=TIMEOUT)
                    page.wait_for_load_state("networkidle", timeout=TIMEOUT)

                    # Tüm ağaç düğümlerini (Sanal, Fiziksel, Pos, Pre ve tüm alt grupları) görünür yap
                    page.evaluate("""() => {
                        document.querySelectorAll('#BodyCenter_treeSanalHat div[id$="Nodes"], #BodyCenter_treeFizikselHat div[id$="Nodes"]').forEach(div => {
                            div.style.display = 'block';
                        });
                    }""")
                    page.wait_for_timeout(300)

                    checked_any = False
                    for m in owner_msisdns:
                        m_str = str(m).strip()
                        # Hem Sanal hem Fiziksel ağaçtaki satır/hücrelerde MSISDN ara
                        row_locator = page.locator(
                            "#BodyCenter_treeSanalHat tr, #BodyCenter_treeFizikselHat tr, #BodyCenter_treeSanalHat td, #BodyCenter_treeFizikselHat td"
                        ).filter(has_text=m_str).first

                        row_found = False
                        if row_locator.count() > 0:
                            cb = row_locator.locator('input[type="checkbox"]').first
                            if cb.count() > 0:
                                cb.check(force=True)
                                checked_any = True
                                cleaned_msisdns.append(m_str)
                                row_found = True

                        if not row_found:
                            # JS fallback ile doğrudan ara ve işaretle
                            js_checked = page.evaluate("""(msisdn) => {
                                const allRows = document.querySelectorAll('#BodyCenter_treeSanalHat tr, #BodyCenter_treeFizikselHat tr');
                                for (const r of allRows) {
                                    if (r.innerText && r.innerText.includes(msisdn)) {
                                        const c = r.querySelector('input[type="checkbox"]');
                                        if (c) {
                                            c.checked = true;
                                            return true;
                                        }
                                    }
                                }
                                return false;
                            }""", m_str)
                            if js_checked:
                                checked_any = True
                                cleaned_msisdns.append(m_str)
                            else:
                                not_found_msisdns.append(m_str)

                    if checked_any:
                        page.evaluate("window.temizleme = window.temizleme || function(){};")
                        submit_btn = page.locator("#BodyCenter_temizleme")
                        submit_btn.click()
                        page.wait_for_load_state("networkidle", timeout=TIMEOUT)
                        page.wait_for_timeout(1000)

                        msg_loc = page.locator("#BodyCenter_hatYok")
                        if msg_loc.count() > 0:
                            msg_txt = msg_loc.inner_text().strip()
                            if msg_txt:
                                portal_messages.append(f"{owner_name}: {msg_txt}")
                finally:
                    context.close()
                    browser.close()

        # Önbellekte temizlik talebi zamanını işaretle ve otomatik kontrol kuyruğuna ekle
        if cleaned_msisdns:
            add_to_cleaning_queue(cleaned_msisdns)

        if not cleaned_msisdns:
            return {
                'success': False,
                'error': f"Seçilen hatlar TestHattiTemizleme sayfasında bulunamadı: {', '.join(not_found_msisdns)}"
            }

        return {
            'success': True,
            'data': {
                'cleaned': cleaned_msisdns,
                'not_found': not_found_msisdns,
                'portal_messages': portal_messages,
            }
        }
    except Exception as e:
        print(f"[ICCID TEMİZLEME HATASI] {e}")
        return {'success': False, 'error': f'Temizleme talebi hatası: {str(e).splitlines()[0] if str(e) else e}'}


# Modül yüklendiğinde temizlik izleme thread'ini başlat (kuyrukta bekleyen hatlar varsa)
start_cleaning_monitor_if_needed()
