# app/services/token_service.py
import sqlite3
from app.core.database import get_sqlite_connection

def store_token(token: str, user_id: int, token_type: str, expires_at: str, client_ip: str = None, user_agent: str = None):
    """
    Almacena un token en la tabla 'tokens'.
    """
    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO tokens (token, user_id, token_type, expires_at, client_ip, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (token, user_id, token_type, expires_at, client_ip, user_agent))
        conn.commit()
    except Exception as e:
        raise Exception(f"Error al almacenar token: {str(e)}")
    finally:
        conn.close()

def revoke_token(token: str):
    """
    Marca un token como revocado, actualizando 'revoked_at' al momento actual.
    """
    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE tokens
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE token = ?
        """
        cursor.execute(query, (token,))
        conn.commit()
    except Exception as e:
        raise Exception(f"Error al revocar token: {str(e)}")
    finally:
        conn.close()

def mark_token_as_used(token: str):
    """
    Marca un token como usado (por ejemplo, para tokens de restablecimiento de contraseña).
    """
    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE tokens
            SET used = 1
            WHERE token = ?
        """
        cursor.execute(query, (token,))
        conn.commit()
    except Exception as e:
        raise Exception(f"Error al marcar token como usado: {str(e)}")
    finally:
        conn.close()

def get_token_record(token: str) -> dict:
    """
    Obtiene el registro del token desde la tabla 'tokens'.
    Devuelve un diccionario con los campos del token o None si no se encuentra.
    """
    conn = get_sqlite_connection()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM tokens WHERE token = ?"
        cursor.execute(query, (token,))
        record = cursor.fetchone()
        if record:
            return dict(record)
        else:
            return None
    except Exception as e:
        raise Exception(f"Error al obtener registro del token: {str(e)}")
    finally:
        conn.close()
