from fastapi import FastAPI, HTTPException, Query, File, UploadFile
import xmlrpc.client
import base64


app = FastAPI()

# Configuración de conexión a Odoo
url = 'http://localhost:8069'
db = 'odoo16db'
username = 'admin'
password = '08b5cacf36383f565a1db2e3b5150bbf8f6dae14'

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
    
# Listar contactos paginados con filtro de nombre y campos especificos
@app.get("/contacts/paginated")
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
    
# Obtener detalles especificos de todos los contactos y el total
@app.get("/contacts/list/details")
def get_contacts_details():
    try:
        result = models.execute_kw(
            db, uid, password,
            'res.partner',
            'search_read',
            [[]],
            {'fields': ['name', 'email', 'phone']}
        )
        return {"contacts": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Actualizar un contacto usando patch
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


#--------------------------------------------------------------------
# Decir hola
@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"Hello, {name}!"}

# Sumar dos números
@app.get("/add")
def add_numbers(a: int, b: int):
    return {"result": a + b}
