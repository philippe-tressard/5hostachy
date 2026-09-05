"""Le canal SMTP : quelles clés le décrivent, et comment on s'y connecte.

Sorti de `email.py` le 08/08/2026, le jour où le garde-fou de modularité a
refusé le lot : y ajouter `connexion_smtp` faisait passer ce fichier de 656 à
663 lignes, alors qu'il dépassait déjà largement le plafond de 500.

Le découpage n'est pas qu'arithmétique. **Configurer un canal** et **composer
un message** sont deux sujets : le premier tient en trois éléments et ne change
que lorsque l'hébergeur change ; le second occupe six cents lignes de gabarits,
de rendu Jinja et de pièces jointes.
"""
from sqlmodel import Session, select

from app.config import get_settings
from app.models.core import ConfigSite

#  ⚠️ `smtp_from_reponse` est la SECONDE adresse d'expédition (05/09/2026) :
#  `contact@` pour ce qui appelle une réponse, `smtp_from` (`noreply@`) pour ce
#  qui n'en appelle aucune. Une clé absente ou vide se replie sur `smtp_from` —
#  une installation qui n'a pas encore renseigné la seconde adresse continue
#  d'envoyer exactement comme avant, plutôt que depuis une adresse vide.
_SMTP_KEYS = {'smtp_enabled', 'smtp_server', 'smtp_port', 'smtp_from', 'smtp_from_reponse', 'smtp_from_name', 'smtp_username', 'smtp_password', 'smtp_starttls', 'smtp_ssl_tls'}


def _get_smtp_config(session: Session) -> dict:
    rows = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(_SMTP_KEYS))).all()
    return {r.cle: r.valeur for r in rows}


def adresse_expedition(smtp_cfg: dict, genre: str) -> str:
    """L'adresse d'expédition pour ce genre d'envoi (`expediteur_du_modele`).

    Repli explicite : sans seconde adresse configurée, tout part de `smtp_from`
    comme avant. Le silence de la configuration ne doit pas produire une adresse
    vide — un message sans expéditeur est refusé par le serveur, et l'envoi
    échouerait sans que le motif ait quoi que ce soit à voir avec son contenu.
    """
    from app.seed.emails import EXPEDITEUR_REPONSE

    defaut = smtp_cfg.get("smtp_from") or get_settings().mail_from
    if genre != EXPEDITEUR_REPONSE:
        return defaut
    return (smtp_cfg.get("smtp_from_reponse") or "").strip() or defaut


def connexion_smtp(smtp_cfg: dict, *, expediteur: str | None = None):
    """La connexion SMTP effective : configuration en base, sinon le `.env`.

    Ces dix-sept lignes étaient écrites **trois fois** — deux dans ce module
    (envoi simple et envoi groupé) et une dans `routers/config.py` pour l'e-mail
    de test. C'est la duplication la plus coûteuse qui soit sur ce chemin : le
    bouton « tester la configuration SMTP » n'a d'intérêt que s'il emprunte
    exactement la même construction que les envois réels. Trois écritures, c'est
    trois occasions de tester autre chose que ce qui part vraiment.

    Le repli est champ par champ, et non « bloc en base OU bloc du .env » : une
    configuration partielle en base (seulement le serveur, par exemple) hérite du
    reste de l'environnement.
    """
    from fastapi_mail import ConnectionConfig

    settings = get_settings()
    #  `in` et non `.get()` pour les deux booléens : une case décochée vaut « 0 »
    #  en base, ce qu'un `or` traiterait comme absent et remplacerait par la
    #  valeur du .env — l'utilisateur ne pourrait alors jamais désactiver STARTTLS.
    starttls = (
        smtp_cfg["smtp_starttls"] == "1" if "smtp_starttls" in smtp_cfg
        else settings.mail_starttls
    )
    ssl_tls = (
        smtp_cfg["smtp_ssl_tls"] == "1" if "smtp_ssl_tls" in smtp_cfg
        else settings.mail_ssl_tls
    )
    username = smtp_cfg.get("smtp_username") or settings.mail_username

    return ConnectionConfig(
        MAIL_USERNAME=username,
        MAIL_PASSWORD=smtp_cfg.get("smtp_password") or settings.mail_password,
        #  L'expéditeur peut être imposé par l'appelant : c'est l'INTENTION du
        #  modèle qui le décide, pas la connexion (voir `adresse_expedition`).
        MAIL_FROM=expediteur or smtp_cfg.get("smtp_from") or settings.mail_from,
        MAIL_FROM_NAME=smtp_cfg.get("smtp_from_name") or settings.mail_from_name,
        MAIL_PORT=int(smtp_cfg.get("smtp_port") or settings.mail_port),
        MAIL_SERVER=smtp_cfg.get("smtp_server") or settings.mail_server,
        MAIL_STARTTLS=starttls,
        MAIL_SSL_TLS=ssl_tls,
        USE_CREDENTIALS=bool(username),
    )
