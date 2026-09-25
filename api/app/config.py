from functools import lru_cache
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

    #: Racine du volume des fichiers téléversés.
    #:
    #: 🔴 Elle était lue à SIX endroits avant le 19/09/2026 (#1026) : trois
    #: `os.getenv("UPLOADS_DIR")` et trois chemins écrits en dur
    #: (`RACINE_UPLOADS`, `UPLOADS_ROOT`, `PDF_DIR`). Six écritures d'un même
    #: chemin, c'est cinq occasions d'en oublier une le jour où le volume bouge
    #: — et un fichier écrit hors du volume n'est ni répliqué vers le standby
    #: par `bascule.sh`, ni sauvegardé par `backup.py`. Il est perdu à la
    #: première bascule, sans aucun signal.
    uploads_dir: str = "/app/uploads"
    backup_hour: int = 3
    backup_keep_versions: int = 7

    # Maintenance cron — clé partagée pour l'endpoint /admin/maintenance/rapport
    # Laisser vide pour désactiver l'enregistrement depuis le script cron
    maintenance_key: str = ""

    #  Budget d'une photo jointe à un message WhatsApp, en kio.
    #
    #  🔴 Déclaré dans `docker-compose.yml` (`WA_PHOTO_BUDGET_KO`) et lu des DEUX
    #  côtés : ici, et par le bridge qui en dérive la borne de son corps JSON.
    #  Ce défaut-ci n'est qu'un repli hors conteneur — la valeur qui fait foi est
    #  celle de compose. Deux nombres écrits séparément divergeraient, et c'est
    #  ce qui a coûté un message le 19/09/2026 (#1057).
    wa_photo_budget_ko: int = 400

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
