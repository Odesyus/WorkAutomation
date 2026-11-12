import oracledb
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import config

# Oracle Instant Client (Thick mode) başlatma
CLIENT_DIR = os.path.join(ROOT, "instantclient_19_25")
try:
    oracledb.init_oracle_client(lib_dir=CLIENT_DIR)
except Exception:
    pass

def get_imsi_by_msisdn(msisdn):
    creds = config.get_db_credentials('bscs')
    username = creds.get('username') or config.BSCS_DB.get('username')
    password = creds.get('password') or config.BSCS_DB.get('password')
    dsn_string = config.BSCS_DB.get('dsn', "10.132.3.46:1535/BSPR")

    if not username or not password:
        return {'success': False, 'error': 'BSCS Veritabanı kullanıcı adı veya şifresi ayarlanmamış. Lütfen Ayarlar sayfasından girin.'}

    try:
        # Establish the connection
        with oracledb.connect(user=username, password=password, dsn=dsn_string) as connection:
            
            # Create a cursor object
            with connection.cursor() as cursor:

                cursor.callproc("dbms_output.enable")
                
                # 1. Executing a SELECT Query (Güvenli bind variable kullanımı)
                sql_select = "select IMSI from eu_rim.iccid_inv where MSISDN = :msisdn"
                
                cursor.execute(sql_select, msisdn=str(msisdn).strip())
                test = cursor.fetchone()
                if test:
                    IMSI = str(test[0])
                    return {'success': True, 'imsi': IMSI}
                else:
                    return {'success': False, 'error': 'IMSI bulunamadı'}

    except oracledb.DatabaseError as e:
        error, = e.args
        print(f"Oracle Database Error: {error.message}")
        return {'success': False, 'error': error.message}

if __name__ == "__main__":
    print(get_imsi_by_msisdn("5538173271"))
