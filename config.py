# -*- coding: utf-8 -*-
"""
Yapılandırma Modülü (Shared vs Personal Configuration)
- ORTAKLAR: DB IP/DSN'leri, SSH bilgileri, Sistem URL'leri, Opera/MDM/ES kullanıcıları
- ORTAK OLMAYANLAR (Bireysel): DB kullanıcı/şifreleri, TestPortal kullanıcı/şifresi, TestPortal kullanıcı listesi
Bireysel veriler 'local_config.json' ve 'users.json' içinde tutulur, Git'e aktarılmaz (.gitignore).
"""

import os
import json

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CONFIG_FILE = os.path.join(ROOT_DIR, "local_config.json")
LOCAL_CONFIG_EXAMPLE = os.path.join(ROOT_DIR, "local_config.example.json")

# =============================================================================
# 1. ORTAK BİLGİLER (SHARED CONFIGURATION - TÜM KULLANICILAR İÇİN AYNI)
# =============================================================================

# Veritabanı DSN ve IP Bilgileri (Ortak)
BSCS_DB = {
    'dsn': '10.132.3.46:1535/BSPR',
    'username': '',  # local_config.json'dan doldurulur
    'password': ''   # local_config.json'dan doldurulur
}

CMPDB_DB = {
    'dsn': '10.248.71.115:1521/CMPDBT'
}

MERNS_DB = {
    'dsn': '10.248.71.115:1521/MERNIST'
}

# SSH Sunucu Bilgileri (Ortak)
SSH_CONFIG = {
    'host': '10.132.1.111',
    'port': 22,
    'username': 'cdpadmin',
    'password': 'cdpadmin123',
    'timeout': 15
}

# Ortak Sistem URL'leri
URLS = {
    'opera': 'http://10.248.67.23:8001/MTS/faces/index',
    'mdm': 'https://test-cdp.turktelekom.com.tr/ui/home.html#/dashboard',
    'mdm_device_add': 'https://test-cdp.turktelekom.com.tr/ui/home.html#/deviceAdd',
    'es': 'http://10.132.1.11:8080/ui/#/dashboard',
    'es_device_add': 'http://10.132.1.11:8080/ui/#/deviceAdd',
    'testportal': 'https://testportal'
}

# Opera Kullanıcıları (Ortak / Koda gömülü)
OPERA_USERS = {
    '61044774': {
        'username': '61044774',
        'password': 'aa1234',
        'label': '61044774 (Varsayılan)'
    },
    'CC51': {
        'username': 'CC51',
        'password': 'aa1234',
        'label': 'CC51'
    }
}

# Opera MTS (Geriye dönük uyumluluk)
OPERA_MTS = {
    'url': URLS['opera'],
    'user': '61044774',
    'password': 'aa1234'
}

# MDM ve ES Yapılandırması (Ortak)
MDM_ES = {
    'mdm_url': URLS['mdm'],
    'mdm_device_add_url': URLS['mdm_device_add'],
    'es_url': URLS['es'],
    'es_device_add_url': URLS['es_device_add'],
    'user': 'superadmin',
    'password': 'superadmin'
}

# TestPortal Genel Bilgileri (URL Ortak, Kullanıcı local_config'den gelir)
TESTPORTAL = {
    'url': URLS['testportal'],
    'user': '',
    'password': ''
}

# Hazır Test Müşterileri (MernsDB yedeği)
TEST_CUSTOMERS = [
    {'dt': '10/10/1970', 'tckn': '38411559398', 'ad': 'YELDA', 'soyad': 'BURAK'},
    {'dt': '24/4/1941',  'tckn': '77373753710', 'ad': 'ÖMER',  'soyad': 'YUSUF'},
    {'dt': '25/6/1989',  'tckn': '76662341690', 'ad': 'FERHAN','soyad': 'REŞAT'},
]

# =============================================================================
# 2. ORTAK OLMAYAN / BİREYSEL YAPILANDIRMA (LOCAL_CONFIG YÖNETİMİ)
# =============================================================================

