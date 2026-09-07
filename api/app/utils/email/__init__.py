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
from app.seed.emails import expediteur_du_modele
from app.utils.smtp import (  # noqa: F401  (ré-export : config.py l'importe d'ici)
    _get_smtp_config,
    adresse_expedition,
    connexion_smtp,
)

from .gabarit import INTENTIONS, _wrap_email  # noqa: F401  (ré-export : admin/communications l'importe d'ici)
from .pieces_jointes import _preparer_pieces_jointes

import re as _re

settings = get_settings()

logger = logging.getLogger("email")


def _masquer(adresse: str | None) -> str:
    """`p***@domaine.fr` — assez pour diagnostiquer, pas assez pour ficher.

    🔴 Les journaux portaient l'adresse ENTIÈRE (#777). Ces lignes partent dans
    les alertes du monitoring et dans les rapports qu'on recopie ailleurs : c'est
    par là qu'une adresse de résident sort. Le premier caractère et le domaine
    suffisent à reconnaître un destinataire quand on cherche pourquoi un envoi a
    échoué.

    ⚠️ L'historique en base garde l'adresse entière : il répond à « qui n'a pas
    reçu quoi ? », derrière une session admin.
    """
    if not adresse:
        return "(vide)"
    tete, _, domaine = adresse.partition("@")
    if not domaine:
        return "***"
    return f"{tete[:1]}***@{domaine}"


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
    return f"🏢 {ref} — " if ref else ""


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


def _reply_to(smtp_cfg: dict, jeton_reponse: str | None) -> dict[str, str]:
    """L'en-tete `Reply-To` d'un envoi lié à un ticket (#703).

    Écrit ICI et nulle part ailleurs : `send_email` et `send_email_group`
    partent tous deux vers le syndic sur un ticket, et deux constructions de la
    même adresse divergeraient au premier changement de domaine.

    Rend un dictionnaire vide quand il n'y a pas de jeton ou pas de domaine
    exploitable : mieux vaut aucune adresse de réponse qu'une adresse fabriquée
    sur un domaine inventé, dont les réponses partiraient dans le vide sans que
    personne ne le sache.
    """
    if not jeton_reponse:
        return {}
    from app.utils.courriel_entrant import adresse_de_reponse, domaine_de

    domaine = domaine_de(smtp_cfg.get("smtp_from") or get_settings().mail_from)
    if not domaine:
        return {}
    return {"Reply-To": adresse_de_reponse(jeton_reponse, domaine)}


async def _envoyer_modele(
    code: str,
    context: dict[str, Any],
    session: Session,
    *,
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[str] | None = None,
    jeton_reponse: str | None = None,
) -> None:
    """Le tronc commun des deux envois : modèle, rendu, SMTP, journal, nettoyage.

    🔴 `send_email` (103 l.) et `send_email_group` (112 l.) étaient identiques à
    **68 %** — mesuré. Deux écritures d'une même séquence, donc deux occasions de
    diverger, et elles avaient déjà divergé : le chemin groupé ne journalisait
    pas le cas « modèle inactif », abandonnant l'envoi sans laisser de trace.

    Ne reste chez les appelants que ce qui les distingue vraiment : la
    vérification des **préférences** et la résolution des destinataires.

    ⚠️ La session n'est ni ouverte ni fermée ici — elle appartient à l'appelant,
    seul à savoir s'il l'a créée.
    """
    trace = ", ".join(to + (cc or []))

    template: ModeleEmail | None = session.exec(
        select(ModeleEmail).where(ModeleEmail.code == code)
    ).first()
    if not template or not template.actif:
        #  JOURNALISE DANS LES DEUX CAS depuis la factorisation : le chemin
        #  groupe abandonnait en silence, et un envoi qui n'a pas eu lieu sans
        #  trace est indistinguable d'un envoi qui n'a jamais ete demande.
        _log_email(session, code, trace, "ignore", erreur="template inactive ou inexistante")
        return

    ctx, site_nom, site_url, email_footer = _contexte_rendu(session, context)
    smtp_cfg = _get_smtp_config(session)
    fixed_attachments: list[str] = []
    try:
        from fastapi_mail import FastMail, MessageSchema

        cfg = connexion_smtp(
            smtp_cfg,
            expediteur=adresse_expedition(
                smtp_cfg, expediteur_du_modele(code, jeton_reponse=jeton_reponse)
            ),
        )
        fm = FastMail(cfg)
        rendered_subject, full_html = composer_email(
            template, ctx, site_nom=site_nom, site_url=site_url,
            email_footer=email_footer, attachments=attachments,
        )
        msg_kwargs: dict[str, Any] = dict(
            subject=rendered_subject,
            #  Sans destinataire principal, les copies le deviennent : un
            #  message sans `recipients` ne part pas.
            recipients=to if to else (cc or []),
            body=full_html,
            subtype="html",
            headers=_reply_to(smtp_cfg, jeton_reponse) or None,
        )
        if to and cc:
            msg_kwargs["cc"] = cc
        if bcc:
            msg_kwargs["bcc"] = bcc
        if attachments:
            prets, fixed_attachments = _preparer_pieces_jointes(attachments)
            msg_kwargs["attachments"] = prets
        await fm.send_message(MessageSchema(**msg_kwargs))
        _log_email(session, code, trace, "succes", sujet=rendered_subject)
    except Exception as exc:
        #  L'ADRESSE EST MASQUEE (#777) : ces lignes partent dans les alertes du
        #  monitoring et dans les rapports qu'on recopie ailleurs. L'historique
        #  en base, lui, garde l'adresse entiere — il est derriere une session
        #  admin, et sert a repondre a « qui n'a pas recu quoi ? ».
        if len(to) + len(cc or []) > 1:
            logger.error(
                "Erreur envoi email groupe [%s] -> %d destinataire(s) : %s",
                code, len(to) + len(cc or []), exc,
            )
        else:
            logger.error("Erreur envoi email [%s] -> %s : %s", code, _masquer(trace), exc)
        _log_email(session, code, trace, "erreur", erreur=str(exc)[:500])
    finally:
        #  Les fichiers temporaires produits par la correction EXIF.
        for fp in fixed_attachments:
            if not attachments or fp not in attachments:
                try:
                    os.unlink(fp)
                except OSError:
                    pass


