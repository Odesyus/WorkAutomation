import re
import sys

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from playwright.sync_api import Playwright, sync_playwright, expect
import random
import time
import json
import os
import MernsDB
import ICCID as ICCID_Func
import CMPDB as OTP
import config

# Test ICCID listesi (Ben ve Ezgi üzerindeki temiz ICCID'ler)
ICCID_LIST = [
    # Ben (37157378)
    '89902860372001744591',
    '89902860372001744609',
    '89902860372001744617',
    '89902860372001744823',
    '89902860372001744831',
    '89902860372001744849',
    '89902860372001745036',
    # Ezgi
    '89902860372001718876',
    '89902860372001718926',
    '89902860372001718934',
    '89902860372001718942',
    '89902860372001718959',
    '89902860372001718967',
    '89902860372001720526',
    '89902860372001744567',
    '89902860372001744575',
    '89902860372001744583',
]

ICCID_Index = 0
DEFAULT_TIMEOUT = 60000  # 60 saniye


def main():
    global ICCID_Index
    with sync_playwright() as playwright:
        Merns = MernsDB.get_Merns()
        #Data = ICCID_Func.get_ICCID(playwright)
        #Data_ICCID = Data[ICCID_Index]["ICCID"]
        # Kullanımda olan ICCID'leri atlayarak sıradakini dene
        while ICCID_Index < len(ICCID_LIST):
            Data_ICCID = ICCID_LIST[ICCID_Index]
            sonuc = run(playwright, Merns["TCKN"], Merns["DOĞUM TARİHİ"], Data_ICCID)
            if sonuc != 'ICCID_IN_USE':
                return
            ICCID_Index = ICCID_Index + 1
        print("Tüm ICCID'ler denendi, uygun ICCID bulunamadı.")


