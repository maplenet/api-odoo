import os
import logging
from app.config import settings

# Asegúrate de que el directorio existe
log_directory = "storage"
os.makedirs(log_directory, exist_ok=True)
log_file_path = os.path.join(log_directory, "app.log")

log_level = settings.LOG_LEVEL.upper()  # Por ejemplo, 'DEBUG' o 'INFO'

logging.basicConfig(
    level=log_level,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file_path, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)
logger.debug("Logging configurado en nivel DEBUG")

logging.getLogger("python_http_client.client").setLevel(logging.WARNING)
