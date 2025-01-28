import sqlite3

def query_table():
    connection = sqlite3.connect("verification_codes.db")
    cursor = connection.cursor()
    
    # Consulta el contenido de la tabla
    cursor.execute("SELECT * FROM verification_codes")
    rows = cursor.fetchall()
    
    print("Contenido de la tabla `verification_codes`:")
    for row in rows:
        print(row)
    
    connection.close()

if __name__ == "__main__":
    query_table()
