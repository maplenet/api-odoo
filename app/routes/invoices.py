import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from app.core.security import verify_token
from app.core.database import get_odoo_connection
from datetime import date

from app.services.odoo_service import execute_odoo_method


router = APIRouter(prefix="/invoices", tags=["invoices"])

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Obtener todos los datos de un factura
@router.get("/get_invoice/{invoice_id}")
async def get_invoice(invoice_id: int):
    """
    Obtiene todos los datos de una factura en Odoo.
    """
    conn = get_odoo_connection()
    try:
        # Obtener los datos de la factura
        invoice_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'read', [invoice_id]
        )

        if not invoice_data:
            raise HTTPException(status_code=404, detail="No se encontró la factura solicitada.")

        # obtenemos el invoice_line_ids
        invoice_line_ids = invoice_data[0]['invoice_line_ids']
        invoice_lines = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move.line', 'read', [invoice_line_ids], {'fields': ['product_id', 'quantity', 'price_unit']}
        )

        return {
            "success": True,
            "invoice_data": invoice_data,
            "invoice_lines": invoice_lines
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener la factura: {str(e)}")
    
# Crear una factura en estado de borrador
@router.post("/create_draft_invoice")
async def create_draft_invoice(request: Request, token: str = Depends(verify_token)):

    data = await request.json()  # Obtener JSON del request

    # Validar que los campos requeridos estén presentes
    required_fields = ["partner_id", "product_id"]
    for field in required_fields:
        if field not in data:
            logger.error(f"El campo '{field}' es obligatorio.")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Campo obligatorio faltante",
                    "detail": f"El campo '{field}' es obligatorio."
                }
            )

    partner_id = data["partner_id"]
    product_id = data["product_id"]

    conn = get_odoo_connection()
    try:
        # Paso 1: Verificar que el partner exista
        logger.info(f"Verificando la existencia del partner con ID {partner_id}...")
        partner_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner', 'read', [partner_id], {'fields': ['name']}
        )
        if not partner_data:
            logger.error(f"No se encontró el partner con ID {partner_id}.")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Partner no encontrado",
                    "detail": f"El partner con ID {partner_id} no existe en Odoo."
                }
            )
        logger.info(f"Partner verificado: {partner_data[0]['name']}")

        # Paso 2: Obtener el precio de venta del producto
        logger.info(f"Obteniendo el precio de venta del producto con ID {product_id}...")
        product_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'product.product', 'read', [product_id], {'fields': ['list_price']}
        )
        if not product_data:
            logger.error(f"No se pudo obtener el producto con ID {product_id}.")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Producto no encontrado",
                    "detail": f"El producto con ID {product_id} no existe en Odoo."
                }
            )

        list_price = product_data[0]['list_price']  # Precio de venta del producto
        if list_price < 0:
            logger.error(f"El precio del producto {product_id} no es válido: {list_price}.")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Precio no válido",
                    "detail": f"El precio del producto {product_id} no es válido: {list_price}."
                }
            )
        logger.info(f"Precio de venta del producto obtenido: {list_price}")


        # Obtener la información pertinente del contacto para la factura
        partner_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner', 'read', [partner_id], {'fields': [
                'name',                                 # Nombre
                'vat',                                  # NIT
                'l10n_bo_extension',                    # Extensión de carnet
                'l10n_latam_identification_type_id',    # Tipo de identificación
                'l10n_bo_business_name',                # Razón social
                ]}
        )

        logger.info(f"Datos del contacto obtenidos: {partner_data}")

        if not partner_data:
            raise HTTPException(status_code=404, detail="No se encontró el contacto.")
        
        if not all([
            partner_data[0].get('name'), 
            partner_data[0].get('vat'), 
            partner_data[0].get('l10n_latam_identification_type_id'),
            partner_data[0].get('l10n_bo_business_name')
            ]):
            raise HTTPException(status_code=400, detail="Datos incompletos del contacto.")
        
        # Almacenamos en variables los datos obtenidos
        partner_name = partner_data[0]['name']
        partner_vat = partner_data[0]['vat']
        partner_extension = partner_data[0]['l10n_bo_extension'] or ''
        partner_identification_type = partner_data[0]['l10n_latam_identification_type_id'][1]
        

   
        # Crear la factura en estado de borrador llenando los campos necesarios con la información del contacto y el producto
        invoice_id = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'create', [{
                'move_type': 'out_invoice',
                'partner_id': [partner_id, partner_name],
                'vr_nit_ci': partner_vat,
                'vr_extension': partner_extension,

                'invoice_line_ids': [
                    [0, 0, {
                        'product_id': product_id,
                        'quantity': 1,
                        'price_unit': list_price  # Usar el precio del producto
                    }]
                ]
            }]
        )

        if not invoice_id:
            raise HTTPException(status_code=500, detail="No se pudo crear la factura en estado de borrador.")
        
        return {
            "success": True,
            "message": "Proceso exitoso.",
            "invoice_id": invoice_id,
            "product_price": list_price  # Opcional: Devolver el precio usado
        }
        

    except HTTPException as e:
        raise e  # Re-lanzar excepciones HTTP
    except ValueError as e:
        logger.error(f"Error de valor: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Error de valor",
                "detail": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Error en el proceso: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error en el proceso",
                "detail": str(e)
            }
        )

