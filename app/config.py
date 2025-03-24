from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
	# Configuración para Odoo
	ODOO_URL: str
	ODOO_DB: str
	ODOO_USERNAME: str
	ODOO_PASSWORD: str

	# Configuración para JWT
	JWT_SECRET_KEY: str
	JWT_ALGORITHM: str
	JWT_EXPIRATION_MINUTES: int

	# Configuración para correo electrónico
	EMAIL_FROM: str = Field(..., env="EMAIL_FROM")
    
	# variable de encriptación
	ENCRYPTION_KEY: str = Field(..., env="ENCRYPTION_KEY")
	LOG_LEVEL: str = Field("DEBUG", env="LOG_LEVEL") 
	OTT_URL_BASE_API: str = Field(..., env="OTT_URL_BASE_API")
	OTT_USERNAME: str = Field(..., env="OTT_USERNAME")
	OTT_PASSWORD: str = Field(..., env="OTT_PASSWORD")
	SENDGRID_API_KEY: str = Field(..., env="SENDGRID_API_KEY")
	URL_BASE_API_PONTIS: str = Field(..., env="URL_BASE_API_PONTIS")

	class Config:
		env_file = ".env"
		env_file_encoding = "utf-8"

settings = Settings(_env_file=".env", _env_file_encoding="utf-8")