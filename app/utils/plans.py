from app.config import settings

var_env = settings.ODOO_DB.lower()

if var_env == "maplenet-prod":
    # Lista de IDs de productos en Odoo para producción
    PRODUCTS = {
        "M+_ESTANDAR_PROMO": 6,
        "M+_ESTANDAR": 7,
        "M+ _REMIUM": 8,
        "M+_PREMIUM_+_HBO": 9,
        "BRASIL_VS_COLOMBIA_20-03-2025": 46,
        "ECUADOR_VS_VENEZUELA_21-03-2025": 47,
        "BOLIVIA_VS_URUGUAY_Y_ARGENTINA_VS_BRASIL_25-03-2025": 49,
    }
else:
    # Lista de IDs de productos en Odoo para test
    PRODUCTS = {
        "ID_ESTADAR": 11,
        "PREMIUM_PLUS": 13,
        "HBO": 14,
        "ID_PREMIUM": 22,
        "[M+M] FUTBOL": 12, 
    }
