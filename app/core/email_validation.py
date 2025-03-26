import re
from fastapi import HTTPException
from app.core.logging_config import logger


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
    if not EMAIL_REGEX.match(email):
        logger.error("Formato de email inválido: %s", email)
        raise HTTPException(status_code=400, detail="El formato de correo es incorrecto.")
    
    domain = email.split("@")[-1].lower()
    if domain in BLACKLISTED_DOMAINS:
        logger.error("Dominio no permitido en email: %s", domain)
        raise HTTPException(status_code=400, detail="El dominio de correo electrónico no está permitido.")
    
    logger.debug("El email %s es válido", email)
    return True