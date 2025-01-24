from fastapi import HTTPException

# TODO: USAR ESTA BLACKLIST PARA ENVIO DE CORREOS
# Lista negra de dominios temporales
BLACKLISTED_DOMAINS = {
     "yopmail.com", "10minutemail.com", "mailinator.com", "guerrillamail.com",
    "dispostable.com", "fakeinbox.com", "getnada.com", "maildrop.cc", "throwawaymail.com"
}

def is_valid_email(email: str):
    """Validate email domain against a blacklist."""
    domain = email.split("@")[-1]
    if domain in BLACKLISTED_DOMAINS:
        raise HTTPException(status_code=400, detail="El dominio del correo no es permitido.")
    return True
