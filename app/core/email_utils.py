from smtplib import SMTP
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
from fastapi import HTTPException
from app.config import settings
import logging
logger = logging.getLogger(__name__)


def send_verification_email(to_email: str, subject: str, code: str):
    """
    Envía un correo de verificación usando la plantilla 'email_template.html'.
    Reemplaza {{ code }} en el template con el código de verificación.
    """
    try:
        template_path = Path(__file__).parent / "templates" / "email_template.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()
        html_content = html_template.replace("{{ code }}", code)

        server = SMTP(settings.EMAIL_SERVER, settings.EMAIL_PORT)
        if settings.EMAIL_TLS:
            server.starttls()

        username = settings.EMAIL_USERNAME.encode('utf-8').decode('utf-8')
        password = settings.EMAIL_PASSWORD.encode('utf-8').decode('utf-8')

        server.login(username, password)
        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("Error al enviar el correo de verificación:", e)
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo de verificación: {str(e)}")

def send_reset_password_email(to_email: str, subject: str, reset_link: str):
    """
    Envía un correo para restablecer la contraseña usando la plantilla
    'password_reset_template.html'. Reemplaza {{ reset_link }} en el template
    con el enlace de restablecimiento.
    """
    try:
        template_path = Path(__file__).parent / "templates" / "password_reset_template.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()
        html_content = html_template.replace("{{ reset_link }}", reset_link)

        server = SMTP(settings.EMAIL_SERVER, settings.EMAIL_PORT)
        if settings.EMAIL_TLS:
            server.starttls()

        username = settings.EMAIL_USERNAME.encode('utf-8').decode('utf-8')
        password = settings.EMAIL_PASSWORD.encode('utf-8').decode('utf-8')

        server.login(username, password)
        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("Error al enviar el correo de restablecimiento:", e)
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo de restablecimiento: {str(e)}")

def send_pontis_credentials_email(to_email: str, subject: str, pontis_username: str, pontis_password: str):
    """
    Envía un correo con las credenciales para acceder al portal de Pontis usando la plantilla
    'pontis_credentials_template.html'.
    """
    try:
        template_path = Path(__file__).parent / "templates" / "pontis_credentials_template.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()
        # Reemplazar los placeholders por los valores reales
        html_content = html_template.replace("{{ pontis_username }}", pontis_username)\
                                    .replace("{{ pontis_password }}", pontis_password)

        server = SMTP(settings.EMAIL_SERVER, settings.EMAIL_PORT)
        if settings.EMAIL_TLS:
            server.starttls()

        username = settings.EMAIL_USERNAME.encode('utf-8').decode('utf-8')
        password = settings.EMAIL_PASSWORD.encode('utf-8').decode('utf-8')

        server.login(username, password)
        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("Error al enviar el correo de credenciales de Pontis:", e)
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo de credenciales de acceso.: {str(e)}")
    

def send_final_match_email(to_email: str, subject: str, extra_params: dict):

    try:
        template_path = Path(__file__).parent / "templates" / "url_final_match_template.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()
        
        html_content = html_template

        # Configurar conexión SMTP
        server = SMTP(settings.EMAIL_SERVER, settings.EMAIL_PORT)
        if settings.EMAIL_TLS:
            server.starttls()

        username = settings.EMAIL_USERNAME
        password = settings.EMAIL_PASSWORD

        server.login(username, password)
        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
        server.quit()
        logger.info("Correo enviado correctamente a %s", to_email)
    except Exception as e:
        logger.exception("Error al enviar el correo de invitación:")
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo de invitación: {str(e)}")