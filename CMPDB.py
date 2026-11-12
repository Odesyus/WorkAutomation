import oracledb
import re
import config

def get_OTP():
    # Database connection parameters
    creds = config.get_db_credentials('cmpdb')
    username = creds.get('username') or config.CMPDB_DB.get('username', '')
    password = creds.get('password') or config.CMPDB_DB.get('password', '')
    dsn_string = config.CMPDB_DB.get('dsn', "10.248.71.115:1521/CMPDBT")
    data = {}

    if not username or not password:
        print("CMPDB kullanıcı adı veya şifresi eksik.")
        return ""
    try:
        # Establish the connection
        with oracledb.connect(user=username, password=password, dsn=dsn_string) as connection:
            
            # Create a cursor object
            with connection.cursor() as cursor:

                cursor.callproc("dbms_output.enable")
                
                # 1. Executing a SELECT Query
                sql_select = "select CONTENT from CMP_MOBILE.sms_outgoing where target_addres = '905333333333' order by create_date DESC FETCH FIRST 1 ROWS ONLY"
                
                # Use bind variables (e.g., :sal) for performance and security
                cursor.execute(sql_select)
                test = cursor.fetchone()
                metin = test[0]
                OTP = re.search(r'\d+', metin).group(0)
                return OTP
                


    except oracledb.DatabaseError as e:
        error, = e.args
        print(f"Oracle Database Error: {error.message}")
    return data

if __name__ == "__main__":
    print(get_OTP())