from fastapi import APIRouter, HTTPException, Request, Depends, Response
from app.core.email_validation import is_valid_email
from app.core.security import create_access_token, verify_token, oauth2_scheme, blacklisted_tokens
from app.core.database import get_odoo_connection
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

    # Conectar con Odoo
    try:
        conn = get_odoo_connection()

        if "common" not in conn or "models" not in conn:
            raise HTTPException(status_code=500, detail="Error en la conexión con Odoo.")

        # **Autenticar usuario con Odoo**
        user_id = conn["common"].authenticate(conn["db"], email, password, {})

        if not user_id:
            raise HTTPException(status_code=401, detail="Credenciales inválidas.")  # <-- Aquí lanzamos el error 401 correctamente

        # **Obtener información del usuario desde res.users**
        users = conn["models"].execute_kw(
            conn["db"], conn["uid"], conn["password"],
            "res.users", "search_read", [[["id", "=", user_id]]], 
            {"fields": ["id", "name", "login", "email"]}
        )

        if not users:
            raise HTTPException(status_code=404, detail="No se encontró el usuario.")

        user = users[0]  # Usuario autenticado

        # **Generar token**
        access_token = create_access_token(email)

        # **Configurar respuesta con cookie**
        response = JSONResponse(
            content={
                "user_id": user["id"], 
                # "email": user["email"], 
                # "access_token": access_token, 
                "detail": "Proceso exitoso."
            }
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=False,
            secure=False,  
            samesite="Lax"
        )

        return response

    except HTTPException as http_err:
        raise http_err  

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")




# Refrescar el token de acceso
@router.post("/refresh-token")
def refresh_token(response: Response, token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=400, detail="Token de acceso no proporcionado.")
    
    if token in blacklisted_tokens:
        raise HTTPException(status_code=401, detail="Token inválido.")

    access_token = create_access_token(token)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="Lax"
    )

    return {"detail": "Token de acceso actualizado."}


# @router.post("/logout")
# def logout(token: str = Depends(oauth2_scheme)):
#     blacklisted_tokens.add(token)
#     return {"detail": "Sesión cerrada exitosamente"}

# Cierra sesión y elimina la cookie y el token de la lista negra por medio de un identificador
@router.post("/logout")
def logout(response: Response, token: str = Depends(oauth2_scheme)):
    blacklisted_tokens.add(token)
    response.delete_cookie(key="access_token")
    return {"detail": "Sesión cerrada exitosamente"}

@router.get("/protected")
def protected_route(username: str = Depends(verify_token)):
    return {"detail": f"Bienvenido {username}, esta es una ruta protegida."}

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