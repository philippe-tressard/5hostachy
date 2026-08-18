"""Calendrier — ce qu'un événement ENVOIE : WhatsApp, syndic, conseil syndical.

Extrait de `calendrier.py` le 18/08/2026, parce qu'une **entrée d'Historique doit
pouvoir notifier elle aussi** — signalé à l'écran : *« il manque en mode suivi la
section Diffusion »*. Le bloc faisait 80 lignes au milieu de `create_evenement` ;
le recopier dans l'endpoint des évolutions aurait produit deux envois libres de
diverger au premier template modifié, et c'est exactement le défaut que
`test_email_contexte_appel` traque depuis trois récidives.

⚠️ **Le contexte du template est la partie fragile.** Il attend `evenement`, et
non `ticket` : cette clé avait été reprise du courriel de ticket sans être
renommée, d'où un `'evenement' is undefined` à chaque envoi — six membres du CS
n'ont rien reçu le 28/07/2026, sans autre trace que `historique_email`, l'envoi
étant en tâche de fond. Toucher à ce dictionnaire sans vérifier le template, c'est
rouvrir cette panne.
"""
from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.models.core import Evenement, MembreSyndic, Utilisateur
from app.utils.dates_fr import datetime_longue
from app.utils.fichiers import chemins_locaux
from app.utils.photos import parse_photos
from app.utils.whatsapp import config_whatsapp, envoyer_whatsapp_avec_log, whatsapp_actif


def notifier_canaux(
    ev: Evenement,
    user: Utilisateur,
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    whatsapp: bool = False,
    syndic: bool = False,
    cs: bool = False,
    suivi: dict | None = None,
) -> None:
    """Prévient les canaux demandés — et eux seuls.

    Appelée à la création d'un événement et à l'ajout d'une entrée dans son
    Historique. Les trois drapeaux sont **une intention explicite** : rien ne part
    si l'appelant ne le demande pas.
    """
    if not (whatsapp or syndic or cs):
        return

    #  ⚠️ Le code du modèle se calcule ICI, en ternaire de deux littéraux, et
    #  n'est PAS un paramètre. `test_email_contexte_appel` lit l'arbre syntaxique
    #  pour vérifier que le contexte fournit ce que le template cite ; un code
    #  reçu en argument lui est opaque, et l'envoi sort du garde-fou. Il l'a
    #  refusé — à raison : c'est ainsi que trois `'X' is undefined` sont partis
    #  en production sans autre trace que `historique_email`.
    #  Écrit en ternaire, les DEUX modèles sont vérifiés contre ce même contexte.
    code = "calendrier_evenement_suivi" if suivi else "calendrier_evenement_cree"
    cfg_map = config_whatsapp(session, "reference_copro", "site_nom")

    if whatsapp:
        if whatsapp_actif(cfg_map):
            background_tasks.add_task(
                envoyer_whatsapp_avec_log,
                f"📅 {ev.titre}", ev.description or "", False, None, None, cfg_map,
            )

    if syndic or cs:
        from app.utils.email import send_email_group

        # Photos et documents de l'affaire, résolus en chemins locaux comme
        # pour les tickets et les actualités.
        pieces_jointes = chemins_locaux(
            parse_photos(ev.photos_urls) + parse_photos(ev.fichiers_urls)
        )

        destinataires: list[tuple[int | None, str]] = []
        seen_emails: set[str] = set()

        if syndic:
            syndic_principal = session.exec(
                select(MembreSyndic).where(MembreSyndic.est_principal == True)
            ).first()
            if syndic_principal and syndic_principal.email:
                destinataires.append((syndic_principal.user_id, syndic_principal.email))
                seen_emails.add(syndic_principal.email.lower())

        if cs:
            cs_users = session.exec(
                select(Utilisateur.id, Utilisateur.email)
                .where(
                    Utilisateur.actif == True,
                    Utilisateur.email.isnot(None),
                    Utilisateur.roles_json.contains("conseil_syndical"),
                )
            ).all()
            for uid, email in cs_users:
                if email and email.lower() not in seen_emails:
                    destinataires.append((uid, email))
                    seen_emails.add(email.lower())

        # Le template `calendrier_evenement_cree` attend `evenement`, pas
        # `ticket` : ce contexte avait été repris du mail de ticket sans
        # renommer la clé, d'où un `'evenement' is undefined` à chaque envoi
        # — six membres du CS n'ont rien reçu le 28/07/2026, sans aucune
        # trace ailleurs que dans `historique_email` (l'envoi est en
        # BackgroundTask). Même cause racine que `reinitialisation_mdp`
        # (03/06) et `ticket_statut_change` (15/06).
        ctx = {
            "evenement": {
                "id": ev.id,
                "titre": ev.titre,
                # `datetime_longue` et NON `datetime_longue_paris` : à la
                # différence des `cree_le` de la base, `debut` est l'heure de
                # tenue telle qu'elle a été saisie (le front envoie
                # `2026-08-05T14:00`, sans fuseau). La convertir depuis UTC
                # annoncerait 16:00 pour un événement à 14:00.
                "date": datetime_longue(ev.debut) if ev.debut else "",
                "description": ev.description or "",
                "type": ev.type.value if ev.type else "",
            },
            "auteur": {"prenom": user.prenom, "nom": user.nom},
            "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
            "app": {"url": cfg_map.get("site_url", "https://localhost")},
            "reference_copro": cfg_map.get("reference_copro", ""),
            # Calculé sur la liste réellement attachée, jamais sur l'intention :
            # ce que l'e-mail annonce doit être ce qu'il transporte.
            "fichiers": bool(pieces_jointes),
            #  ⚠️ TOUJOURS présent, même vide, et écrit DANS le littéral : le
            #  template du suivi cite `suivi.etat` et `suivi.commentaire`, et une
            #  clé absente est très exactement la panne `'evenement' is undefined`
            #  du 28/07/2026. Un `ctx.update()` aurait fait la même chose à
            #  l'exécution — mais `test_email_contexte_appel` lit l'arbre
            #  syntaxique, et un dictionnaire construit après coup lui échappe.
            #  Il l'a refusé, à raison : un envoi hors garde-fou échoue en silence.
            "suivi": suivi or {"commentaire": "", "etat": ""},
        }
        if destinataires:
            background_tasks.add_task(
                send_email_group, code=code,
                to_recipients=destinataires, context=ctx,
                session=session,
                # Cet envoi ne transportait AUCUNE pièce jointe : une affaire
                # créée avec son devis notifiait le syndic sans le devis.
                attachments=pieces_jointes or None,
            )
