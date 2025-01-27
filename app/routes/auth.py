from fastapi import APIRouter, HTTPException, Request, Depends, Response
from app.core.email_validation import is_valid_email
from app.core.security import create_access_token, verify_token, oauth2_scheme, blacklisted_tokens
from app.core.database import get_odoo_connection
from app.services.verification_service import handle_verification_request

router = APIRouter(tags=["authentication"])

from fastapi.responses import JSONResponse

@router.post("/login")
async def login(request: Request, response: Response):
    body = await request.json()
    username = body.get("username")
    password = body.get("password")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Se requieren 'username' y 'password'")

    conn = get_odoo_connection()
    contacts = conn['models'].execute_kw(
        conn['db'], conn['uid'], conn['password'],
        'res.partner', 'search_read', [[]]
    )

    matched_contact = next((contact for contact in contacts 
                             if contact['email'] == username and contact['mobile'] == password), None)
    
    if not matched_contact:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    access_token = create_access_token(username)
    
    # Configurar la cookie segura
    response = JSONResponse(content={"user_id": matched_contact['id'], "access_token":access_token, "message": "Inicio de sesión exitoso"})

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=False,          # No accesible por JavaScript
        secure=False,            # Solo en HTTPS
        samesite="Lax",      # Previene CSRF
    )
    return response


@router.post("/refresh")
def refresh_token(username: str = Depends(verify_token)):
    new_access_token = create_access_token(username)
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(token: str = Depends(oauth2_scheme)):
    blacklisted_tokens.add(token)
    return {"message": "Sesión cerrada exitosamente"}

@router.get("/protected")
def protected_route(username: str = Depends(verify_token)):
    return {"message": f"Bienvenido {username}, esta es una ruta protegida."}

from fastapi import APIRouter, HTTPException, Request

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

