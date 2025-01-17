from fastapi import FastAPI, HTTPException, Query
import xmlrpc.client

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

#--------------------------------------------------------------------
# Decir hola
@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"Hello, {name}!"}

# Sumar dos números
@app.get("/add")
def add_numbers(a: int, b: int):
    return {"result": a + b}
