from fastapi import APIRouter, HTTPException, Query, Depends, Request
from app.core.email_validation import is_valid_email
from app.core.security import verify_token
from app.core.database import get_odoo_connection
from app.core.email_utils import send_final_match_email
from app.services.odoo_service import execute_odoo_method

import logging

from app.services.sqlite_service import update_user_record

router = APIRouter(prefix="/contacts", tags=["contacts"])
logger = logging.getLogger(__name__)

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
        {'fields': ["id", "name", "company_registry", "l10n_bo_district", "mobile", "email", "city", "state_id", "country_id"]}
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
            "city": contact.get("city", ""),
            "state_id": contact.get("state_id", ""),
            "country_id": contact.get("country_id", "")
        }
        results.append(new_contact)
    
    return {"total": len(results), "contacts": results}


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: int,
    request: Request,
    token_payload: dict = Depends(verify_token)
):

    try:
        logger.info("Iniciando actualización de contacto en Odoo. contact_id=%s", contact_id)

        # user_id del token
        user_id = token_payload.get("user_id")
        if not user_id:
            logger.error("El token no contiene 'user_id'.")
            raise HTTPException(status_code=403, detail="Token inválido o sin user_id.")

        # Leer body
        data = await request.json()
        logger.debug("Body recibido: %s", data)

        # Validaciones mínimas
        if "name" not in data or "last_name" not in data:
            logger.error("Campos 'name' o 'last_name' ausentes en el body.")
            raise HTTPException(status_code=400, detail="Both 'name' and 'last_name' fields are required.")
        if "email" not in data:
            logger.error("Campo 'email' ausente en el body.")
            raise HTTPException(status_code=400, detail="The 'email' field is required.")

        # Limpieza
        first_name = data["name"].strip()
        last_name = data["last_name"].strip()
        email = data["email"].strip()

        if not first_name or not last_name:
            logger.error("name o last_name vacíos.")
            raise HTTPException(status_code=400, detail="Fields 'name' and 'last_name' cannot be empty.")
        if not email:
            logger.error("El campo 'email' está vacío.")
            raise HTTPException(status_code=400, detail="The 'email' field cannot be empty.")

        # Validar email
        if not is_valid_email(email):
            logger.error("Email con formato no válido: %s", email)
            raise HTTPException(status_code=400, detail="The email format is not valid.")

        # Armar el payload para Odoo
        full_name_for_odoo = f"{first_name} {last_name}"
        update_fields = {
            "name": full_name_for_odoo,
            "email": email
        }

        # Opcionales
        direction_val = ""
        if "direction" in data:
            direction_val = data["direction"].strip()
            if direction_val:
                update_fields["l10n_bo_district"] = direction_val  # Odoo

        mobile_val = ""
        if "mobile" in data:
            mobile_val = str(data["mobile"]).strip()
            if mobile_val:
                update_fields["mobile"] = mobile_val

        ci_val = ""
        if "ci" in data:
            ci_val = data["ci"].strip()
            if ci_val:
                update_fields["company_registry"] = ci_val

        if "city" in data:
            city_val = str(data["city"]).strip()
            if city_val:
                update_fields["city"] = city_val
            else:
                logger.error("El campo 'city' está vacío.")
                raise HTTPException(status_code=400, detail="The 'city' field cannot be empty.")

        if "state_id" in data:
            try:
                state_id = int(data["state_id"])
                update_fields["state_id"] = state_id
            except (TypeError, ValueError):
                logger.error("El 'state_id' no es un número válido: %s", data["state_id"])
                raise HTTPException(status_code=400, detail="The 'state_id' field must be a valid number.")

        # País por defecto (ejemplo: 29 => Bolivia)
        update_fields["country_id"] = 29

        logger.debug("Campos a actualizar en Odoo: %s", update_fields)

        # Conectar a Odoo
        conn = get_odoo_connection()
        logger.info("Actualizando contacto en Odoo con ID=%s", contact_id)
        result = execute_odoo_method(
            conn, 'res.partner', 'write',
            [[contact_id], update_fields]
        )
        if not result:
            logger.error("No se pudo actualizar el contacto en Odoo contact_id=%s", contact_id)
            raise HTTPException(status_code=500, detail="Could not update contact in Odoo.")

        logger.info("Contacto en Odoo actualizado correctamente. contact_id=%s", contact_id)

        # --- Sincronizar en SQLite ---
        logger.debug("Sincronizando datos en SQLite para user_id=%s", user_id)

        try:
            update_user_record(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                mobile=mobile_val,
                ci=ci_val,
                street=direction_val 
            )
            logger.info("Datos sincronizados en SQLite para user_id=%s", user_id)
        except Exception as ex:
            logger.exception("Fallo la actualización en SQLite para user_id=%s", user_id)
            raise HTTPException(
                status_code=500,
                detail=f"Contacto actualizado en Odoo, pero falló la actualización en SQLite: {str(ex)}"
            )

        return {
            "detail": "Contact updated successfully."
        }

    except HTTPException as http_err:
        logger.error("HTTPException en update_contact (contact_id=%s): %s", contact_id, http_err.detail)
        raise http_err
    except Exception as e:
        logger.exception("Error interno al actualizar contacto (contact_id=%s):", contact_id)
        raise HTTPException(status_code=500, detail=str(e))


    
 # DE ACA PARA ABAJO ES NUEVO------------------------------------------------------------------------------------------   


