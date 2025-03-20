import re
from fastapi import HTTPException

# Expresión regular para validar el formato de un correo electrónico
EMAIL_REGEX = re.compile(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,4}$', re.IGNORECASE)

# Lista negra de dominios temporales
BLACKLISTED_DOMAINS = {
    '10minutemail.com',
    'fremont.nodebalancer.linode.com',
    'yopmail.com',
    'temp-mail.org',
    'cool.fr.nf',
    'jetable.fr.nf',
    'nospam.ze.tc',
    'nomail.xl.cx',
    'mega.zik.dj',
    'speed.1s.fr',
    'courriel.fr.nf',
    'moncourrier.fr.nf',
    'monemail.fr.nf',
    'monmail.fr.nf',
    'mailinator',
    'binkmail.com',
    'bobmail.info',
    'chammy.info',
    'devnullmail.com',
    'letthemeatspam.com',
    'mailinator.com',
    'mailinater.com',
    'mailinator.net',
    'mailinator2.com',
    'notmailinator.com',
    'reallymymail.com',
    'reconmail.com',
    'safetymail.info',
    'sendspamhere.com',
    'sogetthis.com',
    'spambooger.com',
    'spamherelots.com',
    'spamhereplease.com',
    'spamthisplease.com',
    'streetwisemail.com',
    'suremail.info',
    'thisisnotmyrealemail.com',
    'tradermail.info',
    'veryrealemail.com',
    'zippymail.info',
    'guerrillamail',
    'maildrop',
    'mailnesia',
    'worldmagic.ink',
    'gufum.com',
    'mail.com',
    'theeyeoftruth.com',
    'bmomento.com',
    'bixolabs.com',
    'evildrako654.online',
    'mailtemporal.net',
}

def is_valid_email(email: str) -> bool:
    """
    Valida que el correo tenga un formato correcto y que el dominio no esté en la lista negra.
    
    :param email: Dirección de correo a validar.
    :raises HTTPException: Si el formato es inválido o el dominio está prohibido.
    :return: True si el correo es válido.
    """
    if not EMAIL_REGEX.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format.")
    
    # Se extrae el dominio y se convierte a minúsculas para la comparación
    domain = email.split("@")[-1].lower()
    if domain in BLACKLISTED_DOMAINS:
        raise HTTPException(status_code=400, detail="The email domain is not allowed.")
    
    return True