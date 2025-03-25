import sqlite3
import random
from app.core.logging_config import logger
from fastapi import HTTPException
from app.core.database import get_sqlite_connection
from app.core.email_utils import send_verification_email

def generate_verification_code():
    return f"{random.randint(100000, 999999)}"

def get_latest_verification_code(email: str):
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row  # Hacer que SQLite devuelva los resultados como diccionarios
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM verification
        WHERE email = ?
        ORDER BY created_at DESC
        LIMIT 1
        """, (email,))
        return cursor.fetchone()  # Devuelve None si no hay resultados

def get_user_info(email: str):
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM users
        WHERE email = ?
        LIMIT 1
        """, (email,))
        return cursor.fetchone()

def create_verification_code(email: str):
    code = generate_verification_code()
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO verification (email, code, status)
        VALUES (?, ?, 0)
        """, (email, code))
        conn.commit()

    # Enviar el código por correo electrónico
    send_verification_email(
        to_email=email,
        subject="Código de verificación: " + code,
        code=code,  # No necesitamos el cuerpo en texto plano
    )
    return code

def handle_verification_request(email: str):
    latest_record = get_latest_verification_code(email)
    user_info = get_user_info(email)

    if latest_record:
        if latest_record["status"] and not user_info:
            return {"detail": "El correo ya está verificado.", "code": 1}
        if latest_record["status"] and user_info:
            return {"error": "El correo ya está habilitado."}
        else:  # Si el estado es False, generar un nuevo código
            create_verification_code(email)
            return {"detail": "Nuevo código enviado al correo.", "correo": email}
    else:
        # Si no existe ningún registro previo, crear uno nuevo
        create_verification_code(email)
        return {"detail": "Código enviado al correo.", "correo": email}

def verify_code_and_email(email: str, code: str):
    logger.info("Iniciando verificación de código para email: %s", email)
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row  # Usar sqlite3.Row para obtener un diccionario
        cursor = conn.cursor()

        # Verificar si el correo existe en la tabla
        cursor.execute("""
            SELECT * FROM verification
            WHERE email = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (email,))
        latest_record = cursor.fetchone()

        if not latest_record:
            logger.error("No se encontró registro para el email: %s", email)
            return {"error": "No se encontró un registro para el correo proporcionado."}

        logger.debug("Registro encontrado: %s", dict(latest_record))

        # Validar el código y el estado
        if latest_record["status"] == 1:
            logger.warning("El email %s ya ha sido verificado previamente", email)
            raise HTTPException(status_code=409, detail="El correo ya ha sido verificado previamente.")

        if latest_record["code"] != code:
            logger.warning("El código proporcionado no coincide para email %s", email)
            return {"error": "El código proporcionado no coincide."}
        
        # Actualizar el estado a true (1)
        cursor.execute("""
            UPDATE verification
            SET status = 1
            WHERE email = ? AND code = ?
        """, (email, code))
        conn.commit()
        logger.info("Estado actualizado a verificado para email: %s", email)

        return {"detail": "El correo ha sido verificado exitosamente."}