# -*- coding: utf-8 -*-
"""
Merkezi Oracle Veritabanı Servisi (MERNS, CMPDB, BSCS).
- get_Merns(): MERNS DB'den rastgele test müşterisi (TCKN, Doğum Tarihi, Ad, Soyad) üretir (Thin Mode).
- get_OTP(): CMPDB'den son SMS OTP kodunu çeker.
- get_imsi_by_msisdn(msisdn): BSCS DB'den MSISDN'e ait IMSI bilgisini sorgular (Thick Mode).
"""

import os
import re
import sys
import oracledb

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)
from core import config

CLIENT_DIR = os.path.join(config.DRIVERS_DIR, "instantclient_19_25")
if not os.path.isdir(CLIENT_DIR):
    CLIENT_DIR = os.path.join(config.ROOT_DIR, "instantclient_19_25")


def _ensure_thick_mode():
    """BSCS DB bağlantısı için gerektiğinde Oracle Instant Client (Thick mode) başlatır."""
    try:
        oracledb.init_oracle_client(lib_dir=CLIENT_DIR)
    except Exception:
        pass


def get_Merns():
    """MERNS veritabanından rastgele TCKN ve doğum tarihi çeker."""
    creds = config.get_db_credentials('merns')
    username = creds.get('username') or config.MERNS_DB.get('username', '')
    password = creds.get('password') or config.MERNS_DB.get('password', '')
    dsn_string = config.MERNS_DB.get('dsn', "10.248.71.115:1521/MERNIST")
    data = {}

    if not username or not password:
        print("MERNS veritabanı kullanıcı adı veya şifresi eksik.")
        return data
    try:
        with oracledb.connect(user=username, password=password, dsn=dsn_string) as connection:
            with connection.cursor() as cursor:
                cursor.callproc("dbms_output.enable")
                cursor.execute("BEGIN MERNS.CREATE_RANDOM_DATA_TCKK('T'); END;")

                status = cursor.var(oracledb.NUMBER)
                line = cursor.var(oracledb.STRING)

                print("--- Query Results ---")
                while True:
                    cursor.callproc("dbms_output.get_line", (line, status))
                    if status.getvalue() != 0:
                        break
                    val = line.getvalue()
                    if val and ":" in val:
                        key, value = val.split(":", 1)
                        data[key.strip()] = value.strip()
    except oracledb.DatabaseError as e:
        error, = e.args
        print(f"Oracle Database Error (MERNS): {error.message}")
    return data


def get_OTP():
    """CMPDB veritabanından son doğrulama SMS içerisindeki OTP kodunu döndürür."""
    creds = config.get_db_credentials('cmpdb')
    username = creds.get('username') or config.CMPDB_DB.get('username', '')
    password = creds.get('password') or config.CMPDB_DB.get('password', '')
    dsn_string = config.CMPDB_DB.get('dsn', "10.248.71.115:1521/CMPDBT")

    if not username or not password:
        print("CMPDB kullanıcı adı veya şifresi eksik.")
        return ""
    try:
        with oracledb.connect(user=username, password=password, dsn=dsn_string) as connection:
            with connection.cursor() as cursor:
                cursor.callproc("dbms_output.enable")
                sql_select = (
                    "select CONTENT from CMP_MOBILE.sms_outgoing "
                    "where target_addres = '905333333333' "
                    "order by create_date DESC FETCH FIRST 1 ROWS ONLY"
                )
                cursor.execute(sql_select)
                row = cursor.fetchone()
                if row and row[0]:
                    match = re.search(r'\d+', str(row[0]))
                    return match.group(0) if match else ""
    except oracledb.DatabaseError as e:
        error, = e.args
        print(f"Oracle Database Error (CMPDB): {error.message}")
    return ""


def get_imsi_by_msisdn(msisdn):
    """BSCS veritabanından verilen MSISDN'e karşılık gelen IMSI numarasını döndürür."""
    _ensure_thick_mode()
    creds = config.get_db_credentials('bscs')
    username = creds.get('username') or config.BSCS_DB.get('username')
    password = creds.get('password') or config.BSCS_DB.get('password')
    dsn_string = config.BSCS_DB.get('dsn', "10.132.3.46:1535/BSPR")

    if not username or not password:
        return {
            'success': False,
            'error': 'BSCS Veritabanı kullanıcı adı veya şifresi ayarlanmamış. Lütfen Ayarlar sayfasından girin.'
        }

    try:
        with oracledb.connect(user=username, password=password, dsn=dsn_string) as connection:
            with connection.cursor() as cursor:
                cursor.callproc("dbms_output.enable")
                sql_select = "select IMSI from eu_rim.iccid_inv where MSISDN = :msisdn"
                cursor.execute(sql_select, msisdn=str(msisdn).strip())
                row = cursor.fetchone()
                if row:
                    return {'success': True, 'imsi': str(row[0])}
                return {'success': False, 'error': 'IMSI bulunamadı'}
    except oracledb.DatabaseError as e:
        error, = e.args
        print(f"Oracle Database Error (BSCS): {error.message}")
        return {'success': False, 'error': error.message}
