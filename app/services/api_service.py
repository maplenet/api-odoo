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
   
def _compute_dates_for_plan(plan_id: int) -> tuple[str, str]:
    """
    Devuelve (effectiveDt, expireDt) con formato 'dd/MM/yyyy' según la lógica
    de planes especiales (46..49) o la fecha actual +30 días.
    """
    if plan_id == 46:
        return ("20/03/2025", "20/03/2025")
    elif plan_id == 47: #TODO: CAMBIAR------------
        return ("21/03/2025", "21/03/2025")
    elif plan_id == 49:
        return ("25/03/2025", "26/03/2025")
    else:
        now = datetime.now()
        return (
            now.strftime("%d/%m/%Y"),
            (now + timedelta(days=30)).strftime("%d/%m/%Y")
        )

def _build_services_for_plan_create(plan_id: int, eff: str, exp: str) -> list:
    """
    Arma la lista de servicios para un plan dado en la CREACIÓN de un customer.
    A diferencia del 'update', aquí tenemos la particularidad de que:
      - Planes 6,8,9,46..49 añaden sus menús con expireDt=exp
      - Otros planes: default
      - Se podría dejar flexible si se necesitan 'obligatorios' o no.
    
    NOTA: en tu código original, pones 6213, 6214, 6215 siempre con expireDt = "" (en blanco).
    """
    services = []
    
    # Plan 6
    if plan_id == 6:
        services.extend([
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6294"}}
        ])
    # Plan 8
    elif plan_id == 8:
        services.extend([
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6217"}},
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6294"}}
        ])
    # Plan 9
    elif plan_id == 9:
        services.extend([
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6217"}},
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6293"}},
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6294"}}
        ])
    # Plan 46..49
    elif plan_id in [46, 47, 49]:
        services.extend([
            {"effectiveDt": eff, "expireDt": exp, "serviceMenu": {"serviceMenuId": "6294"}}
        ])
    else:
        # Plan por defecto (si llegas a necesitar)
        pass

    return services

def _determine_auto_prov_counts(plan_id: int) -> tuple[str, str]:
    """
    Devuelve (autoProvCountStationary, autoProvisionCountMobile) 
    según tu lógica de planes.
    """
    if plan_id == 6:
        return ("1", "2")
    elif plan_id in [8, 9]:
        return ("2", "3")
    elif plan_id in [46, 47, 49]:
        return ("1", "2")
    else:
        # Por defecto
        return ("1", "2")

