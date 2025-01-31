from fastapi import APIRouter, HTTPException, Depends
from app.core.security import verify_token
from app.core.database import get_odoo_connection
from app.services.sale_service import confirm_quotation, create_invoice, confirm_invoice, send_invoice_by_email


router = APIRouter(prefix="/sales", tags=["sales"])


# Obtener los datos de una venta específica
@router.get("/{order_id}")
async def get_sale_order(order_id: int, token: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Obtener los datos de una venta específica
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'read', [[order_id]]
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"La venta con ID {order_id} no existe.")
        return {"sale_order": result}
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener la venta: {str(e)}")

# Obtener Todas las Órdenes de Venta
@router.get("/orders")
async def get_sale_orders(token: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Obtener todas las órdenes de venta
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_read', [[]]
        )
        return {"sale_orders": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener las órdenes de venta: {str(e)}")
    
# Crear una cotización (orden de venta en estado "draft")
@router.post("/create_quotation")
async def create_quotation(request: dict, token: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Validar que el JSON contenga las claves necesarias
        if "partner_id" not in request or "order_line" not in request:
            raise HTTPException(
                status_code=400, detail="El JSON debe contener 'partner_id' y 'order_line'"
            )

        # Validar que solo haya un producto en order_line
        order_lines = request.get("order_line", [])
        if len(order_lines) != 1:
            raise HTTPException(
                status_code=400, detail="Solo se permite un producto en 'order_line'."
            )

        # Validar que el producto tenga los campos obligatorios
        product = order_lines[0]
        required_fields = ["product_id", "product_uom_qty", "price_unit"]
        for field in required_fields:
            if field not in product:
                raise HTTPException(
                    status_code=400, detail=f"El campo '{field}' es obligatorio en 'order_line'."
                )

        # Validar que los valores sean válidos
        if not isinstance(product["product_id"], int) or product["product_id"] <= 0:
            raise HTTPException(
                status_code=400, detail="El campo 'product_id' debe ser un número entero positivo."
            )

        if not isinstance(product["product_uom_qty"], (int, float)) or product["product_uom_qty"] <= 0:
            raise HTTPException(
                status_code=400, detail="El campo 'product_uom_qty' debe ser un número positivo."
            )

        if not isinstance(product["price_unit"], (int, float)) or product["price_unit"] <= 0:
            raise HTTPException(
                status_code=400, detail="El campo 'price_unit' debe ser un número positivo."
            )

        # Asegurarse de que no se apliquen impuestos
        product["tax_id"] = []  # Desactivar impuestos

        # Transformar las líneas de pedido al formato esperado por Odoo
        formatted_lines = [[0, 0, product]]

        # Crear la cotización en Odoo
        quotation_id = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'create', [{
                'partner_id': request['partner_id'],
                'order_line': formatted_lines,
                'state': 'draft'  # Estado de cotización
            }]
        )

        return {"success": True, "quotation_id": quotation_id}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la cotización: {str(e)}")

# Cancelar una cotización
@router.post("/cancel_quotation/{quotation_id}")
async def cancel_quotation(quotation_id: int, token: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Validar que la cotización exista
        quotation_exists = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', quotation_id]]]
        )
        if not quotation_exists:
            raise HTTPException(status_code=404, detail=f"La cotización con ID {quotation_id} no existe.")

        # Validar que la cotización esté en estado "draft" (borrador)
        quotation_state = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'read', [[quotation_id]], {'fields': ['state']}
        )
        if quotation_state[0]['state'] != 'draft':
            raise HTTPException(
                status_code=400,
                detail=f"La cotización con ID {quotation_id} no está en estado 'draft' y no puede ser cancelada."
            )

        # Cambiar el estado de la cotización a "cancel"
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'write', [[quotation_id], {'state': 'cancel'}]
        )

        if not result:
            raise HTTPException(
                status_code=500,
                detail=f"No se pudo cancelar la cotización con ID {quotation_id}."
            )

        return {"success": True, "message": f"La cotización con ID {quotation_id} ha sido cancelada exitosamente."}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cancelar la cotización: {str(e)}")
    
# Eliminar una venta
@router.delete("/delete_sale/{sale_id}")
async def delete_sale(sale_id: int, token: str = Depends(verify_token)):
    conn = get_odoo_connection()
    try:
        # Validar que la venta exista
        sale_exists = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', sale_id]]]
        )
        if not sale_exists:
            raise HTTPException(status_code=404, detail=f"La venta con ID {sale_id} no existe.")

        # Validar que la venta esté en estado "draft" o "cancel"
        sale_state = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'read', [[sale_id]], {'fields': ['state']}
        )
        if sale_state[0]['state'] not in ['draft', 'cancel']:
            raise HTTPException(
                status_code=400,
                detail=f"La venta con ID {sale_id} no está en estado 'draft' o 'cancel' y no puede ser eliminada."
            )

        # Eliminar la venta
        result = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'unlink', [[sale_id]]
        )

        if not result:
            raise HTTPException(
                status_code=500,
                detail=f"No se pudo eliminar la venta con ID {sale_id}."
            )

        return {"success": True, "detail": f"La venta con ID {sale_id} ha sido eliminada exitosamente."}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la venta: {str(e)}")

# Confirmar una cotización    
@router.post("/confirm_quotation/{quotation_id}")
async def confirm_quotation_endpoint(quotation_id: int, token: str = Depends(verify_token)):
    try:
        # Paso 1: Confirmar la cotización
        confirm_quotation(quotation_id)

        # Paso 2: Crear la factura
        invoice_id = create_invoice(quotation_id)

        # Paso 3: Enviar la factura por correo
        send_invoice_by_email(invoice_id)

        return {
            "success": True,
            "detail": f"La cotización con ID {quotation_id} ha sido confirmada, facturada y enviada por correo.",
            "invoice_id": invoice_id
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el proceso: {str(e)}")