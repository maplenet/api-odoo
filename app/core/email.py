from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import BaseModel, EmailStr
from app.config import settings

class EmailSchema(BaseModel):
    email: EmailStr
    subject: str
    body: str

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_TLS=settings.MAIL_TLS,
    MAIL_SSL=settings.MAIL_SSL,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    # TEMPLATE_FOLDER="/home/maplenet/Documentos/pruebas/app/templates"
)

async def send_email(email: EmailSchema):
    message = MessageSchema(
        subject=email.subject,
        recipients=[email.email],
        body=email.body,
        subtype="html"
    )
    fm = FastMail(conf)
    await fm.send_message(message)