@router.post("/create")
async def create_contact(request: Request):
    try:
        # Leer y validar el JSON recibido
        data = await request.json()
        nombre = data.get("name", "").strip()
        apellido = data.get("last_name", "").strip()
        pais = data.get("country", "").strip()
        ciudad = data.get("city", "").strip()
        phone = data.get("phone", "").strip()
        correo = data.get("email", "").strip()

        # Validación de campos obligatorios
        if not (nombre and apellido and pais and ciudad and phone and correo):
            raise HTTPException(
                status_code=400,
                detail="Todos los campos (name, last_name, country, city, phone y email) son obligatorios."
            )
        logger.info("Datos recibidos para crear contacto: %s %s", nombre, apellido)

        # Combinar nombre y apellido para formar el 'name' del contacto en Odoo
        full_name = f"{nombre} {apellido}"
        logger.debug("Nombre completo para contacto: %s", full_name)

        # Conectar a Odoo
        conn = get_odoo_connection()

        # Validar que el correo no exista ya en Odoo
        existing_contacts = execute_odoo_method(
            conn,
            'res.partner',
            'search_read',
            [[('email', '=', correo)]],
            {'fields': ['id']}
        )
        if existing_contacts:
            raise HTTPException(status_code=400, detail=f"El correo '{correo}' ya está registrado en Odoo.")
        logger.debug("Correo validado, no existe registro previo con el mismo correo.")

        # Buscar el país en Odoo usando el nombre (ilike para búsqueda flexible)
        country_records = execute_odoo_method(
            conn,
            'res.country',
            'search_read',
            [[('name', 'ilike', pais)]],
            {'fields': ['id', 'name']}
        )
        if not country_records:
            raise HTTPException(status_code=404, detail=f"País '{pais}' no encontrado en Odoo.")
        country_id = country_records[0]['id']
        logger.info("País encontrado: %s con ID: %s", country_records[0]['name'], country_id)

        # Validar que el correo no exista ya en Odoo
        existing_contacts = execute_odoo_method(
            conn,
            'res.partner',
            'search_read',
            [[('email', '=', correo)]],
            {'fields': ['id']}
        )
        if existing_contacts:
            # RUTA DE ACTUALIZACIÓN: Si existe un contacto con ese correo, se actualiza
            contact_id = existing_contacts[0]['id']
            logger.info("Contacto existente con email '%s' encontrado. ID: %s. Se procederá a actualizar.", correo, contact_id)
            
            # Preparar el payload para actualizar el contacto en Odoo:
            # Se actualizan los campos "city", "country_id" y "mobile" (puedes agregar más si es necesario)
            update_payload = {
                "city": ciudad,
                "country_id": country_id,
                "mobile": phone
            }
            logger.debug("Payload para actualizar contacto existente: %s", update_payload)
            update_result = execute_odoo_method(
                conn,
                'res.partner',
                'write',
                [[contact_id], update_payload]
            )
            logger.info("Resultado de la actualización en Odoo: %s", update_result)
            if not update_result:
                raise HTTPException(status_code=500, detail="No se pudo actualizar el contacto en Odoo.")
            
            # Leer los datos actualizados del contacto
            updated_contact = execute_odoo_method(conn, "res.partner", "read", [[contact_id]])
            if not updated_contact:
                raise HTTPException(status_code=500, detail="Error al leer el contacto actualizado.")
            logger.debug("Datos del contacto actualizado: %s", updated_contact[0]['id'])
            
            # Enviar correo de invitación usando la plantilla de torneo (url_final_match_template.html)
            logger.info("Enviando correo de invitación para el final del torneo al contacto actualizado.")
            send_final_match_email(
                to_email=correo,
                subject="ENLACE DE LA FINAL TORNEO AMISTOSO DE VERANO",
                extra_params={}  # Puedes agregar parámetros adicionales si la plantilla los requiere
            )
            
            return {
                "detail": "Contacto actualizado y correo enviado con éxito.",
                "contact_id": contact_id
            }
        else:
            # RUTA DE CREACIÓN: Si no existe un contacto con ese correo, se crea uno nuevo
            logger.debug("No se encontró contacto existente; se procederá a crear uno nuevo.")
            contact_payload = {
                "name": full_name,     # Se guarda la combinación de name y last_name
                "mobile": phone,       # Campo 'mobile'
                "email": correo,       # Campo 'email'
                "city": ciudad,        # Campo 'city'
                "country_id": country_id  # Campo 'country_id'
            }
            logger.debug("Payload para crear contacto en Odoo: %s", contact_payload)
            new_contact_id = execute_odoo_method(conn, "res.partner", "create", [contact_payload])
            logger.info("ID de nuevo contacto creado en Odoo: %s", new_contact_id)
            if not new_contact_id:
                raise HTTPException(status_code=500, detail="No se pudo crear el contacto en Odoo.")

            # Leer los datos del contacto recién creado
            created_contact = execute_odoo_method(conn, "res.partner", "read", [[new_contact_id]])
            if not created_contact:
                raise HTTPException(status_code=500, detail="Error al leer el contacto creado.")
            logger.debug("Datos del contacto creado: %s", created_contact[0]['id'])

            # Enviar correo de invitación usando la plantilla de torneo (url_final_match_template.html)
            logger.info("Enviando correo de invitación para el final del torneo.")
            send_final_match_email(
                to_email=correo,
                subject="ENLACE DE LA FINAL TORNEO AMISTOSO DE VERANO",
                extra_params={}  # Puedes agregar parámetros adicionales si la plantilla los requiere
            )

            return {
                "detail": "Contacto creado y correo enviado con éxito.",
                "contact_id": new_contact_id
            }

    except HTTPException as http_err:
        logger.error("HTTPException en create_contact: %s", http_err.detail)
        raise http_err
    except Exception as e:
        logger.exception("Error interno al crear contacto:")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")





@router.get("/{contact_id}")
async def get_contact_details(
    contact_id: int,
):
    """
    Obtiene todos los detalles de un contacto en Odoo a partir de su ID.
    
    Parámetros:
      - contact_id: ID del contacto (entero).
      - Se requiere un token válido (token_payload).
    
    Devuelve:
      - Un JSON con todos los campos del contacto.  
        Nota: Si se pasa una lista vacía en 'fields', Odoo devuelve todos los campos disponibles.
    """
    # Conectar a Odoo
    conn = get_odoo_connection()
    
    # Obtener todos los campos del contacto (lista vacía => todos)
    contact_data = execute_odoo_method(
        conn,
        'res.partner',
        'read',
        [[contact_id]],  # El ID del contacto dentro de una lista
        {'fields': []}   # Lista vacía para solicitar todos los campos
    )
    
    if not contact_data:
        raise HTTPException(status_code=404, detail="Contacto no encontrado.")
    
    return contact_data[0]




 # ------------------------------------------------------------------------------------------   


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
# def get_contact(contact_id: int):
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

# Actualizar un contacto
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
