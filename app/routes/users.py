from fastapi import APIRouter, HTTPException, Depends, Request
import re
from app.core.security import verify_token
from app.core.database import get_odoo_connection, get_sqlite_connection
from datetime import datetime, timedelta, timezone
from app.services.api_service import build_customer_data, create_customer_in_pontis, login_to_external_api
from app.services.odoo_service import execute_odoo_method
from app.services.sqlite_service import get_decrypted_password, insert_user_record, update_user_password


router = APIRouter(prefix="/users", tags=["users"])

def _is_valid_password(password: str) -> bool:
    pattern = r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&_])[A-Za-z\d@$!%*?&_]{8,}$"
    return bool(re.match(pattern, password))

@router.post("/create")
async def create_user(request: Request):
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
                detail="The password must have at least 8 characters, including 1 uppercase, 1 lowercase, 1 number, and 1 special character."
            )

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
        insert_user_record(user_id, first_name, last_name, email, password)

        return {"detail": "Successful process", "id": user_id}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error:: {str(e)}")
    finally:
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
                detail="The new password must be at least 8 characters, 1 uppercase letter, 1 lowercase letter, 1 number, and 1 special character."
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

        return {"detail": "Password changed successfully."}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")
    


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

@router.patch("/update_user")
async def update_user(request: Request):
    conn = get_odoo_connection()
    try:
        # Obtener los datos del cuerpo de la solicitud
        body = await request.json()
        id_plan = body.get("id_plan")
        id_user = body.get("id_usuario")
        # company_registry = body.get("ci")
        legal_Name = body.get("razon_social")
        type_doc = body.get("tipo_doc")
        num_doc = body.get("num_doc")
        l10n_bo_extension = body.get("extension")
        id_payment_method = body.get("id_metodo_pago")
        num_card = body.get("num_tarjeta")

        company_registry=num_doc

        # Validar que todos los campos requeridos estén presentes
        if not id_plan:
            raise HTTPException(status_code=400, detail="El campo 'id_plan' es obligatorio.")
        if not id_user:
            raise HTTPException(status_code=400, detail="El campo 'id_usuario' es obligatorio.")
        if not company_registry:
            raise HTTPException(status_code=400, detail="El campo 'ci' es obligatorio.")
        if not legal_Name:
            raise HTTPException(status_code=400, detail="El campo 'razon_social' es obligatorio.")
        if not type_doc:
            raise HTTPException(status_code=400, detail="El campo 'tipo_doc' es obligatorio.")
        if not num_doc:
            raise HTTPException(status_code=400, detail="El campo 'num_doc' es obligatorio.")
        if not id_payment_method:
            raise HTTPException(status_code=400, detail="El campo 'id_metodo_pago' es obligatorio.")
        if not num_card:
            raise HTTPException(status_code=400, detail="El campo 'num_tarjeta' es obligatorio.")

        
        # Validar que los campos no sean espacios en blanco por ejemplo " " y quitar espacios en blanco al principio y al final
        if legal_Name.strip() == "" or num_doc.strip() == "":
            raise HTTPException(status_code=400, detail="Los campos no pueden estar vacíos.")
        
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
            'tax_ids': [(6, 0, [1])],  # Impuestos
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
 
        # -------------------------------------REGISTRAR PAGO---------------------------------------- 
       
        # Obtener información de la factura
        invoice_info = execute_odoo_method(conn, 'account.move', 'read', [[invoice_id], ['amount_total', 'currency_id', 'partner_id', 'name']])[0]

        payment_data = {
            # 'payment_type': 'inbound',  # Tipo de pago (entrante)
            # 'journal_id': 7,  # Diario de pago (ajusta este valor según tu configuración)
            # 'payment_method_line_id': 3,  # Método de pago (ajusta este valor según tu configuración)
            # 'partner_bank_id': 1,  # Cuenta bancaria receptora (ajusta este valor según tu configuración)
            # 'amount': invoice_data['amount_total'],  # Monto total de la factura
            # 'highest_name': invoice_data['name'],  # Nombre de la factura
            # 'date': datetime.now().strftime("%Y-%m-%d"),  # Fecha de pago
            # 'currency_id': invoice_data['currency_id'][0],  # Moneda
            # 'partner_id': invoice_data['partner_id'][0],  # ID del contacto

            'payment_type': 'inbound',
            'communication': invoice_info['name'],
            'payment_date': datetime.now().strftime("%Y-%m-%d"),
            'amount': invoice_info['amount_total'],
            'currency_id': invoice_info['currency_id'][0],
            'partner_id': invoice_info['partner_id'][0],
            'journal_id': 7,  # Ajustar según configuración de Odoo
            'partner_bank_id': 1,  
            
        }

        context = {
            'active_ids': [invoice_id],  # IDs de las facturas
            'active_model': 'account.move',  # Modelo de la factura
            'active_id': invoice_id  # ID de la factura activa
        }


        context = {'active_ids': [invoice_id], 'active_model': 'account.move', 'active_id': invoice_id}

        payment_register_id = execute_odoo_method(conn, 'account.payment.register', 'create', [[payment_data]], {'context': context})

        # Confirmar el pago
        execute_odoo_method(conn, 'account.payment.register', 'action_create_payments', [[payment_register_id[0]]])



        # ------------------------------------ CONEXIÓN A PONTIS ------------------------------------

        # Obtene datos de contacto actualizados
        updated_contact = execute_odoo_method(conn, 'res.partner', 'read', [[id_user]])[0]

        # Llamar a la API externa para autenticarse
        login_response = await login_to_external_api()
        api_token = login_response.get("token")  # Obtener el token de autenticación

        # Construir el cuerpo de la solicitud para crear el cliente en Pontis
        customer_data = build_customer_data(id_user, updated_contact, id_plan)

        # Llamar a la API de creación de clientes en Pontis
        create_customer_response = await create_customer_in_pontis(api_token, customer_data)
        # -------------------------------------------------------------------------------------------

       
        return {"detail": "Factura creada y pagada correctamente", 
                "invoice_id": invoice_id, 
                "payment_id": payment_register_id,
                "res_pontis": create_customer_response
                }

    except HTTPException as http_error:
        # Error esperado
        raise http_error
    except Exception as e:
        # Error inesperado
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    

