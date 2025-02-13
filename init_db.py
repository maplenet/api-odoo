import sqlite3

def create_tables():
    connection = sqlite3.connect("verification.db")
    cursor = connection.cursor()
    
    # Tabla de códigos de verificación (ya existente)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        code TEXT NOT NULL,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Nueva tabla para almacenar la información de los usuarios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL,
        mobile TEXT NOT NULL,
        password TEXT NOT NULL,
        street TEXT,
        ci TEXT,
        service_policies_accepted INTEGER NOT NULL DEFAULT 0,
        service_policies_acceptance_date TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        token_type TEXT NOT NULL,
        issued_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        revoked_at TIMESTAMP,
        used INTEGER DEFAULT 0,
        client_ip TEXT,
        user_agent TEXT
    )
    """)
    
    connection.commit()
    connection.close()
    print("Tablas creadas correctamente.")

if __name__ == "__main__":
    create_tables()