def run(playwright: Playwright, TCKN, DT, ICCID, progress=None, options=None):
    """
    Opera aktivasyon akışını çalıştırır.
    progress: isteğe bağlı callback -> progress(yuzde, mesaj). Web arayüzü durum takibi için kullanır.
    options: {'gsm': bool, 'wcdma': bool, 'lte': bool, 'nr': bool, 'volte': bool, 'vowifi': bool}
    Dönüş: 'OK' (başarılı) veya 'ICCID_IN_USE' (ICCID kullanımda).
    """
    def report(yuzde, mesaj):
        try:
            print(f"[%{yuzde}] {mesaj}", flush=True)
        except Exception:
            try:
                print(f"[%{yuzde}] {str(mesaj).encode('ascii', 'ignore').decode()}", flush=True)
            except Exception:
                pass
        if progress:
            progress(yuzde, mesaj)

    opts = options or {}
    MSISDN = opts.get('msisdn') or ICCID
    POS_PRE = opts.get('pos_pre')
    if MSISDN == ICCID or not POS_PRE:
        try:
            with open("iccid_cache.json", "r", encoding="utf-8") as f:
                for item in json.load(f):
                    if str(item.get("iccid", "")).strip() == str(ICCID).strip():
                        if MSISDN == ICCID and item.get("msisdn"):
                            MSISDN = str(item.get("msisdn")).strip()
                        if not POS_PRE:
                            POS_PRE = item.get("pos_pre")
                        break
        except Exception:
            pass
    # Pre -> Faturasız, diğer tüm durumlar (Pos / bilinmiyor) -> Faturalı
    is_prepaid = str(POS_PRE or "").strip().lower() in ["pre", "prepaid", "faturasız", "faturasiz"]
    HAT_TIPI = "Faturasız Hat" if is_prepaid else "Faturalı Hat"
    NR = bool(opts.get('nr', False))
    VoLTE = bool(opts.get('volte', True))
    VoWifi = bool(opts.get('vowifi', True))
    LTE = bool(opts.get('lte', True)) or NR or VoLTE or VoWifi
    WCDMA = bool(opts.get('wcdma', True)) or LTE
    GSM = bool(opts.get('gsm', True)) or WCDMA

    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        if callable(opts.get("is_stopped")) and opts["is_stopped"]():
            return None

        if attempt > 1:
            report(10, f"Zaman aşımı sonrası aktivasyon yeniden başlatılıyor (Deneme {attempt}/{MAX_RETRIES})...")
        else:
            report(5, "Opera MTS'e giriş yapılıyor...")

        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        # Tarayıcı yazdırma penceresinin (window.print) otomasyonu bloklamasını engelle
        context.add_init_script("window.print = function() {};")
        page = context.new_page()
        page.set_default_timeout(60000)  # Yavaş ADF istekleri için 60 saniye default timeout
        page.set_default_navigation_timeout(60000)
        if callable(opts.get("on_page_ready")):
            opts["on_page_ready"](page)

        def capture_error_screenshot():
            if callable(opts.get("is_stopped")) and opts["is_stopped"]():
                return None
            try:
                root_dir = os.path.dirname(os.path.abspath(__file__))
                shots_dir = os.path.join(root_dir, "static", "screenshots")
                os.makedirs(shots_dir, exist_ok=True)
                fname = f"opera_error_{int(time.time() * 1000)}.png"
                fpath = os.path.join(shots_dir, fname)
                page.screenshot(path=fpath, full_page=True)
                shot_url = f"/static/screenshots/{fname}"
                if callable(opts.get("on_screenshot")):
                    opts["on_screenshot"](shot_url)
                return shot_url
            except Exception as shot_err:
                print(f"[SCREENSHOT HATA] {shot_err}")
                return None

        try:
            return _execute_opera_flow(page, context, browser, TCKN, DT, ICCID, MSISDN, GSM, WCDMA, LTE, NR, VoLTE, VoWifi, report, capture_error_screenshot, HAT_TIPI)
        except Exception as e:
            capture_error_screenshot()
            try:
                context.close()
                browser.close()
            except Exception:
                pass

            if callable(opts.get("is_stopped")) and opts["is_stopped"]():
                raise

            err_text = str(e).lower()
            is_timeout = (
                isinstance(e, TimeoutError) or
                "timeout" in err_text or
                "timed out" in err_text or
                "waiting for" in err_text or
                "target page, context or browser has been closed" in err_text
            )

            if is_timeout and attempt < MAX_RETRIES:
                ozet = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
                # Yarım kalan işlem nedeniyle Opera aynı TCKN'yi kilitler. Yeniden denemede taze Mernis verisi al:
                try:
                    m_data = MernsDB.get_Merns()
                    TCKN = m_data["TCKN"]
                    DT = m_data["DOĞUM TARİHİ"]
                except Exception:
                    pass
                report(10, f"⚠️ Zaman aşımı (Timeout) oluştu: {ozet}. Yeni Müşteri (TCKN: {TCKN}) ve Hat ({MSISDN}) ile yeniden deneniyor (Deneme {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(3)
                continue
            else:
                raise


def _execute_opera_flow(page, context, browser, TCKN, DT, ICCID, MSISDN, GSM, WCDMA, LTE, NR, VoLTE, VoWifi, report, capture_error_screenshot, HAT_TIPI="Faturalı Hat"):
    def wait_glasspane(timeout=20000):
        try:
            glass = page.locator(".AFBlockingGlassPane, .AFModalGlassPane")
            if glass.count() > 0 and glass.first.is_visible():
                glass.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass

    opera_url = config.URLS.get('opera', "http://10.248.67.23:8001/MTS/faces/index")
    page.goto(opera_url)

    # Opera kullanıcısı seçimi (61044774 veya CC51 vb.)
    selected_user_key = (options.get('opera_user') if options else None)
    if not selected_user_key:
        try:
            local_cfg = config.load_local_config()
            selected_user_key = local_cfg.get('default_opera_user', '61044774')
        except Exception:
            selected_user_key = '61044774'

    opera_user_info = config.OPERA_USERS.get(str(selected_user_key))
    if not opera_user_info:
        opera_user_info = {'username': str(selected_user_key), 'password': 'aa1234'}

    report(5, f"Opera'ya giriş yapılıyor (Kullanıcı: {opera_user_info['username']})...")
    page.get_by_role("textbox", name="Kullanıcı Adı (Gerekli)").fill(opera_user_info['username'])
    page.get_by_role("textbox", name="Kullanıcı Şifre (Gerekli)").click()
    page.get_by_role("textbox", name="Kullanıcı Şifre (Gerekli)").fill(opera_user_info['password'])
    page.get_by_role("link").filter(has_text=re.compile(r"^$")).click()
    page.get_by_title("Genişlet").nth(5).click()
    page.get_by_role("link", name="Aktivasyon").click()
    page.get_by_role("button", name="İptal").click()
    page.get_by_role("button", name="Bireysel Müşteri Oluştur").click()

    #Müşteri Anasayfası
    report(15, "Müşteri bilgileri giriliyor...")

    name_box = page.get_by_role("textbox", name=re.compile(r"^Adı", re.IGNORECASE)).first
    for mernis_attempt in range(3):
        wait_glasspane(timeout=10000)
        dt_box = page.get_by_role("textbox", name="Doğum Tarihi")
        dt_box.fill(DT)
        dt_box.press("Tab")

        tckn_box = page.get_by_role("textbox", name="TC Kimlik Numarası")
        tckn_box.fill(TCKN)
        tckn_box.press("Tab")

        page.wait_for_timeout(500)
        mernis_btn = page.get_by_role("button", name="Mernis Sorgulama")
        if mernis_btn.count() > 0 and mernis_btn.is_visible():
            try:
                mernis_btn.click(force=True)
                wait_glasspane(timeout=30000)
            except Exception:
                pass

        found = False
        for _ in range(10):
            try:
                val = (name_box.input_value(timeout=500) or "").strip()
                if val:
                    found = True
                    break
            except Exception:
                pass
            page.wait_for_timeout(1000)

        if found:
            break

        # Mernis'ten yeni TCKN çek ve yeniden dene
        try:
            new_m = MernsDB.get_Merns()
            if new_m and new_m.get("TCKN"):
                TCKN = new_m["TCKN"]
                DT = new_m["DOĞUM TARİHİ"]
                report(15, f"Mernis verisi güncelleniyor: {TCKN}")
        except Exception:
            pass

    expect(name_box).not_to_have_value("", timeout=DEFAULT_TIMEOUT)

    # Anne Kızlık Soyadı / Güvenlik Kelimesi (it20)
    it20 = page.locator("input[name*='it20']")
    if it20.count() > 0:
        it20.first.click()
        it20.first.fill("ada")
    else:
        page.locator("input[name=\"pt1:r1:1:r1:2:it20\"]").fill("ada")

    # Kimlik Türü seçimi (soc7)
    soc7 = page.locator("select[name*='soc7']")
    if soc7.count() > 0:
        ks = soc7.first
    else:
        ks = page.locator("select[name=\"pt1:r1:1:r1:2:soc7\"]")
    ks.focus()
    for _ in range(3):
        ks.press("ArrowDown")
    ks.press("Tab")
    page.wait_for_timeout(500)

    try:
        expect(page.get_by_role("textbox", name="Kimlik Kayıt Numarası")).not_to_be_visible(timeout=5000)
    except Exception:
        pass

    seri_no = page.get_by_role("textbox", name="Seri Numarası")
    if seri_no.count() > 0:
        seri_no.first.click()
        seri_no.first.fill("aa123456")
    else:
        page.locator("input[name*='it22']").first.fill("aa123456")
    if (not(page.get_by_role("combobox", name="İl (Gerekli)", exact=True).is_visible())):
        page.get_by_title("Ara: İl").first.click()
        expect(page.get_by_role("grid", name="Tablodan satır seçin")).to_contain_text("ADANA", timeout=DEFAULT_TIMEOUT)
        page.get_by_role("row", name="ADANA").click()
        expect(page.get_by_role("combobox", name="İl (Gerekli)", exact=True)).to_have_value("ADANA", timeout=DEFAULT_TIMEOUT)
        page.wait_for_timeout(1000)
        page.get_by_title("Ara: İlçe").first.click()
        expect(page.get_by_role("grid", name="Tablodan satır seçin")).to_contain_text("ALADAĞ(KARSANTI)", timeout=DEFAULT_TIMEOUT)
        page.get_by_role("row", name="ALADAĞ(KARSANTI)").click()
        expect(page.get_by_role("combobox", name="İlçe (Gerekli)", exact=True)).to_have_value("ALADAĞ(KARSANTI)", timeout=DEFAULT_TIMEOUT)
        expect(page.get_by_role("combobox", name="Semt")).not_to_be_disabled(timeout=DEFAULT_TIMEOUT)
        page.wait_for_timeout(1500)
        page.get_by_title("Ara: Semt").first.click()
        expect(page.get_by_role("grid", name="Tablodan satır seçin")).to_contain_text("AKÖREN", timeout=DEFAULT_TIMEOUT)
        page.get_by_role("row", name="AKÖREN").click()
        expect(page.get_by_role("combobox", name="Semt")).to_have_value("AKÖREN", timeout=DEFAULT_TIMEOUT)
        page.get_by_role("textbox", name="Adres").click()
        page.get_by_role("textbox", name="Adres").fill("aaa")
        page.get_by_role("textbox", name="Bina/Kapı Numarası").click()
        page.get_by_role("textbox", name="Bina/Kapı Numarası").fill("123")
        page.get_by_role("textbox", name="İrtibat Telefon Numarası 1").click()
        page.get_by_role("textbox", name="İrtibat Telefon Numarası 1").fill("53333333333")
    wait_glasspane()
    page.get_by_role("button", name="İleri").click()

    # İrtibat Doğrulama — OTP devre dışı:
    # İlk İleri tıklaması doğrudan "Hat Tipi ve Numara Seçimi" ekranını açıyorsa ikinci kez İleri'ye basılmaz.
    report(30, "Hat Tipi ve Numara Seçimi ekranı bekleniyor...")
    try:
        expect(page.get_by_role("radio", name="Faturalı Hat")).to_be_visible(timeout=DEFAULT_TIMEOUT)
    except Exception:
        if page.locator("td").filter(has_text="Hata İşleme devam edebilmek i").is_visible():
            wait_glasspane()
            page.get_by_role("button", name="Tamam").click()
        wait_glasspane()
        page.get_by_role("button", name="İleri").click()
        expect(page.get_by_role("radio", name="Faturalı Hat")).to_be_visible(timeout=DEFAULT_TIMEOUT)

    #Hat Tipi ve Numara Seçimi
    report(40, f"{HAT_TIPI} seçiliyor, MSISDN: {MSISDN}")

    radio_btn = page.get_by_role("radio", name=HAT_TIPI, exact=True)
    radio_btn.check()
    wait_glasspane()
    page.wait_for_timeout(1000)
    if not radio_btn.is_checked():
        radio_btn.check()
        wait_glasspane()
        page.wait_for_timeout(1000)

    page.get_by_text("Fiziksel SIM ile ilerlemek").click()
    page.get_by_role("radio", name="Fiziksel SIM ile ilerlemek").check()
    page.get_by_role("textbox", name="SIM Kart Numarası").dblclick()
    page.get_by_role("textbox", name="SIM Kart Numarası").fill(ICCID)
    wait_glasspane()
    page.locator("td").filter(has_text="Özel Numara AktivasyonuSIM").get_by_role("button").click()
    for _ in range(120):
        if page.locator("[id=\"d1::msgDlg\"]").is_visible():
            capture_error_screenshot()
            report(40, f"Hat Kullanımda (MSISDN: {MSISDN})")
            context.close()
            browser.close()
            return 'ICCID_IN_USE'
        try:
            tel_val = (page.get_by_role("textbox", name="Telefon Numarası:").input_value(timeout=500) or "").strip()
            if tel_val:
                break
        except Exception:
            pass
        page.wait_for_timeout(500)
    expect(page.get_by_role("textbox", name="Telefon Numarası:")).not_to_be_empty(timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(1500)
    wait_glasspane()
    page.get_by_role("button", name="İleri").click()


    #Ürün Kataloğu
    report(55, "Ürün kataloğundan tarife seçiliyor...")
    try:
        expect(page.get_by_role("combobox")).to_be_visible(timeout=10000)
    except Exception:
        if page.locator("[id=\"d1::msgDlg\"]").is_visible():
            capture_error_screenshot()
            report(40, f"Hat Kullanımda (MSISDN: {MSISDN})")
            context.close()
            browser.close()
            return 'ICCID_IN_USE'
        page.get_by_role("button", name="İleri").click()
        expect(page.get_by_role("combobox")).to_be_visible(timeout=DEFAULT_TIMEOUT)

    # Katalog combobox'ının seçeneklerinin yüklenmesini bekle (en az 2 seçenek)
    katalog_cb = page.get_by_role("combobox")
    for _ in range(40):
        try:
            if katalog_cb.locator("option").count() > 1:
                break
        except Exception:
            pass
        page.wait_for_timeout(300)

    is_faturasiz = (HAT_TIPI == "Faturasız Hat")
    target_katalog_val = "2" if is_faturasiz else "3"
    target_katalog_label = "BİREYSEL TARİFELER" if is_faturasiz else None

    # Seçim yapma ve Ara butonuna basma döngüsü (ADF PPR ve doğrulama garantisi)
    for attempt in range(5):
        try:
            try:
                katalog_cb.select_option(target_katalog_val, timeout=3000)
            except Exception:
                if target_katalog_label:
                    try:
                        katalog_cb.select_option(label=target_katalog_label, timeout=3000)
                    except Exception:
                        katalog_cb.select_option(index=1, timeout=3000)
                else:
                    katalog_cb.select_option(index=1, timeout=3000)

            katalog_cb.dispatch_event("change")
            katalog_cb.press("Tab")
            page.wait_for_timeout(1000)

            wait_glasspane()
            page.get_by_role("button", name="Ara", exact=True).click()
            page.wait_for_timeout(1500)

            # Tarife tablosunda hedef satır veya Ekle linki geldi mi kontrol et
            if is_faturasiz:
                if page.locator("tr").filter(has_text=re.compile(r"KRAL TAR[Iİ]FE", re.IGNORECASE)).count() > 0:
                    break
            else:
                if page.get_by_role("link", name="Ekle").count() > 0:
                    break
        except Exception:
            page.wait_for_timeout(1000)

    if is_faturasiz:
        report(58, "Kral Tarife seçiliyor...")
        kral_row = page.locator("tr").filter(has_text=re.compile(r"KRAL TAR[Iİ]FE", re.IGNORECASE))
        if kral_row.count() == 0:
            try:
                tarife_inp = page.get_by_role("textbox", name="Tarife Adı")
                if tarife_inp.count() == 0:
                    tarife_inp = page.locator("input[id*='it']")
                tarife_inp.first.fill("KRAL")
                wait_glasspane()
                page.get_by_role("button", name="Ara", exact=True).click()
                page.wait_for_timeout(1500)
                kral_row = page.locator("tr").filter(has_text=re.compile(r"KRAL TAR[Iİ]FE", re.IGNORECASE))
            except Exception:
                pass

        expect(kral_row.first).to_be_visible(timeout=DEFAULT_TIMEOUT)
        kral_ekle = kral_row.first.locator("a[title*='Ekle'], button[title*='Ekle'], a:has-text('Ekle'), img[title*='Ekle'], [id*='add']")
        if kral_ekle.count() > 0:
            kral_ekle.first.click()
        elif kral_row.first.get_by_role("link", name="Ekle").count() > 0:
            kral_row.first.get_by_role("link", name="Ekle").first.click()
        else:
            links = kral_row.first.locator("a")
            if links.count() > 1:
                links.nth(1).click()
            elif links.count() > 0:
                links.first.click()
        report(60, "Kral Tarife başarıyla eklendi.")
    else:
        ekle_links = page.get_by_role("link", name="Ekle")
        expect(ekle_links.first).to_be_visible(timeout=DEFAULT_TIMEOUT)
        ekle_target = ekle_links.nth(3) if ekle_links.count() > 3 else ekle_links.first
        ekle_target.click()

    page.wait_for_timeout(1500)
    report(62, "Tarife onay ve detay pencereleri kapatılıyor...")

    # Üst üste açılan "DİKKAT!" ve "Teklif Detay Bilgileri" modal pencerelerini sırasıyla ve eksiksiz kapat
    for close_attempt in range(15):
        has_popup = False

        # 1. JavaScript ile hem ana sayfada hem de tüm iframe'lerdeki 'x' ve 'Kapat'/'Tamam' elemanlarını doğrudan tetikle
        try:
            page.evaluate("""() => {
                const scanAndDismiss = (doc) => {
                    if (!doc) return;
                    // Kapat ikonları (x)
                    const closeSelectors = [
                        '.af_messages_close-icon',
                        'a.af_dialog_close-icon',
                        'a.af_panelWindow_close-icon',
                        'a[title*="Kapat" i]',
                        'a[title*="kapat" i]',
                        'a[title*="Close" i]',
                        'a[title*="close" i]',
                        '[id*="close" i]',
                        '[id*="d6"]',
                        '[id*="msgDlg::cancel"]'
                    ];
                    closeSelectors.forEach(sel => {
                        try {
                            doc.querySelectorAll(sel).forEach(el => {
                                try { el.click(); } catch(e) {}
                                try { el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); } catch(e) {}
                            });
                        } catch(e) {}
                    });

                    // 'Kapat' veya 'Tamam' butonları / linkleri
                    const buttons = doc.querySelectorAll('button, a, input[type="button"], div[role="button"]');
                    buttons.forEach(el => {
                        const txt = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
                        if (/^(Kapat|Tamam)$/i.test(txt)) {
                            try { el.click(); } catch(e) {}
                            try { el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); } catch(e) {}
                        }
                    });
                };

                scanAndDismiss(document);
                document.querySelectorAll('iframe').forEach(iframe => {
                    try {
                        scanAndDismiss(iframe.contentDocument || iframe.contentWindow.document);
                    } catch(e) {}
                });
            }""")
        except Exception:
            pass

        # 2. Playwright ile tüm frame'lerde (özellikle 'İçerik' iframe'inde) Kapat butonlarını ve DİKKAT x ikonunu tıkla
        for frame in page.frames:
            try:
                frame_icons = frame.locator("a.af_messages_close-icon, a.af_dialog_close-icon, a.af_panelWindow_close-icon, a[title*='Kapat' i], a[title*='Close' i], [id*='close' i]")
                for fi in range(min(frame_icons.count(), 3)):
                    try:
                        frame_icons.nth(fi).click(force=True, timeout=800)
                        has_popup = True
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                frame_btns = frame.locator("button, a").filter(has_text=re.compile(r"^\s*(Kapat|Tamam)\s*$", re.IGNORECASE))
                for fbi in range(min(frame_btns.count(), 3)):
                    try:
                        frame_btns.nth(fbi).click(force=True, timeout=800)
                        has_popup = True
                    except Exception:
                        try:
                            frame_btns.nth(fbi).dispatch_event("click")
                            has_popup = True
                        except Exception:
                            pass
            except Exception:
                pass

        # 3. Ana sayfadaki bilinen ADF DİKKAT (d6) ve Kapat linkleri
        try:
            d6_close = page.locator("[id*='r1:4:d6'] a, [id*='d6'] a, .af_messages_close-icon, a.af_dialog_close-icon")
            if d6_close.count() > 0 and d6_close.first.is_visible():
                d6_close.first.click(force=True, timeout=800)
                has_popup = True
        except Exception:
            pass

        try:
            main_kapat = page.locator("button, a").filter(has_text=re.compile(r"^\s*(Kapat|Tamam)\s*$", re.IGNORECASE))
            for mi in range(min(main_kapat.count(), 3)):
                if main_kapat.nth(mi).is_visible():
                    try:
                        main_kapat.nth(mi).click(force=True, timeout=800)
                        has_popup = True
                    except Exception:
                        try:
                            main_kapat.nth(mi).dispatch_event("click")
                            has_popup = True
                        except Exception:
                            pass
        except Exception:
            pass

        # 4. Klavyeden Escape tuşu bas
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        # 5. Kontrol: Ekranda hala "Teklif Detay Bilgileri" veya "DİKKAT!" var mı?
        try:
            if page.locator("text=Teklif Detay Bilgileri").is_visible() or page.locator("text=DİKKAT!").is_visible():
                has_popup = True
            elif page.locator("div[role='dialog']:visible, div[class*='af_dialog']:visible, div[class*='af_panelWindow']:visible").count() > 0:
                has_popup = True
        except Exception:
            pass

        if not has_popup and not page.locator(".AFModalGlassPane").is_visible() and not page.locator(".AFBlockingGlassPane").is_visible():
            break
        page.wait_for_timeout(500)

    # Tarifenin sepete ("Ürün Listesi") eklendiğini doğrula
    try:
        page.locator("a[title*='Çıkart'], button[title*='Çıkart'], text=Çıkart, [id*='del']").first.wait_for(state="visible", timeout=15000)
    except Exception:
        pass

    # DOM'da kalıntı glasspane veya wait popup varsa temizle
    page.evaluate("""() => {
        document.querySelectorAll('.AFBlockingGlassPane, .AFModalGlassPane, [id*="WaitPopup"]').forEach(el => {
            el.style.display = 'none';
            if (el.parentNode) el.parentNode.removeChild(el);
        });
        document.querySelectorAll('div[role="dialog"], [id*="::popup-container"]').forEach(el => {
            if (el.innerText && (el.innerText.includes('Teklif Detay') || el.innerText.includes('DİKKAT'))) {
                el.style.display = 'none';
            }
        });
    }""")
    page.wait_for_timeout(500)

    ileri_btn = page.get_by_role("button", name="İleri")
    expect(ileri_btn).to_be_visible(timeout=DEFAULT_TIMEOUT)

    def _is_musteri_tercihleri_reached():
        try:
            if page.get_by_role("heading", name="Müşteri Tercihleri").is_visible():
                return True
            if page.locator("select:has(option:has-text('İzin Verilsin')), select:has(option:has-text('İzin Verilmesin'))").count() > 0:
                return True
            if page.locator("text='Paylaşım ve Bilgilendirme İzinleri'").is_visible():
                return True
        except Exception:
            pass
        return False

    # İleri butonuna basarak "Müşteri Tercihleri" sayfasına geçişi garantiye al
    for _ in range(30):
        if _is_musteri_tercihleri_reached():
            break

        # Glasspane engeli varsa kaldır ve force click yap
        page.evaluate("""() => {
            document.querySelectorAll('.AFBlockingGlassPane, .AFModalGlassPane, [id*="WaitPopup"]').forEach(el => {
                el.style.display = 'none';
                if (el.parentNode) el.parentNode.removeChild(el);
            });
        }""")
        try:
            ileri_btn.click(force=True, timeout=3000)
        except Exception:
            try:
                ileri_btn.dispatch_event("click")
            except Exception:
                pass
        page.wait_for_timeout(1000)

    #Müşteri Tercihleri
    secilen_tercihler = [
        lbl for lbl, aktif in [
            ("2G", GSM), ("3G", WCDMA), ("4.5G", LTE), ("5G", NR),
            ("VoLTE", VoLTE), ("VoWifi", VoWifi)
        ] if aktif
    ]
    report(70, f"Müşteri tercihleri ayarlanıyor ({', '.join(secilen_tercihler) or 'Varsayılan'})...")

    # Müşteri Tercihleri ekranının yüklendiğini bekle
    for _ in range(30):
        if _is_musteri_tercihleri_reached():
            break
        page.wait_for_timeout(500)
    print("Müşteri Tercihleri sayfasına ulaşıldı")
    wait_glasspane()

    # Müşteri Tercihleri ekranındaki tüm izin dropdown'larını (Paylaşım ve Bilgilendirme İzinleri) doldur
    # Seçenekte "İzin Verilsin" / "İzin Verilmesin" barındıran tüm select'leri bul ve Seçiniz olanları ayarla
    try:
        izin_selects = page.locator("select:has(option:has-text('İzin Verilsin')), select:has(option:has-text('İzin Verilmesin'))")
        for iz_idx in range(izin_selects.count()):
            try:
                iz_sel = izin_selects.nth(iz_idx)
                sel_text = iz_sel.evaluate("el => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : ''")
                if not sel_text or "seçiniz" in sel_text.lower():
                    iz_sel.scroll_into_view_if_needed()
                    iz_sel.focus()
                    iz_sel.press("ArrowDown")
                    iz_sel.press("Tab")
                    page.wait_for_timeout(250)
            except Exception:
                pass
    except Exception:
        pass

    # Müşteri Grubu kesinlikle "Normal" olmalıdır (kullanıcının VIP yetkisi yoktur)
    try:
        musteri_grubu = page.locator("select[name*='soc'], select[name*='customerGroup'], select:has(option:has-text('Normal'))")
        if musteri_grubu.count() > 0:
            for mg_idx in range(musteri_grubu.count()):
                try:
                    mg = musteri_grubu.nth(mg_idx)
                    if mg.locator("option:has-text('Normal')").count() > 0:
                        mg.select_option(label="Normal")
                        mg.dispatch_event("change")
                except Exception:
                    pass
    except Exception:
        pass

    expect(page.get_by_role("checkbox", name="5N hizmetlerinden yararlanmak istiyorum")).to_be_enabled(timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(1000)
    if not NR:
        page.get_by_role("checkbox", name="5N hizmetlerinden yararlanmak").click()
        expect(page.get_by_role("checkbox", name="4.5N hizmetlerinden")).to_be_checked(checked=False)
        checkbox_45n = page.get_by_role("checkbox", name="4.5N hizmetlerinden")
        if checkbox_45n.is_checked():
            checkbox_45n.uncheck()

        # Faturasız hatlarda (Pre SIM'ler 3G uyumlu olduğundan) doğrudan 3N seçilir
        if is_faturasiz or (WCDMA and not LTE):
            cb_3n = page.get_by_role("checkbox", name=re.compile(r"3N hizmetlerinden", re.IGNORECASE))
            if cb_3n.count() > 0:
                cb_3n.first.scroll_into_view_if_needed()
                cb_3n.first.check()
            else:
                lbl = page.locator("text=3N hizmetlerinden").first
                lbl.scroll_into_view_if_needed()
                lbl.click()
            page.wait_for_timeout(1000)
            if page.get_by_role("button", name="Tamam").is_visible():
                page.get_by_role("button", name="Tamam").click()
        elif (LTE):
            cb_45n = page.get_by_role("checkbox", name=re.compile(r"4\.5N hizmetlerinden", re.IGNORECASE))
            if cb_45n.count() > 0:
                cb_45n.first.scroll_into_view_if_needed()
                cb_45n.first.check()
            else:
                lbl = page.locator("text=4.5N hizmetlerinden").first
                lbl.scroll_into_view_if_needed()
                lbl.click()
            page.wait_for_timeout(1000)
            if page.get_by_role("button", name="Tamam").is_visible():
                page.get_by_role("button", name="Tamam").click()
            page.wait_for_timeout(1000)
            if page.locator("text=4.5G uyumlu değildir").is_visible() or page.locator("text=2G veya 3G").is_visible():
                if page.get_by_role("button", name="Tamam").is_visible():
                    page.get_by_role("button", name="Tamam").click()
                page.wait_for_timeout(500)
                cb_3n = page.get_by_role("checkbox", name=re.compile(r"3N hizmetlerinden", re.IGNORECASE))
                if cb_3n.count() > 0:
                    cb_3n.first.scroll_into_view_if_needed()
                    cb_3n.first.check()
                else:
                    lbl = page.locator("text=3N hizmetlerinden").first
                    lbl.scroll_into_view_if_needed()
                    lbl.click()
                if page.get_by_role("button", name="Tamam").is_visible():
                    page.get_by_role("button", name="Tamam").click()
        elif (GSM):
            cb_2n = page.get_by_role("checkbox", name=re.compile(r"Sadece 2N", re.IGNORECASE))
            if cb_2n.count() > 0:
                cb_2n.first.scroll_into_view_if_needed()
                cb_2n.first.check()
            else:
                lbl = page.locator("text=Sadece 2N").first
                lbl.scroll_into_view_if_needed()
                lbl.click()
            if page.get_by_role("button", name="Tamam").is_visible():
                page.get_by_role("button", name="Tamam").click()
    else:
        checkbox_5n = page.get_by_role("checkbox", name="5N hizmetlerinden yararlanmak istiyorum")
        if not checkbox_5n.is_checked():
            checkbox_5n.check()
            if page.get_by_role("button", name="Tamam").is_visible():
                page.get_by_role("button", name="Tamam").press("Enter")

    volte_cb = page.get_by_role("checkbox", name="HD+ Görüsme Teknolojisi (Volte) Hizmetleri")
    if VoLTE and not NR:
        if volte_cb.is_enabled() and not volte_cb.is_checked():
            volte_cb.check()
    elif not VoLTE:
        if volte_cb.is_enabled() and volte_cb.is_checked():
            volte_cb.uncheck()

    vowifi_cb = page.get_by_role("checkbox", name="Wifi Arama Tercihi")
    if VoWifi:
        if vowifi_cb.is_enabled() and not vowifi_cb.is_checked():
            vowifi_cb.check()
    elif vowifi_cb.is_enabled() and vowifi_cb.is_checked():
        vowifi_cb.uncheck()

    # İleriye basmadan önce tüm izin dropdown'larını bir kez daha teyit et
    try:
        izin_selects_final = page.locator("select:has(option:has-text('İzin Verilsin')), select:has(option:has-text('İzin Verilmesin'))")
        for iz_idx in range(izin_selects_final.count()):
            try:
                iz_s = izin_selects_final.nth(iz_idx)
                txt = iz_s.evaluate("el => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : ''")
                if not txt or "seçiniz" in txt.lower():
                    iz_s.scroll_into_view_if_needed()
                    iz_s.focus()
                    iz_s.press("ArrowDown")
                    iz_s.press("Tab")
                    page.wait_for_timeout(200)
            except Exception:
                pass
    except Exception:
        pass
    page.wait_for_timeout(500)

    report(75, "Müşteri ve Fatura Tercihleri onaylanıyor...")
    wait_glasspane()
    ileri_btn_tercih = page.get_by_role("button", name="İleri")
    if ileri_btn_tercih.is_visible():
        ileri_btn_tercih.click(force=True)
    page.wait_for_timeout(1000)

    def click_any_visible_tamam():
        # 1. Doğrudan d1::msgDlg ve af:dialog butonlarına Playwright ile tıkla
        try:
            msg_btn = page.locator("[id*='msgDlg::cancel'], [id*='msgDlg::_afrOk'], [id*='msgDlg'] button, [id*='msgDlg'] a")
            if msg_btn.count() > 0:
                for mi in range(msg_btn.count()):
                    if msg_btn.nth(mi).is_visible():
                        msg_btn.nth(mi).click(force=True, timeout=1500)
                        page.wait_for_timeout(500)
                        return True
        except Exception:
            pass

        # 2. get_by_role("button", name="Tamam")
        try:
            t_btns = page.get_by_role("button", name="Tamam")
            for ti in range(t_btns.count()):
                if t_btns.nth(ti).is_visible():
                    t_btns.nth(ti).click(force=True, timeout=1500)
                    page.wait_for_timeout(500)
                    return True
        except Exception:
            pass

        # 3. Doğrudan JavaScript ile textContent veya value 'Tamam' olan elemanı tıkla
        try:
            clicked = page.evaluate("""() => {
                const dlgBtn = document.getElementById('d1::msgDlg::cancel') ||
                               document.querySelector("[id*='msgDlg'] button, [id*='msgDlg'] a, [id*='msgDlg'] input");
                if (dlgBtn) {
                    dlgBtn.click();
                    return true;
                }
                const candidates = Array.from(document.querySelectorAll("button, input, a, td, span, div[role='button']"));
                for (const el of candidates) {
                    const txt = (el.textContent || el.value || el.innerText || '').trim().toLowerCase();
                    if (txt === 'tamam') {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            el.click();
                            return true;
                        }
                    }
                }
                const closeIcons = document.querySelectorAll("a.af_messages_close-icon, a.af_dialog_close-icon, a.af_panelWindow_close-icon, a[title*='Kapat']");
                for (const ci of closeIcons) {
                    const r = ci.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        ci.click();
                        return true;
                    }
                }
                return false;
            }""")
            if clicked:
                page.wait_for_timeout(500)
                return True
        except Exception:
            pass

        # 4. Enter / Escape tuşu gönder
        try:
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
        except Exception:
            pass
        return False

    # Sipariş / İşlem Özeti ekranına ulaşana kadar ilerle (Fatura Tercihleri ve Uyarı pencerelerini geç)
    for _ in range(50):
        # 1. Hedef ekrana varıldı mı?
        if page.get_by_role("button", name="Sözleşme Özeti Gönder").is_visible():
            break
        if page.locator("td").filter(has_text=re.compile(r"(İşlem|Sipariş)\s*Özeti", re.IGNORECASE)).count() > 0:
            if page.locator("td").filter(has_text=re.compile(r"(İşlem|Sipariş)\s*Özeti", re.IGNORECASE)).first.is_visible():
                break

        # Çıkış onay penceresi yanlışlıkla açıldıysa Hayır'a bas
        try:
            hayir_btn = page.get_by_role("button", name="Hayır")
            if hayir_btn.count() > 0 and hayir_btn.first.is_visible():
                hayir_btn.first.click()
                page.wait_for_timeout(300)
        except Exception:
            pass

        # 2N/3N uyarısı çıkarsa 3N seç
        try:
            if page.locator("text=2N/3N/4.5N servislerinden birini seçmeniz gerekmektedir").is_visible():
                click_any_visible_tamam()
                cb_3n = page.locator("input[type='checkbox']").filter(has=page.locator("xpath=..//label[contains(.,'3N')]"))
                if cb_3n.count() == 0:
                    cb_3n = page.get_by_role("checkbox", name=re.compile(r"3N hizmetlerinden", re.IGNORECASE))
                if cb_3n.count() > 0:
                    cb_3n.first.scroll_into_view_if_needed()
                    cb_3n.first.check()
                else:
                    lbl = page.locator("text=3N hizmetlerinden").first
                    lbl.scroll_into_view_if_needed()
                    lbl.click()
                page.wait_for_timeout(1000)
                click_any_visible_tamam()
        except Exception:
            pass

        # İzin uyarısı çıkarsa kapat ve boş kalan izinleri seç
        try:
            if page.locator("text=Lütfen izinlerinizi tekrar kontrol ediniz").is_visible() or page.locator("text=IVIT").is_visible() or page.locator("text=TT Mobil Veri İşleme İzni").is_visible():
                click_any_visible_tamam()
                iz_loop = page.locator("select:has(option:has-text('İzin Verilsin')), select:has(option:has-text('İzin Verilmesin'))")
                for iz_i in range(iz_loop.count()):
                    try:
                        s_el = iz_loop.nth(iz_i)
                        s_txt = s_el.evaluate("el => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : ''")
                        if not s_txt or "seçiniz" in s_txt.lower():
                            s_el.scroll_into_view_if_needed()
                            s_el.focus()
                            s_el.press("ArrowDown")
                            s_el.press("Tab")
                            page.wait_for_timeout(200)
                    except Exception:
                        pass
                page.wait_for_timeout(500)
        except Exception:
            pass

        # Uyarı / Mesaj popup'ı varsa ("Mobil ödeme...", "E-fatura..." vb.) Tamam'a tıkla ve bekle
        if page.locator("[id*='msgDlg']:visible, div[role='dialog']:has-text('Tamam'):visible").count() > 0:
            click_any_visible_tamam()
            page.wait_for_timeout(1000)
            continue

        # Kapat iconu / butonu varsa
        try:
            kapat_icon = page.locator("div[role='dialog'] a[title='Kapat'], div[class*='af_dialog'] a[title='Kapat'], div[class*='af_panelWindow'] a[title='Kapat'], a.af_messages_close-icon")
            for ki in range(kapat_icon.count()):
                if kapat_icon.nth(ki).is_visible():
                    kapat_icon.nth(ki).click(force=True, timeout=1500)
                    page.wait_for_timeout(300)
        except Exception:
            pass

        # Fatura Tercihleri veya diğer adımlarda "İleri" butonuna bas
        try:
            clicked_ileri = page.evaluate("""() => {
                const candidates = Array.from(document.querySelectorAll("button, input[type='button'], a, [role='button']"));
                for (const el of candidates) {
                    const txt = (el.innerText || el.value || '').trim();
                    if (txt === 'İleri' || txt === 'Ileri') {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            if not clicked_ileri:
                ilr_btns = page.get_by_role("button", name="İleri")
                for ib in range(ilr_btns.count()):
                    if ilr_btns.nth(ib).is_visible():
                        ilr_btns.nth(ib).click(force=True, timeout=2000)
                        break
        except Exception:
            pass

        page.wait_for_timeout(1500)

    expect(page.get_by_role("button", name="Sözleşme Özeti Gönder")).to_be_visible(timeout=DEFAULT_TIMEOUT)
    report(85, "Sözleşme özeti gönderiliyor...")
    wait_glasspane()
    page.get_by_role("button", name="Sözleşme Özeti Gönder").click()
    sozlesme_frame = page.locator("iframe[title=\"İçerik\"]").content_frame
    expect(sozlesme_frame.get_by_text("Gsm No", exact=True)).to_be_visible(timeout=DEFAULT_TIMEOUT)
    gsm_select = sozlesme_frame.get_by_label("Gsm No", exact=True)
    gsm_select.focus()
    gsm_select.press("ArrowDown")
    gsm_select.press("Tab")
    page.wait_for_timeout(1500)
    gonder_btn = sozlesme_frame.get_by_role("button", name="Sözleşme Özeti Gönder")
    if gonder_btn.is_disabled():
        gsm_select.select_option("0")
        gsm_select.dispatch_event("change")
        gsm_select.press("Tab")
        page.wait_for_timeout(1500)
    expect(gonder_btn).to_be_enabled(timeout=DEFAULT_TIMEOUT)
    gonder_btn.click()
    expect(page.locator("td").filter(has_text=re.compile(r"Sözleşme\s*özetinin\s*görüntü", re.IGNORECASE)).first).to_be_visible(timeout=DEFAULT_TIMEOUT)
    try:
        page.get_by_role("link", name="Kapat").click(timeout=3000)
    except Exception:
        page.get_by_role("button", name="Kapat").click(timeout=3000)
    wait_glasspane()
    page.get_by_role("button", name="Aktivasyona Devam Et").click()
    expect(page.locator("td").filter(has_text=re.compile(r"Bilgi\s*Aktivasyon", re.IGNORECASE)).first).to_be_visible(timeout=DEFAULT_TIMEOUT)
    wait_glasspane()
    page.get_by_role("button", name="Tamam").click()
    page.get_by_text("Kimlik Doğrulama Yapılmasın").click()
    page.get_by_role("radio", name="Kimlik Doğrulama Yapılmasın").check()
    report(92, "Sözleşme çıktısı alınıyor...")
    wait_glasspane()
    with page.expect_popup() as page1_info:
        page.get_by_role("button", name="Çıktı Al").click()
    page1 = page1_info.value
    try:
        page1.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(2000)
    if not page.get_by_role("button", name="Tamam").is_visible():
        current_popup_url = page1.url or ""
        if "printOverYn=" not in current_popup_url:
            if "reportservlet?" in current_popup_url:
                target_url = current_popup_url + "&printOverYn=false"
            else:
                target_url = f"http://10.248.67.23:8001/MTS/reportservlet?showPrintDialog=true&rand={int(time.time() * 1000)}&printOverYn=false"
            try:
                page1.goto(target_url, wait_until="commit", timeout=10000)
            except Exception:
                pass
    for _ in range(30):
        if page.get_by_role("button", name="Tamam").is_visible():
            break
        page.wait_for_timeout(500)
    try:
        page1.close()
    except Exception:
        pass
    expect(page.get_by_role("button", name="Tamam")).to_be_visible(timeout=DEFAULT_TIMEOUT)
    wait_glasspane()
    page.get_by_role("button", name="Tamam").click()
    page.wait_for_timeout(1000)

    # ---------------------
    context.close()
    browser.close()
    report(100, "Aktivasyon tamamlandı.")
    return 'OK'

if __name__ == "__main__":
    main()
