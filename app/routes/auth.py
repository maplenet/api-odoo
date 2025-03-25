import aiosqlite
from app.core.logging_config import logger
from fastapi import APIRouter, HTTPException, Request, Depends, Response
from jose import jwt, JWTError
from datetime import datetime, timedelta
from app.core.security import settings 
from app.core.email_utils import send_reset_password_email
from app.core.email_validation import is_valid_email
from app.core.security import create_access_token, create_password_reset_token, verify_token, oauth2_scheme, blacklisted_tokens
from app.core.database import get_odoo_connection
from app.routes.users import _is_valid_password
from app.services.api_service import update_customer_password_in_pontis
from app.services.sqlite_service import update_user_password
from app.services.token_service import get_token_record, mark_token_as_used, revoke_token, store_token
from app.services.verification_service import handle_verification_request, verify_code_and_email

router = APIRouter(tags=["authentication"])

from fastapi.responses import JSONResponse

@router.post("/login")
async def login(request: Request, response: Response):
    body = await request.json()
    email = body.get("email")
    password = body.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Se requieren 'email' y 'password'.")

    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Correo inválido.")

    try:
        # Conectar con Odoo
        conn = get_odoo_connection()
        if "common" not in conn or "models" not in conn:
            raise HTTPException(status_code=500, detail="Error en la conexión con Odoo.")

        # Autenticar usuario en Odoo
        user_id = conn["common"].authenticate(conn["db"], email, password, {})
        if not user_id:
            raise HTTPException(status_code=401, detail="Credenciales inválidas.")

        # Obtener información del usuario
        users = conn["models"].execute_kw(
            conn["db"], conn["uid"], conn["password"],
            "res.users", "search_read", [[["id", "=", user_id]]],
            {"fields": ["id", "name", "login", "email", "partner_id"]}
        )
        if not users:
            raise HTTPException(status_code=404, detail="No se encontró el usuario.")
        user = users[0]

        # Generar token de acceso
        access_token = create_access_token(user["id"], user["partner_id"][0])
        expires_at = (datetime.now() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)).isoformat()

        # Almacenar el token en la tabla 'tokens'
        # (Puedes obtener client_ip y user_agent del request si lo deseas)
        store_token(access_token, user["id"], "access", expires_at)

        # Configurar respuesta con cookie
        response = JSONResponse(
            content={
                "user_id": user["id"],
                "partner_id": user["partner_id"][0],
                "access_token": access_token,
                "detail": "Proceso exitoso."
            }
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=False,
            secure=True,
            samesite="strict"
        )

        return response

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
@router.post("/login_internal")
async def login_internal(request: Request, response: Response):
    """
    Endpoint exclusivo para usuarios internos.
    Se autentica al usuario en Odoo y, además, se verifica que el usuario pertenezca
    al grupo interno (base.group_user). Si no es así, se rechaza el acceso.
    """
    body = await request.json()
    email = body.get("email")
    password = body.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Se requieren 'email' y 'password'.")

    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Correo inválido.")

    try:
        # Conectar con Odoo
        conn = get_odoo_connection()
        if "common" not in conn or "models" not in conn:
            raise HTTPException(status_code=500, detail="Error en la conexión con Odoo.")

        # Autenticar usuario en Odoo
        user_id = conn["common"].authenticate(conn["db"], email, password, {})
        if not user_id:
            raise HTTPException(status_code=401, detail="Credenciales inválidas.")

        # Obtener información del usuario, incluyendo grupos (agregamos groups_id)
        user_data = conn["models"].execute_kw(
            conn["db"], conn["uid"], conn["password"],
            "res.users", "search_read", [[["id", "=", user_id]]],
            {"fields": ["id", "name", "login", "email", "partner_id", "groups_id"]}
        )
        if not user_data:
            raise HTTPException(status_code=404, detail="No se encontró el usuario.")
        user = user_data[0]

        # Obtener el ID del grupo interno "base.group_user"
        internal_group = conn["models"].execute_kw(
            conn["db"], conn["uid"], conn["password"],
            "ir.model.data", "search_read",
            [[('model', '=', 'res.groups'), ('module', '=', 'base'), ('name', '=', 'group_user')]],
            {"fields": ["res_id"], "limit": 1}
        )
        if not internal_group:
            raise HTTPException(status_code=500, detail="No se encontró el grupo interno.")
        internal_group_id = internal_group[0]["res_id"]

        # Verificar que el usuario pertenezca al grupo interno
        # Los grupos se retornan como una lista de IDs.
        if internal_group_id not in user.get("groups_id", []):
            raise HTTPException(status_code=403, detail="No estás autorizado para usar este portal.")

        # Si la verificación es correcta, generar token de acceso
        access_token = create_access_token(user["id"], user["partner_id"][0])
        expires_at = (datetime.now() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)).isoformat()

        # Almacenar el token en la tabla 'tokens'
        store_token(access_token, user["id"], "access", expires_at)

        # Configurar respuesta con cookie
        response = JSONResponse(
            content={
                "user_id": user["id"],
                "partner_id": user["partner_id"][0],
                "access_token": access_token,
                "detail": "Proceso exitoso."
            }
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=False,
            secure=False,
            samesite="lax"
        )

        return response

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")



