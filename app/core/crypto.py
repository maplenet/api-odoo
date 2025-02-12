# app/core/crypto.py
import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from app.config import settings  # Importa la configuración centralizada

# Cargar las variables de entorno (opcional, ya que Pydantic lo hace en config)
load_dotenv()

# Inicializar el objeto Fernet con la clave obtenida de la configuración
fernet = Fernet(settings.ENCRYPTION_KEY)

def encrypt_password(password: str) -> str:
    """
    Encripta la contraseña en texto plano y devuelve la cadena encriptada.
    """
    return fernet.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    """
    Desencripta una contraseña previamente encriptada y devuelve la contraseña en texto plano.
    """
    return fernet.decrypt(encrypted_password.encode()).decode()
