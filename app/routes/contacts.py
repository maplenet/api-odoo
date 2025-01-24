from fastapi import APIRouter, HTTPException, Query, Depends
from app.core.security import verify_token
from app.core.database import get_odoo_connection
from app.core.email_utils import send_email

router = APIRouter(prefix="/contacts", tags=["contacts"])

# Todo: Verificar de todos los endpoints las validaciones de los campos requeridos

# Buscar contactos por nombre o datos específicos
@router.post("/search")
def search_contacts(search: dict, str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        query = search.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="El campo 'query' es requerido.")
        limit = search.get("limit", 10)

        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'name_search',
            [query],
            {'limit': limit}
        )
        return {"contacts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Obtener IDs de todos los contactos
@router.get("/ids")
def get_contact_ids(username: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'search',
            [[]]
        )
        return {"contacts": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# TODO: Validar que no exista un contacto con el mismo email o móvil
# Crear un nuevo contacto
@router.post("/create")
def create_contact(contact: dict, str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        contact_id = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'create',
            [contact]
        )
        return {"contact_id": contact_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# TODO: Validar que no exista un contacto con el mismo email o móvil
# Crear un nuevo contacto básico
# @router.post("/create_basic")
# def create_contact_basic(contact: dict, str = Depends(verify_token)):
#     conn = get_odoo_connection()
#     try:
#         email = contact.get("email")
#         mobile = contact.get("mobile")
#         if not email or not mobile:
#             raise HTTPException(status_code=400, detail="Los campos 'email' y 'mobile' son requeridos.")

#         existing_contacts = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'search_count',
#             [[
#                 '|', ['email', '=', email], ['mobile', '=', mobile]
#             ]]
#         )
#         if existing_contacts > 0:
#             raise HTTPException(status_code=400, detail="Ya existe un contacto con el mismo email o móvil.")

#         contact_id = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'create',
#             [contact]
#         )
#         return {
#             "contact_id": contact_id,
#             "user": email,
#             "password": mobile
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# Todo: COnvertir todas las funciones en Funciones asincronas
@router.post("/create_basic")
def create_contact_basic(contact: dict, str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Validar los campos requeridos
        email = contact.get("email")
        mobile = contact.get("mobile")
        if not email or not mobile:
            raise HTTPException(status_code=400, detail="Los campos 'email' y 'mobile' son requeridos.")

        # Verificar si ya existe un contacto con el mismo email o móvil
        existing_contacts = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'search_count',
            [['|', ['email', '=', email], ['mobile', '=', mobile]]]
        )
        if existing_contacts > 0:
            raise HTTPException(status_code=400, detail="Ya existe un contacto con el mismo email o móvil.")

        # Crear el contacto
        contact_id = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'create',
            [contact]
        )

        # Enviar correo de notificación
        subject = "¡Contacto registrado exitosamente!"
        body = f"""
        <html>
        <body>
            <h1>Hola {contact.get('name', 'Usuario')}!</h1>
            <p>Tu contacto ha sido registrado exitosamente en nuestro sistema, OH YEAHaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.</p>
            <p>Si tienes alguna pregunta, no dudes en contactarnos.</p>
        </body>
        </html>
        """
        send_email(to_email=email, subject=subject, body=body)

        return {
            "contact_id": contact_id,
            "message": f"Contacto creado exitosamente y correo enviado a {email}"
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Error interno: {error_trace}")


# Obtener todos los contactos
@router.get("/")
def get_contacts(username: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'search_read',
            [[]]
        )
        return {"contacts": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Obtener contactos paginados y filtrados
@router.get("/paginated")
def get_contacts_paginated(
    offset: int = Query(0), 
    limit: int = Query(10), 
    query: str = Query(None),
    str = Depends(verify_token)
):
    conn = get_odoo_connection()
    try:
        domain = []
        if query:
            domain = ['|', ['name', 'ilike', query], ['parent_id.name', 'ilike', query]]
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'search_read',
            [domain],
            {'offset': offset, 'limit': limit, 'fields': ['name', 'email', 'phone', 'parent_id']}
        )
        return {"contacts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Obtener contactos paginados filtrados por nombre
@router.get("/paginated/name")
def get_contacts_paginated_by_name(
    offset: int = Query(0), 
    limit: int = Query(10), 
    query: str = Query(None),
    str = Depends(verify_token)
):
    conn = get_odoo_connection()
    try:
        domain = []
        if query:
            domain = [['name', 'ilike', query]]
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'search_read',
            [domain],
            {'offset': offset, 'limit': limit, 'fields': ['name', 'email', 'phone']}
        )
        return {"contacts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Obtener detalles específicos de todos los contactos
@router.get("/list/details")
def get_contacts_details(username: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'search_read',
            [[]],
            {'fields': ['name', 'email', 'mobile', 'street', 'city', 'country_id', 'pos_order_ids', 'sale_order_ids']}
        )
        return {"contacts": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Obtener detalles de un contacto
@router.get("/{contact_id}")
def get_contact(contact_id: int, str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'read',
            [[contact_id]]
        )
        return {"contact": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Actualizar un contacto
@router.patch("/{contact_id}")
def update_contact(contact_id: int, contact: dict, token:str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'write',
            [[contact_id], contact]
        )
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Eliminar un contacto
@router.delete("/{contact_id}")
def delete_contact(contact_id: int, str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',
            'unlink',
            [[contact_id]]
        )
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
