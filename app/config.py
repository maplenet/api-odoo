from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ODOO_URL: str
    ODOO_DB: str
    ODOO_USERNAME: str
    ODOO_PASSWORD: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_EXPIRATION_MINUTES: int

    class Config:
        env_file = ".env"

settings = Settings()