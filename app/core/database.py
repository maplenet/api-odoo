import xmlrpc.client
from app.config import settings

def get_odoo_connection():
    common = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(settings.ODOO_DB, settings.ODOO_USERNAME, settings.ODOO_PASSWORD, {})
    
    if not uid:
        raise Exception("Autenticación fallida en Odoo")
    
    models = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/object")
    
    return {
        'db': settings.ODOO_DB,
        'uid': uid,
        'password': settings.ODOO_PASSWORD,
        'models': models
    }