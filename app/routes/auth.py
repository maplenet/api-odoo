from fastapi import APIRouter, HTTPException, Request, Depends, Response
from app.core.security import create_access_token, verify_token, oauth2_scheme, blacklisted_tokens
from app.core.database import get_odoo_connection

router = APIRouter(tags=["authentication"])

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
    response.headers["Authorization"] = f"Bearer {access_token}"
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(token: str = Depends(oauth2_scheme)):
    blacklisted_tokens.add(token)
    return {"message": "Sesión cerrada exitosamente"}

@router.get("/protected")
def protected_route(username: str = Depends(verify_token)):
    return {"message": f"Bienvenido {username}, esta es una ruta protegida."}