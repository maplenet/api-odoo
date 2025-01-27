import sqlite3

def create_tables():
    connection = sqlite3.connect("verification_codes.db")
    cursor = connection.cursor()
    
    # Crear la tabla `verification_codes`
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verification_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        code TEXT NOT NULL,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    connection.commit()
    connection.close()
    print("Tabla `verification_codes` creada correctamente.")

if __name__ == "__main__":
    create_tables()
