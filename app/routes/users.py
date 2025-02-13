from fastapi import APIRouter, HTTPException, Depends, Request
import re
from app.core.security import verify_token
from app.core.database import get_odoo_connection, get_sqlite_connection
from datetime import datetime, timedelta, timezone
from app.services.api_service import build_customer_data, create_customer_in_pontis, login_to_external_api
from app.services.odoo_service import execute_odoo_method
from app.services.sqlite_service import get_decrypted_password, get_user_record, insert_user_record, update_user_password
from app.services.sqlite_service import update_user_policies  # Asegúrate de importar la función



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
                detail="The password must have at least 8 characters and max 40 characteres, including 1 uppercase, 1 lowercase and 1 number."
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
async def get_user_with_service(user_id: int, token_payload: dict = Depends(verify_token)):
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
            {'fields': ['email', 'name', 'password', 'mobile', 'street', 'partner_id']}
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
                "street": user_record.get("street") or "",
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
async def update_user(request: Request, token_payload: dict = Depends(verify_token)):
    """
    Actualiza los datos del usuario, crea una factura y registra el pago.
    Se requiere que el 'id_usuario' enviado en el body coincida con el 'user_id' del token.
    Se realizan múltiples validaciones sobre los datos ingresados.
    """
    try:
        # Obtener el user_id del token y comparar con el id_usuario del body
        token_user_id = token_payload.get("user_id")
        
        body = await request.json()
        
        # Convertir y validar que id_plan e id_usuario sean enteros
        try:
            id_plan = int(body.get("id_plan"))
            id_user = int(body.get("id_usuario"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Los campos 'id_plan' e 'id_usuario' deben ser números.")
        
        if id_user != token_user_id:
            raise HTTPException(status_code=403, detail="No estás autorizado para actualizar otro usuario.")
        
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
        company_registry = num_doc
        
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
                "company_registry": company_registry,
                "vat": num_doc,
                "l10n_bo_extension": l10n_bo_extension if type_doc == "4" else '',
                'l10n_bo_business_name': legal_Name,
            }]
        )
        if not success:
            raise HTTPException(status_code=500, detail="No se pudo actualizar el usuario.")
        
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
        
        updated_contact = execute_odoo_method(conn, 'res.partner', 'read', [[partner_id]])


        # Obtener el password desencriptado del usuario (nuevo)
        plain_password = get_decrypted_password(id_user)

        print("plain_password: ", plain_password)

        # Conexión a Pontis
        await login_to_external_api()
        customer_data = build_customer_data(id_user, updated_contact, id_plan, plain_password)
        create_customer_response = await create_customer_in_pontis(customer_data)

        # Actualizar el usuario en SQLite para marcar la aceptación de políticas
        update_user_policies(id_user)
        
        return {
            "detail": "Factura creada y pagada correctamente", 
            "invoice_id": invoice_id, 
            "payment_id": payment_register_id,
            "res_pontis": create_customer_response
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


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