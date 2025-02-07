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
    pin = mobile[-4:] if mobile else "1234"

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
            "autoProvCountStationary": "1",
            "autoProvisionCount": "0",
            "autoProvisionCountMobile": "2",
            "customerId": "MAP006", 
            "favoritesEnabled": "Y",
            "firstName": "", 
            "hasVod": "Y",
            "lastName": "maplenet",  
            "localizationId": "71",
            "pin": pin, 
            "status": "A",
            "displayTimeout": "10",
            "multicastTunein": "N",
            "multicastenabled": "N"
        },
        "customerAccount": {
            "effectiveDt": effective_dt, 
            "expireDt": "",  
            "secondaryAudioLanguage": "eng",
            "primarySubtitleLanguage": "spa",
            "secondarySubtitleLanguage": "eng",
            "login": "MAP006", 
            "password": "abc123" 
        },
        "customerInfo": {
            "address1": "CALLE MAPLENET",  
            "address2": "",
            "address3": "",
            "city": "La Paz",  
            "easLocationCode": "",
            "email": "", 
            "homePhone": "",
            "mobilePhone": "",  
            "note": "",
            "state": "La Paz",  
            "workPhone": "",
            "zipcode": "0000"  
        },
        "subscribeService": [
            {
                "effectiveDt": effective_dt,  
                "expireDt": "",  
                "serviceMenu": {
                    "serviceMenuId": "6213"  
                }
            },
            {
                "effectiveDt": effective_dt,  
                "expireDt": "",  
                "serviceMenu": {
                    "serviceMenuId": "6214"  
                }
            },
            {
                "effectiveDt": effective_dt,  
                "expireDt": "",  
                "serviceMenu": {
                    "serviceMenuId": "6215"  
                }
            },
            {
                "effectiveDt": effective_dt,  
                "expireDt": expire_dt,  
                "serviceMenu": {
                    "serviceMenuId": "6212"  
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