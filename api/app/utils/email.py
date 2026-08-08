"""Envoi d'emails via fastapi-mail + templates Jinja2 stockés en base."""
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any

from jinja2.sandbox import SandboxedEnvironment
from jinja2 import BaseLoader
from sqlmodel import Session, select

from app.config import get_settings
from app.models.core import ConfigSite, HistoriqueEmail, ModeleEmail, Utilisateur
from app.utils.fichiers import libelle_pieces_jointes, nom_lisible
#  La configuration du canal SMTP est un sujet distinct de la composition
#  d'un message : elle vit dans `app/utils/smtp.py` depuis le 08/08/2026,
#  ce qui ramène aussi ce module sous son poids d'avant la factorisation.
from app.utils.smtp import _get_smtp_config, connexion_smtp  # noqa: F401  (ré-export : config.py l'importe d'ici)

settings = get_settings()


# Mapping code email → clé préférence utilisateur (catégorie_mail)
# Les codes absents (system, account) sont toujours envoyés.
_EMAIL_PREF_MAP: dict[str, str] = {
    "ticket_bug_admin": "ticket_mail",
    "ticket_statut_change": "ticket_mail",
    "ticket_nouveau_message": "ticket_mail",
    "ticket_syndic": "ticket_mail",
    "publication_syndic": "actu_mail",
    "calendrier_evenement_cree": "actu_mail",
    "document_publie": "doc_mail",
    "reponse_communaute": "communaute_mail",
    "idee_statut": "communaute_mail",
}

# Intention d'un e-mail : ce qui est attendu du destinataire, annoncé d'emblée.
#
# La plupart des modèles entrent dans le détail sans annoncer la couleur : le
# lecteur doit lire jusqu'au bout pour savoir si on l'informe ou si on attend
# quelque chose de lui. Un bandeau en tête le dit en trois mots.
#
# Le bandeau est rendu par le gabarit commun, à partir d'une colonne de
# `modele_email` — surtout pas recopié dans chaque corps : il resterait
# introuvable le jour où il faudrait le changer, et une migration qui réécrit
# vingt-quatre corps écraserait les personnalisations faites depuis
# Admin → Emails.
#
# code → (libellé affiché, fond, texte)
INTENTIONS: dict[str, tuple[str, str, str]] = {
    "information": ("Pour information", "#EEF2F7", "#1E3A5F"),
    "action_requise": ("Action requise", "#FEF3E2", "#8A5A0B"),
    "reponse_attendue": ("Réponse attendue", "#F0F7F2", "#2C5138"),
    # Disponible depuis Admin → Emails, aucun modèle ne la porte aujourd'hui :
    # elle vaut pour un envoi qu'on garde sans avoir à en faire quoi que ce soit.
    "archive": ("À conserver", "#F4F2ED", "#5A6070"),
}


def _bandeau_intention(intention: str | None) -> str:
    """Bandeau « ce qu'on attend de vous », ou rien si l'intention est inconnue.

    Une intention vide ou non reconnue ne rend rien plutôt que d'afficher une
    étiquette fausse : un modèle sans intention déclarée reste exactement ce
    qu'il était.
    """
    entree = INTENTIONS.get((intention or "").strip())
    if not entree:
        return ""
    libelle, fond, couleur = entree
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" '
        f'style="width:100%;margin:0 0 20px"><tr>'
        f'<td style="background:{fond};border-radius:6px;padding:10px 14px">'
        f'<span style="font-size:12px;font-weight:700;letter-spacing:.6px;'
        f'text-transform:uppercase;color:{couleur}">{libelle}</span>'
        f'</td></tr></table>'
    )


logger = logging.getLogger("email")


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


# ── Logo SVG inline (favicon du site) — base64 pour compatibilité email ──
_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="48" height="48">'
    '<rect width="64" height="64" rx="14" fill="#1E3A5F"/>'
    '<g fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M18 54V18a4 4 0 0 1 4-4h20a4 4 0 0 1 4 4v36Z"/>'
    '<path d="M18 34h-6a4 4 0 0 0-4 4v16h10"/>'
    '<path d="M46 30h6a4 4 0 0 1 4 4v20H46"/>'
    '<path d="M25 22h14"/><path d="M25 30h14"/><path d="M25 38h14"/><path d="M25 46h14"/>'
    '</g>'
    '<path d="M48 50c0 4.4-3.6 8-8 8h14a8 8 0 0 0-6-8Z" fill="#C9983A" opacity=".95"/>'
    '</svg>'
)


import re as _re


