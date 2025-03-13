# import os
# from pydantic_settings import BaseSettings
# from pydantic import Field

# ENVIRONMENT = os.getenv("ENVIRONMENT", "test")

# class Settings(BaseSettings):
#     # Variables de configuración...
#     ODOO_URL: str
#     ODOO_DB: str
#     ODOO_USERNAME: str
#     ODOO_PASSWORD: str

#     JWT_SECRET_KEY: str
#     JWT_ALGORITHM: str
#     JWT_EXPIRATION_MINUTES: int

#     EMAIL_USERNAME: str = Field(..., env="EMAIL_USERNAME")
#     EMAIL_PASSWORD: str = Field(..., env="EMAIL_PASSWORD")
#     EMAIL_FROM: str = Field(..., env="EMAIL_FROM")
#     EMAIL_PORT: int = Field(..., env="EMAIL_PORT")
#     EMAIL_SERVER: str = Field(..., env="EMAIL_SERVER")
#     EMAIL_TLS: bool = Field(..., env="EMAIL_TLS")
#     EMAIL_SSL: bool = Field(..., env="EMAIL_SSL")

#     ENCRYPTION_KEY: str = Field(..., env="ENCRYPTION_KEY")

#     LOG_LEVEL: str = Field("DEBUG", env="LOG_LEVEL")

#     class Config:
#         env_file = f".env.{ENVIRONMENT}"
#         env_file_encoding = "utf-8"

# settings = Settings()




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
	EMAIL_USERNAME: str = Field(..., env="EMAIL_USERNAME")
	EMAIL_PASSWORD: str = Field(..., env="EMAIL_PASSWORD")
	EMAIL_FROM: str = Field(..., env="EMAIL_FROM")
	EMAIL_PORT: int = Field(..., env="EMAIL_PORT")
	EMAIL_SERVER: str = Field(..., env="EMAIL_SERVER")
	EMAIL_TLS: bool = Field(..., env="EMAIL_TLS")
	EMAIL_SSL: bool = Field(..., env="EMAIL_SSL")
    
	# variable de encriptación
	ENCRYPTION_KEY: str = Field(..., env="ENCRYPTION_KEY")
	LOG_LEVEL: str = Field("DEBUG", env="LOG_LEVEL") 
	URL_BASE_API_PONTIS: str = Field(..., env="URL_BASE_API_PONTIS")

	class Config:
		env_file = ".env"
		env_file_encoding = "utf-8"

settings = Settings(_env_file=".env", _env_file_encoding="utf-8")