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
