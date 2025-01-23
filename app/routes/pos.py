from fastapi import APIRouter, HTTPException, Depends
from app.core.security import verify_token
from app.core.database import get_odoo_connection

router = APIRouter(prefix="/pos", tags=["point_of_sale"])

# Obtener todos los puntos de venta
@router.get("/")
def get_pos(str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'pos.config', 'search_read', [[]]
        )
        return {"pos": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Cerar una sesión de punto de venta 
@router.patch("/close_sessions/{pos_id}")
def close_pos_sessions(pos_id: int, str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Buscar sesiones abiertas para el punto de venta especificado
        open_sessions = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'], 
            'pos.session', 'search',
            [[['config_id', '=', pos_id], ['state', '=', 'opened']]]
        )

        if not open_sessions:
            return {"message": f"No hay sesiones abiertas para el punto de venta con ID {pos_id}."}
        # Cerrar cada sesión abierta
        conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'], 
            'pos.session', 'action_pos_session_closing_control',
            [open_sessions]
        )

        return {
            "message": f"Se cerraron {len(open_sessions)} sesiones abiertas para el punto de venta con ID {pos_id}."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cerrar las sesiones: {str(e)}")
    
# Todo: completar los endpoints para el módulo de punto de venta que sean necesarios, en otro caso si este archivo no es necesario eliminarlo