import httpx
from datetime import datetime, timedelta
from fastapi import HTTPException
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
   
def build_customer_data(id_user, contact_data, id_plan):

    # Obtener los últimos 4 dígitos del móvil
    mobile = contact_data.get("mobile", "")
    pin = mobile[-4:] if mobile else "0000"

    # Obtener el serviceMenuId según el id_plan
    service_menu_id_map = {
        999999997: "6213",  # M+ Básico servicio
        999999998: "6214",  # M+ mobile
        999999999: "6215",  # M+ estacionario
        11: "6212",  # M+ Básico paquete
        13: "6217",  # M+ Premium paquete
    }

    # Obtener el serviceMenuId según el id_plan
    service_menu_id = service_menu_id_map.get(id_plan)
    
    # EN caso de serviceMenuId no encontrado poner por defecto el paquete basico
    if not service_menu_id:
        service_menu_id = "6213"

    # service_menu_id = service_menu_id_map.get(id_plan, "6213")  # Por defecto, M+ Básico

    # Fechas
    effective_dt = datetime.now().strftime("%d/%m/%Y")
    expire_dt = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")

    # Construir el cuerpo de la solicitud
    customer_data = {
        "customer": {
            "autoProvCountStationary": "2",
            "autoProvisionCount": "0",
            "autoProvisionCountMobile": "2",
            "customerId": "MAP003",  # Prefijo MAP + id_user
            # "customerId": f"MAP{id_user}",  # Prefijo MAP + id_user
            "favoritesEnabled": "Y",
            "firstName": contact_data.get("name",""),  # Nombre del contacto
            "lastName": contact_data.get("name",""),  
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
            "login": contact_data.get("email", ""), # Igual que customerId
            "password": "abc123"  # Contraseña fija # TODO: REVISAR
        },
        "customerInfo": {
            "address1": contact_data.get("street", ""),  # Dirección del contacto
            "address2": "",
            "address3": "",
            "city": "La Paz",  # Ciudad fija # TODO: revisar
            "easLocationCode": "",
            "email": contact_data.get("email", ""),  # Correo del contacto
            "homePhone": "",
            "mobilePhone": mobile,  # Móvil del contacto
            "note": "",
            "state": "La Paz",  # Estado fijo # TODO: revisar
            "workPhone": "",
            "zipcode": "0000"  # Código postal fijo
        },
        "subscribeService": [
            {
                "effectiveDt": effective_dt,  # Fecha actual
                "expireDt": "",  # Fecha actual + 30 días
                "serviceMenu": {
                    "serviceMenuId": "6213"  # serviceMenuId según el plan
                }
            },
            {
                "effectiveDt": effective_dt,  # Fecha actual
                "expireDt": "",  # Fecha actual + 30 días
                "serviceMenu": {
                    "serviceMenuId": "6214"  # serviceMenuId según el plan
                }
            },
            {
                "effectiveDt": effective_dt,  # Fecha actual
                "expireDt": "",  # Fecha actual + 30 días
                "serviceMenu": {
                    "serviceMenuId": "6215"  # serviceMenuId según el plan
                }
            },
            {
                "effectiveDt": effective_dt,  # Fecha actual
                "expireDt": expire_dt,  # Fecha actual + 30 días
                "serviceMenu": {
                    "serviceMenuId": service_menu_id  # serviceMenuId según el plan
                }
            },
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