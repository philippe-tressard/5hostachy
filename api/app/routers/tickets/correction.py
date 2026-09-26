"""Tickets — ce qu'une CORRECTION écrit, et ce qu'elle raconte.

Extrait de `crud.py` le 18/08/2026 : la réouverture des sections fermées
(photos, « Saisi pour », diffusion) l'a porté de 432 à 507 lignes, et le
garde-fou de modularité a refusé le lot. Il a fonctionné comme prévu — on
découpe le fichier quand on y touche (`standards/02` §6).

La frontière retenue est la même que partout ailleurs dans ce paquet : **la
décision d'un côté, le cycle de vie de l'autre**. Ces trois fonctions ne
connaissent ni la session, ni les droits, ni les envois — elles répondent à une
seule question : *étant donné ce que le client a transmis, qu'est-ce qui change
sur ce ticket, et sous quel nom cela se lit-il dans l'Historique ?*

C'est ce qui les rend lisibles seules, et c'est ce qui permettra de les tester
sans monter une requête.
"""

import json

from app.models.core import Ticket
from app.schemas import TicketUpdate
from app.utils.categories_ticket import libelle_categorie
from app.utils.photos import photos_internes, photos_json
from app.utils.assiste_ia import marquer as marquer_assiste_ia
from app.utils.saisi_pour import corriger as corriger_saisi_pour


def _liste_json(brut: str | None) -> list:
    """Une colonne qui stocke un tableau JSON, lue comme liste. `[]` si vide ou illisible.

    ⚠️ Une colonne illisible rend `[]`, donc « différent de tout » : la correction
    sera annoncée, ce qui est le bon côté pour se tromper. L'inverse — avaler
    l'erreur et conclure « rien n'a changé » — écrirait la modification sans la
    tracer.
    """
    if not brut:
        return []
    try:
        valeur = json.loads(brut)
    except (TypeError, ValueError):
        return []
    return valeur if isinstance(valeur, list) else []


def _appliquer_contenu(body: TicketUpdate, ticket: Ticket, *, est_cs: bool = False) -> list[str]:
    """Champs de contenu, et la liste des changements qui alimentera l'historique.

    🔴 **CHAQUE champ est COMPARÉ à l'existant avant d'être annoncé** (18/08/2026,
    signalé à l'écran). Quatre d'entre eux ne l'étaient pas — description,
    périmètre, pièces jointes, photos : leur seule PRÉSENCE dans le `PATCH` suffisait
    à écrire « modifié ». Or le formulaire d'édition envoie les neuf sections à
    chaque enregistrement, par conception (c'est ce qui permet d'EFFACER un champ).
    Corriger le seul périmètre inscrivait donc :

        Correction : Description modifiée ; Périmètre modifié ;
                     Pièces jointes modifiées ; Photos modifiées ; Saisi pour modifié

    Cinq mentions dont **une** était vraie. Un Historique qui annonce des
    modifications qui n'ont pas eu lieu est pire qu'un Historique muet : il fait
    douter de ce qu'on lit, et il rend illisible la seule ligne qui comptait.

    ⚠️ Le titre et la catégorie, eux, étaient corrects depuis toujours — ils
    comparaient. C'est ce qui rendait le défaut discret : l'entrée n'était jamais
    entièrement fausse, seulement gonflée.
    """
    changes: list[str] = []
    if body.titre is not None and body.titre != ticket.titre:
        changes.append(f"Titre : {ticket.titre} → {body.titre}")
        ticket.titre = body.titre
    if body.description is not None and body.description != ticket.description:
        changes.append("Description modifiée")
        ticket.description = body.description
    #  La marque « assistant IA » ne s'écrit que dans un sens, et ne s'annonce
    #  pas : ce n'est pas une correction, c'est la provenance de celle-ci.
    marquer_assiste_ia(ticket, body)
    if body.categorie is not None and body.categorie != ticket.categorie:
        #  Les LIBELLÉS, pas les valeurs : l'historique se lit (#1350).
        changes.append(
            f"Catégorie : {libelle_categorie(ticket.categorie)} → {libelle_categorie(body.categorie)}"
        )
        ticket.categorie = body.categorie
    if body.perimetre_cible is not None:
        #  Comparaison sur des ENSEMBLES : le périmètre est une cible, pas une
        #  séquence. Deux mêmes codes dans un autre ordre désignent le même
        #  périmètre, et l'ordre dépend de celui des clics — l'annoncer comme une
        #  modification serait faux.
        if set(body.perimetre_cible) != set(_liste_json(ticket.perimetre_cible)):
            changes.append("Périmètre modifié")
        ticket.perimetre_cible = json.dumps(body.perimetre_cible)
    if body.fichiers_urls is not None:
        #  On compare ce qui sera RÉELLEMENT stocké : `photos_internes()` écarte
        #  les URLs externes. Comparer avant le filtre annoncerait une
        #  modification là où le serveur n'a rien retenu de neuf.
        #  ⚠️ Ici l'ordre COMPTE — les pièces jointes s'affichent dans l'ordre
        #  donné, et le réordonner est une modification visible.
        retenus = photos_internes(body.fichiers_urls)
        if retenus != _liste_json(ticket.fichiers_urls):
            changes.append("Pièces jointes modifiées")
        ticket.fichiers_urls = photos_json(retenus)
    #  Les PHOTOS se corrigent comme les documents depuis le 18/08/2026 : la
    #  dette `api` que la déclaration citait (#431) est soldée. Deux sections
    #  distinctes à l'écran, deux colonnes distinctes ici — elles ne fusionnent
    #  nulle part.
    if body.photos_urls is not None:
        retenues = photos_internes(body.photos_urls)
        if retenues != _liste_json(ticket.photos_urls):
            changes.append("Photos modifiées")
        ticket.photos_urls = photos_json(retenues)
    #  Ce que porte une actualité (#1091) : le public visé, l'Accès. Ils
    #  décident qui LIT — le conseil seul, comme à la création (`crud.py`) :
    #  pour un autre, ignorés comme les options (l'écran ne les lui propose
    #  pas), et non refusés — l'auteur d'une annonce d'arrivée corrige son texte.
    if (
        est_cs
        and _envoye(body, "public_cible")
        and (body.public_cible or None) != (_liste_json(ticket.public_cible) or None)
    ):
        changes.append("Public visé modifié")
        ticket.public_cible = json.dumps(body.public_cible) if body.public_cible else None
    if (
        est_cs
        and body.reserve_perimetre is not None
        and body.reserve_perimetre != ticket.reserve_perimetre
    ):
        changes.append("Accès modifié")
        ticket.reserve_perimetre = body.reserve_perimetre
    return changes