@router.post("/logout/{id_user}")
def logout(id_user: int, response: Response, token: str = Depends(oauth2_scheme)):
    """
    Cierra la sesión del usuario.
    Se recibe el 'id_user' por ruta y se compara con el 'user_id' del token.
    Si el token ya ha sido revocado, se retorna un error.
    """
    # Obtener el payload del token
    payload = verify_token(token)
    token_user_id = payload.get("user_id")
    
    if int(id_user) != int(token_user_id):
        raise HTTPException(status_code=403, detail="No autorizado para cerrar sesión de otro usuario.")
    
    # Obtener el registro del token de la base de datos
    token_record = get_token_record(token)
    if token_record is None:
        raise HTTPException(status_code=401, detail="Token no encontrado.")
    if token_record.get("revoked_at") is not None:
        raise HTTPException(status_code=401, detail="El token ya fue revocado.")

    # Revocar el token
    try:
        revoke_token(token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al revocar token: {str(e)}")
    
    response.delete_cookie(key="access_token")
    return {"detail": "Sesión cerrada exitosamente."}


@router.post("/verify-email")
async def verify_email(request: Request):
    body = await request.json()  # Extraer el cuerpo de la solicitud como JSON
    email = body.get("email")   # Obtener el campo "email" del JSON

    # Verificar si el campo "email" está presente
    if not email:
        raise HTTPException(status_code=400, detail="El campo 'email' es obligatorio.")

    # Validar el formato del correo
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Correo inválido.")
    
    # Verificar que el correo sea unico en los contactos de odoo, es decir que no exista
    conn = get_odoo_connection()
    contacts = conn['models'].execute_kw(
        conn['db'], conn['uid'], conn['password'],
        'res.partner', 'search_read', [[['email', '=', email]]]
    )   
    if contacts:
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")
    
    # Manejar la lógica de verificación
    try:
        result = handle_verification_request(email)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post("/verify-code")
async def verify_code(request: Request):
    body = await request.json()
    email = body.get("email")
    code = body.get("code")

    # Verificar si ambos campos están presentes
    if not email or not code:
        raise HTTPException(status_code=400, detail="Los campos 'email' y 'code' son obligatorios.")

    # Lógica de verificación
    result = verify_code_and_email(email, code)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result

@router.post("/forgot_password")
async def forgot_password(request: Request):
    """
    Genera un token de restablecimiento y envía un email con un enlace para recuperar la contraseña.
    Se responde siempre con un mensaje genérico.
    """
    try:
        body = await request.json()
        email = body.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="El campo 'email' es obligatorio.")

        # Verificar si el usuario existe en la base de datos 'users' (usando aiosqlite)
        user = None
        async with aiosqlite.connect("verification.db") as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT user_id, email FROM users WHERE email = ?", (email,)) as cursor:
                user = await cursor.fetchone()
        generic_response = {"detail": "Si existe una cuenta asociada, se han enviado instrucciones al correo."}
        if not user:
            return generic_response

        user_id = user["user_id"]
        # Generar token de restablecimiento (JWT) con expiración corta
        reset_token = create_password_reset_token(user_id)
        expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()

        # Almacenar el token de restablecimiento en la tabla 'tokens'
        store_token(reset_token, user_id, "password_reset", expires_at)

        # Construir el enlace de restablecimiento (ajusta la URL a tu frontend)
        reset_link = f"https://maplenet.com.bo/reset-password?token={reset_token}"
        # reset_link = f"http://192.168.10.200:4321/reset-password?token={reset_token}"
        send_reset_password_email(
            to_email=email,
            subject="Recupera tu contraseña",
            reset_link=reset_link
        )

        send_reset_password_email(
            to_email="recuperapassword@maplenet.com.bo",
            subject=f"Recupera tu contraseña - {email}",
            reset_link=reset_link
        )


        return generic_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")