def _envoi_actif(session: Session) -> bool:
    """L'envoi est-il actif ? La configuration prime sur le réglage.

    Écrit une fois : `smtp_enabled` absent de la base signifie « pas encore
    configuré », et c'est alors `settings.mail_enabled` qui tranche — subtilité
    que les deux chemins portaient chacun de leur côté.
    """
    smtp_cfg = _get_smtp_config(session)
    if smtp_cfg.get("smtp_enabled") is not None:
        return smtp_cfg["smtp_enabled"] == "1"
    return bool(settings.mail_enabled)


def _session_ou_neuve(session: Session | None) -> tuple[Session, bool]:
    """La session de l'appelant, ou une neuve — et qui devra la fermer.

    Les tâches d'arrière-plan n'en ont pas : elles s'exécutent après la réponse.
    """
    if session is not None:
        return session, False
    from app.database import SessionLocal

    return SessionLocal(), True


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
    jeton_reponse: str | None = None,
):
    """Envoie le modèle `code` à UN destinataire, si ses préférences l'acceptent.

    Fail graceful : une erreur d'envoi est journalisée, jamais propagée — un
    ticket créé ne doit pas échouer parce que le SMTP est indisponible.

    Rendu, envoi et journal vivent dans `_envoyer_modele`, partagé avec l'envoi
    groupé : ne reste ici que **la préférence du destinataire**.
    """
    session, close_session = _session_ou_neuve(session)
    try:
        if destinataire_id:
            user = session.get(Utilisateur, destinataire_id)
            if user and not mail_autorise(user, batiments_concernes):
                logger.debug(
                    "Email [%s] non envoye -> preference de batiment, user %s",
                    code, destinataire_id,
                )
                _log_email(session, code, to, "ignore", erreur="preference de batiment")
                return

        if not _envoi_actif(session):
            return

        await _envoyer_modele(
            code, context, session,
            to=[to], cc=cc, bcc=bcc,
            attachments=attachments, jeton_reponse=jeton_reponse,
        )
    finally:
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
    jeton_reponse: str | None = None,
):
    """Envoie UN seul message à plusieurs destinataires (to + cc facultatif).

    Les préférences de chacun sont vérifiées **individuellement** — c'est la
    seule vraie différence avec l'envoi unitaire. Les destinataires se voient
    entre eux, et l'historique n'enregistre qu'une ligne pour tous.

    Le reste vient de `_envoyer_modele`, partagé avec `send_email`.
    """
    session, close_session = _session_ou_neuve(session)
    try:
        if not _envoi_actif(session):
            return

        to_emails = [
            email for uid, email in to_recipients
            if _check_pref(uid, session, batiments_concernes)
        ]
        cc_emails = [
            email for uid, email in (cc_recipients or [])
            if _check_pref(uid, session, batiments_concernes)
        ]
        #  Personne ne veut de ce message : ce n'est pas un echec, c'est la
        #  preference de chacun qui a ete respectee.
        if not to_emails and not cc_emails:
            return

        await _envoyer_modele(
            code, context, session,
            to=to_emails, cc=cc_emails, bcc=bcc,
            attachments=attachments, jeton_reponse=jeton_reponse,
        )
    finally:
        if close_session:
            session.close()
