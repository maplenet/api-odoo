import httpx
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.services.odoo_service import execute_odoo_method
from datetime import datetime, timedelta


async def login_to_external_api():
    """
    Realiza una solicitud HTTP POST a la API externa para autenticarse.
    """
    url = "http://18.117.185.30:3000/api/auth/login"
    payload = {
        "customer_id": "subop_maplenet1",
        "password": "s8Xh5671O9xR"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()  # Lanza una excepción si la respuesta no es exitosa
            return response.json()  # Devuelve la respuesta JSON
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error al autenticarse en la API externa: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al conectarse a la API externa: {str(e)}"
        )
    
# async def create_customer_in_pontis(id_user: int, id_plan: int):
#     """
#     Crea un cliente en Pontis basado en los datos del usuario en Odoo.
#     """
#     # Obtener datos del contacto asociado al usuario
#     user_data = execute_odoo_method('res.partner', 'read', [[id_user], ['name', 'mobile', 'email', 'street']])
#     if not user_data:
#         raise HTTPException(status_code=404, detail="El usuario no existe en Odoo.")
    
#     user = user_data[0]
#     name = user.get('name', 'Usuario')
#     mobile = user.get('mobile', '0000000000')
#     email = user.get('email', '')
#     street = user.get('street', '')
    
#     # Extraer los últimos 4 dígitos del número móvil para el PIN
#     pin = mobile[-4:] if len(mobile) >= 4 else '1234'
    
#     # Formatear las fechas
#     effective_date = datetime.now().strftime("%d/%m/%Y")
#     expire_date = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
    
#     # Determinar el serviceMenuId basado en id_plan
#     service_menu_mapping = {
#         11: "6213",  # M+ Básico
#         12: "6215",  # M+ Medium
#         13: "6217"   # M+ Premium
#     }
#     service_menu_id = service_menu_mapping.get(id_plan)
#     if not service_menu_id:
#         raise HTTPException(status_code=400, detail="El id_plan proporcionado no es válido.")
    
#     # Construir el JSON de la solicitud
#     customer_id = f"MAP{id_user}"
#     payload = {
#         "customer": {
#             "autoProvCountStationary": "1",
#             "autoProvisionCount": "0",
#             "autoProvisionCountMobile": "1",
#             # "customerId": customer_id,
#             "customerId": "MAP003",
#             "favoritesEnabled": "Y",
#             "firstName": name,
#             "hasVod": "Y",
#             "lastName": "",
#             "localizationId": "71",
#             "pin": pin,
#             "status": "A",
#             "displayTimeout": "10",
#             "multicastTunein": "N",
#             "multicastenabled": "N"
#         },
#         "customerAccount": {
#             "effectiveDt": effective_date,
#             "expireDt": expire_date,
#             "primaryAudioLanguage": "spa",
#             "secondaryAudioLanguage": "eng",
#             "primarySubtitleLanguage": "spa",
#             "secondarySubtitleLanguage": "eng",
#             # "login": customer_id,
#             "login": "MAP003",
#             "password": "abc123"
#         },
#         "customerInfo": {
#             "address1": street,
#             "address2": "",
#             "address3": "",
#             "city": "La Paz",
#             "easLocationCode": "",
#             "email": email,
#             "homePhone": "",
#             "mobilePhone": "",
#             "note": "",
#             "state": "La Paz",
#             "workPhone": "",
#             "zipcode": "0000"
#         },
#         "subscribeService": [{
#             "effectiveDt": effective_date,
#             "expireDt": "",
#             "serviceMenu": {"serviceMenuId": service_menu_id}
#         }]
#     }
    
#     # Hacer la solicitud HTTP
#     url = "http://18.117.185.30:3000/api/customers/create"
#     headers = {"Content-Type": "application/json"}
#     try:
#         async with httpx.AsyncClient() as client:
#             response = await client.post(url, json=payload, headers=headers)
#             response.raise_for_status()
#             return response.json()
#     except httpx.HTTPStatusError as e:
#         raise HTTPException(status_code=e.response.status_code, detail=f"Error en API Pontis: {e.response.text}")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error interno al conectar con Pontis: {str(e)}")


