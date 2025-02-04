from fastapi import APIRouter, HTTPException, Query, Depends, Request
from app.core.security import verify_token
from app.core.database import get_odoo_connection, get_sqlite_connection
from app.core.email_utils import send_email
from datetime import datetime, timedelta, timezone


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
    
# TODO: Verificar el funcionamiento de la función    
# Restablecer la contraseña de un usuario
@router.post("/reset_password")
async def reset_password(request: Request):
    odoo_conn = get_odoo_connection()
    try:
        # Obtener los datos del cuerpo de la solicitud
        body = await request.json()
        email = body.get("email")

        # Validar que el campo de correo electrónico esté presente
        if not email:
            raise HTTPException(status_code=400, detail="El campo 'email' es obligatorio.")

        # Buscar el usuario por correo electrónico
        user_ids = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'search', [[('email', '=', email)]]
        )
        if not user_ids:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        # Enviar correo de restablecimiento de contraseña
        response = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'action_reset_password', [user_ids]
        )

        # Registrar la respuesta para depuración
        print(f"Respuesta de action_reset_password: {response}")

        if not response:
            raise HTTPException(status_code=500, detail="No se pudo enviar el correo de restablecimiento de contraseña.")

        return {"detail": "Correo de restablecimiento de contraseña enviado exitosamente."}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# Actualizar un usuario smtp.gmail.com

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

@router.get("/{user_id}")
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
            "date_expiration": date_expiration.strftime("%Y-%m-%d %H:%M:%S"),
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

