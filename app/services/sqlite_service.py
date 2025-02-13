# app/services/sqlite_service.py
import sqlite3
from app.core.database import get_sqlite_connection
from app.core.crypto import encrypt_password, decrypt_password


def insert_user_record(user_id: int, first_name: str, last_name: str, email: str, mobile: str, password: str):
    """
    Inserta un registro en la tabla `users` en SQLite con la contraseña encriptada.
    Los campos 'service_policies_accepted' se inicializan en 0 (false) y 'service_policies_acceptance_date' en NULL.
    """
    encrypted_password = encrypt_password(password)
    
    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO users (user_id, first_name, last_name, email, mobile, password, service_policies_accepted, service_policies_acceptance_date)
            VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
        """
        cursor.execute(query, (user_id, first_name, last_name, email, mobile, encrypted_password))
        conn.commit()
    except Exception as e:
        raise Exception(f"Error al insertar el registro del usuario: {str(e)}")
    finally:
        conn.close()

def get_decrypted_password(user_id: int) -> str:
    """
    Obtiene la contraseña desencriptada de la tabla 'users' para el usuario dado.
    """
    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT password FROM users WHERE user_id = ?"
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        if not row:
            raise Exception("Usuario no encontrado en la base de datos.")
        encrypted_password = row[0]
        return decrypt_password(encrypted_password)
    except Exception as e:
        raise Exception(f"Error al obtener la contraseña: {str(e)}")
    finally:
        conn.close()

def update_user_password(user_id: int, new_password: str):
    """
    Actualiza la contraseña de un usuario en la tabla 'users' en SQLite, encriptándola.
    """
    encrypted_password = encrypt_password(new_password)
    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        query = "UPDATE users SET password = ? WHERE user_id = ?"
        cursor.execute(query, (encrypted_password, user_id))
        conn.commit()
    except Exception as e:
        raise Exception(f"Error al actualizar la contraseña en la base de datos: {str(e)}")
    finally:
        conn.close()

def get_user_record(user_id: int) -> dict:
    """
    Obtiene el registro completo del usuario desde la tabla 'users'.
    Se espera que la tabla incluya: first_name, last_name, email, mobile, street, ci.
    """
    conn = get_sqlite_connection()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM users WHERE user_id = ?"
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        if not row:
            raise Exception("Usuario no encontrado en la base de datos.")
        return dict(row)
    except Exception as e:
        raise Exception(f"Error al obtener el registro del usuario: {str(e)}")
    finally:
        conn.close()

def update_user_policies(user_id: int):
    """
    Actualiza el registro del usuario en la tabla 'users' para marcar que ha aceptado las políticas
    de servicio (service_policies_accepted = 1) y registra la fecha de aceptación (service_policies_acceptance_date)
    con la fecha y hora actual.
    """
    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE users
            SET service_policies_accepted = 1,
                service_policies_acceptance_date = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """
        cursor.execute(query, (user_id,))
        conn.commit()
    except Exception as e:
        raise Exception(f"Error al actualizar las políticas del usuario: {str(e)}")
    finally:
        conn.close()