def build_customer_data(
    id_user: int,
    contact_data: list,
    id_plan: int,
    id_plan2: int,
    password: str
) -> dict:
    """
    Construye el payload de creación (primer alta) de un customer en Pontis.
    - id_plan2 puede ser 0 => no hay segundo plan.
    - Los planes 6,8,9,46..49 añaden servicios con expireDt=exp
    - Se añaden 3 servicios "obligatorios" (6213, 6214, 6215) con expireDt="".
    """
    contact = contact_data[0]
    mobile = contact.get("mobile", "")

    # 1) Calcular las fechas y la lista de servicios "obligatorios"
    eff1, exp1 = _compute_dates_for_plan(id_plan)
    # id_plan2
    eff2, exp2 = ("", "")  # Por si no se usa
    if id_plan2 != 0:
        eff2, exp2 = _compute_dates_for_plan(id_plan2)

    # 2) Armar la lista con servicios "obligatorios" (siempre con expireDt = "")
    #   tal cual tu código original
    subscribe_service_list = [
        {"effectiveDt": eff1, "expireDt": "", "serviceMenu": {"serviceMenuId": "6213"}},
        {"effectiveDt": eff1, "expireDt": "", "serviceMenu": {"serviceMenuId": "6214"}},
        {"effectiveDt": eff1, "expireDt": "", "serviceMenu": {"serviceMenuId": "6215"}}
    ]

    # 3) Agregar los servicios del primer plan
    services_plan1 = _build_services_for_plan_create(id_plan, eff1, exp1)
    subscribe_service_list.extend(services_plan1)

    # 4) Si hay un segundo plan
    if id_plan2 != 0:
        services_plan2 = _build_services_for_plan_create(id_plan2, eff2, exp2)
        subscribe_service_list.extend(services_plan2)

    # 5) autoProvCountStationary, autoProvisionCountMobile
    #   => podrías decidir cómo combinar ambos planes si hay 2. 
    #   Ejemplo: tomar el mayor de ambos
    apc1, apm1 = _determine_auto_prov_counts(id_plan)
    if id_plan2 != 0:
        apc2, apm2 = _determine_auto_prov_counts(id_plan2)
        autoProvCountStationary = str(max(int(apc1), int(apc2)))
        autoProvisionCountMobile = str(max(int(apm1), int(apm2)))
    else:
        autoProvCountStationary = apc1
        autoProvisionCountMobile = apm1

    # 6) Construir el payload final
    customer_data = {
        "customer": {
            "autoProvCountStationary": autoProvCountStationary,
            "autoProvisionCount": "0",
            "autoProvisionCountMobile": autoProvisionCountMobile,
            "customerId": "MAP0" + str(id_user),
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
            "effectiveDt": eff1,  # El primer plan define effectiveDt de la cuenta
            "expireDt": "",
            "primaryAudioLanguage": "spa",
            "secondaryAudioLanguage": "eng",
            "primarySubtitleLanguage": "spa",
            "secondarySubtitleLanguage": "eng",
            "login": "MAP0" + str(id_user),
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
    # url = f"{settings.OTT_URL_BASE_API}/customers/deleteServices/MAP006" 
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
    

def _build_services_for_plan(plan_id: int, effective_dt: str, expire_dt: str) -> tuple[str, str, list]:
    """
    Dado un plan_id y sus fechas, devuelve:
      - autoProvCountStationary (str)
      - autoProvisionCountMobile (str)
      - la lista de servicios (list) que corresponden a ese plan.
    
    Ajusta según tu propia lógica de planes 6, 8, 9, 46-49, etc.
    """
    # Valores por defecto
    autoProvCountStationary = "2"
    autoProvisionCountMobile = "3"
    services = []
    
    if plan_id == 6:
        autoProvCountStationary = "1"
        autoProvisionCountMobile = "2"
        services = [
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}}
        ]
    elif plan_id == 8:
        autoProvCountStationary = "2"
        autoProvisionCountMobile = "3"
        services = [
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6217"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}}
        ]
    elif plan_id == 9:
        autoProvCountStationary = "2"
        autoProvisionCountMobile = "3"
        services = [
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6217"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6293"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}}
        ]
    elif plan_id in [46, 47, 49]:
        # Ejemplo de tu caso especial
        autoProvCountStationary = "1"
        autoProvisionCountMobile = "2"
        services = [
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}}
        ]
    else:
        # Plan por defecto (ejemplo)
        autoProvCountStationary = "2"
        autoProvisionCountMobile = "3"
        services = [
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6212"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6217"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6293"}},
            {"effectiveDt": effective_dt, "expireDt": expire_dt, "serviceMenu": {"serviceMenuId": "6294"}}
        ]
    
    return autoProvCountStationary, autoProvisionCountMobile, services


async def build_update_customer_data(id_plan: int, id_plan2: int = 0) -> dict:
    """
    Construye el payload para actualizar los paquetes en Pontis.
    Si id_plan2 != 0, se combinan ambos planes en un mismo subscribeService.
    """
    # 1) Calcular fechas y servicios para el primer plan
    eff1, exp1 = _compute_dates_for_plan(id_plan)
    apc1, apm1, services1 = _build_services_for_plan(id_plan, eff1, exp1)

    # 2) Si existe un segundo plan, calculamos y unimos
    if id_plan2 != 0:
        eff2, exp2 = _compute_dates_for_plan(id_plan2)
        apc2, apm2, services2 = _build_services_for_plan(id_plan2, eff2, exp2)
        
        # Decide cómo quieres combinar autoProvCountStationary y autoProvisionCountMobile.
        # Ejemplo: tomar el máximo
        autoProvCountStationary = str(max(int(apc1), int(apc2)))
        autoProvisionCountMobile = str(max(int(apm1), int(apm2)))
        
        # Unir las listas de servicios
        all_services = services1 + services2
    else:
        # Solo un plan
        autoProvCountStationary = apc1
        autoProvisionCountMobile = apm1
        all_services = services1

    # 3) Construir el payload final
    payload = {
        "customer": {
            "autoProvCountStationary": autoProvCountStationary,
            "autoProvisionCountMobile": autoProvisionCountMobile
        },
        "subscribeService": all_services
    }
    return payload



async def update_customer_in_pontis(update_data_customer, pontis_customer_id):

    url = f"{settings.OTT_URL_BASE_API}/customers/{pontis_customer_id}" 
    # url = f"{settings.OTT_URL_BASE_API}/customers/MAP006" 


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
    # url = f"{settings.OTT_URL_BASE_API}/customers/getCustomer/MAP006"   #TODO: CAMBIAR------------

    
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