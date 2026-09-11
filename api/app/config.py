from functools import lru_cache
from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings

_INSECURE_KEY_DEFAULTS = {
    "dev-secret-key-change-in-production",
    "changez-cette-valeur-secrete-en-production-min-32-chars",
}


class Settings(BaseSettings):
    # Identité du nœud — déjà fournie au conteneur par docker-compose
    # (`INSTANCE_ID: ${INSTANCE_ID:-}`) et utilisée par le front pour afficher
    # « RPi1 » au pied de page. L'API l'ignorait, si bien qu'elle ne pouvait pas
    # dire sur quel nœud elle exécutait ses propres tâches (sauvegarde, maintenance
    # déclenchée à la main) : la colonne « Nœud » restait vide. Vide en local.
    instance_id: str = ""

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

    #  Synthèse de contrat assistée — `app/utils/synthese_contrat.py`
    #
    #  🔴 **Vide par défaut, et c'est la fonctionnalité entière qui en dépend.**
    #  Sans clé, `synthese_active()` répond « non », l'API ne rend pas le bouton
    #  et rien ne sort de la résidence. Une copropriété qui n'a pas souscrit n'a
    #  donc aucun appel externe à désactiver : il n'y en a pas.
    #
    #  ⚠️ La clé se pose dans le `.env` du serveur, **jamais** dans le dépôt ni
    #  dans `.env.example` — même règle que `SECRET_KEY` et `MAIL_PASSWORD`.
    #  `test_config_secrets_masques.py` vérifie qu'elle ne ressort pas par
    #  `/config`.
    openai_api_key: str = ""
    #  ⚠️ **À vérifier avant la première MEP.** L'identifiant exact des modèles
    #  évolue plus vite que ce dépôt, et un identifiant inconnu produit un 404
    #  dont le message est repris tel quel par l'écran (voir `_appeler`). Les
    #  identifiants réellement ouverts à la clé se listent par :
    #      curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
    openai_modele: str = "gpt-5.6-terra"
    openai_base_url: str = "https://api.openai.com/v1"
    #  Un contrat de trente pages demande une à plusieurs minutes. Le défaut de
    #  httpx est de 5 s : sans ce réglage, l'appel expirerait toujours.
    openai_timeout_s: int = 180

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
