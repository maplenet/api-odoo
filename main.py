from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from fastapi.middleware.cors import CORSMiddleware
import xmlrpc.client

app = FastAPI()


# Configura las opciones de CORS
origins = [
    "http://localhost",  # Origenes permitidos
    "http://localhost:4321",  # Otro origen permitido
    "https://maplenet-api.com",  # Dominios en producción
    "https://maplenet.com.bo",  # Dominios en producción

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Lista de orígenes permitidos
    allow_credentials=True,  # Permitir cookies y autenticación
    allow_methods=["*"],  # Métodos permitidos (GET, POST, etc.)
    allow_headers=["*"],  # Encabezados permitidos
)

# Configuración JWT
SECRET_KEY = "your_secret_key"  # Cambia esto por una clave segura
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# Configuración de conexión a Odoo
url = 'http://192.168.10.184:8069'
db = 'odoo16db'
username = 'admin'
password = '0c55a31bbfa992802c0c8ef87fcae9ef294382b1'

# Conexión común a Odoo
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
if not uid:
    raise Exception("Autenticación fallida en Odoo")

# Objeto para interactuar con modelos de Odoo
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# Bienvenida
@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de integración con Odoo"}

# Obtener versión de Odoo
@app.get("/version")
def get_odoo_version():
    try:
        version = common.version()
        return {"version": version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Confirmar orden de compra
@app.post("/confirm_order")
def confirm_order(order: dict):
    try:
        order_id = order.get("order_id")
        if not order_id:
            raise HTTPException(status_code=400, detail="El campo 'order_id' es requerido.")
        result = models.execute_kw(
            db, uid, password,
            'purchase.order',
            'button_confirm',
            [[order_id]]
        )
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Buscar contactos
@app.post("/search_contacts")
def search_contacts(search: dict):
    try:
        query = search.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="El campo 'query' es requerido.")
        limit = search.get("limit", 10)
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'name_search',
            [query],
            {'limit': limit}
        )
        return {"contacts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Obtener IDs de contactos en general
@app.get("/contacts")
def get_contacts():
    try:
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'search',
            [[]]
        )
        return {"contacts": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Obtener empresas clientes
@app.get("/companies")
def get_companies():
    try:
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'search',
            [[['is_company', '=', True]]]
        )
        return {"companies": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Listar compañías paginadas
@app.get("/companies_paginated")
def get_companies_paginated(offset: int = Query(0), limit: int = Query(10)):
    try:
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'search',
            [[['is_company', '=', True]]],
            {'offset': offset, 'limit': limit}
        )
        return {"companies": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Crear un nuevo contacto
@app.post("/create_contact")
def create_contact(contact: dict):
    try:
        contact_id = models.execute_kw(
            db, uid, password,
            'res.partner',
            'create',
            [contact]
        )
        return {"contact_id": contact_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Crear un nuevo contacto básico 
@app.post("/create_contact_basic")
def create_contact_basic(contact: dict):
    try:
        # Validar que no exista otro contacto con el mismo email o móvil
        email = contact.get("email")
        mobile = contact.get("mobile")
        if not email or not mobile:
            raise HTTPException(status_code=400, detail="Los campos 'email' y 'mobile' son requeridos.")

        existing_contacts = models.execute_kw(
            db, uid, password,
            'res.partner',
            'search_count',
            [[
                '|', ['email', '=', email], ['mobile', '=', mobile]
            ]]
        )
        if existing_contacts > 0:
            raise HTTPException(status_code=400, detail="Ya existe un contacto con el mismo email o móvil.")
        
        # Crear el contacto
        contact_id = models.execute_kw(
            db, uid, password,
            'res.partner',
            'create',
            [contact]
        )
        
        # Devolver el resultado incluyendo las líneas extra
        return {
            "contact_id": contact_id,
            "user": email,
            "password": mobile
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
# @app.post("/create_contact")
# async def create_contact(
#     image: UploadFile = File(None),
#     **contact_fields  # Captura el resto de los campos dinámicamente
# ):
#     try:
#         # Procesar la imagen si está presente
#         if image:
#             image_content = await image.read()
#             contact_fields["image_1920"] = base64.b64encode(image_content).decode("utf-8")

#         # Convertir `category_id` de cadena a lista de enteros si está presente
#         if "category_id" in contact_fields:
#             contact_fields["category_id"] = [
#                 int(cid) for cid in contact_fields["category_id"].split(",")
#             ]

#         # Crear el contacto en Odoo
#         contact_id = models.execute_kw(
#             db, uid, password,
#             'res.partner',
#             'create',
#             [contact_fields]
#         )
#         return {"contact_id": contact_id}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# Obtener detalles de contacto
@app.get("/contact/{contact_id}")
def get_contact(contact_id: int):
    try:
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'read',
            [[contact_id]]
        )
        return {"contact": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Obtener detalles de todos los contactos
@app.get("/contacts/list")
def get_contacts():
    try:
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'search_read',
            [[]]
        )
        return {"contacts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# TODO: Realizar más endpoints de listados en función de más parámetros requeridos 

# Lista contactos paginados y filtrados por nombre y empresa a la que pertenecen, y campos especificos
@app.get("/contacts/paginated")
def get_contacts_paginated(offset: int = Query(0), limit: int = Query(10), query: str = Query(None)):
    try:
        domain = []
        if query:
            domain = ['|', ['name', 'ilike', query], ['parent_id.name', 'ilike', query]]
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'search_read',
            [domain],
            {'offset': offset, 'limit': limit, 'fields': ['name', 'email', 'phone', 'parent_id']}
        )
        return {"contacts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Listar contactos paginados con filtro de nombre y campos especificos
@app.get("/contacts/paginated/name")
def get_contacts_paginated(offset: int = Query(0), limit: int = Query(10), query: str = Query(None)):
    try:
        domain = []
        if query:
            domain = [['name', 'ilike', query]]
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'search_read',
            [domain],
            {'offset': offset, 'limit': limit, 'fields': ['name', 'email', 'phone']}
        )
        return {"contacts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Obtener detalles especificos de todos los contactos, es decir nombre, correo, celular, direccion, las ordenes de venta que tiene este contacto y el total de registros
@app.get("/contacts/list/details")
def get_contacts_details():
    try:
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'search_read',
            [[]],
            {'fields': ['name', 'email', 'mobile', 'street', 'city', 'country_id', 'pos_order_ids', 'sale_order_ids']}
        )
        return {"contacts": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Actualizar un contacto 
@app.patch("/contact/{contact_id}")
def update_contact(contact_id: int, contact: dict):
    try:
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'write',
            [[contact_id], contact]
        )
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Eliminar un contacto
@app.delete("/contact/{contact_id}")
def delete_contact(contact_id: int):
    try:
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'unlink',
            [[contact_id]]
        )
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#--------------------------------------------------------------------Inicio de sesión con JWT

# OAuth2PasswordBearer (URL para obtener el token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Lista negra para invalidar tokens
blacklisted_tokens = set()

# Crear un token de acceso
def create_access_token(username: str, expires_delta: timedelta = None):
    to_encode = {"sub": username, "iat": datetime.now(timezone.utc)}
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Verificar el token
def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        if token in blacklisted_tokens:
            raise HTTPException(status_code=401, detail="Token inválido o expirado")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

@app.post("/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username")
    password = body.get("password")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Se requieren 'username' y 'password'")

    # Obtener
    contacts = get_contacts_details().get("contacts")

    # Verificar si existe un contacto con email == username y mobile == password
    matched_contact = next((contact for contact in contacts if contact['email'] == username and contact['mobile'] == password), None)
    if not matched_contact:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    # Crear el token si se encuentra coincidencia
    access_token = create_access_token(username)
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint protegido para probar endpoints con JWT
@app.get("/protected")
def protected_route(username: str = Depends(verify_token)):
    return {"message": f"Bienvenido {username}, esta es una ruta protegida."}

# Endpoint para cerrar sesión (Logout)
@app.post("/logout")
def logout(token: str = Depends(oauth2_scheme)):
    blacklisted_tokens.add(token)
    return {"message": "Sesión cerrada exitosamente"}

#--------------------------------------------------------------------Enpoints para el módulo Puntos de Venta

# Obtener todos los puntos de venta
@app.get("/pos")
def get_pos():
    try:
        result = models.execute_kw(
            db, uid, password,
            'pos.config',
            'search_read',
            [[]]
        )
        return {"pos": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Cerar una sesión de punto de venta 
@app.patch("/pos/close_sessions/{pos_id}")
def close_pos_sessions(pos_id: int):
    try:
        # Buscar sesiones abiertas para el punto de venta especificado
        open_sessions = models.execute_kw(
            db, uid, password, 'pos.session', 'search',
            [[['config_id', '=', pos_id], ['state', '=', 'opened']]]
        )

        if not open_sessions:
            return {"message": f"No hay sesiones abiertas para el punto de venta con ID {pos_id}."}

        # Cerrar cada sesión abierta
        models.execute_kw(
            db, uid, password, 'pos.session', 'action_pos_session_closing_control',
            [open_sessions]
        )

        return {
            "message": f"Se cerraron {len(open_sessions)} sesiones abiertas para el punto de venta con ID {pos_id}."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cerrar las sesiones: {str(e)}")



