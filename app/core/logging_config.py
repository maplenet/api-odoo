import logging
import os
from app.config import settings

# Usa el nivel definido en la configuración o en la variable de entorno
log_level = settings.LOG_LEVEL.upper()  # Por ejemplo, 'DEBUG' o 'INFO'

logging.basicConfig(
    level=log_level,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)
logger.debug("Logging configurado en nivel DEBUG")
