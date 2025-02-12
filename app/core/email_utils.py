from smtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
from fastapi import HTTPException
def send_email(to_email: str, subject: str, body: str):
    try:
        # Conectar al servidor SMTP
        server = SMTP(settings.EMAIL_SERVER, settings.EMAIL_PORT)
        if settings.EMAIL_TLS:
            server.starttls()

        # Codificar credenciales en utf-8
        username = settings.EMAIL_USERNAME.encode('utf-8').decode('utf-8')
        password = settings.EMAIL_PASSWORD.encode('utf-8').decode('utf-8')
        # print(username, password)
        # Autenticación
        server.login(username, password)

        # Crear el mensaje de correo
        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        # Enviar el correo
        server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo: {str(e)}")
