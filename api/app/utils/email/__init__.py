"""Envoi d'e-mails via fastapi-mail + modèles Jinja2 stockés en base.

`email.py` faisait **686 lignes**. Découpé le 11/08/2026, au fil de l'eau.

| Module | Ce qui y change |
|---|---|
| `__init__` | à qui l'on écrit, quand, et avec quel contexte |
| `gabarit` | ce que le destinataire voit : gabarit HTML, bandeaux, logo |
| `pieces_jointes` | orientation EXIF, noms d'origine, en-têtes de disposition |

La surface publique ne bouge pas : `send_email`, `send_email_group`,
`INTENTIONS`, `get_site_manager_notification_email`, `_get_smtp_config` et
`connexion_smtp` s'importent depuis `app.utils.email` comme avant — vingt
modules en dépendent, plus les tests.
"""
import logging
import os
from datetime import datetime
from typing import Any

from jinja2.sandbox import SandboxedEnvironment
from jinja2 import BaseLoader
from sqlmodel import Session, select

from app.config import get_settings
from app.utils.preferences_mail import mail_autorise
from app.models.core import ConfigSite, HistoriqueEmail, ModeleEmail, Utilisateur
from app.utils.fichiers import nom_lisible
#  La configuration du canal SMTP est un sujet distinct de la composition
#  d'un message : elle vit dans `app/utils/smtp.py` depuis le 08/08/2026.
from app.utils.smtp import _get_smtp_config, connexion_smtp  # noqa: F401  (ré-export : config.py l'importe d'ici)

from .gabarit import INTENTIONS, _wrap_email  # noqa: F401  (ré-export : admin/communications l'importe d'ici)
from .pieces_jointes import _preparer_pieces_jointes

import re as _re

settings = get_settings()

logger = logging.getLogger("email")


# Mapping code email → clé préférence utilisateur (catégorie_mail)
# Les codes absents (system, account) sont toujours envoyés.
#  Les rubriques ont disparu le 14/08/2026 (#339) : le réglage ne se fait plus par
#  type de contenu mais par BÂTIMENT — le mien, les autres. La décision est dans
#  `utils/preferences_mail.py`, seul endroit qui lit les préférences.


def get_site_manager_notification_email(session: Session) -> tuple[str, dict[str, str]]:
    """Retourne l'email de notification du gestionnaire du site et la config lue."""
    rows = session.exec(
        select(ConfigSite).where(
            ConfigSite.cle.in_(("site_email", "site_nom", "site_url", "site_manager_user_id"))
        )
    ).all()
    config = {row.cle: row.valeur for row in rows}

    site_email = (config.get("site_email") or "").strip()
    site_manager_email = ""
    site_manager_user_id = (config.get("site_manager_user_id") or "").strip()
    if site_manager_user_id.isdigit():
        manager_user = session.get(Utilisateur, int(site_manager_user_id))
        if manager_user and manager_user.email:
            site_manager_email = manager_user.email.strip()

    return site_manager_email or site_email, config


def _log_email(session: Session, code: str, to: str, statut: str, *, sujet: str = "", erreur: str | None = None) -> None:
    """Enregistre une entrée dans historique_email (fail-safe)."""
    try:
        entry = HistoriqueEmail(code=code, destinataire=to, sujet=sujet[:200], statut=statut, erreur=erreur)
        session.add(entry)
        session.commit()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass


def _render(template_str: str, context: dict) -> str:
    env = SandboxedEnvironment(loader=BaseLoader())
    tmpl = env.from_string(template_str)
    return tmpl.render(**context)


def _prefixe_copro(reference: str) -> str:
    """« 🏢 00213 — » en tête d'objet, ou rien si la référence n'est pas renseignée.

    Forme **unique** du rappel de référence, obligatoire sans exception dans tout
    message adressé au syndic — c'est l'identifiant sous lequel il classe ses
    dossiers. Elle était recopiée sept fois dans les modèles, sous deux formes
    déjà différentes (« 🏢 00213 — » et « [🏢 00213] – ») : deux copies d'une même
    notion finissent toujours par diverger, et celles-ci l'avaient déjà fait.

    La composer ici plutôt que dans les modèles a une seconde conséquence, plus
    importante que la forme : un modèle vit en base et se réécrit depuis
    Admin → Emails. Le `{% if reference_copro %}` qui y était recopié pouvait
    être retiré d'un formulaire, et la règle avec lui.
    """
    ref = (reference or "").strip()
    return f"\U0001f3e2 {ref} — " if ref else ""


