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
from datetime import datetime, timedelta
import json
import os
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)
from core import MernsDB
from core import ICCID as ICCID_Func
from core import CMPDB as OTP
from core import config

DEFAULT_TIMEOUT = 150000  # 150 saniye (2.5 dk - yavaş Opera geçişleri için)


def main():
    with sync_playwright() as playwright:
        Merns = MernsDB.get_Merns()
        iccid_list = []
        try:
            cache_path = os.path.join(config.DATA_DIR, "iccid_cache.json")
            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                iccid_list = [
                    str(x.get("iccid")).strip()
                    for x in data
                    if x.get("status") == "clean" and str(x.get("iccid", "")).strip()
                ]
        except Exception:
            pass

        if not iccid_list:
            data = ICCID_Func.get_ICCID(playwright)
            iccid_list = [str(item.get("ICCID", "")).strip() for item in data if item.get("ICCID")]

        for data_iccid in iccid_list:
            sonuc = run(playwright, Merns["TCKN"], Merns["DOĞUM TARİHİ"], data_iccid)
            if sonuc != 'ICCID_IN_USE':
                return
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
            with open(os.path.join(config.DATA_DIR, "iccid_cache.json"), "r", encoding="utf-8") as f:
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

        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        # Tarayıcı yazdırma penceresinin (window.print) otomasyonu bloklamasını engelle
        context.add_init_script("window.print = function() {};")
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)  # Yavaş ADF istekleri için 150 saniye default timeout
        page.set_default_navigation_timeout(DEFAULT_TIMEOUT)
        if callable(opts.get("on_page_ready")):
            opts["on_page_ready"](page)

        def capture_error_screenshot():
            if callable(opts.get("is_stopped")) and opts["is_stopped"]():
                return None
            try:
                shots_dir = os.path.join(config.BUNDLE_DIR, "static", "screenshots")
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
            return _execute_opera_flow(page, context, browser, TCKN, DT, ICCID, MSISDN, GSM, WCDMA, LTE, NR, VoLTE, VoWifi, report, capture_error_screenshot, HAT_TIPI, opts)
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


