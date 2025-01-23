from fastapi import APIRouter, HTTPException, Depends
from app.core.security import verify_token
from app.core.database import get_odoo_connection

router = APIRouter(prefix="/sales", tags=["sales"])

@router.get("/orders")
def get_sale_orders(username: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_read', [[]]
        )
        return {"sale_orders": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))