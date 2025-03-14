import random
import string
from fastapi import APIRouter, HTTPException, Depends, Request, Query
import re
from app.core.email_validation import is_valid_email
from app.core.security import verify_token
from app.core.database import get_odoo_connection, get_sqlite_connection
from app.core.email_utils import send_pontis_credentials_email
from datetime import datetime, timedelta, timezone
from app.services.api_service import build_customer_data, build_update_customer_data, create_customer_in_pontis, delete_packages_in_pontis, login_to_external_api, update_customer_in_pontis, update_customer_password_in_pontis
from app.services.odoo_service import execute_odoo_method
from app.services.sqlite_service import get_decrypted_password, get_user_record, insert_user_record, update_user_password
from app.services.sqlite_service import update_user_policies  # Asegúrate de importar la función
from app.utils.plans import PRODUCTS
from app.core.logging_config import logger


router = APIRouter(prefix="/users", tags=["users"])

def _is_valid_password(password: str) -> bool:
    # El password debe ser alfanumérico, tener entre 8 y 40 caracteres, 
    # al menos 1 mayúscula, 1 minúscula y 1 número. 
    pattern = r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)[A-Za-z\d]{8,40}$"
    return bool(re.match(pattern, password))


@router.post("/create")
async def create_user(request: Request):
    sqlite_conn = None  # Declaramos la variable por adelantado
    try:
        body = await request.json()
        first_name = body.get("first_name")
        last_name = body.get("last_name")
        email = body.get("email")
        mobile = body.get("mobile")
        password = body.get("password")
        password2 = body.get("verify_password")

        # Validaciones básicas...
        if not first_name:
            raise HTTPException(status_code=400, detail="The 'first_name' field is required.")
        if not last_name:
            raise HTTPException(status_code=400, detail="The 'last_name' field is required.")
        if not email:
            raise HTTPException(status_code=400, detail="The 'email' field is required.")
        if not mobile:
            raise HTTPException(status_code=400, detail="The 'mobile' field is required.")
        if not password:
            raise HTTPException(status_code=400, detail="The 'password' field is required.")
        if not password2:
            raise HTTPException(status_code=400, detail="The 'verify_password' field is required.")

        if first_name.strip() == "" or last_name.strip() == "" or email.strip() == "" or mobile.strip() == "":
            raise HTTPException(status_code=400, detail="The fields cannot be empty.")

        if password != password2:
            raise HTTPException(status_code=400, detail="The passwords do not match.")

        if not _is_valid_password(password):
            raise HTTPException(
                status_code=400, 
                detail="The password must have at least 8 characters and max 40 characteres, including 1 uppercase, 1 lowercase and 1 number."
            )
        
        is_valid_email(email)  # Lanza una excepción si el correo no es válido

        sqlite_conn = get_sqlite_connection()
        cursor = sqlite_conn.cursor()

        # Verificar el correo en la tabla de verification
        cursor.execute("SELECT * FROM verification WHERE email = ? ORDER BY id DESC LIMIT 1", (email,))
        verification_record = cursor.fetchone()

        if not verification_record:
            raise HTTPException(status_code=400, detail="The email has not been registered for verification.")

        status = verification_record[2]
        if status == 0:
            raise HTTPException(status_code=400, detail="The email has not been verified.")

        odoo_conn = get_odoo_connection()

        existing_user = execute_odoo_method(odoo_conn, 'res.users', 'search_count', [[('login', '=', email)]])
        if existing_user:
            raise HTTPException(status_code=400, detail="The email is already registered in the system.")

        group_portal = execute_odoo_method(
            odoo_conn, 'ir.model.data', 'search_read',
            [[('model', '=', 'res.groups'), ('module', '=', 'base'), ('name', '=', 'group_portal')]],
            {'fields': ['res_id'], 'limit': 1}
        )
        if not group_portal:
            raise HTTPException(status_code=500, detail="The Portal group was not found in Odoo.")
        group_portal_id = group_portal[0]['res_id']

        user_id = execute_odoo_method(
            odoo_conn, 'res.users', 'create', [{
                'login': email,
                'name': first_name + " " + last_name,
                'email': email,
                'mobile': mobile,
                'password': password,
                'lang': 'es_MX',
                'groups_id': [(6, 0, [group_portal_id])]
            }],
            kwargs={'context': {'no_reset_password': True}}
        )

        # Insertar el registro del usuario en SQLite (la contraseña se encripta automáticamente)
        insert_user_record(user_id, first_name, last_name, email, mobile, password)

        return {"detail": "Successful process", "id": user_id}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error:: {str(e)}")
    finally:
        if sqlite_conn is not None:  # Solo cerrar si se asignó
            sqlite_conn.close()

@router.patch("/change_password")
async def change_password(request: Request, token_payload: dict = Depends(verify_token)):
    try:
        body = await request.json()
        current_password = body.get("current_password")
        new_password = body.get("new_password")
        verify_password = body.get("verify_password")

        # Validar que se envíen los campos requeridos
        if not current_password or not new_password or not verify_password:
            raise HTTPException(
                status_code=400,
                detail="The fields 'current_password', 'new_password' and 'verify_password' are required."
            )

        # Validar que la nueva contraseña y su verificación coincidan
        if new_password != verify_password:
            raise HTTPException(status_code=400, detail="The new password and your verification do not match.")

        # Validar el formato de la nueva contraseña
        if not _is_valid_password(new_password):
            raise HTTPException(
                status_code=400,
                detail="The password must have at least 8 characters and max 40 characters, including 1 uppercase, 1 lowercase and 1 number."
            )

        # Extraer user_id desde el token
        user_id = token_payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: 'user_id' is missing.")

        # Obtener y desencriptar la contraseña almacenada en SQLite
        try:
            stored_password = get_decrypted_password(user_id)
        except Exception as ex:
            raise HTTPException(status_code=404, detail=str(ex))

        # Comparar la contraseña actual proporcionada con la almacenada
        if current_password != stored_password:
            raise HTTPException(status_code=400, detail="The current password is incorrect.")

        # Actualizar la contraseña en Odoo
        odoo_conn = get_odoo_connection()
        update_success = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'write', [[user_id], {'password': new_password}]
        )
        if not update_success:
            raise HTTPException(status_code=500, detail="Could not update password in Odoo.")

        # Actualizar la contraseña en SQLite
        update_user_password(user_id, new_password)

        # --- NUEVO: Actualizar la contraseña en Pontis ----
        # Construir el customer_id para Pontis
        pontis_customer_id = "MAP0" + str(user_id)
        pontis_update = await update_customer_password_in_pontis(pontis_customer_id, new_password)
        # (Podrías validar la respuesta según lo necesites)
        
        return {
            "detail": "Password changed successfully.",
            "pontis_response": pontis_update
            }

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")
    


