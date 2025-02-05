from fastapi import APIRouter, HTTPException, Query, Depends, Request
from app.core.security import verify_token
from app.core.database import get_odoo_connection, get_sqlite_connection
from app.core.email_utils import send_email
from datetime import datetime, timedelta, timezone

from app.services.api_service import build_customer_data, create_customer_in_pontis, login_to_external_api
from app.services.odoo_service import execute_odoo_method


router = APIRouter(prefix="/users", tags=["users"])


@router.post("/create")
async def create_user(request: Request):
    try:
        # Obtener los datos del cuerpo de la solicitud
        body = await request.json()
        name = body.get("name")
        email = body.get("email")
        mobile = body.get("mobile")

        # Validar que todos los campos requeridos estén presentes
        if not all([name, email, mobile]):
            raise HTTPException(status_code=400, detail="Todos los campos son obligatorios.")

        # Verificar el correo en la tabla de verification_codes
        sqlite_conn = get_sqlite_connection()
        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT * FROM verification_codes WHERE email = ? ORDER BY id DESC LIMIT 1", (email,))
        verification_record = cursor.fetchone()

        if not verification_record:
            raise HTTPException(status_code=400, detail="El correo no ha sido registrado para verificación.")

        # Verificar el estado del registro
        status = verification_record[2]  # Índice del estado en la tabla
        if status == 0:
            raise HTTPException(status_code=400, detail="El correo no ha sido verificado.")


        # Obtener la conexión a Odoo
        odoo_conn = get_odoo_connection()

        # Verificar que el correo no esté registrado en Odoo
        existing_user = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'search_count', [[('login', '=', email)]]
        )
        if existing_user:
            raise HTTPException(status_code=400, detail="El correo ya está registrado en el sistema.")

        # Obtener el res_id del grupo "Portal"
        group_portal = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'ir.model.data', 'search_read',
            [[('model', '=', 'res.groups'), ('module', '=', 'base'), ('name', '=', 'group_portal')]],
            {'fields': ['res_id'], 'limit': 1}
        )
        if not group_portal:
            raise HTTPException(status_code=500, detail="No se encontró el grupo Portal en Odoo.")
        group_portal_id = group_portal[0]['res_id']

        # Crear el usuario en Odoo
        user_id = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'create', [{
                'login': email,
                'name': name,
                'email': email,
                'mobile': mobile,
                'lang': 'es_MX',  # Establecer el idioma a español de México
                'groups_id': [(6, 0, [group_portal_id])]  # Asignar grupo Portal
            }]
        )

        return {"detail": "Proceso exitoso.", "id": user_id}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        sqlite_conn.close()

# Cambiar la contraseña de un usuario
@router.post("/change_password")
async def change_password(request: Request):
    odoo_conn = get_odoo_connection()
    try:
        # Obtener los datos del cuerpo de la solicitud
        body = await request.json()
        user_id = body.get("user_id")
        new_password = body.get("new_password")

        # Validar que los campos requeridos estén presentes
        if not user_id or not new_password:
            raise HTTPException(status_code=400, detail="Los campos 'user_id' y 'new_password' son obligatorios.")

        # Cambiar la contraseña del usuario
        success = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'write', [[user_id], {'password': new_password}]
        )

        # Verificar que la operación fue exitosa
        if not success:
            raise HTTPException(status_code=500, detail="No se pudo cambiar la contraseña.")

        return {"detail": "Contraseña cambiada exitosamente."}

    except HTTPException as http_error:
        # Error esperado
        raise http_error
    except Exception as e:
        # Error inesperado
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    

