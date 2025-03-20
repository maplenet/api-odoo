import httpx
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from datetime import datetime, timedelta
from app.config import settings
from app.core.logging_config import logger

async def login_to_external_api():
    """
    Realiza una solicitud HTTP POST a la API externa para autenticarse.
    """
    url = f"{settings.OTT_URL_BASE_API}/auth/login"
    payload = {
        "customer_id": f"{settings.OTT_USERNAME}",
        "password": f"{settings.OTT_PASSWORD}"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()  # Lanza una excepción si la respuesta no es exitosa
            return response.json()  # Devuelve la respuesta JSON
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error al autenticarse en la API externa de PONTIS: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al conectarse a la API externa de PONTIS: {str(e)}"
        )
   
def build_customer_data(id_user, contact_data, id_plan, password):

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

    if id_plan == 6:
        subscribe_service_list.extend([
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6212"}  
            },
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6294"} 
            }
        ])

    if id_plan == 8:
        subscribe_service_list.extend([
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6212"}  
            },
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6217"}  
            },
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6294"} 
            }
        ])

    if id_plan == 9:
        subscribe_service_list.extend([
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6212"}  
            },
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6217"}  
            },
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6293"}  
            },
            {
                "effectiveDt": effective_dt,
                "expireDt": expire_dt,
                "serviceMenu": {"serviceMenuId": "6294"}  
            }
        ])
    
    if id_plan == 46:
        subscribe_service_list.extend([
            {
                "effectiveDt": "20/03/2025",
                "expireDt": "20/03/2025",
                "serviceMenu": {"serviceMenuId": "6294"} 
            }
        ])
    if id_plan == 47:
        subscribe_service_list.extend([
            {
                "effectiveDt": "21/03/2025",
                "expireDt": "21/03/2025",
                "serviceMenu": {"serviceMenuId": "6294"} 
            }
        ])
    if id_plan == 48:
        subscribe_service_list.extend([
            {
                "effectiveDt": "25/03/2025",
                "expireDt": "25/03/2025",
                "serviceMenu": {"serviceMenuId": "6294"} 
            }
        ])
    if id_plan == 49:
        subscribe_service_list.extend([
            {
                "effectiveDt": "25/03/2025",
                "expireDt": "25/03/2025",
                "serviceMenu": {"serviceMenuId": "6294"} 
            }
        ])

    if id_plan == 6:
        autoProvCountStationary = "1"
        autoProvisionCountMobile = "2"
    elif id_plan in [8, 9]:
        autoProvCountStationary = "2"
        autoProvisionCountMobile = "3"
    elif id_plan in [46, 47, 48, 49]:
        autoProvCountStationary = "1"
        autoProvisionCountMobile = "2"
    else:
        autoProvCountStationary = "2"
        autoProvisionCountMobile = "3"
 
    customer_data = {
        "customer": {
            "autoProvCountStationary": autoProvCountStationary,
            "autoProvisionCount": "0",
            "autoProvisionCountMobile": autoProvisionCountMobile,
            "customerId": "MAP0"+str(id_user),
            "favoritesEnabled": "Y",
            "firstName": contact.get("name", ""),
            "hasVod": "Y",
            "lastName": "maplenet",
            "localizationId": "71",
            "pin": "1234",
            "status": "A",
            "displayTimeout": "10",
            "multicastTunein": "N",
            "multicastenabled": "N"
        },
        "customerAccount": {
            "effectiveDt": effective_dt,
            "expireDt": "",
            "primaryAudioLanguage": "spa", 
            "secondaryAudioLanguage": "eng",
            "primarySubtitleLanguage": "spa",
            "secondarySubtitleLanguage": "eng",
            "login": "MAP0"+str(id_user),
            "password": password
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
    url = f"{settings.OTT_URL_BASE_API}/customers/create"
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
    
async def update_customer_password_in_pontis(customer_id: str, new_password: str):
    """
    Realiza una solicitud HTTP PUT a la API de Pontis para actualizar la contraseña del cliente.
    :param customer_id: ID del cliente en Pontis, por ejemplo "MAP0" + id
    :param new_password: La nueva contraseña en texto plano.
    :return: La respuesta JSON de la API de Pontis.
    """
    url = f"{settings.OTT_URL_BASE_API}/customers/{customer_id}"
    payload = {
        "customerAccount": {
            "password": new_password
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(url, json=payload, headers=headers)
            response.raise_for_status()  # Lanza error si la respuesta no es exitosa
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error al actualizar la contraseña en Pontis: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al conectarse a la API de Pontis: {str(e)}"
        )
    
 # DE ACA PARA ABJO ES NUEVO------------------------------------------------------------------------------------------   

async def delete_packages_in_pontis(pontis_customer_id):
    url = f"{settings.OTT_URL_BASE_API}/customers/deleteServices/{pontis_customer_id}" 
    headers = {"Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()  # Lanza excepción si la respuesta no es exitosa
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error al eliminar los paquetes en Pontis: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al conectarse a la API de Pontis: {str(e)}"
        )

    return true
    

async def build_update_customer_data(id_plan):


    if id_plan in [46, 47, 48, 49]:
        # Si el id_plan es 46, effective_dt y  expire_dt seran ambos el 20/03/2025 
        if id_plan == 46:
            effective_dt = "20/03/2025"
            expire_dt = "20/03/2025"
        # Si el id_plan es 47, effective_dt y  expire_dt seran ambos el 21/03/2025
        if id_plan == 47:
            effective_dt = "21/03/2025"
            expire_dt = "21/03/2025"
        # Si el id_plan es 48, effective_dt y  expire_dt seran ambos el 21/03/2025
        if id_plan == 48:
            effective_dt = "25/03/2025"
            expire_dt = "25/03/2025"
        # Si el id_plan es 49, effective_dt y  expire_dt seran ambos el 25/03/2025
        if id_plan == 49:
            effective_dt = "25/03/2025"
            expire_dt = "25/03/2025"
    else:
        effective_dt = datetime.now().strftime("%d/%m/%Y")
        expire_dt = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")


    # Definir los valores de auto provisión según el plan
    if id_plan == 6:
        autoProvCountStationary = "1"
        autoProvisionCountMobile = "2"
        services = [
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}}
        ]
    elif id_plan == 8:
        autoProvCountStationary = "2"
        autoProvisionCountMobile = "3"
        services = [
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6217"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}}
        ]
    elif id_plan == 9:
        autoProvCountStationary = "2"
        autoProvisionCountMobile = "3"
        services = [
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6217"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6293"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}}
        ]
    elif id_plan in [46, 47, 48, 49]:
        autoProvCountStationary = "1"
        autoProvisionCountMobile = "2"
        services = [
            # {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}}
        ]
    else:
        # Valor por defecto: se utiliza la configuración de id_plan 8
        autoProvCountStationary = "2"
        autoProvisionCountMobile = "3"
        services = [
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6212"}}, # TODO: MODIFICAR O BORRAR TODO ESTO
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6217"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6293"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}} 
        ]

    # Construir el payload de actualización
    payload = {
        "customer": {
            "autoProvCountStationary": autoProvCountStationary,
            "autoProvisionCountMobile": autoProvisionCountMobile
        },
        "subscribeService": services
    }
    return payload



