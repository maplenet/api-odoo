from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
blacklisted_tokens = set()

def create_access_token(user_id: int, contact_id: int, expires_delta: timedelta = None):
    to_encode = {
        "user_id": user_id, 
        "contact_id":contact_id, 
        "iat": datetime.now(timezone.utc)
        }
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.JWT_EXPIRATION_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_password_reset_token(user_id: int, expires_minutes: int = 15) -> str:
    """
    Crea un token JWT para el restablecimiento de contraseña con un tiempo de expiración corto.
    El token incluirá:
      - user_id: identificador del usuario
      - action: "reset_password" (para distinguirlo de otros tokens)
      - iat y exp: tiempos de emisión y expiración.
    """
    payload = {
        "user_id": user_id,
        "action": "reset_password",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def verify_token(token: str = Depends(oauth2_scheme)):
    """
    Verifica el token de acceso y retorna el payload completo.
    Se rechaza el token si está en la lista negra o si faltan campos obligatorios.
    """
    try:
        if token in blacklisted_tokens:
            raise HTTPException(status_code=401, detail="Token inválido o expirado")
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("user_id")
        contact_id = payload.get("contact_id")
        if user_id is None or contact_id is None:
            raise HTTPException(status_code=401, detail="Token inválido: falta información.")
        return payload  # Retorna el payload completo
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")