# Actualizar solo la contraseña de un usuario por medio de su id
@router.post("/update_password")
async def update_password(request: Request):
    odoo_conn = get_odoo_connection()
    try:
        # Obtener los datos del cuerpo de la solicitud
        body = await request.json()
        user_id = body.get("user_id")
        new_password = body.get("new_password")

        # Validar que los campos requeridos estén presentes
        if not user_id or not new_password:
            raise HTTPException(status_code=400, detail="Los campos 'user_id' y 'new_password' son obligatorios.")

        # Cambiar la contraseña del usuario
        success = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'write', [[user_id], {'password': new_password}]
        )

        # Verificar que la operación fue exitosa
        if not success:
            raise HTTPException(status_code=500, detail="No se pudo cambiar la contraseña.")

        return {"detail": "Contraseña cambiada exitosamente."}

    except HTTPException as http_error:
        # Error esperado
        raise http_error
    except Exception as e:
        # Error inesperado
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/get/{user_id}")
async def get_user_with_service(user_id: int, token=Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Obtener información del usuario
        user_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.users', 'read', [[user_id]],
            {'fields': ['email', 'name', 'password', 'mobile', 'street', 'partner_id']}
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        user = user_data[0]
        partner_id = user.get("partner_id", [None])[0]

        if not partner_id:
            raise HTTPException(status_code=404, detail="El usuario no tiene un contacto asociado.")

        today = datetime.now(timezone.utc)  # Convertimos a UTC

        # Obtener la última factura válida
        invoice = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'search_read',
            [[
                ['partner_id', '=', partner_id],
                ['payment_state', '=', 'paid'],
                ['vr_estado', '=', 'send_and_confirm']
            ]],
            {
                'fields': ['id', 'invoice_date', 'amount_total', 'invoice_line_ids'],
                'order': 'invoice_date desc',
                'limit': 1
            }
        )

        if not invoice:
            return {
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user["name"],
                    "password": user["password"],
                    "mobile": user["mobile"],
                    "street": user["street"] or ""
                },
                "service": {}
            }

        invoice = invoice[0]

        # Obtener el producto asociado a la factura
        invoice_line = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move.line', 'read', [invoice['invoice_line_ids']],
            {'fields': ['product_id']}
        )

        product_id = invoice_line[0]['product_id'][0] if invoice_line and invoice_line[0]['product_id'] else None

        # Obtener detalles del producto
        product_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'product.product', 'read', [[product_id]],
            {'fields': ['name']}
        ) if product_id else None

        # Calcular la fecha de expiración
        invoice_date = datetime.strptime(invoice['invoice_date'], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        date_expiration = invoice_date + timedelta(days=30)

        # Calcular el estado del servicio
        status = invoice_date <= today <= date_expiration

        # Construir el objeto service
        service = {
            "id": invoice["id"],
            "id_service": product_id,
            "name": product_data[0]["name"] if product_data else "Desconocido",
            "price_paid": invoice["amount_total"],
            "date_order": invoice["invoice_date"],
            "date_expiration": date_expiration.strftime("%Y-%m-%d"),
            # "date_expiration": date_expiration.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status
        }

        return {
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "password": user["password"],
                "mobile": user["mobile"],
                "street": user["street"] or ""
            },
            "service": service
        }
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")

# Obtener todos los detalles de un usuario por su id
@router.get("/all/{user_id}")
async def get_user_all(user_id: int, token=Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Llamada síncrona a Odoo
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.users', 'read', [[user_id]]
        )
        # Devolver el usuario encontrado
        return {"user": result}
    except Exception as e:
        # Manejo de errores genérico
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")

# Actualizar uno o varios campos de un usuario por su id

# @router.patch("/update_user")
# async def update_user(request: Request):
#     conn = get_odoo_connection()
#     try:
#         # Obtener los datos del cuerpo de la solicitud
#         body = await request.json()
#         id_plan = body.get("id_plan")
#         id_user = body.get("id_user")
#         company_registry = body.get("ci")
#         legal_Name = body.get("razon_social")
#         type_doc = body.get("tipo_doc")
#         num_doc = body.get("num_doc")
#         l10n_bo_extension = body.get("extension")
#         id_payment_method = body.get("id_metodo_pago")
#         num_card = body.get("num_tarjeta")

