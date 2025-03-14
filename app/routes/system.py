from fastapi import APIRouter, HTTPException
from app.core.database import get_odoo_connection
from app.config import settings
import xmlrpc.client

from app.services.odoo_service import execute_odoo_method

router = APIRouter(tags=["system"])

@router.get("/")
def read_root():
    return {"detail": "Bienvenido a la API de integración con Odoo"}

@router.get("/version")
def get_odoo_version():
    try:
        # Crear conexión al cliente 'common' de Odoo
        common = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/common")
        
        # Llamar al método 'version' para obtener información del sistema
        version = common.version()
        
        return {"version": version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/countries", summary="Obtiene la lista de países")
async def get_countries():
    """
    Obtiene todos los países registrados en Odoo.
    Devuelve un JSON con una lista de países, cada uno con su ID y nombre.
    """
    try:
        conn = get_odoo_connection()
        countries = execute_odoo_method(
            conn,
            'res.country',
            'search_read',
            [[]],  # sin dominio, obtiene todos
            {'fields': ['id', 'name']}
        )
        return {"countries": countries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener países: {str(e)}")

@router.get("/states", summary="Obtiene la lista de estados/regiones")
async def get_states():
    """
    Obtiene todos los estados/regiones registrados en Odoo.
    Cada estado incluye su ID, nombre y el país asociado (devuelto como [id, name]).
    """
    try:
        conn = get_odoo_connection()
        states = execute_odoo_method(
            conn,
            'res.country.state',
            'search_read',
            [[]],
            {'fields': ['id', 'name', 'country_id']}
        )
        return {"states": states}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estados: {str(e)}")