def _contexte_rendu(session: Session, context: dict) -> tuple[dict, str, str, str]:
    """(contexte complet du rendu, nom du site, URL du site, pied de page).

    Les deux fonctions d'envoi lisaient ces valeurs chacune de leur côté, en
    trois `session.get` recopiés — la même configuration, deux fois.
    """
    lignes = {
        r.cle: r.valeur
        for r in session.exec(
            select(ConfigSite).where(
                ConfigSite.cle.in_(
                    ("site_nom", "site_url", "email_footer", "reference_copro")
                )
            )
        ).all()
    }
    site_nom = lignes.get("site_nom") or "Ma Résidence"
    site_url = lignes.get("site_url") or "https://localhost"
    reference = (lignes.get("reference_copro") or "").strip()

    ctx = {
        "annee": datetime.utcnow().year,
        "app": {"url": site_url.rstrip("/")},
        "residence": {"nom": site_nom},
        **context,
        #  Après `context`, donc non surchargeable : la référence vient de la
        #  configuration du site, jamais d'un point d'appel. Cinq d'entre eux la
        #  lisaient séparément et deux ne la fournissaient pas du tout — leurs
        #  objets partaient sans référence, et Jinja évalue un indéfini à faux
        #  sans rien signaler. Lue ici, elle ne peut plus être oubliée.
        "reference_copro": reference,
        "prefixe_copro": _prefixe_copro(reference),
    }
    return ctx, site_nom, site_url, (lignes.get("email_footer") or "").strip()


#  Au-delà, un objet n'informe plus personne : aucun client de messagerie n'en
#  affiche le quart. La borne n'est pas cosmétique — ni `ticket.titre` ni
#  `publication.titre` n'ont de longueur maximale en base, donc rien ne limitait
#  la taille d'un objet depuis qu'ils y figurent.
_SUJET_MAX = 150


def _sujet_sur_une_ligne(sujet: str) -> str:
    """Objet d'un message : une seule ligne, de longueur bornée.

    Depuis le 11/08/2026, l'objet des e-mails de tickets et de publications
    porte le **titre** de l'objet métier — donc une saisie libre, qui n'était
    jusqu'ici rendue que dans le corps HTML. Deux conséquences, et aucune ne
    relève du modèle :

    1. **Sécurité.** Un `\\n` dans un titre coupe l'en-tête `Subject:` et laisse
       injecter un `Bcc:` — le message part alors à un destinataire choisi par
       l'auteur du ticket. Nos objets contiennent aujourd'hui tous un tiret
       cadratin, donc Python les encode en RFC 2047 et la coupure est
       neutralisée : c'est une protection **de circonstance**, qui disparaîtrait
       sans bruit le jour où un objet devient purement ASCII. On ne s'appuie pas
       dessus (`standards/03-securite.md` §4).
    2. **Lisibilité.** Un titre de 400 caractères produisait un objet de 400
       caractères.

    Écrit ici et non dans les modèles pour la même raison que
    `_bandeau_pieces_jointes` : ceux-ci vivent en base et sont réécrivables
    depuis Admin → Emails. Une règle qu'un formulaire peut retirer n'est pas une
    règle. À cet endroit, elle couvre les vingt-quatre modèles et tous ceux à
    venir.
    """
    #  Les caractères de contrôle d'abord : `\\s` ignore NUL, qui ferait lever
    #  la bibliothèque `email` au lieu d'être simplement neutralisé.
    propre = _re.sub(r"[\x00-\x1f\x7f]+", " ", sujet or "")
    propre = _re.sub(r"\s+", " ", propre).strip()
    if len(propre) <= _SUJET_MAX:
        return propre
    return propre[: _SUJET_MAX - 1].rstrip() + "…"