#         # Validar que todos los campos requeridos estén presentes
#         if not all([id_plan, id_user, company_registry, legal_Name, type_doc, num_doc, l10n_bo_extension, id_payment_method, num_card]):
#             raise HTTPException(status_code=400, detail="Todos los campos son obligatorios.")
        
#         # Validar que el plan exista
#         plan = execute_odoo_method(conn, 'product.product', 'read', [[id_plan]])
#         if not plan:
#             raise HTTPException(status_code=404, detail="El plan no existe.")
        
#         # Obtenemos la data del producto por medio del id_plan
#         product_data = execute_odoo_method(conn, 'product.product', 'read', [[id_plan]])
#         if not product_data:
#             raise HTTPException(status_code=404, detail="El producto no existe.")
        
#         # Verificamos que el contacto exista
#         user = execute_odoo_method(conn, 'res.partner', 'read', [[id_user]])
#         if not user:
#             raise HTTPException(status_code=404, detail="El contacto no existe.")
                
#         # Actualizar los campos del contacto ligado al usuario
#         success = execute_odoo_method(
#             conn, 'res.partner', 'write', [[id_user], {
#                 "company_registry": company_registry,
#                 "vat": num_doc,
#                 "l10n_bo_extension": l10n_bo_extension if type_doc == 4 else '',
#                 "l10n_latam_identification_type_id": type_doc,
#                 'l10n_bo_business_name': legal_Name,
#             }]
#         )
        
#         # Verificar que la operación fue exitosa
#         if not success:
#             raise HTTPException(status_code=500, detail="No se pudo actualizar el usuario.")
        
#         # Obtener los datos actualizados del contacto
#         updated_contact = execute_odoo_method(conn, 'res.partner', 'read', [[id_user]])[0]
#         # print(updated_contact)

#         # Crear un borrador de factura
#         # data_to_create_invoice = {

#         #     'partner_id': id_user,  # ID del contacto
#         #     'move_type': 'out_invoice',  # Tipo de factura (out_invoice para factura de cliente)
#         #     'vr_nit_ci': updated_contact['vat'],  # NIT o CI del contacto
#         #     'vr_extension': updated_contact['l10n_bo_extension'] or '',  # Extensión del NIT
#         #     'vr_razon_social': updated_contact['l10n_bo_business_name'],  # Razón social del contacto
#         #     'vr_warehouse_id': 1,  # ID del almacén
            




#         #     # 'invoice_date': datetime.now().strftime("%Y-%m-%d"),  # Fecha de la factura
#         #     # 'invoice_line_ids': [(0, 0, {
#         #     #     'product_id': id_plan,  # ID del producto (usamos el id_plan)
#         #     #     'quantity': 1,  # Cantidad
#         #     #     'price_unit': product_data[0]['list_price'],  # Precio unitario del producto
#         #     #     'name': product_data[0]['name'],  # Nombre del producto
#         #     # })]
#         # }

#         # Crear la factura
#         # invoice_id = execute_odoo_method(conn, 'account.move', 'create', [data_to_create_invoice])
#         # if not invoice_id:
#         #     raise HTTPException(status_code=500, detail="No se pudo crear el borrador de factura.")

#         # Llamar a la API externa para autenticarse
#         api_response = await login_to_external_api()

#         #Usamos el metodo para actualizar el portis
#         create_response = await create_customer_in_pontis(id_user, id_plan)

#         return {
#             "detail": "Usuario actualizado exitosamente y factura creada",
#             "api_response": api_response,
#             "update_response": create_response,
#             # "contact": updated_contact,
#             # "invoice_id": invoice_id
#             "invoice_id": 80
#         }

