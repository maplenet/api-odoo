from fastapi import APIRouter, HTTPException, Query, Depends, Request
from app.core.email_validation import is_valid_email
from app.core.security import verify_token
from app.core.database import get_odoo_connection
from app.services.odoo_service import execute_odoo_method

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.get("/search")
async def search_contacts(
    email: str = Query(..., description="Correo electrónico a buscar"),
    # token_payload: dict = Depends(verify_token)
):
    """
    Busca en Odoo todos los contactos cuyo correo electrónico contenga (case-insensitive)
    el valor indicado en 'email'. Además, para cada contacto se verifica si está asociado
    a un usuario; si lo está, se devuelve el id del usuario, de lo contrario se devuelve "".
    
    Devuelve un JSON con:
      - total: Cantidad total de contactos encontrados.
      - contacts: Una lista de objetos con la siguiente estructura:
            {
              "id_contact": <id del contacto>,
              "id_user": <id del usuario asociado o "" si no existe>,
              "name": <nombre del contacto>,
              "company_registry": <valor de company_registry>,
              "l10n_bo_district": <valor de l10n_bo_district>,
              "mobile": <número de móvil>,
              "email": <correo electrónico>,
              "vat": <valor del campo vat>,
              "l10n_latam_identification_type_id": <valor>,
              "l10n_bo_business_name": <valor>
            }
    """
    # Validación inicial: el Query ya asegura que se envíe 'email'
    if not email:
        raise HTTPException(status_code=400, detail="El campo 'email' es obligatorio.")
    
    # Conectar a Odoo
    conn = get_odoo_connection()
    
    # Buscar contactos cuyo correo contenga (ilike) el valor proporcionado
    contacts = execute_odoo_method(
        conn,
        'res.partner',
        'search_read',
        [[('email', 'ilike', email)]],
        {'fields': ["id", "name", "company_registry", "l10n_bo_district", "mobile", "email", "vat"]}
    )

    
    total = len(contacts)
    if total == 0:
        raise HTTPException(status_code=404, detail="No se encontraron contactos para el correo proporcionado.")
    
    # Extraer los IDs de los contactos para la búsqueda masiva de usuarios asociados
    contact_ids = [contact["id"] for contact in contacts]
    
    # Buscar en res.users todos los usuarios cuyo partner_id esté en la lista de contact_ids
    associated_users = execute_odoo_method(
        conn,
        'res.users',
        'search_read',
        [[('partner_id', 'in', contact_ids)]],
        {'fields': ['id', 'partner_id']}
    )
    
    # Crear un diccionario para mapear partner_id al id de usuario
    partner_to_user = { user["partner_id"][0]: user["id"] for user in associated_users if user.get("partner_id") }
    
    results = []
    # Recorrer los contactos y agregar el id_user si existe
    for contact in contacts:
        id_user = partner_to_user.get(contact["id"], "")
        new_contact = {
            "id_contact": contact["id"],
            "id_user": id_user,
            "name": contact.get("name", ""),
            "ci": contact.get("company_registry", ""),
            "direction": contact.get("l10n_bo_district", ""),
            "mobile": contact.get("mobile", ""),
            "email": contact.get("email", ""),
            "nit_ci_cex": contact.get("vat", ""),
            "type_doc": contact.get("l10n_latam_identification_type_id", ""),
            "business_name": contact.get("l10n_bo_business_name", "")
        }
        results.append(new_contact)
    
    return {"total": len(results), "contacts": results}


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: int, request: Request, 
    # token_payload: dict = Depends(verify_token)
    ):
    """
    Actualiza ciertos campos de un contacto en Odoo.
    
    Se requieren:
      - El 'contact_id' en la URL.
      - En el body, se debe enviar al menos:
          - "name": El nombre del contacto (no vacío ni solo espacios).
          - "email": El correo electrónico (no vacío, sin espacios y en formato válido).
      - Otros campos opcionales se actualizarán si se proporcionan y no están vacíos.
      
    Devuelve un JSON con:
      - detail: Mensaje de éxito.
    """
    try:
        # Leer el JSON enviado en la solicitud
        data = await request.json()

        # Validar que se envíen los campos obligatorios "name" y "email"
        if "name" not in data:
            raise HTTPException(status_code=400, detail="The 'name' field is required.")
        if "email" not in data:
            raise HTTPException(status_code=400, detail="The 'email' field is required.")

        # Eliminar espacios en blanco y validar que no queden vacíos
        name = data["name"].strip()
        email = data["email"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="The 'name' field cannot be empty.")
        if not email:
            raise HTTPException(status_code=400, detail="The 'email' field cannot be empty.")

        # Validar el formato de email utilizando la función is_valid_email
        if not is_valid_email(email):
            raise HTTPException(status_code=400, detail="The email format is not valid.")

        # Preparar un diccionario con los campos a actualizar
        update_fields = {
            "name": name,
            "email": email
        }

        # Actualizar opcionalmente otros campos si se envían
        if "mobile" in data:
            # Asegurarse de tratar el dato como string
            mobile = str(data["mobile"]).strip()
            if mobile:
                update_fields["mobile"] = mobile

        if "ci" in data:
            # Convertir a string para poder usar strip() y validar
            company_registry = str(data["ci"]).strip()
            if company_registry:
                update_fields["company_registry"] = company_registry

        if "direction" in data:
            district = str(data["direction"]).strip()
            if district:
                update_fields["l10n_bo_district"] = district

        # Conectar a Odoo
        conn = get_odoo_connection()

        # Actualizar el contacto usando el método 'write' de Odoo
        result = execute_odoo_method(
            conn,
            'res.partner',
            'write',
            [[contact_id], update_fields]
        )
        if not result:
            raise HTTPException(status_code=500, detail="Could not update contact in Odoo.")

        return {"detail": "Contact updated successfully."}

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        # Se envía solo el mensaje de error sin prefijo adicional.
        raise HTTPException(status_code=500, detail=str(e))
    
    






