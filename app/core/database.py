import os
import sqlite3
import xmlrpc.client
from app.config import settings

def get_odoo_connection():
    common = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(settings.ODOO_DB, settings.ODOO_USERNAME, settings.ODOO_PASSWORD, {})
    
    if not uid:
        raise Exception("Autenticación fallida en Odoo")
    
    models = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/object")
    
    return {
        "common": common,  
        'db': settings.ODOO_DB,
        'uid': uid,
        'password': settings.ODOO_PASSWORD,
        'models': models
    }

# Conexión a SQLite
def get_sqlite_connection():
    try:
        # Construir la ruta al archivo de la base de datos en la carpeta 'storage'
        db_directory = "storage"
        os.makedirs(db_directory, exist_ok=True)  # Asegura que el directorio exista
        db_path = os.path.join(db_directory, "verification.db")
        
        connection = sqlite3.connect(db_path)
        return connection
    except sqlite3.Error as e:
        raise Exception(f"Error al conectar con SQLite: {e}")