#     except HTTPException as http_error:
#         # Error esperado
#         raise http_error
#     except Exception as e:
#         # Error inesperado
#         raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.patch("/update_user")
async def update_user(request: Request):
    conn = get_odoo_connection()
    try:
        # Obtener los datos del cuerpo de la solicitud
        body = await request.json()
        id_plan = body.get("id_plan")
        id_user = body.get("id_user")
        company_registry = body.get("ci")
        legal_Name = body.get("razon_social")
        type_doc = body.get("tipo_doc")
        num_doc = body.get("num_doc")
        l10n_bo_extension = body.get("extension")
        id_payment_method = body.get("id_metodo_pago")
        num_card = body.get("num_tarjeta")

        # Validar que todos los campos requeridos estén presentes
        if not all([id_plan, id_user, company_registry, legal_Name, type_doc, num_doc, l10n_bo_extension, id_payment_method, num_card]):
            raise HTTPException(status_code=400, detail="Todos los campos son obligatorios.")
        
        # Validar que el plan exista
        plan = execute_odoo_method(conn, 'product.product', 'read', [[id_plan]])
        if not plan:
            raise HTTPException(status_code=404, detail="El plan no existe.")
        
        # Validar la data del producto por medio del id_plan
        product_data = execute_odoo_method(conn, 'product.product', 'read', [[id_plan]])
        if not product_data:
            raise HTTPException(status_code=404, detail="El producto no existe.")
        
        # Verificamos que el contacto exista
        user = execute_odoo_method(conn, 'res.partner', 'read', [[id_user]])
        if not user:
            raise HTTPException(status_code=404, detail="El contacto no existe.")
        
        if type_doc != "1":
            l10n_bo_extension = ""
        
        if len(num_card) != 8:
            raise HTTPException(status_code=400, detail="El número de tarjeta debe tener 8 dígitos.")
                
        # Actualizar los campos del contacto ligado al usuario
        success = execute_odoo_method(
            conn, 'res.partner', 'write', [[id_user], {
                "company_registry": company_registry,
                "vat": num_doc,
                "l10n_bo_extension": l10n_bo_extension if type_doc == 4 else '',
                "l10n_latam_identification_type_id": type_doc,
                'l10n_bo_business_name': legal_Name,
            }]
        )

        # Verificar que la operación fue exitosa
        if not success:
            raise HTTPException(status_code=500, detail="No se pudo actualizar el usuario.")
        
        # Obtener los datos actualizados del contacto
        updated_contact = execute_odoo_method(conn, 'res.partner', 'read', [[id_user]])[0]

        print("hasta aqui ok")

        # ----------------------------Flujo de creación de factura--------------------------------------


        # Obtener los detalles del producto
        product = product_data[0]
        product_id = product['id']
        product_name = product['name']
        product_price = product['list_price']  # Precio unitario del producto

        # Construir la línea de la factura
        invoice_line = (0, 0, {
            'product_id': product_id,  # ID del producto
            'name': product_name,  # Nombre del producto
            'quantity': 1,  # Cantidad (en este caso, 1)
            'price_unit': product_price,  # Precio unitario
            'tax_ids': [(6, 0, [1])],  # Impuestos (vacío por defecto)
        })

        # Crear el objeto para la factura
        data_to_create_invoice = {
            'partner_id': id_user,
            'move_type': 'out_invoice',  # Tipo de factura (out_invoice para factura de cliente)
            "currency_id": 63,  # ID de la moneda (BOB)
            'vr_nit_ci': num_doc,  # NIT o CI del contacto
            'vr_extension': l10n_bo_extension or '',  # Extensión del NIT
            'vr_razon_social': legal_Name,  # Razón social del contacto
            'vr_warehouse_id': 1,  # ID del almacén
            'vr_metodo_pago': id_payment_method,  # ID del método de pago
            'vr_nro_tarjeta': num_card,
            'vr_tipo_documento_identidad': type_doc,
            'invoice_line_ids': [invoice_line],  # Línea de la factura con el producto
        }

        # Crear la factura como borrador

        invoice_id = execute_odoo_method(conn, 'account.move', 'create', [data_to_create_invoice])
        

        # -------------------------------------CONFIRMAR FACTURA-------------------------------------
  
        execute_odoo_method(conn, 'account.move', 'action_post', [[invoice_id]])
 
        # -------------------------------------Registrar Pago---------------------------------------- ACA

        # Crear el pago

        invoice_data = execute_odoo_method(conn, 'account.move', 'read', [[invoice_id], ['amount_total', 'currency_id', 'partner_id', 'name']])[0]

        print(invoice_data)
        payment_data = {
            'payment_type': 'inbound',  # Tipo de pago (entrante)
            'journal_id': 1,  # Diario de pago (ajusta este valor según tu configuración)
            'payment_method_line_id': "1",  # Método de pago (ajusta este valor según tu configuración)
            'partner_bank_id': "1",  # Cuenta bancaria receptora (ajusta este valor según tu configuración)
            'amount': invoice_data['amount_total'],  # Monto total de la factura
            'highest_name': invoice_data['name'],  # Nombre de la factura
            'payment_date': datetime.now().strftime("%Y-%m-%d"),  # Fecha de pago
            'currency_id': invoice_data['currency_id'][0],  # Moneda
            'partner_id': invoice_data['partner_id'][0],  # ID del contacto
        }

        # Crear el pago
        payment_register_id = execute_odoo_method(conn, 'account.payment', 'create', [payment_data])

        # ------------------------------------------------------- Deepseek generado ---------------------------------------

        # # Obtener los detalles de la factura
        # invoice_data = execute_odoo_method(conn, 'account.move', 'read', [[invoice_id], ['amount_total', 'currency_id', 'partner_id', 'name']])[0]

        # # Preparar los datos para el registro del pago
        # payment_data = {
        #     'payment_type': 'inbound',  # Tipo de pago (entrante)
        #     'communication': invoice_data['name'],  # Nombre de la factura
        #     'payment_date': datetime.now().strftime("%Y-%m-%d"),  # Fecha de pago
        #     'amount': invoice_data['amount_total'],  # Monto total de la factura
        #     'currency_id': invoice_data['currency_id'][0],  # Moneda
        #     'partner_id': invoice_data['partner_id'][0],  # ID del contacto
        #     'journal_id': 1,  # Diario de pago (ajusta este valor según tu configuración)
        #     'partner_bank_id': 1,  # Cuenta bancaria receptora (ajusta este valor según tu configuración)
        #     'payment_method_line_id': 1,  # Método de pago (ajusta este valor según tu configuración)
        # }

        # # Agregar el contexto
        # context = {
        #     'active_ids': [invoice_id],  # IDs de las facturas
        #     'active_model': 'account.move',  # Modelo de la factura
        #     'active_id': invoice_id  # ID de la factura activa
        # }

        # # Crear el registro de pago
        # payment_register_id = execute_odoo_method(
        #     conn, 'account.payment.register', 'create', [[payment_data]], {'context': context}
        # )

        # # Confirmar el pago
        # execute_odoo_method(conn, 'account.payment.register', 'action_create_payments', [[payment_register_id]])


        # -------------------------------------------------------------------------- HASTA ACA


        # ------------------------------------ CONEXI{ON A PONTIS ------------------------------------
        # Llamar a la API externa para autenticarse
        # login_response = await login_to_external_api()
        # api_token = login_response.get("token")  # Obtener el token de autenticación

        # # Construir el cuerpo de la solicitud para crear el cliente en Pontis
        # customer_data = build_customer_data(id_user, updated_contact, id_plan)

        # # Llamar a la API de creación de clientes en Pontis
        # create_customer_response = await create_customer_in_pontis(api_token, customer_data)
        # -------------------------------------------------------------------------------------------

        return {
            "detail": "Usuario actualizado exitosamente y cliente creado en Pontis.",
            "invoice_id": invoice_id,
            "payment_id": payment_register_id,

            # "invoice_id_confirmed": id_invoice_confirmed,
            # "login_response": login_response,
            # "contact": updated_contact,
            # "pontis_response": create_customer_response
        }

    except HTTPException as http_error:
        # Error esperado
        raise http_error
    except Exception as e:
        # Error inesperado
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    

