from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic_settings import BaseSettings

class EmailSettings(BaseSettings):
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str
    EMAIL_FROM: str
    EMAIL_PORT: int
    EMAIL_SERVER: str
    EMAIL_TLS: bool
    EMAIL_SSL: bool

    class Config:
        env_file = ".env"

email_settings = EmailSettings()

conf = ConnectionConfig(
    MAIL_USERNAME=email_settings.EMAIL_USERNAME,
    MAIL_PASSWORD=email_settings.EMAIL_PASSWORD,
    MAIL_FROM=email_settings.EMAIL_FROM,
    MAIL_PORT=email_settings.EMAIL_PORT,
    MAIL_SERVER=email_settings.EMAIL_SERVER,
    MAIL_TLS=email_settings.EMAIL_TLS,
    MAIL_SSL=email_settings.EMAIL_SSL
)

async def send_email(subject: str, recipients: list, body: str):
    """Send an email using FastAPI-Mail."""
    message = MessageSchema(
        subject=subject,
        recipients=recipients,  # List of email addresses
        body=body,
        subtype="html"  # Use "plain" for plain text emails
    )
    fm = FastMail(conf)
    await fm.send_message(message)
