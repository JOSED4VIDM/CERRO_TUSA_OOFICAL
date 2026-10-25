from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongodb_uri: str = ""
    mongodb_database: str = "cerro_tusa_turismo"
    admin_email: str = ""
    jwt_secret: str = ""
    frontend_url: str = ""
    cors_origins: str = ""
    whatsapp_number: str = ""
    contact_email: str = ""
    environment: str = "development"
    business_name: str = "Cerro Tusa Experience"

    @property
    def allowed_origins(self) -> list[str]:
        values = [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]
        if self.frontend_url.strip():
            values.append(self.frontend_url.strip().rstrip("/"))
        return list(dict.fromkeys(values))


@lru_cache
def get_settings() -> Settings:
    return Settings()
