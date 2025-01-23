from fastapi import APIRouter, HTTPException, Depends
from app.core.security import verify_token
from app.core.database import get_odoo_connection

router = APIRouter(prefix="/sales", tags=["sales"])

# Obtener todas las órdenes de venta
@router.get("/orders")
def get_sale_orders(str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_read', [[]]
        )
        return {"sale_orders": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Obtener los datos de una venta
@router.get("/order/{order_id}")
def get_sale_order(order_id: int, str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'read', [[order_id]]
        )
        return {"sale_order": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Crear una nueva venta
@router.post("/create_order")
def create_sale_order(sale_order: dict, str=Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Validar que el JSON contenga las claves necesarias
        if "partner_id" not in sale_order or "order_line" not in sale_order:
            raise HTTPException(
                status_code=400, detail="El JSON debe contener 'partner_id' y 'order_line'"
            )

        # Transformar las líneas de pedido al formato esperado por Odoo
        order_lines = sale_order.get("order_line", [])
        sale_order["order_line"] = [
            [0, 0, line] for line in order_lines if "product_id" in line and "product_uom_qty" in line and "price_unit" in line
        ]

        # Crear la orden de venta en Odoo
        sale_order_id = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'create', [sale_order]
        )
        return {"sale_order_id": sale_order_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Confirmar una orden de venta 
@router.post("/confirm_order/{order_id}")
def confirm_sale_order(order_id: int, token: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Validar que la venta exista
        sale_order_exists = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', order_id]]]
        )
        if not sale_order_exists:
            raise HTTPException(status_code=404, detail=f"La venta con ID {order_id} no existe.")

        # Validar que la venta no esté confirmada
        sale_order_confirmed = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', order_id], ['state', '=', 'sale']]]
        )
        if sale_order_confirmed:
            raise HTTPException(status_code=400, detail=f"La venta con ID {order_id} ya está confirmada.")

        # Confirmar la venta
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'action_confirm', [[order_id]]
        )
        return {"success": True, "message": f"La venta con ID {order_id} ha sido confirmada."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al confirmar la venta: {str(e)}")


# Actualizar una venta comprobando que dicha venta exista y que no esté confirmada
@router.patch("/update_order/{order_id}")
def update_sale_order(order_id: int, sale_order: dict, token: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Validar que la venta exista
        sale_order_exists = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', order_id]]]
        )
        if not sale_order_exists:
            raise HTTPException(status_code=404, detail=f"La venta con ID {order_id} no existe.")

        # TODO: Verificar que campos si se podrian actualizar a pesar de que la venta este confirmada
        # Validar que la venta no esté confirmada
        sale_order_confirmed = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', order_id], ['state', '=', 'sale']]]
        )
        if sale_order_confirmed:
            raise HTTPException(status_code=400, detail=f"La venta con ID {order_id} ya está confirmada.")

        # Actualizar la venta
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'write', [[order_id], sale_order]
        )
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Cancelar una venta ya confirmada, verificando que la venta exista y que esté confirmada
@router.post("/cancel_order/{order_id}")
def cancel_sale_order(order_id: int, token: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Validar que la venta exista
        sale_order_exists = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', order_id]]]
        )
        if not sale_order_exists:
            raise HTTPException(status_code=404, detail=f"La venta con ID {order_id} no existe.")

        # Validar que la venta esté confirmada
        sale_order_confirmed = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', order_id], ['state', '=', 'sale']]]
        )
        if not sale_order_confirmed:
            raise HTTPException(status_code=400, detail=f"La venta con ID {order_id} no está confirmada.")

        # Cambiar el estado de la orden a "cancel"
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'write', [[order_id], {'state': 'cancel'}]
        )

        if not result:
            raise HTTPException(status_code=500, detail=f"No se pudo cancelar la venta con ID {order_id}.")

        return {"success": True, "message": f"La venta con ID {order_id} ha sido cancelada exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Eliminar una venta
@router.delete("/delete_order/{order_id}")
def delete_sale_order(order_id: int, token: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Validar que la venta exista
        sale_order_exists = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', order_id]]]
        )
        if not sale_order_exists:
            raise HTTPException(status_code=404, detail=f"La venta con ID {order_id} no existe.")

        # Validar que la venta no esté confirmada
        sale_order_confirmed = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', order_id], ['state', '=', 'sale']]]
        )
        if sale_order_confirmed:
            raise HTTPException(status_code=400, detail=f"No se puede eliminar la venta con ID {order_id} porque ya está confirmada.")

        # Eliminar la venta
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'unlink', [[order_id]]
        )
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))