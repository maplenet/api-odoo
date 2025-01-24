import smtplib
from dotenv import load_dotenv
import os

# Cargar variables del archivo .env
load_dotenv()

EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

try:
    # Conexión al servidor SMTP de Gmail
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()  # Inicia TLS
    server.login(EMAIL_USERNAME, EMAIL_PASSWORD)  # Intenta iniciar sesión
    print("Inicio de sesión exitoso")
    server.quit()
except smtplib.SMTPAuthenticationError as e:
    print(f"Error de autenticación: {e}")
except Exception as e:
    print(f"Otro error: {e}")