@router.post("/reset_password")
async def reset_password(request: Request):
    """
    Recibe el token de restablecimiento y las nuevas contraseñas, valida el token,
    actualiza la contraseña en Odoo, en la base de datos 'users' y en Pontis,
    y marca el token como usado.
    """
    logger.info("Iniciando endpoint [reset_password]...")
    try:
        body = await request.json()
        logger.debug("Body recibido: %s", body)

        reset_token = body.get("token")
        new_password = body.get("new_password")
        verify_password = body.get("verify_password")

        if not reset_token or not new_password or not verify_password:
            logger.warning("Campos obligatorios faltantes en la petición: token=%s, new_password=%s, verify_password=%s",
                           reset_token, bool(new_password), bool(verify_password))
            raise HTTPException(
                status_code=400,
                detail="Los campos 'token', 'new_password' y 'verify_password' son obligatorios."
            )

        logger.debug("Validando que las contraseñas coincidan...")
        if new_password != verify_password:
            logger.warning("Las contraseñas no coinciden.")
            raise HTTPException(status_code=400, detail="La nueva contraseña y su verificación no coinciden.")

        logger.debug("Validando formato de la nueva contraseña...")
        if not _is_valid_password(new_password):
            logger.warning("La nueva contraseña no cumple con el formato requerido.")
            raise HTTPException(
                status_code=400,
                detail="The password must have at least 8 characters and max 40 characteres, "
                       "including 1 uppercase, 1 lowercase and 1 number."
            )

        logger.debug("Decodificando y verificando el token...")
        try:
            payload = jwt.decode(reset_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        except JWTError:
            logger.error("Token inválido o expirado al decodificar.")
            raise HTTPException(status_code=401, detail="Token inválido o expirado.")

        if payload.get("action") != "reset_password":
            logger.warning("El token no está autorizado para restablecer contraseña. action=%s", payload.get("action"))
            raise HTTPException(status_code=401, detail="Token no autorizado para restablecer contraseña.")

        user_id = payload.get("user_id")
        if not user_id:
            logger.warning("El token no contiene 'user_id'.")
            raise HTTPException(status_code=401, detail="Token inválido: falta 'user_id'.")

        logger.debug("Verificando estado del token en la base de datos...")
        token_record = get_token_record(reset_token)
        if token_record is None:
            logger.warning("Token no encontrado en la base de datos.")
            raise HTTPException(status_code=401, detail="Token no encontrado.")
        if token_record.get("used") == 1:
            logger.warning("El token ya ha sido utilizado.")
            raise HTTPException(status_code=401, detail="El token ya ha sido utilizado.")
        if token_record.get("revoked_at") is not None:
            logger.warning("El token ha sido revocado.")
            raise HTTPException(status_code=401, detail="El token ha sido revocado.")

        logger.info("Actualizando contraseña en Odoo para user_id=%s", user_id)
        odoo_conn = get_odoo_connection()
        update_success = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'write', [[user_id], {'password': new_password}]
        )
        if not update_success:
            logger.error("Fallo al actualizar la contraseña en Odoo para user_id=%s", user_id)
            raise HTTPException(status_code=500, detail="No se pudo actualizar la contraseña en Odoo.")

        logger.debug("Actualizando contraseña en SQLite para user_id=%s", user_id)
        update_user_password(user_id, new_password)

        logger.debug("Actualizando contraseña en Pontis para MAP0%s", user_id)
        pontis_customer_id = "MAP0" + str(user_id)
        response_pontis = await update_customer_password_in_pontis(pontis_customer_id, new_password)
        logger.debug("Respuesta de Pontis: %s", response_pontis)

        logger.debug("Marcando el token como usado en la base de datos...")
        mark_token_as_used(reset_token)

        logger.info("Contraseña restablecida exitosamente para user_id=%s", user_id)
        return {
            "detail": "Contraseña restablecida exitosamente.",
            "pontis_response": response_pontis
        }

    except HTTPException as http_error:
        logger.error("HTTPException en reset_password: %s", http_error.detail)
        raise http_error
    except Exception as e:
        logger.exception("Error interno en reset_password:")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

        