def load_local_config():
    """
    Yerel kullanıcı yapılandırmasını (local_config.json) okur.
    Dosya yoksa local_config.example.json şablonunu kopyalayarak oluşturur.
    """
    if not os.path.exists(LOCAL_CONFIG_FILE):
        default_data = {
            "db": {
                "bscs": {"username": "", "password": ""},
                "cmpdb": {"username": "", "password": ""},
                "merns": {"username": "", "password": ""}
            },
            "testportal": {"user": "", "password": ""},
            "credentials": {"sicil": "", "password": "", "name": ""},
            "default_opera_user": "61044774"
        }
        if os.path.exists(LOCAL_CONFIG_EXAMPLE):
            try:
                with open(LOCAL_CONFIG_EXAMPLE, "r", encoding="utf-8") as f:
                    default_data = json.load(f)
            except Exception:
                pass
        save_local_config(default_data)
        return default_data

    try:
        with open(LOCAL_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[CONFIG] local_config.json okuma hatası: {e}")
        return {}


def save_local_config(data):
    """Bireysel yapılandırmayı local_config.json dosyasına kaydeder ve bellekteki değerleri yeniler."""
    try:
        with open(LOCAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if '_sync_runtime_config' in globals():
            _sync_runtime_config(data)
        return True
    except Exception as e:
        print(f"[CONFIG] local_config.json kaydetme hatası: {e}")
        return False


def get_secret_key():
    """
    Her kurulum için makineye özel, güvenli ve rastgele bir SECRET_KEY üretir ve saklar.
    """
    cfg = load_local_config()
    secret = cfg.get("secret_key")
    if not secret:
        import secrets
        secret = secrets.token_hex(32)
        cfg["secret_key"] = secret
        save_local_config(cfg)
    return secret

# Flask Gizli Anahtarı (Makineye özel dinamik)
SECRET_KEY = get_secret_key()


def _sync_runtime_config(local_cfg=None):
    """local_config.json'dan okunan değerleri global config değişkenleriyle senkronize eder."""
    if local_cfg is None:
        local_cfg = load_local_config()

    db_cfg = local_cfg.get("db", {})
    bscs = db_cfg.get("bscs", {})
    BSCS_DB['username'] = bscs.get('username', '')
    BSCS_DB['password'] = bscs.get('password', '')

    tp = local_cfg.get("testportal", {})
    TESTPORTAL['user'] = tp.get('user', '')
    TESTPORTAL['password'] = tp.get('password', '')


def get_db_credentials(service='bscs'):
    """
    İlgili veritabanı servisi için kullanıcı adı ve şifresini döndürür.
    service: 'bscs' | 'cmpdb' | 'merns'
    """
    cfg = load_local_config()
    db_group = cfg.get("db", {})
    return db_group.get(service, {})


def get_testportal_credentials():
    """TestPortal için kullanıcının bireysel kullanıcı adı ve şifresini döndürür."""
    cfg = load_local_config()
    return cfg.get("testportal", {})


def get_user_credentials():
    """Giriş yapmış kullanıcının sicil ve şifre bilgilerini döndürür."""
    cfg = load_local_config()
    return cfg.get("credentials", {})


def save_user_session_credentials(sicil, password, full_name):
    """
    Giriş yapan kullanıcının sicil ve şifresini hem genel 'credentials'
    hem de 'testportal' altına kaydeder; diğer sistemlerde doğrudan kullanılmasını sağlar.
    """
    cfg = load_local_config()
    cfg['credentials'] = {
        'sicil': str(sicil).strip(),
        'password': str(password).strip(),
        'name': str(full_name).strip()
    }
    cfg.setdefault('testportal', {})
    cfg['testportal']['user'] = str(sicil).strip()
    cfg['testportal']['password'] = str(password).strip()

    # Eğer BSCS kullanıcısı boş ise sicil numarasından varsayılan oluştur
    cfg.setdefault('db', {})
    cfg['db'].setdefault('bscs', {})
    if not cfg['db']['bscs'].get('username'):
        cfg['db']['bscs']['username'] = f"U{str(sicil).strip()}"

    save_local_config(cfg)
    return cfg


# Modül yüklendiğinde yerel yapılandırmayı bağla
_sync_runtime_config()