def _linkify_urls(text: str) -> str:
    """Transforme les URLs brutes en liens cliquables dans le footer."""
    return _re.sub(
        r'(https?://\S+|(?<!\w)([a-zA-Z0-9-]+\.)+[a-z]{2,}(?:/\S*)?)',
        lambda m: f'<a href="{m.group(0) if m.group(0).startswith("http") else "https://" + m.group(0)}" '
                  f'style="color:#1E3A5F;text-decoration:underline">{m.group(0)}</a>',
        text,
    )


def _html_echappe(texte: str) -> str:
    """Un nom de fichier est une donnée : il ne doit pas pouvoir injecter de balise.

    Les noms produits par `nom_stocke` sont déjà réduits à `[A-Za-z0-9_.-]`, mais
    les fichiers antérieurs à ce nommage n'ont pas eu ce traitement. On ne fait
    donc pas confiance à la provenance — cf. `standards/03-securite.md` §4.
    """
    return (
        (texte or "")
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _preparer_pieces_jointes(paths: list[str]) -> tuple[list[dict], list[str]]:
    """(pièces jointes prêtes pour le message, chemins temporaires à nettoyer).

    Deux renommages techniques faisaient perdre le nom d'origine dans la
    messagerie du destinataire :
      - le préfixe UUID de `nom_stocke` → « 0d41107a6c…lasseurs.pdf » ;
      - `_fix_image_orientations`, qui écrit un fichier `exif_XXXX.jpg`.

    Le nom affiché est donc calculé sur le chemin **d'origine**, avant toute
    correction, et transmis explicitement en `Content-Disposition`.

    Écrit une fois : `send_email` et `send_email_group` faisaient déjà le même
    `_fix_image_orientations` suivi du même nettoyage, chacun de son côté.
    """
    corriges = _fix_image_orientations(paths)
    prets: list[dict] = []
    for origine, chemin in zip(paths, corriges):
        # Le nom vient de `nom_stocke`, donc déjà réduit à [A-Za-z0-9_.-] ; on
        # neutralise malgré tout guillemets et sauts de ligne, qui casseraient
        # l'en-tête pour les fichiers plus anciens, aux noms non assainis.
        affiche = _re.sub(r'["\r\n]', "_", nom_lisible(origine))
        prets.append({
            "file": chemin,
            "headers": {"Content-Disposition": f'attachment; filename="{affiche}"'},
        })
    temporaires = [c for c in corriges if c not in paths]
    return prets, temporaires


def _bandeau_pieces_jointes(noms: list[str]) -> str:
    """Sommaire des pièces jointes, en pied de contenu : décompte puis liste nommée.

    Écrite **ici** et pas dans les modèles, pour trois raisons :

    1. Les modèles vivent en **base** (`modele_email`) et `seed()` ne les met à jour
       que s'ils n'existent pas encore : modifier `seed.EMAIL_TEMPLATES` n'a aucun
       effet sur une installation en service. Ce qui est écrit dans le code, si.
    2. Le nombre vient de la liste **réellement transmise** au constructeur du
       message, pas d'un drapeau de contexte. Un drapeau peut mentir — deux le
       faisaient encore le 03/08/2026, l'un annonçant des pièces jointes sans en
       attacher, l'autre l'inverse. Ici, la mention et la pièce jointe ont la même
       source : elles ne peuvent pas diverger.
    3. Un seul endroit couvre les six modèles susceptibles de porter des pièces
       jointes, et tous ceux à venir.

    La liste nommée n'est pas un doublon de ce que montre la messagerie : c'est le
    **repli**. Le nom d'origine est déjà rétabli dans l'en-tête
    `Content-Disposition` (cf. `_preparer_pieces_jointes`), mais un client ou une
    passerelle peut l'ignorer, tronquer, ou retirer la pièce jointe sans le dire.
    Écrit dans le corps du message, le sommaire survit à tout cela — et il permet
    au destinataire de constater qu'il manque quelque chose.

    ⚠️ `ticket_syndic` et `publication_syndic` portent en base une mention
    « Pièces jointes disponibles ci-dessous », **conservée volontairement**
    (décision du 03/08/2026). Ce n'est pas un doublon : elle est imbriquée dans
    `{% if is_commentaire %}` et rendue *à l'intérieur du cadre du commentaire*,
    donc elle dit **à quoi** les pièces jointes se rattachent — ce commentaire-ci,
    pas l'historique. Le sommaire, lui, dit combien et lesquelles. Sur un ticket
    à dix messages, les deux informations sont utiles.
    Elle ne s'affiche jamais à la création (`is_commentaire` faux).

    Les noms viennent de `nom_lisible`, comme l'en-tête : une seule règle, donc
    aucune divergence possible entre ce qui est annoncé et ce qui est joint.
    """
    if not noms:
        return ""
    #  « 1 photo » plutôt que « 1 pièce jointe » quand l'extension permet de le
    #  dire : le décompte seul oblige le destinataire à ouvrir pour savoir de quoi
    #  il s'agit. Repli sur le libellé générique si aucune extension n'est
    #  exploitable — mieux vaut vague qu'inexact.
    libelle = libelle_pieces_jointes(noms) or (
        "1 pièce jointe" if len(noms) == 1 else f"{len(noms)} pièces jointes"
    )
    lignes = "".join(
        f'<tr><td style="padding:2px 0;font-size:13px;color:#1A1A2E">'
        f'<span style="color:#8A8FA0">{i}.</span>&nbsp;{_html_echappe(nom)}</td></tr>'
        for i, nom in enumerate(noms, start=1)
    )
    return (
        '<tr><td style="background-color:#FFFFFF;padding:0 32px 20px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-top:1px solid #E4E7EC">'
        '<tr><td style="padding-top:14px;font-size:13px;color:#5A6070">'
        f'\U0001F4CE Ce message comporte <strong>{libelle}</strong> :'
        '</td></tr>'
        f'<tr><td style="padding-top:6px"><table role="presentation" cellpadding="0" '
        f'cellspacing="0">{lignes}</table></td></tr>'
        '<tr><td style="padding-top:8px;font-size:12px;color:#8A8FA0">'
        "Si l'une d'elles n'apparaît pas, votre messagerie a pu la filtrer."
        '</td></tr>'
        '</table></td></tr>'
    )


def _wrap_email(
    body_html: str, site_nom: str, site_url: str, footer: str, annee: int,
    pieces_jointes: list[str] | None = None, intention: str | None = None,
) -> str:
    """Encapsule le contenu HTML dans un gabarit email aux couleurs du site."""
    bandeau_pj = _bandeau_pieces_jointes(pieces_jointes or [])
    bandeau_intention = _bandeau_intention(intention)
    safe_footer = ""
    if footer:
        linked_footer = _linkify_urls(footer)
        safe_footer = (
            f'<tr><td style="background-color:#FAFAF7;padding:20px 32px 24px;text-align:center">'
            f'<p style="margin:0;font-size:13px;color:#5A6070">{linked_footer}</p>'
            f'</td></tr>'
        )
    return f'''<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{site_nom}</title></head>
<body style="margin:0;padding:0;background-color:#F2EFE9;font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Roboto,'Helvetica Neue',Arial,sans-serif;color:#1A1A2E;-webkit-text-size-adjust:100%">

<!-- Wrapper -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F2EFE9;padding:24px 0">
<tr><td align="center">

<!-- Container -->
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(30,58,95,0.12)">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#1E3A5F 0%,#16304F 100%);padding:28px 32px;text-align:center">
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto"><tr>
      <td style="vertical-align:middle;padding-right:14px">{_LOGO_SVG}</td>
      <td style="vertical-align:middle;text-align:left">
        <div style="font-family:Georgia,'Palatino Linotype','Book Antiqua',Palatino,serif;font-size:22px;font-weight:700;color:#FFFFFF;letter-spacing:0.3px">{site_nom}</div>
        <div style="font-size:12px;color:#C9983A;letter-spacing:1.5px;text-transform:uppercase;margin-top:2px;font-weight:600">Espace numérique de résidence</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Accent bar -->
  <tr><td style="height:4px;background:linear-gradient(90deg,#C9983A 0%,#1E3A5F 50%,#3D6B4F 100%)"></td></tr>

  <!-- Body -->
  <tr><td style="background-color:#FFFFFF;padding:32px 32px 24px;font-size:15px;line-height:1.65;color:#1A1A2E">
    {bandeau_intention}{body_html}
  </td></tr>

  <!-- Pièces jointes -->
  {bandeau_pj}

  <!-- Notification preferences -->
  <tr><td style="background-color:#FFFFFF;padding:0 32px 20px;text-align:center">
    <p style="margin:0;font-size:12px;color:#8A8FA0">Pour g\u00e9rer vos pr\u00e9f\u00e9rences de notification, rendez-vous dans votre <a href="{site_url.rstrip('/')}/profil" style="color:#1E3A5F;text-decoration:underline">profil</a>.</p>
  </td></tr>

  <!-- Footer -->
  {safe_footer}

</table>
<!-- /Container -->

</td></tr>
</table>
<!-- /Wrapper -->
</body>
</html>'''


def _fix_image_orientations(paths: list[str]) -> list[str]:
    """Applique la rotation EXIF sur les images JPEG et retourne les chemins corrigés."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return paths

    fixed: list[str] = []
    for path in paths:
        ext = os.path.splitext(path)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
            fixed.append(path)
            continue
        try:
            with Image.open(path) as img:
                corrected = ImageOps.exif_transpose(img)
                if corrected is img:
                    # Pas de correction nécessaire
                    fixed.append(path)
                    continue
                tmp = tempfile.NamedTemporaryFile(
                    suffix=ext, prefix="exif_", dir=os.path.dirname(path), delete=False,
                )
                corrected.save(tmp.name, quality=92)
                tmp.close()
                fixed.append(tmp.name)
        except Exception:
            fixed.append(path)
    return fixed


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
        pref_key = _EMAIL_PREF_MAP.get(code)
        if pref_key and destinataire_id:
            user = session.get(Utilisateur, destinataire_id)
            if user:
                try:
                    prefs = json.loads(user.preferences_notifications or "{}")
                except (json.JSONDecodeError, TypeError):
                    prefs = {}
                if not prefs.get(pref_key, True):
                    logger.debug("Email [%s] non envoyé → préférence %s=false pour user %s", code, pref_key, destinataire_id)
                    _log_email(session, code, to, "ignore", erreur=f"préférence {pref_key}=false")
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

        # ── Footer email (similaire au footer WhatsApp) ──────────────────
        email_footer_row = session.get(ConfigSite, "email_footer")
        email_footer = (email_footer_row.valeur if email_footer_row else "").strip()

        # Variables communes
        site_nom_row = session.get(ConfigSite, "site_nom")
        site_url_row = session.get(ConfigSite, "site_url")
        base_ctx = {
            "annee": datetime.utcnow().year,
            "app": {"url": (site_url_row.valeur if site_url_row else "https://localhost").rstrip("/")},
            "residence": {"nom": (site_nom_row.valeur if site_nom_row else "Ma Résidence")},
        }
        ctx = {**base_ctx, **context}

        try:
            from fastapi_mail import FastMail, MessageSchema

            cfg = connexion_smtp(smtp_cfg)
            fm = FastMail(cfg)
            rendered_body = _render(template.corps_html, ctx)
            site_nom = site_nom_row.valeur if site_nom_row else "Ma Résidence"
            site_url = site_url_row.valeur if site_url_row else "https://localhost"
            full_html = _wrap_email(
                rendered_body,
                site_nom=site_nom,
                site_url=site_url,
                footer=email_footer,
                annee=ctx["annee"],
                pieces_jointes=[nom_lisible(p) for p in (attachments or [])],
                intention=template.intention,
            )
            rendered_subject = _render(template.sujet, ctx)
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


def _check_pref(code: str, user_id: int | None, session: Session) -> bool:
    """Retourne False si l'utilisateur a désactivé la préférence pour ce code email."""
    pref_key = _EMAIL_PREF_MAP.get(code)
    if not pref_key or not user_id:
        return True
    user = session.get(Utilisateur, user_id)
    if not user:
        return True
    try:
        prefs = json.loads(user.preferences_notifications or "{}")
    except (json.JSONDecodeError, TypeError):
        prefs = {}
    return prefs.get(pref_key, True)


async def send_email_group(
    code: str,
    to_recipients: list[tuple[int | None, str]],
    context: dict[str, Any],
    session: Session | None = None,
    *,
    cc_recipients: list[tuple[int | None, str]] | None = None,
    bcc: list[str] | None = None,
    attachments: list[str] | None = None,
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
            if _check_pref(code, uid, session)
        ]
        filtered_cc = [
            (uid, email) for uid, email in (cc_recipients or [])
            if _check_pref(code, uid, session)
        ]

        if not filtered_to and not filtered_cc:
            return

        to_emails = [email for _, email in filtered_to]
        cc_emails = [email for _, email in filtered_cc]
        all_emails_str = ", ".join(to_emails + cc_emails)

        # Contexte
        email_footer_row = session.get(ConfigSite, "email_footer")
        email_footer = (email_footer_row.valeur if email_footer_row else "").strip()
        site_nom_row = session.get(ConfigSite, "site_nom")
        site_url_row = session.get(ConfigSite, "site_url")
        base_ctx = {
            "annee": datetime.utcnow().year,
            "app": {"url": (site_url_row.valeur if site_url_row else "https://localhost").rstrip("/")},
            "residence": {"nom": (site_nom_row.valeur if site_nom_row else "Ma Résidence")},
        }
        ctx = {**base_ctx, **context}

        try:
            from fastapi_mail import FastMail, MessageSchema

            cfg = connexion_smtp(smtp_cfg)
            fm = FastMail(cfg)
            site_nom = site_nom_row.valeur if site_nom_row else "Ma Résidence"
            site_url = site_url_row.valeur if site_url_row else "https://localhost"
            rendered_body = _render(template.corps_html, ctx)
            full_html = _wrap_email(
                rendered_body,
                site_nom=site_nom,
                site_url=site_url,
                footer=email_footer,
                annee=ctx["annee"],
                pieces_jointes=[nom_lisible(p) for p in (attachments or [])],
                intention=template.intention,
            )
            rendered_subject = _render(template.sujet, ctx)
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