# Confirmar una factura en estado de borrador
@router.post("/confirm_invoice")
async def confirm_invoice(request: Request, token: str = Depends(verify_token)):
    """
    Confirma una factura que está en estado de borrador (draft).
    """
    data = await request.json()  # Obtener JSON del request

    # Validar que el campo invoice_id esté presente
    if "invoice_id" not in data:
        logger.error("El campo 'invoice_id' es obligatorio.")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Campo obligatorio faltante",
                "detail": "El campo 'invoice_id' es obligatorio."
            }
        )

    invoice_id = data["invoice_id"]

    conn = get_odoo_connection()
    try:
        # Paso 1: Verificar que la factura exista y esté en estado draft
        logger.info(f"Verificando la existencia de la factura con ID {invoice_id}...")
        invoice_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'read', [invoice_id], {'fields': ['state']}
        )
        if not invoice_data:
            logger.error(f"No se encontró la factura con ID {invoice_id}.")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Factura no encontrada",
                    "detail": f"La factura con ID {invoice_id} no existe en Odoo."
                }
            )

        # Verificar que la factura esté en estado draft
        if invoice_data[0]['state'] != 'draft':
            logger.error(f"La factura con ID {invoice_id} no está en estado draft.")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Factura no confirmable",
                    "detail": f"La factura con ID {invoice_id} no está en estado draft."
                }
            )
        logger.info(f"Factura verificada: ID {invoice_id}, estado {invoice_data[0]['state']}.")

        # Paso 2: Confirmar la factura
        logger.info("Confirmando la factura...")
        conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'action_post', [[invoice_id]]
        )
        logger.info(f"Factura con ID {invoice_id} confirmada exitosamente.")

        return {
            "success": True,
            "message": "Factura confirmada exitosamente.",
            "invoice_id": invoice_id
        }

    except HTTPException as e:
        raise e  # Re-lanzar excepciones HTTP
    except ValueError as e:
        logger.error(f"Error de valor: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Error de valor",
                "detail": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Error en el proceso: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error en el proceso",
                "detail": str(e)
            }
        )


