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
import json

from fastapi import BackgroundTasks
from sqlmodel import Session

from app.models.core import Evenement, Utilisateur
from app.utils.dates_fr import datetime_longue
from app.utils.fichiers import chemins_locaux
from app.utils.liens import lien_element
from app.utils.photos import parse_photos, premiere_photo
from app.utils.whatsapp import config_whatsapp, envoyer_whatsapp_avec_log, whatsapp_actif


def _json(urls: list[str] | str | None) -> str:
    """Une liste d'URLs sous la forme que `parse_photos` et `premiere_photo` lisent.

    Les deux attendent du JSON — la forme dans laquelle les colonnes le stockent.
    Les appelants, eux, ont tantôt la colonne (une chaîne), tantôt une liste déjà
    désérialisée. Convertir ici évite que chaque site d'appel choisisse la sienne.
    """
    if urls is None:
        return "[]"
    if isinstance(urls, str):
        return urls
    return json.dumps(urls, ensure_ascii=False)


def _lien_public(ev: Evenement, cfg_map: dict) -> str:
    """L'adresse publique de l'événement — vide si le site n'en déclare pas.

    ⚠️ `lien_element` donne le chemin (`/calendrier#ev-12`), jamais l'origine :
    c'est `site_url` qui la porte, et elle peut manquer en configuration. Un lien
    sans origine mènerait nulle part depuis WhatsApp — mieux vaut pas de lien du
    tout, et `_build_message` sait déjà n'en poser aucun.
    """
    base = (cfg_map.get("site_url") or "").strip().rstrip("/")
    return f"{base}{lien_element('ev', ev.id)}" if base else ""


