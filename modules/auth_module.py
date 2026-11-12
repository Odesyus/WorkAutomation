# -*- coding: utf-8 -*-
"""
TestPortal Kimlik Doğrulama Modülü
Kullanıcının Sicil/Domain ID ve şifresini TestPortal üzerinden doğrular.
Giriş başarılıysa 'Test Hattı Temizleme' sayfasından ad-soyad bilgisini çeker.
"""

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config
from playwright.sync_api import sync_playwright


def authenticate_testportal(username, password, timeout=25000):
    """
    TestPortal üzerinden giriş yapar ve kullanıcı adını ('Ad Soyad (Sicil)') döndürür.
    Dönüş: {'success': True, 'name': 'Tugay Furkan Akbaba (37157378)', 'user': username}
    veya   {'success': False, 'error': 'Hata mesajı'}
    """
    username = str(username).strip()
    password = str(password).strip()

    if not username or not password:
        return {'success': False, 'error': 'Sicil (Kullanıcı Adı) ve Şifre boş bırakılamaz.'}

    tp_url = config.URLS.get('testportal', 'https://testportal')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            try:
                # 1. Login Sayfasına Git
                page.goto(f"{tp_url}/Login.aspx", timeout=timeout)
                page.wait_for_load_state("domcontentloaded", timeout=timeout)

                # 2. Formu Doldur ve Gönder
                page.get_by_role("textbox", name="Domain ID").fill(username)
                page.get_by_role("textbox", name="Domain ID").press("Tab")
                page.get_by_role("textbox", name="******").fill(password)
                page.get_by_role("textbox", name="******").press("Enter")
                page.wait_for_load_state("networkidle", timeout=timeout)

                # 3. Giriş Başarısız mı Kontrol Et
                if "Login.aspx" in page.url:
                    # Sayfadaki hata bildirimlerini tara
                    err_loc = page.locator("span[id*='Error'], div[id*='Error'], .error, .text-danger, .alert, #lblHata")
                    for i in range(err_loc.count()):
                        txt = err_loc.nth(i).inner_text().strip()
                        if txt:
                            return {'success': False, 'error': txt}

                    # Eğer hala login kutusu görünüyorsa şifre yanlıştır
                    domain_box = page.locator("input[name*='Domain'], input[id*='txtUserName']")
                    if domain_box.count() > 0 and domain_box.first.is_visible():
                        return {'success': False, 'error': 'Kullanıcı adı veya şifre hatalı, lütfen tekrar deneyiniz.'}

                # 4. Giriş Başarılı — TestHattiTemizleme Sayfasından İsmi Çek
                clean_url = f"{tp_url}/Talepler/TestHattiTemizleme.aspx"
                page.goto(clean_url, timeout=timeout)
                page.wait_for_load_state("networkidle", timeout=timeout)

                user_display_name = None

                # 'Talebi Yapan Kullanıcı Bilgileri' satırını bul
                row = page.locator("text=Talebi Yapan Kullanıcı Bilgileri").locator("xpath=..")
                if row.count() > 0:
                    span = row.locator("td span, span").first
                    if span.count() > 0:
                        txt = span.inner_text().strip()
                        if txt:
                            user_display_name = txt

                    if not user_display_name:
                        raw = row.inner_text().replace("Talebi Yapan Kullanıcı Bilgileri:", "").strip()
                        if raw:
                            user_display_name = raw

                # Eğer tabloda bulunamazsa yedek olarak sicil numarasını kullan
                if not user_display_name:
                    user_display_name = f"{username}"

                return {
                    'success': True,
                    'name': user_display_name,
                    'user': username,
                    'password': password
                }

            finally:
                context.close()
                browser.close()

    except Exception as e:
        error_msg = str(e)
        if "Timeout" in error_msg:
            return {'success': False, 'error': 'TestPortal sunucusuna bağlanırken zaman aşımı oluştu. VPN veya ağ bağlantınızı kontrol edin.'}
        return {'success': False, 'error': f'Doğrulama hatası: {error_msg}'}