def build_customer_data(id_user, contact_data, id_plan):
    """
    Construye el cuerpo de la solicitud para la API de creación de clientes.

    :param id_user: ID del usuario.
    :param contact_data: Datos del contacto (obtenidos de Odoo).
    :param id_plan: ID del plan (11, 12 o 13).
    :return: Diccionario con el cuerpo de la solicitud.
    """
    # Obtener los últimos 4 dígitos del móvil
    mobile = contact_data.get("mobile", "")
    pin = mobile[-4:] if mobile else "0000"

    # Obtener el serviceMenuId según el id_plan
    service_menu_id_map = {
        11: "6213",  # M+ Básico
        12: "6215",  # M+ Medium
        13: "6217",  # M+ Premium
    }
    service_menu_id = service_menu_id_map.get(id_plan, "6213")  # Por defecto, M+ Básico

    # Fechas
    effective_dt = datetime.now().strftime("%d/%m/%Y")
    expire_dt = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")

    # Construir el cuerpo de la solicitud
    customer_data = {
        "customer": {
            "autoProvCountStationary": "1",
            "autoProvisionCount": "0",
            "autoProvisionCountMobile": "1",
            "customerId": "MAP003",  # Prefijo MAP + id_user
            # "customerId": f"MAP{id_user}",  # Prefijo MAP + id_user
            "favoritesEnabled": "Y",
            "firstName": contact_data.get("name", ""),  # Nombre del contacto
            "lastName": "Dolores",  # Apellido vacío
            "hasVod": "Y",
            "localizationId": "71",
            "pin": pin,  # Últimos 4 dígitos del móvil
            "status": "A",
            "displayTimeout": "10",
            "multicastTunein": "N",
            "multicastenabled": "N"
        },
        "customerAccount": {
            "effectiveDt": effective_dt,  # Fecha actual
            "expireDt": expire_dt,  # Fecha actual + 30 días
            "primaryAudioLanguage": "spa",
            "secondaryAudioLanguage": "eng",
            "primarySubtitleLanguage": "spa",
            "secondarySubtitleLanguage": "eng",
            # "login": f"MAP{id_user}",  # Igual que customerId
            "login": "MAP003",  # Igual que customerId
            "password": "abc123"  # Contraseña fija
        },
        "customerInfo": {
            "address1": contact_data.get("street", ""),  # Dirección del contacto
            "address2": "",
            "address3": "",
            "city": "La Paz",  # Ciudad fija
            "easLocationCode": "",
            "email": contact_data.get("email", ""),  # Correo del contacto
            "homePhone": "",
            "mobilePhone": mobile,  # Móvil del contacto
            "note": "",
            "state": "La Paz",  # Estado fijo
            "workPhone": "",
            "zipcode": "0000"  # Código postal fijo
        },
        "subscribeService": [
            {
                "effectiveDt": effective_dt,  # Fecha actual
                "expireDt": expire_dt,  # Fecha actual + 30 días
                "serviceMenu": {
                    "serviceMenuId": service_menu_id  # serviceMenuId según el plan
                }
            }
        ]
    }

    return customer_data


async def create_customer_in_pontis(api_token, customer_data):
    """
    Realiza una solicitud HTTP POST a la API de creación de clientes en Pontis.

    :param api_token: Token de autenticación obtenido del login.
    :param customer_data: Datos del cliente para crear.
    :return: Respuesta de la API.
    """
    url = "http://18.117.185.30:3000/api/customers/create"
    headers = {
        "Authorization": f"Bearer {api_token}",  # Usar el token de autenticación
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=customer_data, headers=headers)
            response.raise_for_status()  # Lanza una excepción si la respuesta no es exitosa
            return response.json()  # Devuelve la respuesta JSON
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error al crear el cliente en Pontis: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al conectarse a la API de Pontis: {str(e)}"
        )