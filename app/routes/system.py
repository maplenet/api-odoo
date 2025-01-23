from fastapi import APIRouter, HTTPException
from app.core.database import get_odoo_connection

router = APIRouter(tags=["system"])

@router.get("/")
def read_root():
    return {"message": "Bienvenido a la API de integración con Odoo"}

@router.get("/version")
def get_odoo_version():
    conn = get_odoo_connection()
    try:
        version = conn['models'].version()
        return {"version": version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))