def _execute_opera_flow(page, context, browser, TCKN, DT, ICCID, MSISDN, GSM, WCDMA, LTE, NR, VoLTE, VoWifi, report, capture_error_screenshot, HAT_TIPI="Faturalı Hat", options=None):
    def wait_glasspane(timeout=120000):
        try:
            glass = page.locator(".AFBlockingGlassPane, .AFModalGlassPane")
            if glass.count() > 0 and glass.first.is_visible():
                glass.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass

    opera_url = config.URLS.get('opera', "http://10.248.67.23:8001/MTS/faces/index")
    page.goto(opera_url)

    # Opera kullanıcısı seçimi (61044774 veya CC51 vb.)
    opts = options or {}
    selected_user_key = opts.get('opera_user')
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
        try:
            tamam_m = page.get_by_role("button", name="Tamam")
            if tamam_m.count() > 0 and tamam_m.first.is_visible():
                tamam_m.first.click(timeout=2000)
        except Exception:
            pass

        wait_glasspane(timeout=10000)
        dt_box = page.get_by_role("textbox", name="Doğum Tarihi")
        dt_box.click()
        dt_box.fill(DT)
        dt_box.press("Tab")
        try:
            # ADF Doğum Tarihi'ni dd.mm.yyyy formatına çevirene kadar dinamik bekle
            expect(dt_box).to_have_value(re.compile(r"\d{2}\.\d{2}\.\d{4}"), timeout=5000)
        except Exception:
            pass
        wait_glasspane(timeout=10000)

        tckn_box = page.get_by_role("textbox", name="TC Kimlik Numarası")
        tckn_box.click()
        tckn_box.fill(TCKN)
        tckn_box.press("Tab")
        try:
            expect(tckn_box).to_have_value(TCKN, timeout=5000)
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        wait_glasspane(timeout=10000)

        mernis_btn = page.get_by_role("button", name="Mernis Sorgulama")
        found = False
        if mernis_btn.count() > 0 and mernis_btn.is_visible():
            for _m_click in range(3):
                try:
                    expect(mernis_btn).to_be_enabled(timeout=5000)
                    mernis_btn.click()
                    wait_glasspane(timeout=30000)
                except Exception:
                    pass

                # Adı doldu mu yoksa Tamam uyarısı mı çıktı dinamik kontrol et
                try:
                    expect(name_box).not_to_have_value("", timeout=6000)
                    found = True
                    break
                except Exception:
                    pass

                try:
                    tamam_after = page.get_by_role("button", name="Tamam")
                    if tamam_after.count() > 0 and tamam_after.first.is_visible():
                        tamam_after.first.click(timeout=2000)
                        expect(tamam_after.first).to_be_hidden(timeout=5000)
                        tckn_box.click()
                        tckn_box.press("Tab")
                        page.wait_for_load_state("networkidle", timeout=3000)
                        wait_glasspane(timeout=10000)
                        continue
                except Exception:
                    pass

        if not found:
            try:
                expect(name_box).not_to_have_value("", timeout=12000)
                found = True
            except Exception:
                pass

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

    # Kimlik Türü seçimi (soc7): Kesinlikle TC ÇİPLİ KİMLİK KARTI (value='0')
    wait_glasspane()
    def _get_soc7():
        loc = page.locator("select[name*='soc7']")
        return loc.first if loc.count() > 0 else page.locator("select[name=\"pt1:r1:1:r1:2:soc7\"]")

    try:
        id2_loc = page.locator("input[id*='id2::content']").first
        if not (id2_loc.count() > 0 and id2_loc.is_visible()):
            ks = _get_soc7()
            ks.focus()
            ks.click()
            # Boş değerden doğrudan 0'a geçiş ADF PPR tetiklemezse önce value='1' üzerinden PPR tetikle
            ks.select_option(value="1")
            ks.dispatch_event("change")
            ks.press("Tab")
            wait_glasspane()
            try:
                expect(id2_loc).to_be_visible(timeout=5000)
            except Exception:
                pass

        ks = _get_soc7()
        ks.focus()
        ks.click()
        try:
            ks.select_option(label="TC ÇİPLİ KİMLİK KARTI")
        except Exception:
            ks.select_option(value="0")
        ks.dispatch_event("change")
        ks.press("Tab")
        wait_glasspane()
        if id2_loc.count() > 0:
            expect(id2_loc).to_be_visible(timeout=5000)
    except Exception as e:
        print(f"[KİMLİK TÜRÜ SEÇİM UYARI] {e}", flush=True)

