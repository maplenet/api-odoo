from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config import settings
from app.core.logging_config import logger



def send_email_sendgrid(to_email: str, subject: str, html_content: str):
    message = Mail(
        from_email=settings.EMAIL_FROM,  # Se reutiliza el campo EMAIL_FROM ya configurado
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info("Correo enviado a %s, status code: %s", to_email, response.status_code)
        return response
    except Exception as e:
        logger.exception("Error al enviar correo con SendGrid")
        raise e