# Todo: Verificar de todos los endpoints las validaciones de los campos requeridos

# # Buscar contactos por nombre o datos específicos
# @router.post("/search")
# def search_contacts(search: dict, str = Depends(verify_token)):
#     conn = get_odoo_connection()
#     try:
#         query = search.get("query")
#         if not query:
#             raise HTTPException(status_code=400, detail="El campo 'query' es requerido.")
#         limit = search.get("limit", 10)

#         result = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'name_search',
#             [query],
#             {'limit': limit}
#         )
#         return {"contacts": result}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # Obtener IDs de todos los contactos
# @router.get("/ids")
# def get_contact_ids(username: str = Depends(verify_token)):
#     conn = get_odoo_connection()
#     try:
#         result = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'search',
#             [[]]
#         )
#         return {"contacts": result, "total": len(result)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # TODO: Validar que no exista un contacto con el mismo email o móvil
# # Crear un nuevo contacto
# @router.post("/create")
# def create_contact(contact: dict, str = Depends(verify_token)):
#     conn = get_odoo_connection()
#     try:
#         contact_id = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'create',
#             [contact]
#         )
#         return {"contact_id": contact_id}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    

# # Obtener contactos paginados y filtrados
# @router.get("/paginated")
# def get_contacts_paginated(
#     offset: int = Query(0), 
#     limit: int = Query(10), 
#     query: str = Query(None),
#     str = Depends(verify_token)
# ):
#     conn = get_odoo_connection()
#     try:
#         domain = []
#         if query:
#             domain = ['|', ['name', 'ilike', query], ['parent_id.name', 'ilike', query]]
#         result = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'search_read',
#             [domain],
#             {'offset': offset, 'limit': limit, 'fields': ['name', 'email', 'phone', 'parent_id']}
#         )
#         return {"contacts": result}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # Obtener contactos paginados filtrados por nombre
# @router.get("/paginated/name")
# def get_contacts_paginated_by_name(
#     offset: int = Query(0), 
#     limit: int = Query(10), 
#     query: str = Query(None),
#     str = Depends(verify_token)
# ):
#     conn = get_odoo_connection()
#     try:
#         domain = []
#         if query:
#             domain = [['name', 'ilike', query]]
#         result = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'search_read',
#             [domain],
#             {'offset': offset, 'limit': limit, 'fields': ['name', 'email', 'phone']}
#         )
#         return {"contacts": result}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # Obtener detalles específicos de todos los contactos
# @router.get("/list/details")
# def get_contacts_details(username: str = Depends(verify_token)):
#     conn = get_odoo_connection()
#     try:
#         result = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'search_read',
#             [[]],
#             {'fields': ['name', 'email', 'mobile', 'street', 'city', 'country_id', 'pos_order_ids', 'sale_order_ids']}
#         )
#         return {"contacts": result, "total": len(result)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    
# # Obtener detalles de un contacto
# @router.get("/{contact_id}")
# def get_contact(contact_id: int, str = Depends(verify_token)):
#     conn = get_odoo_connection()
#     try:
#         result = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'read',
#             [[contact_id]]
#         )
#         return {"contact": result}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # Actualizar un contacto
# @router.patch("/{contact_id}")
# def update_contact(contact_id: int, contact: dict, token:str = Depends(verify_token)):
#     conn = get_odoo_connection()
#     try:
#         result = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'write',
#             [[contact_id], contact]
#         )
#         return {"success": result}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # Eliminar un contacto
# @router.delete("/{contact_id}")
# def delete_contact(contact_id: int, str = Depends(verify_token)):
#     conn = get_odoo_connection()
#     try:
#         result = conn['models'].execute_kw(
#             conn['db'], conn['uid'], conn['password'],
#             'res.partner',
#             'unlink',
#             [[contact_id]]
#         )
#         return {"success": result}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
