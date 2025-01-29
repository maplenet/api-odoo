from fastapi import APIRouter, HTTPException, Query, Depends, Request
from app.core.security import verify_token
from app.core.database import get_odoo_connection, get_sqlite_connection
from app.core.email_utils import send_email


router = APIRouter(prefix="/users", tags=["users"])


@router.post("/create")
async def create_user(request: Request, token=Depends(verify_token)):
    try:
        # Obtener los datos del cuerpo de la solicitud
        body = await request.json()
        name = body.get("name")
        email = body.get("email")
        password = body.get("password")
        verify_password = body.get("verify_password")
        mobile = body.get("mobile")

        # Validar que todos los campos requeridos estén presentes
        if not all([name, email, password, verify_password, mobile]):
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

        # Verificar que las contraseñas coincidan
        if password != verify_password:
            raise HTTPException(status_code=400, detail="Las contraseñas no coinciden.")

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
                'password': password,
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
async def get_user_with_orders(user_id: int, token=Depends(verify_token)):
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

        # Obtener información del contacto (partner)
        partner_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner', 'read', [[partner_id]],
            {'fields': ['name', 'email', 'phone', 'mobile', 'street', 'city', 'country_id']}
        )

        if not partner_data:
            raise HTTPException(status_code=404, detail="No se encontró información del contacto.")

        partner = partner_data[0]

        # Obtener todas las órdenes de PdV asociadas a este contacto
        pos_orders = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'pos.order', 'search_read',
            [[['partner_id', '=', partner_id]]],
            {'fields': ['name', 'date_order', 'amount_total', 'state', 'lines']}
        )

        # Obtener detalles de las líneas de cada orden
        for order in pos_orders:
            order_lines = conn['models'].execute_kw(
                conn['db'], conn['uid'], conn['password'],
                'pos.order.line', 'search_read',
                [[['order_id', '=', order['id']]]],
                {'fields': ['product_id', 'qty', 'price_unit', 'discount', 'price_subtotal']}
            )

            # Obtener detalles de los productos en las líneas
            for line in order_lines:
                product_id = line.get('product_id', [None])[0]
                if product_id:
                    product_data = conn['models'].execute_kw(
                        conn['db'], conn['uid'], conn['password'],
                        'product.product', 'read', [[product_id]],
                        {'fields': ['name', 'default_code', 'list_price']}
                    )
                    if product_data:
                        line['product_details'] = product_data[0]

            order['order_lines'] = order_lines

        # Respuesta consolidada
        return {
            "user": user,
            "partner": partner,
            "pos_orders": pos_orders
        }

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