def composer_email(
    template: ModeleEmail,
    ctx: dict,
    *,
    site_nom: str,
    site_url: str,
    email_footer: str,
    attachments: list[str] | None = None,
) -> tuple[str, str]:
    """(objet, corps HTML complet) d'un e-mail — **la seule composition du projet**.

    ## Pourquoi cette fonction existe (#498, 19/08/2026)

    Deux raisons, et la seconde est la vraie.

    1. `send_email` et `send_email_group` portaient ces onze lignes **à
       l'identique**. Deux écritures d'une même règle sont deux valeurs libres de
       diverger (`standards/02` §2).

    2. 🔴 **L'aperçu avant envoi doit montrer ce qui partira, pas une
       reconstitution.** Un aperçu recomposé « à peu près » deviendrait faux à la
       première évolution d'un gabarit — et personne ne s'en apercevrait, puisque
       c'est justement l'aperçu qu'on regarderait pour vérifier. C'est le faux-vert
       de `standards/04` §14 : observer la chose, pas son enregistrement.

    ⚠️ **Toute règle de composition s'écrit ICI.** En ajouter une dans un appelant
    la rendrait invisible à l'aperçu, ce qui est exactement le défaut qu'on ferme.
    `api/tests/test_apercu_diffusion.py` échoue si les deux divergent.

    Ne touche ni au réseau ni à la base : elle reçoit tout ce dont elle a besoin.
    """
    corps = _render(template.corps_html, ctx)
    html = _wrap_email(
        corps,
        site_nom=site_nom,
        site_url=site_url,
        footer=email_footer,
        annee=ctx["annee"],
        pieces_jointes=[nom_lisible(p) for p in (attachments or [])],
        intention=template.intention,
    )
    return _sujet_sur_une_ligne(_render(template.sujet, ctx)), html


async def send_email(
    code: str,
    to: str,
    context: dict[str, Any],
    session: Session | None = None,
    *,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[str] | None = None,
    destinataire_id: int | None = None,
    batiments_concernes: set[int] | None = None,
):
    """
    Récupère le ModèleEmail par code, rend sujet + corps, envoie si MAIL_ENABLED.

    Les images jointes sont automatiquement corrigées (orientation EXIF) avant envoi.
    Fail graceful : en cas d'erreur, log sans bloquer l'événement déclencheur.
    
    Si *destinataire_id* est fourni et que le code email est lié à une
    catégorie de préférence, l'email n'est envoyé que si l'utilisateur
    a activé la préférence correspondante.
    """
    from app.database import SessionLocal
    
    # Créer une nouvelle session si elle n'existe pas (pour les background tasks)
    if session is None:
        session = SessionLocal()
        close_session = True
    else:
        close_session = False
    
    try:
        # ── Vérification préférence utilisateur ──────────────────────────
        if destinataire_id:
            user = session.get(Utilisateur, destinataire_id)
            if user and not mail_autorise(user, batiments_concernes):
                logger.debug("Email [%s] non envoyé → préférence de bâtiment, user %s",
                             code, destinataire_id)
                _log_email(session, code, to, "ignore", erreur="préférence de bâtiment")
                return

        smtp_cfg = _get_smtp_config(session)
        if smtp_cfg.get('smtp_enabled') is not None:
            if smtp_cfg['smtp_enabled'] != '1':
                return
        elif not settings.mail_enabled:
            return

        template: ModeleEmail | None = session.exec(
            select(ModeleEmail).where(ModeleEmail.code == code)
        ).first()
        if not template or not template.actif:
            _log_email(session, code, to, "ignore", erreur="template inactive ou inexistante")
            return

        ctx, site_nom, site_url, email_footer = _contexte_rendu(session, context)

        try:
            from fastapi_mail import FastMail, MessageSchema

            cfg = connexion_smtp(smtp_cfg)
            fm = FastMail(cfg)
            rendered_subject, full_html = composer_email(
                template, ctx, site_nom=site_nom, site_url=site_url,
                email_footer=email_footer, attachments=attachments,
            )
            msg_kwargs = dict(
                subject=rendered_subject,
                recipients=[to],
                body=full_html,
                subtype="html",
            )
            if cc:
                msg_kwargs["cc"] = cc
            if bcc:
                msg_kwargs["bcc"] = bcc
            fixed_attachments: list[str] = []
            if attachments:
                prets, fixed_attachments = _preparer_pieces_jointes(attachments)
                msg_kwargs["attachments"] = prets
            msg = MessageSchema(**msg_kwargs)
            await fm.send_message(msg)
            _log_email(session, code, to, "succes", sujet=rendered_subject)
        except Exception as exc:
            logger.error("Erreur envoi email [%s] → %s : %s", code, to, exc)
            _log_email(session, code, to, "erreur", erreur=str(exc)[:500])
    finally:
        # Nettoyer les fichiers temporaires EXIF
        if attachments:
            for fp in fixed_attachments:
                if fp not in attachments:
                    try:
                        os.unlink(fp)
                    except OSError:
                        pass
        if close_session:
            session.close()