@router.get("/get/{user_id}")
async def get_user_with_service(
    user_id: int, 
    token_payload: dict = Depends(verify_token)
    ):

    """
    Obtiene la información del usuario junto con los datos de su servicio.
    Se extrae el 'user_id' del token y se compara con el parámetro.
    Luego se obtiene la información de servicio desde Odoo y se combinan
    con los datos personales obtenidos desde SQLite.
    """
    # Verificar que el user_id en el token coincida con el parámetro
    token_user_id = token_payload.get("user_id")
    if int(user_id) != int(token_user_id):
        raise HTTPException(status_code=403, detail="No está autorizado para consultar otro usuario.")

    # Obtener datos del usuario desde SQLite
    try:
        user_record = get_user_record(user_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # Conectar a Odoo para obtener información adicional (por ejemplo, servicio)
    odoo_conn = get_odoo_connection()
    try:
        # Obtener información del usuario desde Odoo
        user_data = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'read', [[user_id]],
            {'fields': ['email', 'name', 'password', 'mobile', 'l10n_bo_district', 'partner_id']}
        )
        if not user_data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado en Odoo.")
        odoo_user = user_data[0]
        partner_id = odoo_user.get("partner_id", [None])[0]
        if not partner_id:
            raise HTTPException(status_code=404, detail="El usuario no tiene un contacto asociado en Odoo.")

        # Obtener la última factura válida (servicio)
        invoice = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'account.move', 'search_read',
            [[
                ('partner_id', '=', partner_id),
                ('payment_state', '=', 'paid'),
                '|', ('vr_estado', '=', 'send_and_confirm'), ('vr_estado', '=', 'pending')
            ]],
            {
                'fields': ['id', 'invoice_date', 'amount_total', 'invoice_line_ids'],
                'order': 'invoice_date desc',
                'limit': 1
            }
        )

        #invoice = odoo_conn['models'].execute_kw(
        #    odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
        #    'account.move', 'search_read',
        #    [[
        #        ['partner_id', '=', partner_id],
        #        ['payment_state', '=', 'paid'],
        #        ['vr_estado', '=', 'send_and_confirm']
        #    ]],
        #    {
        #        'fields': ['id', 'invoice_date', 'amount_total', 'invoice_line_ids'],
        #        'order': 'invoice_date desc',
        #        'limit': 1
        #    }
        #)
        service = {}
        if invoice:
            invoice = invoice[0]
            # Obtener el producto asociado a la factura
            invoice_line = odoo_conn['models'].execute_kw(
                odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
                'account.move.line', 'read', [invoice['invoice_line_ids']],
                {'fields': ['product_id']}
            )
            product_id = invoice_line[0]['product_id'][0] if invoice_line and invoice_line[0].get('product_id') else None
            # Obtener detalles del producto
            product_data = odoo_conn['models'].execute_kw(
                odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
                'product.product', 'read', [[product_id]],
                {'fields': ['name']}
            ) if product_id else None
            # Calcular fecha de expiración y estado del servicio
            invoice_date = datetime.strptime(invoice['invoice_date'], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            date_expiration = invoice_date + timedelta(days=30)
            today = datetime.now(timezone.utc)
            status = invoice_date <= today <= date_expiration
            service = {
                "id": invoice["id"],
                "id_service": product_id,
                "name": product_data[0]["name"] if product_data else "Desconocido",
                "price_paid": invoice["amount_total"],
                "date_order": invoice["invoice_date"],
                "date_expiration": date_expiration.strftime("%Y-%m-%d"),
                "status": status
            }
        # Construir la respuesta combinada
        response_data = {
            "user": {
                "id": user_record.get("user_id"),
                "email": user_record.get("email"),
                "first_name": user_record.get("first_name"),
                "last_name": user_record.get("last_name"),
                "mobile": user_record.get("mobile"),
                "street": user_record.get("l10n_bo_district") or "",
                "ci": user_record.get("ci") or ""
            },
            "service": service
        }
        return response_data

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")



@router.patch("/update_user")
async def update_user(request: Request):
# ----------------------------------------------------------

# async def update_user(request: Request, token_payload: dict = Depends(verify_token)):

# ----------------------------------------------------------


 
    try:

        # ----------------------------------------------------------
        # # Obtener el user_id del token y comparar con el id_usuario del body
        # token_user_id = token_payload.get("user_id")
        # ----------------------------------------------------------


        
        body = await request.json()
        
        # Convertir y validar que id_plan e id_usuario sean enteros
        try:
            id_plan = int(body.get("id_plan"))
            id_user = int(body.get("id_usuario"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Los campos 'id_plan' e 'id_usuario' deben ser números.")
        
        num_ref = body.get("num_ref")
	
        if not num_ref or not isinstance(num_ref, str):
           raise HTTPException(status_code=400, detail="El campo 'num_ref' es obligatorio y debe ser una cadena.")
        
        # ----------------------------------------------------------
        
        # if id_user != token_user_id:
        #     raise HTTPException(status_code=403, detail="No estás autorizado para actualizar otro usuario.")
        
        # ----------------------------------------------------------

        
        # Extraer y validar datos opcionales
        legal_Name = body.get("razon_social")
        type_doc = body.get("tipo_doc")
        num_doc = body.get("num_doc")
        l10n_bo_extension = body.get("extension")
        id_payment_method = body.get("id_metodo_pago")
        num_card = body.get("num_tarjeta")
        
        # Validación de campos obligatorios
        if not id_plan:
            raise HTTPException(status_code=400, detail="El campo 'id_plan' es obligatorio.")
        
        # Razón social: asignar "SIN NOMBRE" si es nulo o vacío
        if legal_Name is None:
            legal_Name = "SIN NOMBRE"
        legal_Name = legal_Name.strip()
        if legal_Name == "":
            legal_Name = "SIN NOMBRE"
        
        # Tipo de documento: valor por defecto "4" si no se proporciona
        if type_doc is None:
            type_doc = "4"
            l10n_bo_extension = ""
        type_doc = type_doc.strip()
        if type_doc not in ["1", "2", "3", "4", "5"]:
            raise HTTPException(status_code=400, detail="El tipo de documento no es válido.")
        l10n_bo_extension = (l10n_bo_extension or "").strip()
        if type_doc != "1":
            l10n_bo_extension = ""
        if len(l10n_bo_extension) > 4:
            raise HTTPException(status_code=400, detail="La extensión no puede tener más de 4 caracteres.")
        
        # Número de documento: valor por defecto "00" si es nulo o vacío
        if num_doc is None:
            num_doc = "00"
        num_doc = num_doc.strip()
        if num_doc == "":
            num_doc = "00"
        if not num_doc.isdigit():
            raise HTTPException(status_code=400, detail="El número de documento solo puede contener números.")
        if num_doc != "00" and len(num_doc) < 5:
            raise HTTPException(status_code=400, detail="El número de documento debe tener al menos 5 dígitos o ser '00' si no se registra.")
        
        # Método de pago: valor por defecto "7" si es nulo o vacío
        if id_payment_method is None:
            id_payment_method = "7"
        id_payment_method = id_payment_method.strip()
        if id_payment_method == "":
            id_payment_method = "7"
        if id_payment_method not in ["2", "7"]:
            raise HTTPException(status_code=400, detail="El método de pago no es válido.")
        if id_payment_method == "7":
            num_card = ""
        if id_payment_method == "2":
            if num_card is None:
                raise HTTPException(status_code=400, detail="El número de tarjeta es obligatorio para este método de pago.")
            num_card = num_card.strip()
            if num_card == "":
                raise HTTPException(status_code=400, detail="El número de tarjeta no puede estar vacío.")
            if num_card[0] not in ["4", "5"]:
                raise HTTPException(status_code=400, detail="El número de tarjeta no es válido.")
            if len(num_card) != 8:
                raise HTTPException(status_code=400, detail="El número de tarjeta debe tener 8 dígitos.")
            if not num_card.isdigit():
                raise HTTPException(status_code=400, detail="El número de tarjeta solo puede contener números.")
        
        # Conectar a Odoo
        conn = get_odoo_connection()
        
        # Validar que el plan exista y obtener datos del producto
        plan = execute_odoo_method(conn, 'product.product', 'read', [[id_plan]])
        if not plan:
            raise HTTPException(status_code=404, detail="El plan no existe.")
        product_data = execute_odoo_method(conn, 'product.product', 'read', [[id_plan]])
        if not product_data:
            raise HTTPException(status_code=404, detail="El producto no existe.")
        
        # Buscar el usuario por su ID
        user = execute_odoo_method(conn, 'res.users', 'read', [[id_user], ['partner_id']])
        if not user:
            raise HTTPException(status_code=404, detail="El usuario no existe.")
        
        # Buscar el contacto asociado al usuario
        contact = execute_odoo_method(conn, 'res.partner', 'read', [[user[0]['partner_id'][0]]])
        if not contact:
            raise HTTPException(status_code=404, detail="El contacto asociado al usuario no existe.")
        partner_id = contact[0]['id']
        
        # Actualizar los campos del contacto ligado al usuario en Odoo
        success = execute_odoo_method(
            conn, 'res.partner', 'write', [[partner_id], {
                "vat": num_doc,
                "l10n_latam_identification_type_id": int(type_doc),
                "l10n_bo_extension": l10n_bo_extension if type_doc == "4" else '',
                'l10n_bo_business_name': legal_Name,
            }]
        )
        if not success:
            raise HTTPException(status_code=500, detail="No se pudo actualizar el usuario.")
        


        # ----------------------------------------------------------------------------


         # Obtener el password desencriptado del usuario (nuevo)
        plain_password = get_decrypted_password(id_user)

        # Conexión a Pontis
        await login_to_external_api()
        updated_contact = execute_odoo_method(conn, 'res.partner', 'read', [[partner_id]])
        customer_data = build_customer_data(id_user, updated_contact, id_plan, plain_password)

        # -------------------------------------------------------------------------
        create_customer_response = await create_customer_in_pontis(customer_data)

        # Verificar que se obtuvo correctamente el nombre de usuario de Pontis
        if not create_customer_response.get("response"):
            raise HTTPException(status_code=500, detail="No se obtuvieron credenciales de Pontis.")
        pontis_username = create_customer_response["response"]

        # obtenemos el email del usuario desde SQLite
        user_record = get_user_record(id_user)
        email = user_record.get("email")

         # Enviar credenciales al usuario por correo
        send_pontis_credentials_email(
            to_email=email,  # Ajusta: aquí deberías usar el correo del usuario, p.ej. la variable email.
            subject="Tus credenciales de acceso:",
            pontis_username=pontis_username,
            pontis_password=plain_password
        )
        
        # ----------------------- Flujo de creación de factura -----------------------
        
        product = product_data[0]
        product_id = product['id']
        product_name = product['name']
        product_price = product['list_price']
        
        invoice_line = (0, 0, {
            'product_id': product_id,
            'name': product_name,
            'quantity': 1,
            'price_unit': product_price,
            'tax_ids': [(6, 0, [1])],
        })
        
        data_to_create_invoice = {
            'partner_id': partner_id,
            'move_type': 'out_invoice',
            "currency_id": 63,
            'vr_nit_ci': num_doc,
            'vr_extension': l10n_bo_extension or '',
            'vr_razon_social': legal_Name,
            'vr_warehouse_id': 1,
            'vr_metodo_pago': id_payment_method,
            'vr_nro_tarjeta': num_card,
            'vr_tipo_documento_identidad': type_doc,
	        'payment_reference': num_ref,
            'invoice_line_ids': [invoice_line],
        }
        
        invoice_id = execute_odoo_method(conn, 'account.move', 'create', [data_to_create_invoice])
        execute_odoo_method(conn, 'account.move', 'action_post', [[invoice_id]])
        
        invoice_info = execute_odoo_method(conn, 'account.move', 'read', [[invoice_id], ['amount_total', 'currency_id', 'partner_id', 'name']])[0]
        
        payment_data = {
            'payment_type': 'inbound',
            'communication': invoice_info['name'],
            'payment_date': datetime.now().strftime("%Y-%m-%d"),
            'amount': invoice_info['amount_total'],
            'currency_id': invoice_info['currency_id'][0],
            'partner_id': invoice_info['partner_id'][0],
            'journal_id': 7,
            'partner_bank_id': 1,  
        }
        
        context = {'active_ids': [invoice_id], 'active_model': 'account.move', 'active_id': invoice_id}
        payment_register_id = execute_odoo_method(conn, 'account.payment.register', 'create', [[payment_data]], {'context': context})
        execute_odoo_method(conn, 'account.payment.register', 'action_create_payments', [[payment_register_id[0]]])
        


        # Obtener el password desencriptado del usuario (nuevo)
        plain_password = get_decrypted_password(id_user)

        # Conexión a Pontis
        await login_to_external_api()
        customer_data = build_customer_data(id_user, updated_contact, id_plan, plain_password)

        # -------------------------------------------------------------------------
        create_customer_response = await create_customer_in_pontis(customer_data)

        # Verificar que se obtuvo correctamente el nombre de usuario de Pontis
        if not create_customer_response.get("response"):
            raise HTTPException(status_code=500, detail="No se obtuvieron credenciales de Pontis.")
        pontis_username = create_customer_response["response"]

        # ----------------------------------------------------------


        # obtenemos el email del usuario desde SQLite
        user_record = get_user_record(id_user)
        email = user_record.get("email")

         # Enviar credenciales al usuario por correo
        send_pontis_credentials_email(
            to_email=email,  # Ajusta: aquí deberías usar el correo del usuario, p.ej. la variable email.
            subject="Tus credenciales de acceso:",
            pontis_username=pontis_username,
            # pontis_username="pontis_username",
            pontis_password=plain_password
        )

        # ----------------------------------------------------------

        print("Credenciales enviadas a", email)
        print("user", pontis_username)
        print("pass", plain_password)

        # ----------------------------------------------------------

        # Actualizar el usuario en SQLite para marcar la aceptación de políticas
        update_user_policies(id_user)
        
        return {
            "detail": "Factura creada y pagada correctamente", 
            "invoice_id": invoice_id, 
            "payment_id": payment_register_id,
            # ----------------------------------------------------------
            "res_pontis": create_customer_response
            # ----------------------------------------------------------
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    
 # DE ACA PARA ABJO ES NUEVO------------------------------------------------------------------------------------------   

@router.post("/search_contact")
async def search_contact(request: Request):
# async def search_contact(request: Request):
    try:
        logger.info("Buscando contacto en Odoo...")
        # Conectar a Odoo
        conn = get_odoo_connection()

        # Obtener el CI del body (campo 'ci')
        body = await request.json()
        ci = body.get("ci")
        if not ci:
            raise HTTPException(status_code=400, detail="El campo 'ci' es obligatorio.")

        contacts = execute_odoo_method(
            conn, 'res.partner', 'search_read',
            [[('email', '=', ci)]],
            {'fields': ['id', 'name', 'mobile', 'email', 'vat']}
        )
        logger.info("Contactos encontrados: %s", contacts)

        if not contacts:
            raise HTTPException(status_code=404, detail="Contacto no encontrado.")
        contact_info = contacts[0]
        logger.info("Información del contacto: %s", contact_info)

        # obtenemos el id contacts 
        id_contact = contacts[0]['id']
        logger.info("ID del contacto obtenido: %s", id_contact)

        # obtenemos los id de los planes permitidos
        allowed_plan_ids = list(PRODUCTS.values())
        logger.info("IDs de planes permitidos: %s", allowed_plan_ids)

        # Obtener y filtrar facturas válidas
        valid_invoices_filtered = get_valid_invoices_for_search(conn, id_contact, allowed_plan_ids)

        logger.info("Facturas válidas filtradas: %s", valid_invoices_filtered)


        invoice = valid_invoices_filtered[0]
        logger.info("Factura válida seleccionada: %s", invoice)

        invoice_date_str = invoice.get('invoice_date')

        invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        logger.info("Fecha de la factura: %s", invoice_date)
        expiry_date = invoice_date + timedelta(days=28) # TODO: CAMBIAR A 30
        logger.info("Fecha de expiración: %s", expiry_date)
        now = datetime.now(timezone.utc)
        logger.info("Fecha actual: %s", now)

        if now >= invoice_date and now <= expiry_date:
            logger.info("El período de servicio aún sigue activo. No se puede continuar.")
            raise HTTPException(status_code=400, detail="El período de servicio aún sigue activo.")
        else:
            logger.info("El período de servicio ha expirado. Se puede continuar.")

        planId = get_plan_id_from_invoice(conn, invoice)
        logger.info("ID del plan obtenido: %s", planId)

        # Preparar el JSON de respuesta con la estructura solicitada
        result = {
            "id": str(contact_info["id"]),
            "fullName": contact_info.get("name", ""),
            "ci": contact_info.get("vat", ""),
            "phone": contact_info.get("mobile", ""),
            "email": contact_info.get("email", ""),
            "planId": planId
        }
        logger.info("Respuesta generada: %s", result)
        return result

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


 # ------------------------------------------------------------------------------------------   


def generate_random_password(length=8) -> str:
    """Genera una contraseña aleatoria alfanumérica de la longitud dada,
    que contenga al menos una mayúscula, una minúscula y un dígito."""
    if length < 3:
        raise ValueError("La longitud debe ser al menos 3 para cumplir los requisitos.")
    uppercase = random.choice(string.ascii_uppercase)
    lowercase = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    other = ''.join(random.choices(string.ascii_letters + string.digits, k=length-3))
    password_list = list(uppercase + lowercase + digit + other)
    random.shuffle(password_list)
    return ''.join(password_list)

def split_name(full_name: str) -> tuple:
    """Divide el nombre completo en firstName y lastName.
    Si hay solo una palabra, se asigna a firstName.
    Si hay más de una, se asigna el primer elemento a firstName y el resto se unen para formar lastName.
    """
    parts = full_name.split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], " ".join(parts[1:]))

# ------------------------------------------------------------------------------------------------------------
@router.patch("/activate_user")
async def activate_user(request: Request):

    try:
        # 1. Parsear y validar campos obligatorios
        body = await request.json()
        try:
            id_plan = int(body.get("id_plan"))
            id_contact = int(body.get("id_contact"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Los campos 'id_plan' e 'id_contact' deben ser números.")
        
        num_ref = body.get("num_ref")
        if not num_ref or not isinstance(num_ref, str) or not num_ref.strip():
            raise HTTPException(status_code=400, detail="El campo 'num_ref' es obligatorio y debe ser una cadena no vacía.")
        
        # Opcional: id_user (si se envía, debe ser numérico)
        id_user = None
        if "id_user" in body:
            try:
                id_user = int(body.get("id_user"))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="El campo 'id_user' debe ser un número si se proporciona.")
        
        # 2. Extraer y validar campos opcionales para actualizar el contacto
        legal_Name = (body.get("razon_social") or "").strip() or "SIN NOMBRE"
        type_doc = (body.get("tipo_doc") or "4").strip()
        if type_doc not in ["1", "2", "3", "4", "5"]:
            raise HTTPException(status_code=400, detail="El tipo de documento no es válido.")
        l10n_bo_extension = (body.get("extension") or "").strip()
        if type_doc != "1":
            l10n_bo_extension = ""
        if len(l10n_bo_extension) > 4:
            raise HTTPException(status_code=400, detail="La extensión no puede tener más de 4 caracteres.")
        num_doc = str(body.get("num_doc") or "00").strip() or "00"
        if not num_doc.isdigit():
            raise HTTPException(status_code=400, detail="El número de documento solo puede contener números.")
        if num_doc != "00" and len(num_doc) < 5:
            raise HTTPException(status_code=400, detail="El número de documento debe tener al menos 5 dígitos o ser '00' si no se registra.")


        id_payment_method = (body.get("id_metodo_pago") or "7").strip()
        if id_payment_method not in ["2", "7"]:
            raise HTTPException(status_code=400, detail="El método de pago no es válido.")
        num_card = ""
        if id_payment_method == "2":
            if not body.get("num_tarjeta"):
                raise HTTPException(status_code=400, detail="El número de tarjeta es obligatorio para el método de pago '2'.")
            num_card = str(body.get("num_tarjeta")).strip()
            if not num_card:
                raise HTTPException(status_code=400, detail="El número de tarjeta no puede estar vacío.")
            if num_card[0] not in ["4", "5"]:
                raise HTTPException(status_code=400, detail="El número de tarjeta no es válido.")
            if len(num_card) != 8:
                raise HTTPException(status_code=400, detail="El número de tarjeta debe tener 8 dígitos.")
            if not num_card.isdigit():
                raise HTTPException(status_code=400, detail="El número de tarjeta solo puede contener números.")
        
        
        # 2.1. Conectar a Pontis, construir el payload y llamar a la API
        # await login_to_external_api()
        
        # 3. Conectar a Odoo y obtener el contacto
        conn = get_odoo_connection()

        contact_data = execute_odoo_method(conn, 'res.partner', 'read', [[id_contact]], {'fields': []})
        if not contact_data:
            raise HTTPException(status_code=404, detail="Contacto no encontrado en Odoo.")
        contact_info = contact_data[0]

        # obtener name y email del contacto
        name = contact_info.get("name")
        if name is None:
            raise HTTPException(status_code=500, detail="El contacto no tiene un nombre.")
        if not name.strip():
            raise HTTPException(status_code=500, detail="El contacto no tiene un nombre válido.")
        email = contact_info.get("email")
        
        if email is None:
            raise HTTPException(status_code=500, detail="El contacto no tiene un email.")
        if not email.strip():
            raise HTTPException(status_code=500, detail="El contacto no tiene un email válido.")
        is_valid_email(email)

        # 4. Validar asociación del usuario con el contacto
        if id_user is not None:
            # Verificar que el contacto esté vinculado al usuario proporcionado.
            user_search = execute_odoo_method(
                conn, 
                'res.users', 'search_read', [[('partner_id', '=', id_contact)]], {'fields': ['id']})
            if not user_search or user_search[0]["id"] != id_user:
                raise HTTPException(status_code=400, detail="El id_user proporcionado no coincide con el usuario asociado al contacto.")
            
            get_user_record(id_user)

            
            # Obtenemos la contraseña actual del usuario del sqlite
            new_password = get_decrypted_password(id_user)
        else:
            # Si no se proporcionó id_user, asegurarse de que el contacto no esté asociado a ningún usuario.
            associated_users = execute_odoo_method(conn, 'res.users', 'search_read', [[('partner_id', '=', id_contact)]], {'fields': []})
            if not associated_users:

                print("hasta aqui ok")
                new_password = generate_random_password(8)
                # Crear el usuario de tipo portal en Odoo asociado al contacto.
                # Importante: Asignamos partner_id para evitar crear un nuevo contacto.
                group_portal = execute_odoo_method(
                    conn, 'ir.model.data', 'search_read',
                    [[('model', '=', 'res.groups'), ('module', '=', 'base'), ('name', '=', 'group_portal')]],
                    {'fields': ['res_id'], 'limit': 1}
                )
                if not group_portal:
                    raise HTTPException(status_code=500, detail="No se encontró el grupo portal en Odoo.")
                group_portal_id = group_portal[0]['res_id']
                new_user_vals = {
                    'login': contact_info.get("email"),
                    'name': contact_info.get("name"),
                    'email': contact_info.get("email"),
                    'mobile': contact_info.get("mobile"),
                    'password': new_password,
                    'lang': 'es_MX',
                    'partner_id': id_contact,  # Asociamos el usuario al contacto existente
                    'groups_id': [(6, 0, [group_portal_id])]
                }
                id_user = execute_odoo_method(
                    conn, 'res.users', 'create', [new_user_vals],
                    kwargs={'context': {'no_reset_password': True}}
                )
                if not id_user:
                    raise HTTPException(status_code=500, detail="No se pudo crear el usuario portal en Odoo.")
                
                # Divimos el nombre completo en nombre y apellido
                first_name, last_name = split_name(name)


                # Guardar el usuario en SQLite
                insert_user_record(
                    id_user, 
                    first_name,
                    last_name,
                    contact_info.get("email"), 
                    contact_info.get("mobile"), 
                    new_password, 
                    )


            else:
                # obtenemos los datos del usuario del sqlite
                # user_record = get_user_record(id_user)-----------------------

                # Obtenemos el id del usuario
                
                id_user = associated_users[0]["id"]
                

                # Verificamos que en la base de datos de SQLite exista el usuario
                get_user_record(id_user)
                
                # desencriptamos la contraseña
                new_password = get_decrypted_password(id_user)
                

                


        
        # 5. Actualizar campos del contacto en Odoo
        update_fields = {
            "vat": num_doc,
            "l10n_latam_identification_type_id": int(type_doc),
            "l10n_bo_extension": l10n_bo_extension if type_doc == "4" else '',
            "l10n_bo_business_name": legal_Name,
        }
        update_result = execute_odoo_method(conn, 'res.partner', 'write', [[id_contact], update_fields])
        if not update_result:
            raise HTTPException(status_code=500, detail="No se pudo actualizar el contacto en Odoo.")
        
        # 6. Verificar si el contacto tiene facturas pagadas y si el plan está activo.
        invoices = execute_odoo_method(conn, 'account.move', 'search_read',
                                        [[('partner_id', '=', id_contact), ('payment_state', '=', 'paid')]],
                                        {'fields': ['invoice_date', 'invoice_line_ids'], 'order': 'invoice_date desc', 'limit': 1})
        plan_active = False
        if invoices:
            invoice = invoices[0]
            invoice_date_str = invoice.get('invoice_date')
            if invoice_date_str:
                invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                expiry_date = invoice_date + timedelta(days=30)
                now = datetime.now(timezone.utc)
                print("invoice_date:", invoice_date)
                print("expiry_date:", expiry_date)
                print("now:", now)
                if invoice_date <= now <= expiry_date:
                    plan_active = True
        # Si el plan está activo, detener el flujo.
        if plan_active:
            raise HTTPException(status_code=400, detail="El contacto ya tiene un plan activo.")
        
        # 7. Crear una nueva factura en Odoo con payment_reference = num_ref
        product_data = execute_odoo_method(conn, 'product.product', 'read', [[id_plan]])
        if not product_data:
            raise HTTPException(status_code=404, detail="El producto no existe.")
        product = product_data[0]
        invoice_line = (0, 0, {
            'product_id': product['id'],
            'name': product['name'],
            'quantity': 1,
            'price_unit': product['list_price'],
            'tax_ids': [(6, 0, [1])],
        })
        data_to_create_invoice = {
            'partner_id': id_contact,
            'move_type': 'out_invoice',
            "currency_id": 63,
            'vr_nit_ci': num_doc,
            'vr_extension': l10n_bo_extension or '',
            'vr_razon_social': legal_Name,
            'vr_warehouse_id': 1,
            'vr_metodo_pago': id_payment_method,
            'vr_nro_tarjeta': num_card,
            'vr_tipo_documento_identidad': type_doc,
            'payment_reference': num_ref,
            'invoice_line_ids': [invoice_line],
        }
        invoice_id = execute_odoo_method(conn, 'account.move', 'create', [data_to_create_invoice])
        execute_odoo_method(conn, 'account.move', 'action_post', [[invoice_id]])
        
        # 8. Registrar el pago de la factura
        invoice_info = execute_odoo_method(conn, 'account.move', 'read', [[invoice_id],
                                             ['amount_total', 'currency_id', 'partner_id', 'name']])[0]
        payment_data = {
            'payment_type': 'inbound',
            'communication': invoice_info['name'],
            'payment_date': datetime.now().strftime("%Y-%m-%d"),
            'amount': invoice_info['amount_total'],
            'currency_id': invoice_info['currency_id'][0],
            'partner_id': invoice_info['partner_id'][0],
            'journal_id': 7,
            'partner_bank_id': 1,
        }
        context = {'active_ids': [invoice_id], 'active_model': 'account.move', 'active_id': invoice_id}
        payment_register_id = execute_odoo_method(conn, 'account.payment.register', 'create', [[payment_data]], {'context': context})
        execute_odoo_method(conn, 'account.payment.register', 'action_create_payments', [[payment_register_id[0]]])
        
        # 9. Obtener el contacto actualizado desde Odoo
        updated_contact = execute_odoo_method(conn, 'res.partner', 'read', [[id_contact]])
        if not updated_contact:
            raise HTTPException(status_code=500, detail="Error al obtener datos actualizados del contacto.")


        

        
        # customer_data = build_customer_data(id_user, updated_contact, id_plan, new_password)
        # create_customer_response = await create_customer_in_pontis(customer_data)
        # if not create_customer_response.get("response"):
        #     raise HTTPException(status_code=500, detail="No se obtuvieron credenciales de Pontis.")
        # pontis_username = create_customer_response["response"]
        
        # 12. Enviar credenciales al usuario por correo
        send_pontis_credentials_email(
            to_email=get_user_record(id_user).get("email"),
            subject="Tus credenciales de acceso:",
            pontis_username="Prueba",
            # pontis_username=pontis_username,
            pontis_password=new_password
        )
        
        print("Credenciales enviadas a", get_user_record(id_user).get("email"))
        # print("Usuario Pontis:", pontis_username)
        print("Password:", new_password)
        
        # 13. Actualizar las políticas en SQLite para marcar como aceptadas
        update_user_policies(id_user)
        
        return {
            "detail": "Factura creada y pagada correctamente", 
            "invoice_id": invoice_id, 
            "payment_id": payment_register_id,
            # "res_pontis": create_customer_response
        }
        
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------------------------------------------------------
 # DE ACA PARA ABJO ES NUEVO------------------------------------------------------------------------------------------   

def get_valid_invoices_for_search(conn, id_contact: int, allowed_plan_ids: list) -> list:

    logger.debug("Iniciando búsqueda de facturas pagadas para contacto ID: %s", id_contact)
    invoices = execute_odoo_method(
        conn, 'account.move', 'search_read',
        [[('partner_id', '=', id_contact), ('payment_state', '=', 'paid')]],
        {'fields': ['invoice_date', 'invoice_line_ids']}
    )
    logger.debug("Facturas encontradas: %s", invoices)
    if not invoices:
        raise HTTPException(status_code=404, detail="No se encontró factura pagada para este contacto.")
    
    valid_invoices_filtered = []
    for inv in invoices:
        invoice_line_ids = inv.get('invoice_line_ids', [])
        logger.debug("Factura %s - Líneas de factura: %s", inv.get('invoice_date'), invoice_line_ids)
        if not invoice_line_ids:
            continue
        invoice_lines = execute_odoo_method(
            conn, 'account.move.line', 'read', [invoice_line_ids],
            {'fields': ['product_id']}
        )
        logger.debug("Líneas de factura leídas: %s", invoice_lines)
        for line in invoice_lines:
            product_id = line.get('product_id')
            logger.debug("Revisando línea de factura, product_id: %s", product_id)
            if product_id and product_id[0] in allowed_plan_ids:
                valid_invoices_filtered.append(inv)
                logger.debug("Factura agregada por contener producto permitido: %s", inv)
                break
    if not valid_invoices_filtered:
        raise HTTPException(status_code=404, detail="No se encontró factura pagada válida para este contacto emitida hoy.")
    
    sorted_invoices = sorted(valid_invoices_filtered, key=lambda x: x.get('invoice_date'), reverse=True)
    logger.debug("Facturas válidas ordenadas: %s", sorted_invoices)
    return sorted_invoices


# ------------------------------------------------------------------------------------------------------------

def get_valid_invoices(conn, id_contact: int, allowed_plan_ids: list) -> list:

    logger.debug("Iniciando búsqueda de facturas pagadas para contacto ID: %s", id_contact)
    invoices = execute_odoo_method(
        conn, 'account.move', 'search_read',
        [[('partner_id', '=', id_contact), ('payment_state', '=', 'paid')]],
        {'fields': ['invoice_date', 'invoice_line_ids']}
    )
    logger.debug("Facturas encontradas: %s", invoices)
    if not invoices:
        raise HTTPException(status_code=404, detail="No se encontró factura pagada para este contacto.")
    
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.debug("Fecha de hoy (UTC): %s", today_str)
    valid_invoices = [inv for inv in invoices if inv.get('invoice_date') == today_str]
    logger.debug("Facturas emitidas hoy: %s", valid_invoices)
    if not valid_invoices:
        raise HTTPException(status_code=400, detail=" La última factura del contacto no fue emitida hoy, no se puede activar.")
    
    valid_invoices_filtered = []
    for inv in valid_invoices:
        invoice_line_ids = inv.get('invoice_line_ids', [])
        logger.debug("Factura %s - Líneas de factura: %s", inv.get('invoice_date'), invoice_line_ids)
        if not invoice_line_ids:
            continue
        invoice_lines = execute_odoo_method(
            conn, 'account.move.line', 'read', [invoice_line_ids],
            {'fields': ['product_id']}
        )
        logger.debug("Líneas de factura leídas: %s", invoice_lines)
        for line in invoice_lines:
            product_id = line.get('product_id')
            logger.debug("Revisando línea de factura, product_id: %s", product_id)
            if product_id and product_id[0] in allowed_plan_ids:
                valid_invoices_filtered.append(inv)
                logger.debug("Factura agregada por contener producto permitido: %s", inv)
                break
    if not valid_invoices_filtered:
        raise HTTPException(status_code=404, detail="No se encontró factura pagada válida para este contacto emitida hoy.")
    
    sorted_invoices = sorted(valid_invoices_filtered, key=lambda x: x.get('invoice_date'), reverse=True)
    logger.debug("Facturas válidas ordenadas: %s", sorted_invoices)
    return sorted_invoices

def get_plan_id_from_invoice(conn, invoice: dict) -> int:
    """
    Obtiene el ID del plan de servicio a partir de la primera línea de la factura.
    """
    logger.debug("Obteniendo plan desde factura: %s", invoice)
    invoice_lines = execute_odoo_method(
        conn, 'account.move.line', 'read', [invoice.get('invoice_line_ids')],
        {'fields': ['product_id']}
    )
    logger.debug("Líneas de factura para plan: %s", invoice_lines)
    if not invoice_lines or not invoice_lines[0].get('product_id'):
        raise HTTPException(status_code=500, detail="No se pudo determinar el plan de servicio.")
    plan_id = invoice_lines[0]['product_id'][0]
    logger.debug("Plan ID obtenido: %s", plan_id)
    return plan_id

# para la ruta cuando el contacto YA está asociado a un usuario
async def handle_associated_user_flow(conn, id_contact: int, contact_info: dict) -> dict:
    # Nota: si es que asociado a un usuario, asumimos que que hizo una compra previa y se le generó un usuario en la base de datos de SQLite
    associated_users = execute_odoo_method(
        conn, 'res.users', 'search_read',
        [[('partner_id', '=', id_contact)]],
        {'fields': ['id'], 'context': {'active_test': False}}
    )
    id_user = associated_users[0]["id"]
    logger.info("Se encontró usuario asociado con ID: %s", id_user)

    # Obtener los datos del usuario desde SQLite
    user_record = get_user_record(id_user)
    logger.debug("Registro del usuario en SQLite: %s", user_record)
    
    # Obtener el password desencriptado del usuario existente
    existing_password = get_decrypted_password(id_user)
    logger.debug("Contraseña existente (desencriptada): %s", existing_password)
    
    allowed_plan_ids = list(PRODUCTS.values())
    logger.debug("IDs de planes permitidos: %s", allowed_plan_ids)
    
    # Obtener y filtrar facturas válidas
    valid_invoices_filtered = get_valid_invoices(conn, id_contact, allowed_plan_ids)
    invoice = valid_invoices_filtered[0]
    logger.info("Factura válida seleccionada: %s", invoice)
    
    invoice_date_str = invoice.get('invoice_date')
  
    invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    logger.debug("Fecha de factura: %s", invoice_date)
    expiry_date = invoice_date + timedelta(days=30)
    logger.debug("Fecha de expiración: %s", expiry_date)
    now = datetime.now(timezone.utc)
    logger.debug("Fecha actual: %s", now)
    if now < invoice_date or now > expiry_date:
        raise HTTPException(status_code=400, detail="El período de servicio ha expirado.")
    
    id_plan = get_plan_id_from_invoice(conn, invoice)
    logger.info("Plan ID obtenido para la factura: %s", id_plan)
    
    # Armar el ID para Pontis (concatenar 'MAP0' + id_user)
    pontis_customer_id = "MAP0" + str(id_user)
    logger.debug("ID de cliente para Pontis: %s", pontis_customer_id)
    
    await login_to_external_api()
    logger.info("Conexión exitosa a la API externa.")
       
    res = await delete_packages_in_pontis(pontis_customer_id)

    if res:
        logger.info("Paquetes eliminados en Pontis: %s", pontis_customer_id)


    update_data_customer = await build_update_customer_data(id_plan)
    logger.debug("Datos para actualizar en Pontis: %s", update_data_customer)

    update_response = await update_customer_in_pontis(update_data_customer, pontis_customer_id)
    logger.info("Respuesta de actualización en Pontis: %s", update_response)

    if pontis_customer_id != update_response.get("response"):
        logger.warning("El ID de cliente de Pontis no coincide con el esperado.")
    else:
        logger.info("Cliente actualizado en Pontis correctamente.")
    
    # 14. Enviar por correo las credenciales de acceso a Pontis
    send_pontis_credentials_email(
        to_email=contact_info.get("email"),
        subject="Tus credenciales de acceso a M+",
        pontis_username=pontis_customer_id,  # Ajustar: aquí se usa el ID de cliente para Pontis.
        pontis_password=existing_password
    )
    logger.info("Correo de credenciales enviado a: %s", contact_info.get("email"))
    
    return {
        "detail": "Contacto actualizado en Pontis correctamente.",
        "pontis_username": pontis_customer_id,
        "existing_password": existing_password,
        "update_response": update_response # comentar
    }

# Helper para la ruta cuando el contacto NO está asociado a ningún usuario
async def handle_non_associated_user_flow(conn, id_contact: int, contact_info: dict) -> dict:
    allowed_plan_ids = list(PRODUCTS.values())
    logger.debug("IDs de planes permitidos: %s", allowed_plan_ids)
    
    valid_invoices_filtered = get_valid_invoices(conn, id_contact, allowed_plan_ids)
    invoice = valid_invoices_filtered[0]
    logger.info("Factura válida seleccionada: %s", invoice)
    
    invoice_date_str = invoice.get('invoice_date')
   
    invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    expiry_date = invoice_date + timedelta(days=30)
    now = datetime.now(timezone.utc)
    logger.debug("Fecha de factura: %s, Fecha de expiración: %s, Fecha actual: %s", invoice_date, expiry_date, now)
    if now < invoice_date or now > expiry_date:
        raise HTTPException(status_code=400, detail="El período de servicio ha expirado.")
    
    id_plan = get_plan_id_from_invoice(conn, invoice)
    logger.info("Plan ID obtenido para la factura: %s", id_plan)
    
    new_password = generate_random_password(8)
    logger.info("Nueva contraseña generada: %s", new_password)
    
    group_portal = execute_odoo_method(
        conn, 'ir.model.data', 'search_read',
        [[('model', '=', 'res.groups'), ('module', '=', 'base'), ('name', '=', 'group_portal')]],
        {'fields': ['res_id'], 'limit': 1}
    )
    if not group_portal:
        raise HTTPException(status_code=500, detail="No se encontró el grupo portal en Odoo.")
    group_portal_id = group_portal[0]['res_id']
    logger.debug("ID del grupo portal: %s", group_portal_id)
    
    new_user_vals = {
        'login': contact_info.get("email"),
        'name': contact_info.get("name"),
        'email': contact_info.get("email"),
        'mobile': contact_info.get("mobile"),
        'password': new_password,
        'lang': 'es_MX',
        'partner_id': id_contact,  # Asociamos el usuario al contacto existente
        'groups_id': [(6, 0, [group_portal_id])]
    }
    new_user_id = execute_odoo_method(
        conn, 'res.users', 'create', [new_user_vals],
        kwargs={'context': {'no_reset_password': True}}
    )
    if not new_user_id:
        raise HTTPException(status_code=500, detail="No se pudo crear el usuario portal en Odoo.")
    logger.info("Nuevo usuario creado en Odoo con ID: %s", new_user_id)
    
    def split_name(full_name: str) -> tuple:
        parts = full_name.split()
        if not parts:
            return ("", "")
        if len(parts) == 1:
            return (parts[0], "")
        return (parts[0], " ".join(parts[1:]))
    first_name, last_name = split_name(contact_info.get("name", ""))
    insert_user_record(new_user_id,
                       first_name=first_name,
                       last_name=last_name,
                       email=contact_info.get("email"),
                       mobile=contact_info.get("mobile"),
                       password=new_password)
    logger.info("Usuario registrado en SQLite con ID: %s", new_user_id)
    
    update_user_policies(new_user_id)
    logger.debug("Políticas de usuario actualizadas en SQLite para ID: %s", new_user_id)
    
    updated_contact = execute_odoo_method(conn, 'res.partner', 'read', [[id_contact]])
    # Obtenemos el id contacto actualizado
    updated_contact_id = updated_contact[0].get("id")
    logger.debug("Datos actualizados del contacto: %s", updated_contact_id)
    if not updated_contact:
        raise HTTPException(status_code=500, detail="Error al obtener datos actualizados del contacto.")
    
    customer_data = build_customer_data(new_user_id, updated_contact, id_plan, new_password)
    logger.debug("Payload para Pontis: %s", customer_data)
    
    await login_to_external_api()
    logger.info("Conexión exitosa a la API externa.")

    user_name_pontis = "MAP0" + str(new_user_id)

    # activation_response = await create_customer_in_pontis(customer_data)
    # pontis_username = activation_response["response"]


    # if pontis_username != user_name_pontis:
    #     logger.warning("El ID de usuario en Pontis no coincide con el esperado: %s", pontis_username)
    # else:
    #     logger.info("ID de usuario en Pontis: %s", pontis_username)

    # logger.info("Respuesta de activación en Pontis: %s", activation_response)

    
    send_pontis_credentials_email(
        to_email=contact_info.get("email"),
        subject="Tus credenciales de acceso a M+",
        pontis_username=user_name_pontis,  
        pontis_password=new_password
    )
    logger.info("Correo de credenciales enviado a: %s", contact_info.get("email"))
    
    return {
        "detail": "Contacto activado como usuario portal en Pontis correctamente.",
        "pontis_username": user_name_pontis,
        "new_password": new_password,
        # "activation_response": activation_response
    }

@router.post("/activate_contact_from_odoo")
async def activate_contact_portal(request: Request):
    try:
        # 1. Obtener id_contact del body
        body = await request.json()
        try:
            id_contact = int(body.get("id_contact"))
        except (TypeError, ValueError):
            logger.error("Error al convertir 'id_contact' a entero: %s", body.get("id_contact"))
            raise HTTPException(status_code=400, detail="El campo 'id_contact' debe ser un número.")
        if not id_contact:
            raise HTTPException(status_code=400, detail="El campo 'id_contact' es obligatorio.")
        logger.info("Procesando activación para contacto ID: %s", id_contact)
        
        # 3. Buscar el contacto en Odoo
        conn = get_odoo_connection()
        contact_data = execute_odoo_method(
            conn, 'res.partner', 'read', [[id_contact]],
            {'fields': ['id', 'name', 'mobile', 'email', 'vat']}
        )
        logger.debug("Datos del contacto obtenidos: %s", contact_data)
        if not contact_data:
            raise HTTPException(status_code=404, detail="Contacto no encontrado.")
        contact_info = contact_data[0]
        logger.info("Contacto encontrado: %s", contact_info.get("id"))
        
        # 4. Verificar que el contacto NO esté asociado a ningún usuario
        associated_users = execute_odoo_method(
            conn, 'res.users', 'search_read',
            [[('partner_id', '=', id_contact)]],
            {'fields': ['id'], 'context': {'active_test': False}}
        )
        logger.debug("Usuarios asociados: %s", associated_users)
        
        if associated_users:
            # RUTA A: Contacto ya asociado a un usuario
            result = await handle_associated_user_flow(conn, id_contact, contact_info)
        else:
            # RUTA B: Contacto no asociado a ningún usuario
            result = await handle_non_associated_user_flow(conn, id_contact, contact_info)
        return result

    except HTTPException as http_err:
        logger.error("HTTPException: %s", http_err.detail)
        raise http_err
    except Exception as e:
        logger.exception("Error interno:")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")