from fastapi import APIRouter, HTTPException, Depends
from app.core.security import verify_token
from app.core.database import get_odoo_connection

router = APIRouter(prefix="/groups", tags=["groups"])

# Obtener todos los grupos
@router.get("/")
async def get_groups(token=Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Obtener los grupos con sus nombres
        groups = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.groups', 'search_read', 
            [[], ['id', 'name']]
        )
        
        # Obtener los xml_ids de los grupos
        group_ids = [group['id'] for group in groups]
        xml_ids = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'ir.model.data', 'search_read', 
            [[('model', '=', 'res.groups'), ('res_id', 'in', group_ids)]],
            {'fields': ['res_id', 'name']}
        )

        # Mapear xml_ids a sus respectivos grupos
        xml_id_map = {item['res_id']: item['name'] for item in xml_ids}
        for group in groups:
            group['xml_id'] = xml_id_map.get(group['id'], None)

        return {"groups": groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener los grupos: {str(e)}")

# Obtener detalles de un grupo por su ID
@router.get("/{group_id}")
async def get_group(group_id: int, token=Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Obtener información básica del grupo
        group = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.groups', 'read', [[group_id]]
        )
        if not group:
            raise HTTPException(status_code=404, detail="Grupo no encontrado.")

        # Obtener xml_id del grupo
        xml_id_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'ir.model.data', 'search_read',
            [[('model', '=', 'res.groups'), ('res_id', '=', group_id)]],
            {'fields': ['name']}
        )
        group[0]['xml_id'] = xml_id_data[0]['name'] if xml_id_data else None

        return {"group": group[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener el grupo: {str(e)}")