# Seri numarası, Geçerlilik Tarihi ve Kimlik Kayıt No girişi (Opera yeni güncellemesinde zorunlu alanlar)
    STATIK_SERI_NO = "K35B28574"
    gecerlilik_tarihi_str = (datetime.now() + timedelta(days=365)).strftime("%d.%m.%Y")
    try:
        page.evaluate("""(data) => {
            document.querySelectorAll("input:not([disabled])").forEach(inp => {
                if (inp.offsetParent === null) return;
                const row = inp.closest('tr');
                const txt = row ? row.innerText.toLowerCase() : '';
                // Seri Numarası: Sabit K35B28574
                if (txt.includes('seri numarası') || inp.id.includes('it3') || inp.id.includes('it22') || inp.id.includes('it6')) {
                    inp.value = data.seriNo;
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                }
                // Geçerlilik Tarihi: Bugünden 1 sene sonrası
                if (txt.includes('geçerlilik tarihi') || (inp.placeholder === 'dd.mm.yyyy' && !txt.includes('doğum') && !txt.includes('vekalet'))) {
                    inp.value = data.gecerlilik;
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                }
                // Kimlik Kayıt Numarası (sadece görünürse)
                if (txt.includes('kimlik kayıt') || inp.id.includes('it7')) {
                    inp.value = '123456';
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        }""", {'seriNo': STATIK_SERI_NO, 'gecerlilik': gecerlilik_tarihi_str})
    except Exception:
        pass

    try:
        seri_no = page.get_by_role("textbox", name=re.compile(r"Seri Numarası", re.I))
        if seri_no.count() > 0 and seri_no.first.is_visible():
            seri_no.first.click()
            seri_no.first.fill(STATIK_SERI_NO)
    except Exception:
        pass

    try:
        gec_tarih = page.get_by_role("textbox", name=re.compile(r"Geçerlilik Tarihi", re.I))
        if gec_tarih.count() > 0 and gec_tarih.first.is_visible():
            gec_tarih.first.click()
            gec_tarih.first.fill(gecerlilik_tarihi_str)
            gec_tarih.first.press("Tab")
    except Exception:
        pass

    try:
        kayit_no = page.get_by_role("textbox", name=re.compile(r"Kimlik Kayıt", re.I))
        if kayit_no.count() > 0 and kayit_no.first.is_visible():
            kayit_no.first.click()
            kayit_no.first.fill("123456")
    except Exception:
        pass

    # İl, İlçe, Semt seçimi (ADANA -> ALADAĞ(KARSANTI) -> AKÖREN)
    try:
        il_inp = page.locator("input[id*='addrCityName1Id::content']").first
        ilce_inp = page.locator("input[id*='addrSubPrvncName1Id::content']").first
        semt_inp = page.locator("input[id*='addrDstrctName1Id::content']").first

        il_inp.scroll_into_view_if_needed()
        if (il_inp.input_value() or "").strip() != "ADANA":
            il_inp.click()
            il_inp.fill("ADANA")
            il_inp.press("Tab")
            expect(il_inp).to_have_value("ADANA", timeout=DEFAULT_TIMEOUT)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            wait_glasspane()

        expect(ilce_inp).to_be_enabled(timeout=DEFAULT_TIMEOUT)
        for _ilce_try in range(2):
            ilce_inp.click()
            ilce_inp.fill("ALADAĞ(KARSANTI)")
            ilce_inp.press("Tab")
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            wait_glasspane()
            try:
                expect(semt_inp).to_be_enabled(timeout=5000)
                expect(ilce_inp).to_have_value("ALADAĞ(KARSANTI)", timeout=3000)
                break
            except Exception:
                pass

        expect(semt_inp).to_be_enabled(timeout=DEFAULT_TIMEOUT)
        semt_inp.click()
        semt_inp.fill("AKÖREN")
        semt_inp.press("Tab")
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        expect(semt_inp).to_have_value("AKÖREN", timeout=DEFAULT_TIMEOUT)
        wait_glasspane()
        print("[ADRES] İl/İlçe/Semt seçimi tamamlandı.", flush=True)
    except Exception as e:
        print(f"[ADRES SEÇİM HATA] {e}", flush=True)

    # Adres, Bina No ve İrtibat Telefonu alanlarını doldur
    try:
        adres_box = page.get_by_role("textbox", name="Adres")
        if adres_box.count() > 0 and adres_box.first.is_visible():
            adres_box.first.fill("AAA")
        else:
            page.locator("textarea[id*='it30'], [id*='it30']").first.fill("AAA")
    except Exception:
        pass

    try:
        bina_box = page.get_by_role("textbox", name="Bina/Kapı Numarası")
        if bina_box.count() > 0 and bina_box.first.is_visible():
            bina_box.first.fill("123")
        else:
            page.locator("input[id*='it31']").first.fill("123")
    except Exception:
        pass

    try:
        tel_box = page.locator("input[id*='mt1123'], input[name*='mt1123']").first
        if tel_box.count() > 0 and tel_box.is_visible():
            tel_box.click()
            tel_box.fill("5333333333")
            tel_box.dispatch_event("input")
            tel_box.dispatch_event("change")
            tel_box.press("Tab")
        else:
            page.get_by_role("textbox", name=re.compile(r"İrtibat Telefon Numarası 1", re.I)).first.fill("5333333333")
    except Exception:
        pass

    # "Hat Tipi ve Numara Seçimi" ekranına geçiş (OTP ve doğrulama pencerelerini hızlıca aş)
    report(30, "Hat Tipi ve Numara Seçimi ekranına geçiliyor...")
    for ileri_att in range(15):
        if (
            page.get_by_role("radio", name="Faturalı Hat").is_visible()
            or page.get_by_role("radio", name="Faturasız Hat").is_visible()
            or page.get_by_text("Lütfen hat tipini").is_visible()
        ):
            break

        # OTP dialog veya ADF hata modalı varsa Tamam'a bas
        dlg = page.locator("div[role='dialog']:visible, .af_dialog:visible, [id*='msgDlg']:visible")
        if dlg.count() > 0:
            tamam_btn = page.locator("button, a, div[role='button']").filter(has_text=re.compile(r"^\s*Tamam\s*$", re.I))
            if tamam_btn.count() > 0 and tamam_btn.first.is_visible():
                tamam_btn.first.click(force=True)
                page.wait_for_timeout(400)

        # Glasspane engellerini temizle
        page.evaluate("""() => {
            document.querySelectorAll('.AFBlockingGlassPane, .AFModalGlassPane, [id*="WaitPopup"]').forEach(el => {
                el.style.display = 'none';
                if (el.parentNode) el.parentNode.removeChild(el);
            });
        }""")

        # Sadece Yeni Müşteri ekranının İleri butonuna bas (Hat Tipi ekranına geçtiysek basma)
        if page.get_by_text("Lütfen hat tipini").is_visible():
            break

        ileri_btn = page.locator("button[id*='cb23'], button:has-text('İleri')").first
        if ileri_btn.is_visible():
            ileri_btn.click(force=True)
            wait_glasspane()
            try:
                expect(page.get_by_role("radio", name=HAT_TIPI, exact=True)).to_be_visible(timeout=4000)
                break
            except Exception:
                pass

    expect(page.get_by_role("radio", name=HAT_TIPI, exact=True)).to_be_visible(timeout=DEFAULT_TIMEOUT)

        #Hat Tipi ve Numara Seçimi
    report(40, f"{HAT_TIPI} seçiliyor, MSISDN: {MSISDN}")

    radio_btn = page.get_by_role("radio", name=HAT_TIPI, exact=True)
    radio_btn.check()
    expect(radio_btn).to_be_checked(timeout=DEFAULT_TIMEOUT)
    wait_glasspane()
    expect(page.get_by_text("Fiziksel SIM ile ilerlemek")).to_be_visible(timeout=DEFAULT_TIMEOUT)

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
    wait_glasspane()
    ileri_hat_btn = page.get_by_role("button", name="İleri")
    expect(ileri_hat_btn).to_be_enabled(timeout=DEFAULT_TIMEOUT)
    ileri_hat_btn.click()


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

    # Katalog combobox'ının seçeneklerinin yüklenmesini akıllı expect ile bekle (en az 2 seçenek)
    katalog_cb = page.get_by_role("combobox")
    expect(katalog_cb).to_be_enabled(timeout=DEFAULT_TIMEOUT)
    expect(katalog_cb.locator("option").nth(1)).to_be_attached(timeout=DEFAULT_TIMEOUT)

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
            wait_glasspane()

            ara_btn = page.get_by_role("button", name="Ara", exact=True)
            expect(ara_btn).to_be_enabled(timeout=DEFAULT_TIMEOUT)
            ara_btn.click()
            wait_glasspane()

            # Tarife tablosunda hedef satır veya Ekle linki geldi mi akıllı expect ile bekle
            target_row = (
                page.locator("tr").filter(has_text=re.compile(r"KRAL TAR[Iİ]FE", re.IGNORECASE)).first
                if is_faturasiz
                else page.get_by_role("link", name="Ekle").first
            )
            expect(target_row).to_be_visible(timeout=5000)
            break
        except Exception:
            wait_glasspane()

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
                wait_glasspane()
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

    wait_glasspane()
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

    musteri_tercih_target = page.locator("select:has(option:has-text('İzin Verilsin')), select:has(option:has-text('İzin Verilmesin'))").first.or_(page.get_by_role("heading", name="Müşteri Tercihleri"))

    # İleri butonuna basarak "Müşteri Tercihleri" sayfasına geçişi akıllı expect ile garantiye al
    for _ in range(15):
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
        wait_glasspane()
        try:
            expect(musteri_tercih_target).to_be_visible(timeout=5000)
            break
        except Exception:
            pass

    #Müşteri Tercihleri
    secilen_tercihler = [
        lbl for lbl, aktif in [
            ("2G", GSM), ("3G", WCDMA), ("4.5G", LTE), ("5G", NR),
            ("VoLTE", VoLTE), ("VoWifi", VoWifi)
        ] if aktif
    ]
    report(70, f"Müşteri tercihleri ayarlanıyor ({', '.join(secilen_tercihler) or 'Varsayılan'})...")

    # Müşteri Tercihleri ekranının yüklendiğini akıllı expect ile bekle
    expect(musteri_tercih_target).to_be_visible(timeout=DEFAULT_TIMEOUT)
    print("Müşteri Tercihleri sayfasına ulaşıldı")
    wait_glasspane()

    # Müşteri Tercihleri ekranındaki tüm izin dropdown'larını (Paylaşım ve Bilgilendirme İzinleri) "İzin Verilsin" olarak doldur
    def _fill_all_permissions_allowed():
        try:
            izin_selects = page.locator("select:has(option:has-text('İzin Verilsin'))")
            for iz_idx in range(izin_selects.count()):
                try:
                    iz_sel = izin_selects.nth(iz_idx)
                    if not iz_sel.is_visible():
                        continue
                    cur_val = iz_sel.evaluate("el => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text.trim() : ''")
                    if cur_val != "İzin Verilsin":
                        iz_sel.scroll_into_view_if_needed(timeout=2000)
                        try:
                            iz_sel.select_option(label="İzin Verilsin", timeout=1500)
                        except Exception:
                            iz_sel.evaluate("""el => {
                                for (let idx = 0; idx < el.options.length; idx++) {
                                    if (el.options[idx].text.includes('İzin Verilsin')) {
                                        el.selectedIndex = idx;
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                        break;
                                    }
                                }
                            }""")
                        iz_sel.dispatch_event("change")
                        page.wait_for_timeout(100)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            page.evaluate("""() => {
                document.querySelectorAll("select").forEach(sel => {
                    for (let idx = 0; idx < sel.options.length; idx++) {
                        if (sel.options[idx].text.trim().includes('İzin Verilsin')) {
                            if (sel.selectedIndex !== idx) {
                                sel.selectedIndex = idx;
                                sel.dispatchEvent(new Event('change', { bubbles: true }));
                                sel.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                            break;
                        }
                    }
                });
            }""")
        except Exception:
            pass

    _fill_all_permissions_allowed()
    print("[Müşteri Tercihleri] İzinler ayarlandı", flush=True)

    # Müşteri Grubu kesinlikle "Normal" olmalıdır (kullanıcının VIP yetkisi yoktur)
    try:
        musteri_grubu = page.locator("select:has(option:has-text('Normal'))")
        if musteri_grubu.count() > 0:
            for mg_idx in range(musteri_grubu.count()):
                try:
                    mg = musteri_grubu.nth(mg_idx)
                    if mg.is_visible():
                        mg.select_option(label="Normal", timeout=2000)
                        mg.dispatch_event("change")
                except Exception:
                    pass
    except Exception:
        pass
    print("[Müşteri Tercihleri] Müşteri grubu ayarlandı", flush=True)

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
    _fill_all_permissions_allowed()
    page.wait_for_timeout(500)

    report(75, "Müşteri ve Fatura Tercihleri onaylanıyor...")
    wait_glasspane()
    ileri_btn_tercih = page.get_by_role("button", name="İleri")
    if ileri_btn_tercih.is_visible():
        ileri_btn_tercih.click(force=True)
    page.wait_for_timeout(1000)

    def click_any_visible_tamam():
        # 1. Playwright ile 'Tamam' butonları
        try:
            tamam_btns = page.locator("button, a, div[role='button']").filter(has_text=re.compile(r"^\s*Tamam\s*$", re.I))
            for ti in range(tamam_btns.count()):
                if tamam_btns.nth(ti).is_visible():
                    tamam_btns.nth(ti).click(force=True, timeout=1000)
                    page.wait_for_timeout(400)
                    return True
        except Exception:
            pass

        # 2. msgDlg ve dialog cancel/ok butonları
        try:
            msg_btn = page.locator("[id*='msgDlg::cancel'], [id*='msgDlg::_afrOk'], [id*='msgDlg'] button, [id*='msgDlg'] a")
            if msg_btn.count() > 0:
                for mi in range(msg_btn.count()):
                    if msg_btn.nth(mi).is_visible():
                        msg_btn.nth(mi).click(force=True, timeout=1000)
                        page.wait_for_timeout(400)
                        return True
        except Exception:
            pass

        # 3. Kapat (x) butonları
        try:
            close_icons = page.locator(".af_dialog_close-icon, a[title='Kapat'], .af_messages_close-icon, a.af_panelWindow_close-icon")
            for ci in range(close_icons.count()):
                if close_icons.nth(ci).is_visible():
                    close_icons.nth(ci).click(force=True, timeout=1000)
                    page.wait_for_timeout(400)
                    return True
        except Exception:
            pass

        # 4. Doğrudan DOM üzerinden click
        try:
            clicked = page.evaluate("""() => {
                const els = Array.from(document.querySelectorAll("button, a, input, div[role='button'], span"));
                for (const el of els) {
                    const txt = (el.innerText || el.value || el.textContent || '').trim().toLowerCase();
                    if (txt === 'tamam') {
                        el.click();
                        el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        return true;
                    }
                }
                const closeX = document.querySelector(".af_dialog_close-icon, a[title*='Kapat' i], .af_messages_close-icon");
                if (closeX) {
                    closeX.click();
                    return true;
                }
                return false;
            }""")
            if clicked:
                page.wait_for_timeout(400)
                return True
        except Exception:
            pass

        # 5. Klavye tuşları
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            page.keyboard.press("Enter")
            page.wait_for_timeout(200)
        except Exception:
            pass
        return False

    # Sipariş / İşlem Özeti ekranına ulaşana kadar ilerle (Fatura Tercihleri ve Uyarı pencerelerini geç)
    for _ in range(50):
        # 1. Hedef ekrana varıldı mı? (Not: Üst train barındaki "Sipariş Özeti" td'si her sayfada
        # görünür olduğu için asıl gösterge "Sözleşme Özeti Gönder" butonudur.)
        if page.get_by_role("button", name="Sözleşme Özeti Gönder").is_visible():
            print("[FATURA/TERCİH] Sipariş Özeti ekranına ulaşıldı.", flush=True)
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

        # İzin uyarısı çıkarsa kapat ve tüm izinleri 'İzin Verilsin' olarak ayarla
        try:
            if page.locator("text=Lütfen izinlerinizi tekrar kontrol ediniz").is_visible() or page.locator("text=IVIT").is_visible() or page.locator("text=TT Mobil Veri İşleme İzni").is_visible():
                click_any_visible_tamam()
                _fill_all_permissions_allowed()
                page.wait_for_timeout(500)
        except Exception:
            pass

        # Uyarı / Mesaj popup'ı varsa ("Mobil ödeme...", "E-fatura..." vb.) önce Tamam'a basıp kapanmasını bekle
        tamam_vis = False
        try:
            t_loc = page.locator("button, a, div[role='button']").filter(has_text=re.compile(r"^\s*Tamam\s*$", re.I))
            for ti in range(t_loc.count()):
                if t_loc.nth(ti).is_visible():
                    tamam_vis = True
                    break
        except Exception:
            pass
        if tamam_vis or page.locator("[id*='msgDlg']:visible, div[role='dialog']:has-text('Tamam'):visible, .af_dialog:visible, .af_panelWindow:visible").count() > 0:
            print("[FATURA/TERCİH] Uyarı popup'ı kapatılıyor (Tamam)...", flush=True)
            click_any_visible_tamam()
            page.wait_for_timeout(800)
            wait_glasspane()

        # Kapat iconu / butonu varsa
        try:
            kapat_icon = page.locator("div[role='dialog'] a[title='Kapat'], div[class*='af_dialog'] a[title='Kapat'], div[class*='af_panelWindow'] a[title='Kapat'], a.af_messages_close-icon")
            for ki in range(kapat_icon.count()):
                if kapat_icon.nth(ki).is_visible():
                    kapat_icon.nth(ki).click(force=True, timeout=1000)
                    page.wait_for_timeout(300)
        except Exception:
            pass

        # Hâlâ Tamam butonu görünürse: sadece Fatura Tercihleri uyarı popup'ı ("Mobil ödeme..." / "e-fatura...")
        # değilse İleri'ye basmadan bir sonraki turda kapatmayı dene
        is_fatura_uyari = False
        try:
            is_fatura_uyari = (
                page.locator("text=Mobil ödeme tercihini seçmediniz").is_visible()
                or page.locator("text=e-fatura talimatı vermeyi öneriniz").is_visible()
            )
        except Exception:
            pass

        still_tamam = False
        if not is_fatura_uyari:
            try:
                t_loc2 = page.locator("button, a, div[role='button']").filter(has_text=re.compile(r"^\s*Tamam\s*$", re.I))
                for ti in range(t_loc2.count()):
                    if t_loc2.nth(ti).is_visible():
                        still_tamam = True
                        break
            except Exception:
                pass
        if still_tamam:
            page.wait_for_timeout(500)
            continue

        # Glasspane engeli varsa temizle
        page.evaluate("""() => {
            document.querySelectorAll('.AFBlockingGlassPane, .AFModalGlassPane, [id*="WaitPopup"]').forEach(el => {
                el.style.display = 'none';
                if (el.parentNode) el.parentNode.removeChild(el);
            });
        }""")

        # Fatura Tercihleri veya diğer adımlarda en alttaki aktif "İleri" butonuna bas
        try:
            clicked_ileri = False
            visible_ileri = []
            for sel in [
                page.get_by_role("button", name=re.compile(r"İleri|Ileri", re.I)),
                page.locator("button, a, div[role='button']").filter(has_text=re.compile(r"^\s*İleri\s*$|^\s*Ileri\s*$", re.I)),
            ]:
                for ib in range(sel.count()):
                    b = sel.nth(ib)
                    try:
                        if b.is_visible() and b.is_enabled():
                            visible_ileri.append(b)
                    except Exception:
                        pass
                if visible_ileri:
                    break

            if visible_ileri:
                target_btn = visible_ileri[-1]
                target_btn.scroll_into_view_if_needed()
                try:
                    target_btn.click(timeout=2500)
                except Exception:
                    target_btn.click(force=True, timeout=2000)
                clicked_ileri = True
                print("[FATURA/TERCİH] İleri butonuna tıklandı.", flush=True)

            if not clicked_ileri:
                page.evaluate("""() => {
                    const candidates = Array.from(document.querySelectorAll("button, input[type='button'], a, [role='button']"));
                    for (let i = candidates.length - 1; i >= 0; i--) {
                        const el = candidates[i];
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
        except Exception:
            pass

        wait_glasspane()
        try:
            expect(page.get_by_role("button", name="Sözleşme Özeti Gönder")).to_be_visible(timeout=4000)
            print("[FATURA/TERCİH] Sipariş Özeti ekranına ulaşıldı.", flush=True)
            break
        except Exception:
            pass

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
    gonder_btn = sozlesme_frame.get_by_role("button", name="Sözleşme Özeti Gönder")
    try:
        expect(gonder_btn).to_be_enabled(timeout=3000)
    except Exception:
        gsm_select.select_option("0")
        gsm_select.dispatch_event("change")
        gsm_select.press("Tab")
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
    try:
        expect(page.get_by_role("button", name="Tamam")).to_be_visible(timeout=2000)
    except Exception:
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
    try:
        page1.close()
    except Exception:
        pass
    tamam_final = page.get_by_role("button", name="Tamam")
    expect(tamam_final).to_be_visible(timeout=DEFAULT_TIMEOUT)
    wait_glasspane()
    tamam_final.click()
    try:
        expect(tamam_final).to_be_hidden(timeout=10000)
    except Exception:
        pass
    wait_glasspane()

    # ---------------------
    context.close()
    browser.close()
    report(100, "Aktivasyon tamamlandı.")
    return 'OK'

if __name__ == "__main__":
    main()