# Registrar un pago para una factura confirmada
@router.post("/register_payment")
async def register_payment(request: Request, token: str = Depends(verify_token)):
    """
    Registra un pago para una factura ya confirmada.
    """
    data = await request.json()  # Obtener JSON del request

    # Validar que los campos requeridos estén presentes
    required_fields = ["invoice_id", "journal_id", "payment_method_line_id"]
    for field in required_fields:
        if field not in data:
            logger.error(f"El campo '{field}' es obligatorio.")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Campo obligatorio faltante",
                    "detail": f"El campo '{field}' es obligatorio."
                }
            )
    partner_id = 10301
    invoice_id = data["invoice_id"]
    journal_id = data["journal_id"]
    payment_method_line_id = data["payment_method_line_id"]

    conn = get_odoo_connection()

    # --------------------------------

    payment_methods_for_journal = conn['models'].execute_kw(
        conn['db'], conn['uid'], conn['password'],
        'account.payment.method.line', 'search_read',
        [[['journal_id', '=', journal_id]]],  # Filtrar por el diario seleccionado
        {'fields': ['id', 'name']}
    )

    logger.info(f"Métodos de pago para el diario {journal_id}: {payment_methods_for_journal}")



    # Consultar los métodos de pago disponibles y sus diarios
    payment_methods = conn['models'].execute_kw(
        conn['db'], conn['uid'], conn['password'],
        'account.payment.method.line', 'search_read', [[['id', '=', payment_method_line_id]]],
        {'fields': ['id', 'name', 'journal_id']}
    )

    logger.info(f"Métodos de pago obtenidos: {payment_methods}")

    # Validar si el método de pago está asociado al journal_id
    if not payment_methods:
        logger.error(f"El método de pago con ID {payment_method_line_id} no existe en Odoo.")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Método de pago no encontrado",
                "detail": f"El método de pago con ID {payment_method_line_id} no existe en Odoo."
            }
        )

    # Extraer el journal_id del método de pago
    method_journal_id = payment_methods[0].get('journal_id', [None])[0]

    # Comparar con el journal_id enviado en el request
    if method_journal_id != journal_id:
        logger.error(f"El método de pago con ID {payment_method_line_id} no está vinculado al diario {journal_id}.")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Método de pago no válido para este diario",
                "detail": f"El método de pago seleccionado ({payment_methods[0]['name']}) pertenece al diario {method_journal_id}, no al {journal_id}. Elija otro."
            }
        )

    logger.info(f"Método de pago validado: {payment_methods[0]['name']} para el diario {journal_id}.")


    # payment_data = conn['models'].execute_kw(
    #     conn['db'], conn['uid'], conn['password'],
    #     'account.payment', 'read', [payment_id], {'fields': ['payment_method_line_id']}
    # )

    # print(payment_data) 

    #-------

    try:
        # Paso 1: Verificar que la factura exista y esté confirmada
        logger.info(f"Verificando la existencia de la factura con ID {invoice_id}...")
        invoice_data = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.move', 'read', [invoice_id], {'fields': ['state', 'amount_residual', 'partner_id']}
        )
        if not invoice_data:
            logger.error(f"No se encontró la factura con ID {invoice_id}.")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Factura no encontrada",
                    "detail": f"La factura con ID {invoice_id} no existe en Odoo."
                }
            )

        # Verificar que la factura esté confirmada
        if invoice_data[0]['state'] != 'posted':
            logger.error(f"La factura con ID {invoice_id} no está confirmada.")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Factura no confirmada",
                    "detail": f"La factura con ID {invoice_id} no está confirmada."
                }
            )
        logger.info(f"Factura verificada: ID {invoice_id}, estado {invoice_data[0]['state']}.")

        # Paso 2: Obtener el monto residual de la factura
        amount_residual = invoice_data[0]['amount_residual']
        if amount_residual <= 0:
            logger.error(f"La factura con ID {invoice_id} no tiene saldo pendiente.")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Factura sin saldo pendiente",
                    "detail": f"La factura con ID {invoice_id} no tiene saldo pendiente."
                }
            )
        logger.info(f"Monto residual de la factura: {amount_residual}.")

        # Paso 3: Validar que el método de pago exista
        logger.info(f"Validando el método de pago con ID {payment_method_line_id}...")
        payment_method = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.payment.method.line', 'read', [payment_method_line_id], {'fields': ['name']}
        )
        if not payment_method:
            logger.error(f"No se encontró el método de pago con ID {payment_method_line_id}.")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Método de pago no encontrado",
                    "detail": f"El método de pago con ID {payment_method_line_id} no existe en Odoo."
                }
            )
        logger.info(f"Método de pago validado: {payment_method[0]['name']}.")

        # TODO: quedamos hasta aca, corregir el error de payment_method_line_id
        # --------------------------------------------------------------------------------------------
        payment_data = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner_id,  # ID del partner
            'amount': 150,  # Monto del pago
            'journal_id': 6,  # ID del diario contable
            'payment_method_line_id': 1,  # ID del método de pago
            'ref': 'Pago de prueba',  # Referencia opcional
            'currency_id': 1,  # ID de la moneda
        }
                # Registrar el pago en Odoo con el metodo action_register_payment, sin usar action_invoice_sent, y usando los valores de journal_id y payment_method_line_id
        payment_id = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.payment', 'create', [payment_data]
        )
    
        # --------------------------------------------------------------------------------------------




        # # Paso 4: Registrar el pago
        # logger.info("Registrando el pago...")
        # payment_id = conn['models'].execute_kw(
        #     conn['db'], conn['uid'], conn['password'],
        #     'account.payment', 'create', [{
        #         'payment_type': 'inbound',  # Tipo de pago (entrante)
        #         'partner_type': 'customer',  # Tipo de partner (cliente)
        #         'partner_id': int(invoice_data[0]['partner_id'][0]),  # ID del cliente (aseguramos que sea un entero)
        #         'amount': amount_residual,  # Monto del pago (saldo pendiente)
        #         'journal_id': int(journal_id),  # ID del diario (aseguramos que sea un entero)
        #         'payment_method_line_id': int(payment_method_line_id),  # Método de pago (aseguramos que sea un entero)
        #         'ref': f"Pago para la factura {invoice_id}",  # Referencia del pago
        #         'date': date.today().strftime('%Y-%m-%d'),  # Fecha de pago (hoy)
        #     }]
        # )
        # if not payment_id:
        #     logger.error("No se pudo registrar el pago.")
        #     raise HTTPException(
        #         status_code=500,
        #         detail={
        #             "error": "Error al registrar el pago",
        #             "detail": "No se pudo registrar el pago."
        #         }
        #     )
        # logger.info(f"Pago registrado con ID: {payment_id}.")



        # print(payment_id)
        # # Paso 5: Vincular el pago a la factura
        # logger.info("Vinculando el pago a la factura...")
        # conn['models'].execute_kw(
        #     conn['db'], conn['uid'], conn['password'],
        #     'account.move', 'write', [[invoice_id], {
        #         'payment_ids': [(4, payment_id)]  # Vincular el pago a la factura
        #     }]
        # )
        # logger.info("Pago vinculado a la factura.")
        
           
        return {
            "success": True,
            "message": "Pago registrado y vinculado exitosamente.",
            "invoice_id": invoice_id,
            "payment_id": payment_id,
            "amount_paid": amount_residual
        }

    except HTTPException as e:
        raise e  # Re-lanzar excepciones HTTP
    except ValueError as e:
        logger.error(f"Error de valor: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Error de valor",
                "detail": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Error en el proceso: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error en el proceso",
                "detail": str(e)
            }
        )







