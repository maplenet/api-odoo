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

    contact = contact_data[0]

    # Obtener los últimos 4 dígitos del móvil
    mobile = contact.get("mobile", "")
    pin = mobile[-4:] if mobile and len(mobile) >= 4 else "1234"

    # Fechas
    effective_dt = datetime.now().strftime("%d/%m/%Y")
    expire_dt = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")

    # Construcción dinámica de la lista de servicios
    subscribe_service_list = []

    # Servicios obligatorios
    subscribe_service_list.extend([
        {
            "effectiveDt": effective_dt,
            "expireDt": "",
            "serviceMenu": {"serviceMenuId": "6213"}  
        },
        {
            "effectiveDt": effective_dt,
            "expireDt": "",
            "serviceMenu": {"serviceMenuId": "6214"}  
        },
        {
            "effectiveDt": effective_dt,
            "expireDt": "",
            "serviceMenu": {"serviceMenuId": "6215"} 
        }
    ])

    if id_plan == 11:
        subscribe_service_list.append({
            "effectiveDt": effective_dt,
            "expireDt": expire_dt,
            "serviceMenu": {"serviceMenuId": "6212"} 
        })

    if id_plan == 13:
        subscribe_service_list.extend([
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6217"}  
            },
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6212"} 
            }
        ])

    if id_plan == 19:
        subscribe_service_list.extend([
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6293"}  
            },
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6212"}  
            },
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6217"}  
            }
        ])

    customer_data = {
        "customer": {
            "autoProvCountStationary": "4",
            "autoProvisionCount": "0",
            "autoProvisionCountMobile": "8",
            "customerId": "MAP0"+str(id_user),
            "favoritesEnabled": "Y",
            "firstName": contact.get("name", ""),
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
            "login": "MAP0"+str(id_user),
            "password": "abc123"
        },
        "customerInfo": {
            "address1": "CALLE MAPLENET",
            "address2": "",
            "address3": "",
            "city": "La Paz",
            "easLocationCode": "",
            "email": contact.get("email", ""),
            "homePhone": "",
            "mobilePhone": mobile,
            "note": "",
            "state": "La Paz",
            "workPhone": "",
            "zipcode": "0000"
        },
        "subscribeService": subscribe_service_list
    }

    return customer_data


async def create_customer_in_pontis(customer_data):
    """
    Realiza una solicitud HTTP POST a la API de creación de clientes en Pontis.

    :param api_token: Token de autenticación obtenido del login.
    :param customer_data: Datos del cliente para crear.
    :return: Respuesta de la API.
    """
    url = "http://18.117.185.30:3000/api/customers/create"
    headers = {
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