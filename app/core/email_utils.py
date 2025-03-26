from pathlib import Path
from fastapi import HTTPException
from app.core.logging_config import logger
from app.core.sendgrid_email import send_email_sendgrid



def send_verification_email(to_email: str, subject: str, code: str):
    try:
        template_path = Path(__file__).parent / "templates" / "email_template.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()
        html_content = html_template.replace("{{ code }}", code)

        # Enviar usando SendGrid
        response = send_email_sendgrid(to_email, subject, html_content)
        logger.info("Correo de verificación enviado a %s, status code: %s", to_email, response.status_code)
    except Exception as e:
        logger.exception("Error al enviar el correo de verificación:")
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo de verificación: {str(e)}")

def send_reset_password_email(to_email: str, subject: str, reset_link: str):
    try:
        template_path = Path(__file__).parent / "templates" / "password_reset_template.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()
        html_content = html_template.replace("{{ reset_link }}", reset_link)

        response = send_email_sendgrid(to_email, subject, html_content)
        logger.info("Correo de restablecimiento enviado a %s, status code: %s", to_email, response.status_code)
    except Exception as e:
        logger.exception("Error al enviar el correo de restablecimiento:")
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo de restablecimiento: {str(e)}")


def send_ott_mplus_credentials_email(to_email: str, subject: str, ott_mplus_username: str, ott_mplus_password: str):
    try:
        template_path = Path(__file__).parent / "templates" / "ott_mplus_credentials_template.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()
        html_content = html_template.replace("{{ ott_mplus_username }}", ott_mplus_username)\
                                    .replace("{{ ott_mplus_password }}", ott_mplus_password)

        response = send_email_sendgrid(to_email, subject, html_content)
        logger.info("Correo de credenciales enviado a %s, status code: %s", to_email, response.status_code)
    except Exception as e:
        logger.exception("Error al enviar el correo de credenciales de ott_mplus:")
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo de credenciales: {str(e)}")

    

def send_ott_mplus_credentials_email_v2(to_email: str, subject: str, ott_mplus_username: str, ott_mplus_password: str):
    try:
        template_path = Path(__file__).parent / "templates" / "ott_mplus_credentials_template_v2.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()
        html_content = html_template.replace("{{ ott_mplus_username }}", ott_mplus_username)\
                                    .replace("{{ ott_mplus_password }}", ott_mplus_password)

        response = send_email_sendgrid(to_email, subject, html_content)
        logger.info("Correo de credenciales enviado a %s, status code: %s", to_email, response.status_code)
    except Exception as e:
        logger.exception("Error al enviar el correo de credenciales de ott_mplus:")
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo de credenciales: {str(e)}")

    

def send_final_match_email(to_email: str, subject: str, extra_params: dict):
    """
    Envía un correo de invitación (por ejemplo, para la final del torneo) usando la plantilla
    'url_final_match_template.html'. Se pueden utilizar extra_params para realizar reemplazos dinámicos
    en el template, si es necesario.
    """
    try:
        template_path = Path(__file__).parent / "templates" / "url_final_match_template.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()
        
        # Si extra_params contiene claves para reemplazar en el template, puedes hacerlo aquí.
        # Por ejemplo:
        # for key, value in extra_params.items():
        #     html_template = html_template.replace(f"{{{{ {key} }}}}", str(value))
        html_content = html_template  # o con los reemplazos aplicados
        
        # Enviar usando la función centralizada de SendGrid
        response = send_email_sendgrid(to_email, subject, html_content)
        logger.info("Correo de invitación enviado correctamente a %s, status code: %s", to_email, response.status_code)
    except Exception as e:
        logger.exception("Error al enviar el correo de invitación:")
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo de invitación: {str(e)}")