def _appliquer_quand(body: TicketUpdate, ticket: Ticket) -> list[str]:
    """La section « Quand » — PLANIFIÉE par le conseil syndical seul (23/09/2026).

    Ce n'est pas du contenu : l'auteur décrit sa demande, le conseil décide
    quand on intervient. Elle sort donc de `_appliquer_contenu`, et son droit
    est celui du suivi — le conseil la pose sur n'importe quelle affaire qu'il
    peut commenter ; l'appelant ne l'appelle pas pour un autre.

    Testée à la PRÉSENCE (`_envoye`) : effacer une date, c'est l'envoyer à `null`.
    """
    quand = [
        c for c in ("debut", "fin") if _envoye(body, c) and getattr(body, c) != getattr(ticket, c)
    ]
    for c in quand:
        setattr(ticket, c, getattr(body, c))
    return ["Quand modifié"] if quand else []


def _envoye(body: TicketUpdate, champ: str) -> bool:
    """Le client a-t-il ENVOYÉ ce champ, même à `null` ?

    `body.champ is not None` ne sait pas distinguer « champ absent » de « champ
    remis à vide » : c'est tout le motif de la dette `api` qui fermait « Saisi
    pour » à l'édition (#431). Pydantic, lui, le sait — `model_fields_set` ne
    contient que ce qui a été transmis. La section peut donc rouvrir : choisir
    « En mon nom » efface vraiment, au lieu de ne rien faire en silence.
    """
    return champ in body.model_fields_set


def _appliquer_relations(body: TicketUpdate, ticket: Ticket) -> list[str]:
    """Champs relationnels et destinataires — réservés au CS/admin."""
    changes: list[str] = []
    if body.lot_id is not None:
        ticket.lot_id = body.lot_id
        changes.append("Lot modifié")
    if body.batiment_id is not None:
        ticket.batiment_id = body.batiment_id
        changes.append("Bâtiment modifié")
    if body.destinataire_syndic is not None:
        ticket.destinataire_syndic = body.destinataire_syndic
    if body.destinataire_cs is not None:
        ticket.destinataire_cs = body.destinataire_cs
    #  La règle — présence pour écrire, comparaison pour annoncer — vit dans
    #  `utils/saisi_pour` depuis qu'elle sert AUSSI aux actualités et aux
    #  événements (15/09/2026). La garder ici en aurait fait la première de
    #  trois copies, et c'est la plus subtile des trois à maintenir.
    #
    #  ⚠️ `_envoye` reste chez l'appelant : lire `model_fields_set` dépend du
    #  schéma, pas de la notion.
    changes.extend(corriger_saisi_pour(ticket, body, _envoye))
    if body.non_relancable is not None:
        ticket.non_relancable = body.non_relancable
    if body.non_relancable_motif is not None:
        ticket.non_relancable_motif = body.non_relancable_motif
    #  L'archivage décidé par une personne (#1091) — un geste du conseil.
    if body.archive_manuel is not None and body.archive_manuel != ticket.archive_manuel:
        changes.append("Archivée" if body.archive_manuel else "Désarchivée")
        ticket.archive_manuel = body.archive_manuel
    return changes