def contexte_evenement_canaux(
    ev: Evenement,
    user: Utilisateur,
    session: Session,
    *,
    suivi: dict | None = None,
    fichiers_suivi: list[str] | None = None,
) -> tuple[dict, list[str], dict]:
    """Ce que l'envoi RACONTE — contexte du gabarit, pièces jointes, message WhatsApp.

    🔴 EXTRAIT DE `notifier_canaux` LE 31/08/2026, pour que l'aperçu puisse
    l'appeler au lieu de le recopier. Un aperçu recomposé devient faux à la
    première évolution d'un gabarit, sans que personne le voie — puisque c'est
    l'aperçu qu'on regarde pour vérifier.

    ## Une entrée d'Historique parle d'ELLE, pas de l'événement

    Le lot du 17/08 avait ouvert la section Diffusion du suivi mais laissé
    l'appel tel quel : le groupe WhatsApp recevait la description de
    l'événement à chaque commentaire — donc le MÊME message, indéfiniment, sans
    jamais le suivi.

    ⚠️ C'est le défaut typique de l'ajout d'un canal à une entité existante : on
    reprend l'appel qui marche, et l'appel qui marche parle de l'objet porteur.
    Rien ne lève — le message part, il est simplement faux.

    ## Ce que le triplet rend, et pourquoi il est rendu d'un bloc

    Le drapeau `fichiers` du gabarit se calcule **sur la liste** des pièces :
    les séparer permettrait d'annoncer des pièces jointes qui ne partent pas.
    Et le message WhatsApp dépend du même arbitrage suivi / création que le
    contexte — les rendre ensemble empêche les deux de diverger.

    ⚠️ Le `code` du modèle, LUI, reste chez l'appelant, en ternaire de deux
    littéraux : `test_email_contexte_appel` lit l'arbre syntaxique, et un code
    reçu en argument lui serait opaque. Le sortir d'ici est donc délibéré.
    """
    cfg_map = config_whatsapp(session, "reference_copro", "site_nom")

    if suivi:
        etat = (suivi.get("etat") or "").strip()
        commentaire = suivi.get("commentaire") or ""
        #  L'état, quand il y en a un, ouvre le message : c'est l'information
        #  qu'on lit en diagonale dans un groupe. Le commentaire suit.
        wa_titre = f"\U0001f504 {ev.titre}"
        wa_contenu = f"<b>{etat}</b><br>{commentaire}" if etat else commentaire
        #  Les photos du SUIVI d'abord ; à défaut, celles de l'événement — une
        #  entrée sans photo montre au moins de quoi on parle.
        wa_photos = parse_photos(_json(fichiers_suivi)) or parse_photos(ev.photos_urls)
    else:
        wa_titre = f"\U0001f4c5 {ev.titre}"
        wa_contenu = ev.description or ""
        wa_photos = parse_photos(ev.photos_urls)

    #  Les pièces attachées sont celles de CE QU'ON RACONTE : le suivi quand
    #  c'en est un, l'affaire entière à la création. Elles étaient toujours
    #  celles de l'affaire — une photo jointe à une entrée d'Historique
    #  n'atteignait donc jamais le syndic, alors que l'écran l'affichait.
    pieces_jointes = chemins_locaux(
        parse_photos(_json(fichiers_suivi))
        if suivi
        else parse_photos(ev.photos_urls) + parse_photos(ev.fichiers_urls)
    )

    # Le template `calendrier_evenement_cree` attend `evenement`, pas `ticket` :
    # ce contexte avait été repris du mail de ticket sans renommer la clé, d'où
    # un `'evenement' is undefined` à chaque envoi — six membres du CS n'ont rien
    # reçu le 28/07/2026, sans autre trace que `historique_email` (l'envoi est en
    # BackgroundTask). Même cause racine que `reinitialisation_mdp` (03/06) et
    # `ticket_statut_change` (15/06).
    ctx = {
        "evenement": {
            "id": ev.id,
            "titre": ev.titre,
            # `datetime_longue` et NON `datetime_longue_paris` : à la différence
            # des `cree_le` de la base, `debut` est l'heure de tenue telle qu'elle
            # a été saisie (le front envoie `2026-08-05T14:00`, sans fuseau). La
            # convertir depuis UTC annoncerait 16:00 pour un événement à 14:00.
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
        #  ⚠️ TOUJOURS présent, même vide, et écrit DANS le littéral : le template
        #  du suivi cite `suivi.etat` et `suivi.commentaire`, et une clé absente
        #  est très exactement la panne `'evenement' is undefined` du 28/07/2026.
        #  Un `ctx.update()` aurait fait la même chose à l'exécution — mais
        #  `test_email_contexte_appel` lit l'arbre syntaxique, et un dictionnaire
        #  construit après coup lui échappe. Il l'a refusé, à raison.
        "suivi": suivi or {"commentaire": "", "etat": ""},
    }
    whatsapp = {
        "titre": wa_titre,
        "contenu": wa_contenu,
        "photo": premiere_photo(_json(wa_photos)),
        "lien": _lien_public(ev, cfg_map),
        "cfg": cfg_map,
    }
    return ctx, pieces_jointes, whatsapp


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
    fichiers_suivi: list[str] | None = None,
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

    #  🔴 LA MÊME fonction que l'aperçu (#498). Ne pas remettre la construction
    #  ici : c'est ce qui a rendu l'aperçu impossible sur cet écran jusqu'au
    #  31/08/2026, où un envoi est parti sans que personne ait pu le voir.
    ctx, pieces_jointes, wa = contexte_evenement_canaux(
        ev, user, session, suivi=suivi, fichiers_suivi=fichiers_suivi
    )

    if whatsapp and whatsapp_actif(wa["cfg"]):
        #  ⚠️ `image_url` valait `None` EN DUR — les photos n'étaient pas refusées
        #  par le bridge, elles n'étaient jamais proposées. Les actualités y
        #  passent `premiere_photo(...)` depuis toujours.
        #
        #  Le LIEN, lui, est nouveau (18/08/2026) : le commentaire d'un suivi se
        #  lit hors de son contexte, et sans renvoi le lecteur du groupe n'a aucun
        #  moyen de savoir sur quoi il porte.
        background_tasks.add_task(
            envoyer_whatsapp_avec_log,
            wa["titre"], wa["contenu"], False, ev.perimetre,
            wa["photo"], wa["cfg"],
            lien=wa["lien"],
        )

    if syndic or cs:
        from app.utils.destinataires import destinataires_syndic_cs
        from app.utils.email import send_email_group

        destinataires = destinataires_syndic_cs(session, syndic=syndic, cs=cs)
        if destinataires:
            background_tasks.add_task(
                send_email_group, code=code,
                to_recipients=destinataires, context=ctx,
                session=session,
                # Cet envoi ne transportait AUCUNE pièce jointe : une affaire
                # créée avec son devis notifiait le syndic sans le devis.
                attachments=pieces_jointes or None,
            )