def _check_pref(user_id: int | None, session: Session,
                batiments_concernes: set[int] | None = None) -> bool:
    """L'utilisateur veut-il cet e-mail ? — délègue à la décision unique."""
    if not user_id:
        return True
    user = session.get(Utilisateur, user_id)
    if not user:
        return True
    return mail_autorise(user, batiments_concernes)


async def send_email_group(
    code: str,
    to_recipients: list[tuple[int | None, str]],
    context: dict[str, Any],
    session: Session | None = None,
    *,
    cc_recipients: list[tuple[int | None, str]] | None = None,
    bcc: list[str] | None = None,
    attachments: list[str] | None = None,
    batiments_concernes: set[int] | None = None,
):
    """
    Envoie UN seul email groupé à plusieurs destinataires (to + cc optionnel).

    - to_recipients  : liste (user_id | None, email) — destinataires principaux (se voient entre eux)
    - cc_recipients  : liste (user_id | None, email) — destinataires en copie (ex: auteur du ticket)
    - Les préférences de chaque utilisateur sont vérifiées individuellement en amont.
    - Un seul enregistrement dans historique_email liste tous les destinataires.
    - Les pièces jointes (photos) sont transmises si fournies.
    """
    from app.database import SessionLocal

    if session is None:
        session = SessionLocal()
        close_session = True
    else:
        close_session = False

    fixed_attachments: list[str] = []
    try:
        smtp_cfg = _get_smtp_config(session)
        if smtp_cfg.get('smtp_enabled') is not None:
            if smtp_cfg['smtp_enabled'] != '1':
                return
        elif not settings.mail_enabled:
            return

        template: ModeleEmail | None = session.exec(
            select(ModeleEmail).where(ModeleEmail.code == code)
        ).first()
        if not template or not template.actif:
            return

        # Filtrage des préférences individuelles
        filtered_to = [
            (uid, email) for uid, email in to_recipients
            if _check_pref(uid, session, batiments_concernes)
        ]
        filtered_cc = [
            (uid, email) for uid, email in (cc_recipients or [])
            if _check_pref(uid, session, batiments_concernes)
        ]

        if not filtered_to and not filtered_cc:
            return

        to_emails = [email for _, email in filtered_to]
        cc_emails = [email for _, email in filtered_cc]
        all_emails_str = ", ".join(to_emails + cc_emails)

        ctx, site_nom, site_url, email_footer = _contexte_rendu(session, context)

        try:
            from fastapi_mail import FastMail, MessageSchema

            cfg = connexion_smtp(smtp_cfg)
            fm = FastMail(cfg)
            rendered_subject, full_html = composer_email(
                template, ctx, site_nom=site_nom, site_url=site_url,
                email_footer=email_footer, attachments=attachments,
            )
            msg_kwargs: dict[str, Any] = dict(
                subject=rendered_subject,
                recipients=to_emails if to_emails else cc_emails,
                body=full_html,
                subtype="html",
            )
            # CC : uniquement si to non vide (sinon tous en recipients)
            if to_emails and cc_emails:
                msg_kwargs["cc"] = cc_emails
            if bcc:
                msg_kwargs["bcc"] = bcc
            # Pièces jointes (photos) — correction orientation EXIF avant envoi
            if attachments:
                prets, fixed_attachments = _preparer_pieces_jointes(attachments)
                msg_kwargs["attachments"] = prets
            msg = MessageSchema(**msg_kwargs)
            await fm.send_message(msg)
            _log_email(session, code, all_emails_str, "succes", sujet=rendered_subject)
        except Exception as exc:
            logger.error("Erreur envoi email groupé [%s] → %s : %s", code, all_emails_str, exc)
            _log_email(session, code, all_emails_str, "erreur", erreur=str(exc)[:500])
    finally:
        # Nettoyer les fichiers temporaires EXIF
        if attachments:
            for fp in fixed_attachments:
                if fp not in attachments:
                    try:
                        os.unlink(fp)
                    except OSError:
                        pass
        if close_session:
            session.close()
