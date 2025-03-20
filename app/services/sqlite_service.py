import logging
import sqlite3
from app.core.database import get_sqlite_connection
from app.core.crypto import encrypt_password, decrypt_password

# Configuramos el logger para este módulo
logger = logging.getLogger(__name__)

def insert_user_record(user_id: int, first_name: str, last_name: str, email: str, mobile: str, password: str):
    """
    Inserta un registro en la tabla `users` en SQLite con la contraseña encriptada.
    Los campos 'service_policies_accepted' se inicializan en 0 (false) y 'service_policies_acceptance_date' en NULL.
    """
    encrypted_password = encrypt_password(password)
    logger.debug("Password encriptada para user_id %s", user_id)
    
    conn = get_sqlite_connection()
    try:
        logger.info("Insertando registro de usuario para user_id %s", user_id)
        cursor = conn.cursor()
        query = """
            INSERT INTO users (user_id, first_name, last_name, email, mobile, password, service_policies_accepted, service_policies_acceptance_date)
            VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
        """
        cursor.execute(query, (user_id, first_name, last_name, email, mobile, encrypted_password))
        conn.commit()
        logger.info("Registro insertado exitosamente para user_id %s", user_id)
    except Exception as e:
        logger.exception("Error al insertar el registro del usuario con user_id %s", user_id)
        raise Exception(f"Error al insertar el registro del usuario: {str(e)}")
    finally:
        conn.close()
        logger.debug("Conexión SQLite cerrada en insert_user_record")

def get_decrypted_password(user_id: int) -> str:
    """
    Obtiene la contraseña desencriptada de la tabla 'users' para el usuario dado.
    """
    conn = get_sqlite_connection()
    try:
        logger.info("Obteniendo contraseña para user_id %s", user_id)
        cursor = conn.cursor()
        query = "SELECT password FROM users WHERE user_id = ?"
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        if not row:
            logger.error("Usuario no encontrado en la base de datos para user_id %s", user_id)
            raise Exception("Usuario no encontrado en la base de datos.")
        encrypted_password = row[0]
        logger.debug("Contraseña encriptada obtenida para user_id %s", user_id)
        decrypted_password = decrypt_password(encrypted_password)
        logger.info("Contraseña desencriptada obtenida para user_id %s", user_id)
        return decrypted_password
    except Exception as e:
        logger.exception("Error al obtener la contraseña para user_id %s", user_id)
        raise Exception(f"Error al obtener la contraseña: {str(e)}")
    finally:
        conn.close()
        logger.debug("Conexión SQLite cerrada en get_decrypted_password")

def update_user_password(user_id: int, new_password: str):
    """
    Actualiza la contraseña de un usuario en la tabla 'users' en SQLite, encriptándola.
    """
    encrypted_password = encrypt_password(new_password)
    logger.debug("Nueva contraseña encriptada para user_id %s", user_id)
    conn = get_sqlite_connection()
    try:
        logger.info("Actualizando contraseña para user_id %s", user_id)
        cursor = conn.cursor()
        query = "UPDATE users SET password = ? WHERE user_id = ?"
        cursor.execute(query, (encrypted_password, user_id))
        conn.commit()
        logger.info("Contraseña actualizada exitosamente para user_id %s", user_id)
    except Exception as e:
        logger.exception("Error al actualizar la contraseña para user_id %s", user_id)
        raise Exception(f"Error al actualizar la contraseña en la base de datos: {str(e)}")
    finally:
        conn.close()
        logger.debug("Conexión SQLite cerrada en update_user_password")

def get_user_record(user_id: int) -> dict:
    """
    Obtiene el registro completo del usuario desde la tabla 'users'.
    Se espera que la tabla incluya: first_name, last_name, email, mobile, street, ci.
    """
    conn = get_sqlite_connection()
    try:
        logger.info("Obteniendo registro del usuario para user_id %s", user_id)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM users WHERE user_id = ?"
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        if not row:
            logger.error("Usuario no encontrado en la base de datos para user_id %s", user_id)
            raise Exception("Usuario no encontrado en la base de datos.")
        record = dict(row)
        logger.debug("Registro obtenido para user_id %s: %s", user_id, record)
        return record
    except Exception as e:
        logger.exception("Error al obtener el registro para user_id %s", user_id)
        raise Exception(f"Error al obtener el registro del usuario: {str(e)}")
    finally:
        conn.close()
        logger.debug("Conexión SQLite cerrada en get_user_record")

def update_user_policies(user_id: int):
    """
    Actualiza el campo service_policies_accepted a 1 y establece service_policies_acceptance_date 
    a CURRENT_TIMESTAMP solo si el usuario aún no ha aceptado las políticas (valor 0).
    Si ya ha sido aceptado (valor 1) y tiene fecha asignada, no realiza cambios.
    """
    conn = get_sqlite_connection()
    try:
        logger.info("Actualizando políticas para user_id %s", user_id)
        cursor = conn.cursor()
        cursor.execute("SELECT service_policies_accepted, service_policies_acceptance_date FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row is None:
            logger.error("Usuario no encontrado en update_user_policies para user_id %s", user_id)
            raise Exception("Usuario no encontrado en la base de datos.")
        
        current_status, acceptance_date = row[0], row[1]
        logger.debug("Estado para user_id %s: service_policies_accepted=%s, acceptance_date=%s", user_id, current_status, acceptance_date)
        
        if current_status == 0 or acceptance_date is None:
            logger.info("Actualizando políticas para user_id %s", user_id)
            cursor.execute("""
                UPDATE users 
                SET service_policies_accepted = 1, 
                    service_policies_acceptance_date = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            logger.info("Políticas actualizadas para user_id %s", user_id)
    except Exception as e:
        logger.exception("Error al actualizar políticas para user_id %s", user_id)
        raise Exception(f"Error al actualizar las políticas del usuario: {str(e)}")
    finally:
        conn.close()
        logger.debug("Conexión SQLite cerrada en update_user_policies")


def update_user_record(
    user_id: int,
    first_name: str,
    last_name: str,
    email: str,
    mobile: str,
    ci: str,
    street: str = ""
):

    conn = get_sqlite_connection()
    try:
        logger.info("Actualizando usuario en SQLite con user_id=%s", user_id)
        cursor = conn.cursor()
        query = """
            UPDATE users
            SET first_name = ?,
                last_name = ?,
                email = ?,
                mobile = ?,
                ci = ?,
                street = ?
            WHERE user_id = ?
        """
        cursor.execute(query, (first_name, last_name, email, mobile, ci, street, user_id))
        conn.commit()
        logger.debug("Usuario actualizado en SQLite con user_id=%s", user_id)
    except Exception as e:
        logger.exception("Error al actualizar usuario en SQLite para user_id=%s", user_id)
        raise Exception(f"Error al actualizar usuario en SQLite: {str(e)}")
    finally:
        conn.close()
        logger.debug("Conexión SQLite cerrada en update_user_record")


