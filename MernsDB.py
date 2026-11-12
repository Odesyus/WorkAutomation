import oracledb
import config

def get_Merns():
    # Database connection parameters
    creds = config.get_db_credentials('merns')
    username = creds.get('username') or config.MERNS_DB.get('username', '')
    password = creds.get('password') or config.MERNS_DB.get('password', '')
    dsn_string = config.MERNS_DB.get('dsn', "10.248.71.115:1521/MERNIST")
    data = {}

    if not username or not password:
        print("MERNS veritabanı kullanıcı adı veya şifresi eksik.")
        return data
    try:
        # Establish the connection
        with oracledb.connect(user=username, password=password, dsn=dsn_string) as connection:
            
            # Create a cursor object
            with connection.cursor() as cursor:

                cursor.callproc("dbms_output.enable")
                
                # 1. Executing a SELECT Query
                sql_select = "BEGIN MERNS.CREATE_RANDOM_DATA_TCKK('T'); END;"
                
                # Use bind variables (e.g., :sal) for performance and security
                cursor.execute(sql_select)
                
                status = cursor.var(oracledb.NUMBER)
                line = cursor.var(oracledb.STRING)

                print("--- Query Results ---")
                while True:
                    cursor.callproc("dbms_output.get_line", (line,status))
                    if status.getvalue() != 0:
                        break
                    val = line.getvalue()
                    if val:
                        if ":" in val:
                            key, value = val.split(":",1)
                            key = key.strip()
                            value = value.strip()
                            data[key]=value


    except oracledb.DatabaseError as e:
        error, = e.args
        print(f"Oracle Database Error: {error.message}")
    return data

if __name__ == "__main__":
    print(get_Merns())