# Obtener toda la información de todos los metodos de pago para saber cuál usar
@router.get("/payment_methods")
async def get_payment_methods(token: str = Depends(verify_token)):
    """
    Obtiene los métodos de pago disponibles en Odoo.
    """
    conn = get_odoo_connection()
    try:
        payment_methods = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.payment.method', 'search_read', [],
            {'fields': ['id', 'name']}
        )

        if not payment_methods:
            raise HTTPException(status_code=404, detail="No se encontraron métodos de pago en el sistema.")

        return {
            "success": True,
            "payment_methods": payment_methods
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener métodos de pago: {str(e)}")


# Obtener información de todos los diarios para saber cuál usar
@router.get("/journals")
async def get_journals(token: str = Depends(verify_token)):
    """
    Obtiene los diarios disponibles en Odoo.
    """
    conn = get_odoo_connection()
    try:
        journals = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'account.journal', 'search_read', [],
            {'fields': ['id', 'name', 'type']}
        )

        if not journals:
            raise HTTPException(status_code=404, detail="No se encontraron diarios en el sistema.")

        return {
            "success": True,
            "journals": journals
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener diarios: {str(e)}")

 # DE ACA PARA ABJO ES NUEVO------------------------------------------------------------------------------------------   

@router.post("/confirm_invoice/{invoice_id}")
async def confirm_invoice(invoice_id: int):

    try:
        # Conectar a Odoo
        conn = get_odoo_connection()

        # Leer la factura para verificar su estado
        invoice_data = execute_odoo_method(
            conn,
            'account.move',
            'read',
            [[invoice_id]],
            {'fields': ['id', 'state']}
        )
        if not invoice_data:
            raise HTTPException(status_code=404, detail="Factura no encontrada.")
        
        invoice = invoice_data[0]
        if invoice.get('state') != 'draft':
            raise HTTPException(status_code=400, detail="La factura no está en estado borrador.")

        # Confirmar (publicar) la factura en Odoo
        post_result = execute_odoo_method(
            conn,
            'account.move',
            'action_post',
            [[invoice_id]]
        )

        # Volver a leer la factura para verificar el nuevo estado
        updated_invoice = execute_odoo_method(
            conn,
            'account.move',
            'read',
            [[invoice_id]],
            {'fields': ['id', 'state']}
        )[0]

        return {"success": True, "invoice": updated_invoice}

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al confirmar la factura: {str(e)}")