async def update_customer_in_pontis(update_data_customer, pontis_customer_id):

    url = f"{settings.OTT_URL_BASE_API}/customers/{pontis_customer_id}" 

    headers = {"Content-Type": "application/json"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(url, json=update_data_customer, headers=headers)
            response.raise_for_status()  # Lanza excepción si la respuesta no es exitosa
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error al actualizar el cliente en Pontis: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al conectarse a la API de Pontis: {str(e)}"
        )
    

async def check_customer_in_pontis(pontis_customer_id: str) -> dict:
    """
    Llama al endpoint GET /getCustomer/<pontis_customer_id> en la API de Pontis.
    Retorna el JSON completo si existe, o un dict con "response": None si no existe.
    """
    url = f"{settings.OTT_URL_BASE_API}/customers/getCustomer/{pontis_customer_id}"
    
    logger.debug("Consultando API Pontis en URL: %s", url)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            # No usamos raise_for_status() porque la API puede devolver 200 con un error en el JSON.
            data = response.json()
            logger.debug("Respuesta de Pontis: %s", data)
            return data
    except Exception as e:
        logger.error("Error conectándose a la API de Pontis: %s", str(e))
        raise HTTPException(status_code=500, detail="Error interno al conectarse a Pontis.")
    
def check_subscribe_services_expiration(pontis_response: dict) -> bool:
    """
    Dado un dict con la respuesta de Pontis (campo 'response' != null),
    revisa en 'subscribeService' si alguno de los servicios [6212, 6217, 6293, 6294]
    tiene un expireDt >= hoy o vacío (lo cual indica plan activo).
    
    Retorna True si el plan sigue activo, False si ya expiró.
    """
    # Ids de servicio que deseas verificar
    service_ids_interes = {6212, 6217, 6293, 6294}
    hoy = datetime.now(timezone.utc).date()
    
    subscribe_services = pontis_response.get("subscribeService", [])
    for srv in subscribe_services:
        menu = srv.get("serviceMenu", {})
        s_id = menu.get("serviceMenuId")
        if s_id in service_ids_interes:
            expire_str = srv.get("expireDt")  # Puede ser "" o "16/04/2025", etc.
            if not expire_str:
                # Si no hay fecha de expiración => se asume activo
                return True
            # Convertir la fecha expireDt a objeto date
            try:
                expire_date = datetime.strptime(expire_str, "%d/%m/%Y").date()
                if expire_date >= hoy:
                    # El plan sigue activo
                    return True
            except ValueError:
                # Si la fecha viene malformada, lo consideramos activo por seguridad
                return True
    # Si no se encontró ninguno con expire >= hoy => se considera expirado
    return False