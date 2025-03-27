import requests
from app.config import settings
from app.core.logging_config import logger

def send_email_mailgun(to_email: str, subject: str, html_content: str):
    """
    Envía un correo electrónico usando la API de Mailgun.
    """
    url = f"{settings.MAILGUN_BASE_URL}/{settings.MAILGUN_DOMAIN}/messages"
    
    data = {
        "from": settings.EMAIL_FROM,  # Asegúrate que este "from" coincida con el dominio autenticado en Mailgun.
        "to": to_email,
        "subject": subject,
        "html": html_content
    }
    
    try:
        # Mailgun utiliza autenticación básica. El usuario es "api" y la contraseña es la API key.
        response = requests.post(url, auth=("api", settings.MAILGUN_API_KEY), data=data)
        logger.info("Correo enviado a %s, status code: %s", to_email, response.status_code)
        response.raise_for_status()  # Lanza excepción si hay error HTTP
        return response
    except requests.exceptions.RequestException as e:
        logger.exception("Error al enviar correo con Mailgun")
        raise e
