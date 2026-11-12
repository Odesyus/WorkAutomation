import re
import os
import json
from playwright.sync_api import Playwright, sync_playwright, expect
import time
import config

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")
DEFAULT_TIMEOUT = 60000  # 60 saniye


def load_users():
    """users.json dosyasından kullanıcı listesini yükler ve dict {id: {...}} döndürür."""
    if not os.path.exists(USERS_FILE):
        example_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.example.json")
        default_list = []
        if os.path.exists(example_file):
            try:
                with open(example_file, "r", encoding="utf-8") as ef:
                    default_list = json.load(ef)
            except Exception:
                default_list = []
        save_users_list(default_list)
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        items = json.load(f)
    return {
        int(u["id"]): {
            "Id": int(u["id"]),
            "Name": u["name"],
            "User": u["user"],
            "Password": u["password"],
        }
        for u in items
    }


def save_users_list(items):
    """Kullanıcı listesini users.json dosyasına kalıcı olarak kaydeder."""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add_user(name, domain_user, password):
    """Yeni kullanıcı ekler ve users.json'a kaydeder."""
    users_map = load_users()
    next_id = (max(users_map.keys()) + 1) if users_map else 1
    items = [
        {"id": u["Id"], "name": u["Name"], "user": u["User"], "password": u["Password"]}
        for u in users_map.values()
    ]
    new_item = {
        "id": next_id,
        "name": name.strip(),
        "user": domain_user.strip(),
        "password": password.strip(),
    }
    items.append(new_item)
    save_users_list(items)
    return new_item


def delete_user(user_id):
    """Verilen ID'ye sahip kullanıcıyı siler ve users.json'ı günceller."""
    users_map = load_users()
    uid = int(user_id)
    if uid not in users_map:
        return False
    items = [
        {"id": u["Id"], "name": u["Name"], "user": u["User"], "password": u["Password"]}
        for k, u in users_map.items() if k != uid
    ]
    save_users_list(items)
    return True


def _parse_lines_from_raw(raw_text, owner_name, hat_tipi, filter_62=False):
    """Ham ağaç metninden MSISDN / IMSI / ICCID satırlarını ayrıştırır."""
    if not raw_text:
        return []
    if filter_62:
        sonuc = []
        for satir in raw_text.strip().split('\n'):
            parcalar = satir.split("MSISDN")
            if len(parcalar) > 1:
                temp = parcalar[1]
                if len(temp) == 62:
                    sonuc.append("MSISDN" + parcalar[1])
        raw_text = "\n".join(sonuc)

    parsed = []
    temiz_satirlar = [satir.strip() for satir in raw_text.splitlines() if satir.strip()]
    for satir in temiz_satirlar:
        parcalar = satir.split()
        if len(parcalar) >= 6 and parcalar[0].startswith("MSISDN"):
            parsed.append({
                "MSISDN": parcalar[1],
                "IMSI": parcalar[3],
                "ICCID": parcalar[5],
                "OWNER": owner_name,
                "TYPE": hat_tipi,
            })
    return parsed


def _detect_pos_pre(text):
    """Metinde POS/PRE ifadesini arar: 'Pos', 'Pre' veya None döndürür."""
    t = (text or "").upper()
    if re.search(r"\bPOS\b", t):
        return "Pos"
    if re.search(r"\bPRE\b", t):
        return "Pre"
    return None


_TREE_JS = """(treeId) => {
  const tree = document.getElementById(treeId);
  if (!tree) return [];
  const out = [];
  tree.querySelectorAll('a[id^="' + treeId + 't"], span[id^="' + treeId + 't"]').forEach(a => {
    if (!/t\\d+$/.test(a.id)) return;
    out.push((a.textContent || '').replace(/\\s+/g, ' ').trim());
  });
  return out;
}"""


def _parse_tree(page, tree_id, owner_name, hat_tipi):
    """
    Ağaçtaki tüm düğümleri DOM sırasıyla okur.
    - 'MSISDN:' içermeyen düğümler grup başlığıdır (Örn: 'AVEA/POS LTE - 37157378').
    - Hat satırlarında Pos/Pre önce satırın kendisinden (Fiziksel: 'Avea - PRE LTE MSISDN: ...'),
      yoksa bağlı olduğu grup başlığından alınır.
    """
    parsed = []
    grup_pos_pre = None
    for text in page.evaluate(_TREE_JS, tree_id) or []:
        if "MSISDN:" not in text:
            grup_pos_pre = _detect_pos_pre(text)
            continue
        m = re.search(r"MSISDN:\s*(\d*)\s*IMSI:\s*(\d+)\s*ICCID:\s*(\d+)", text)
        if not m or not m.group(1):
            continue  # MSISDN'i olmayan (ESNEK SIM vb.) hatları atla
        on_ek = text.split("MSISDN:")[0]
        parsed.append({
            "MSISDN": m.group(1),
            "IMSI": m.group(2),
            "ICCID": m.group(3),
            "OWNER": owner_name,
            "TYPE": hat_tipi,
            "POS_PRE": _detect_pos_pre(on_ek) or grup_pos_pre or "-",
        })
    return parsed


def get_ICCID(playwright: Playwright, user_id: int = None):
    """
    Seçilen kullanıcının TestHattiTemizleme.aspx sayfasındaki hem Sanal Hatlar
    hem de Fiziksel Hatlar bölümlerini kontrol eder; bulunan hatları
    TYPE='Sanal' veya TYPE='Fiziksel' ve POS_PRE='Pos'/'Pre' bilgisiyle döndürür.
    """
    Users = load_users()
    if not Users:
        raise ValueError("Kayıtlı TestPortal kullanıcısı bulunamadı!")

    secilen_id = int(user_id) if (user_id is not None and int(user_id) in Users) else next(iter(Users.keys()))
    aktif_user = Users[secilen_id]

    if not aktif_user['User'] or not aktif_user['Password']:
        raise ValueError(f"{aktif_user['Name']} kullanıcısı için Domain ID veya şifre henüz tanımlanmamış!")

    data = []
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    try:
        tp_url = config.URLS.get('testportal', 'https://testportal')
        page.goto(f"{tp_url}/Login.aspx", timeout=DEFAULT_TIMEOUT)
        page.get_by_role("textbox", name="Domain ID").click()
        page.get_by_role("textbox", name="Domain ID").fill(aktif_user['User'])
        page.get_by_role("textbox", name="Domain ID").press("Tab")
        page.get_by_role("textbox", name="******").fill(aktif_user['Password'])
        page.get_by_role("textbox", name="******").press("Enter")
        expect(page.locator("[id=bilgilendirme]")).to_be_visible(timeout=DEFAULT_TIMEOUT)

        page.goto(f"{tp_url}/Talepler/TestHattiTemizleme.aspx", timeout=DEFAULT_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT)

        # Sanal ve Fiziksel ağaçlarındaki tüm grupları (POS/PRE başlıklarıyla birlikte) oku
        data.extend(_parse_tree(page, "BodyCenter_treeSanalHat", aktif_user['Name'], "Sanal"))
        data.extend(_parse_tree(page, "BodyCenter_treeFizikselHat", aktif_user['Name'], "Fiziksel"))

    finally:
        context.close()
        browser.close()
    return data


if __name__ == "__main__":
    with sync_playwright() as playwright:
        print(get_ICCID(playwright))
