from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.core.database import get_odoo_connection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
blacklisted_tokens = set()

def create_access_token(user_id: int, email: str, expires_delta: timedelta = None):
    to_encode = {"sub": email, "user_id": user_id, "iat": datetime.now(timezone.utc)}
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.JWT_EXPIRATION_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        if token in blacklisted_tokens:
            raise HTTPException(status_code=401, detail="Token inválido o expirado")
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token inválido")        
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
