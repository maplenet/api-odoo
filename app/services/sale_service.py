from app.core.database import get_odoo_connection

def confirm_quotation(quotation_id):
    """
    Confirma una cotización en Odoo.
    """
    conn = get_odoo_connection()
    try:
        # Validar que la cotización exista
        quotation_exists = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'search_count', [[['id', '=', quotation_id]]]
        )
        if not quotation_exists:
            raise ValueError(f"La cotización con ID {quotation_id} no existe.")

        # Validar que la cotización esté en estado "draft"
        quotation_state = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'read', [[quotation_id]], {'fields': ['state']}
        )
        if quotation_state[0]['state'] != 'draft':
            raise ValueError(f"La cotización con ID {quotation_id} no está en estado 'draft'.")

        # Confirmar la cotización
        conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'action_confirm', [[quotation_id]]
        )
        return True

    except Exception as e:
        raise ValueError(f"Error al confirmar la cotización: {str(e)}")


def create_invoice(quotation_id):
    """
    Crea una factura a partir de una cotización confirmada.
    """
    conn = get_odoo_connection()
    try:
        # Obtener la orden de venta
        sale_order = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'read', [[quotation_id]], {'fields': ['partner_id', 'order_line']}
        )
        if not sale_order:
            raise ValueError(f"La cotización con ID {quotation_id} no existe.")

        # Obtener las líneas de la orden de venta
        order_lines = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order.line', 'read', [sale_order[0]['order_line']], {'fields': ['product_id', 'product_uom_qty', 'price_unit']}
        )

        # Crear las líneas de la factura
        invoice_line_ids = []
        for line in order_lines:
            invoice_line_ids.append([0, 0, {
                'product_id': line['product_id'][0] if isinstance(line['product_id'], (list, tuple)) else line['product_id'],
                'quantity': line['product_uom_qty'],
                'price_unit': line['price_unit'],
            }])

        # Crear la factura manualmente
        invoice_id = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'create', [{
                'move_type': 'out_invoice',  # Tipo de factura (factura de cliente)
                'partner_id': sale_order[0]['partner_id'][0],  # ID del cliente
                'invoice_line_ids': invoice_line_ids,
            }]
        )
        if not invoice_id:
            raise ValueError("No se pudo crear la factura.")

        # Vincular la factura a la orden de venta
        conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'sale.order', 'write', [[quotation_id], {'invoice_ids': [(4, invoice_id)]}]
        )

        # Confirmar la factura
        conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'action_post', [[invoice_id]]
        )

        return invoice_id  # Retorna el ID de la factura creada

    except Exception as e:
        raise ValueError(f"Error al crear la factura: {str(e)}")

def confirm_invoice(invoice_id):
    """
    Confirma una factura en Odoo.
    """
    conn = get_odoo_connection()
    try:
        # Confirmar la factura
        conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'action_post', [[invoice_id]]
        )
        return True

    except Exception as e:
        raise ValueError(f"Error al confirmar la factura: {str(e)}")


def send_invoice_by_email(invoice_id):
    """
    Envía la factura por correo electrónico.
    """
    conn = get_odoo_connection()
    try:
        # Enviar la factura por correo
        conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'action_invoice_sent', [[invoice_id]]
        )
        return True

    except Exception as e:
        raise ValueError(f"Error al enviar la factura por correo: {str(e)}")