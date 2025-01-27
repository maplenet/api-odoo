from fastapi import APIRouter, HTTPException, Query, Depends, Request
from app.core.security import verify_token
from app.core.database import get_odoo_connection, get_sqlite_connection
from app.core.email_utils import send_email


router = APIRouter(prefix="/users", tags=["users"])

# Obtener datos de un usuario usando metodos asincronos y manejo de promesas
@router.get("/{user_id}")
async def get_user(user_id: int, token=Depends(verify_token)):
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
    
# # Crear un nuevo usuario
# @router.post("/create")
# async def create_user(request: Request, str=Depends(verify_token)):
#     try:
#         # Obtener los datos del cuerpo de la solicitud
#         body = await request.json()
#         name = body.get("name")
#         email = body.get("email")
#         username = body.get("username")
#         password = body.get("password")
#         verify_password = body.get("verify_password")
#         mobile = body.get("mobile")

#         # Validar que todos los campos requeridos estén presentes
#         if not all([name, email, username, password, verify_password, mobile]):
#             raise HTTPException(status_code=400, detail="Todos los campos son obligatorios.")

#         # Verificar el correo en la tabla de verification_codes
#         sqlite_conn = get_sqlite_connection()
#         cursor = sqlite_conn.cursor()
#         cursor.execute("SELECT * FROM verification_codes WHERE email = ? ORDER BY id DESC LIMIT 1", (email,))
#         verification_record = cursor.fetchone()

#         if not verification_record:
#             raise HTTPException(status_code=400, detail="El correo no ha sido registrado para verificación.")

#         # Verificar el estado del registro
#         status = verification_record[2]  # Índice del estado en la tabla
#         if status == 0:
#             raise HTTPException(status_code=400, detail="El correo no ha sido verificado.")

#         # Verificar que las contraseñas coincidan
#         if password != verify_password:
#             raise HTTPException(status_code=400, detail="Las contraseñas no coinciden.")

#         # Verificar que el username no esté en uso
#         odoo_conn = get_odoo_connection()
#         username_exists = odoo_conn['models'].execute_kw(
#             odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
#             'res.users', 'search_count', [[('phone', '=', username)]]
#         )
#         if username_exists > 0:
#             raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso.")

#         # Iniciar transacción para crear el usuario
#         odoo_conn['models'].execute_kw(
#             odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
#             'res.users', 'create', [{
#                 'login': email,
#                 'name': name,
#                 'email': email,
#                 'password': password,
#                 'phone': username,
#                 'mobile': mobile,
#             }]
#         )

#         return {"detail": "Usuario creado exitosamente."}

#     except HTTPException as http_error:
#         raise http_error
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
#     finally:
#         sqlite_conn.close()

# Crear un nuevo usuario
@router.post("/create")
async def create_user(request: Request, str=Depends(verify_token)):
    try:
        # Obtener los datos del cuerpo de la solicitud
        body = await request.json()
        name = body.get("name")
        email = body.get("email")
        username = body.get("username")
        password = body.get("password")
        verify_password = body.get("verify_password")
        mobile = body.get("mobile")

        # Validar que todos los campos requeridos estén presentes
        if not all([name, email, username, password, verify_password, mobile]):
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

        # Verificar que el username no esté en uso
        odoo_conn = get_odoo_connection()
        username_exists = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'search_count', [[('phone', '=', username)]]
        )
        if username_exists > 0:
            raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso.")

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

        # Iniciar transacción para crear el usuario
        user_id = odoo_conn['models'].execute_kw(
            odoo_conn['db'], odoo_conn['uid'], odoo_conn['password'],
            'res.users', 'create', [{
                'login': email,
                'name': name,
                'email': email,
                'password': password,
                'phone': username,
                'mobile': mobile,
                'groups_id': [(6, 0, [group_portal_id])]  # Asignar grupo Portal
            }]
        )

        return {"detail": "Usuario creado exitosamente.", "user_id": user_id}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        sqlite_conn.close()
