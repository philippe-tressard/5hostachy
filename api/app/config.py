from functools import lru_cache
from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings

_INSECURE_KEY_DEFAULTS = {
    "dev-secret-key-change-in-production",
    "changez-cette-valeur-secrete-en-production-min-32-chars",
}


class Settings(BaseSettings):
    # Sécurité
    secret_key: str = "dev-secret-key-change-in-production"

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_secure(cls, v: str) -> str:
        if v in _INSECURE_KEY_DEFAULTS:
            raise ValueError(
                "SECRET_KEY n'est pas configuré. Définissez une valeur aléatoire "
                "d'au moins 32 caractères dans votre fichier .env."
            )
        if len(v) < 32:
            raise ValueError("SECRET_KEY doit faire au moins 32 caractères.")
        return v

    cookie_secure: bool = True  # False uniquement pour dev HTTP local
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # Base de données
    database_url: str = "sqlite:////app/data/app.db"

    # Email
    mail_enabled: bool = False
    mail_from: str = "noreply@localhost"
    mail_from_name: str = "Ma Résidence"
    mail_username: str = ""
    mail_password: str = ""
    mail_server: str = "localhost"
    mail_port: int = 587
    mail_starttls: bool = True
    mail_ssl_tls: bool = False

    # Sauvegardes
    backup_dir: str = "/backups"
    backup_frequency: Literal["daily", "weekly", "monthly"] = "daily"
    backup_hour: int = 3
    backup_day_of_week: int = 6   # 0=lun … 6=dim
    backup_keep_versions: int = 7

    # Maintenance cron — clé partagée pour l'endpoint /admin/maintenance/rapport
    # Laisser vide pour désactiver l'enregistrement depuis le script cron
    maintenance_key: str = ""

    # OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
