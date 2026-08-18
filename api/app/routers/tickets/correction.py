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
from app.utils.photos import photos_internes


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


def _appliquer_contenu(body: TicketUpdate, ticket: Ticket) -> list[str]:
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
    if body.categorie is not None and body.categorie != ticket.categorie:
        changes.append(f"Catégorie : {ticket.categorie} → {body.categorie}")
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
        ticket.fichiers_urls = json.dumps(retenus, ensure_ascii=False)
    #  Les PHOTOS se corrigent comme les documents depuis le 18/08/2026 : la
    #  dette `api` que la déclaration citait (#431) est soldée. Deux sections
    #  distinctes à l'écran, deux colonnes distinctes ici — elles ne fusionnent
    #  nulle part.
    if body.photos_urls is not None:
        retenues = photos_internes(body.photos_urls)
        if retenues != _liste_json(ticket.photos_urls):
            changes.append("Photos modifiées")
        ticket.photos_urls = json.dumps(retenues, ensure_ascii=False)
    return changes


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
    #  Présence et non non-nullité : c'est ce qui permet d'EFFACER (voir
    #  `_envoye`). Les trois champs voyagent ensemble — revenir à « En mon nom »
    #  doit les vider tous les trois, sinon un nom d'ancien destinataire
    #  survivrait à un résident inscrit désigné depuis.
    if any(_envoye(body, c) for c in ('saisi_pour_user_id', 'saisi_pour_nom', 'saisi_pour_email')):
        #  🔴 La PRÉSENCE décide d'ÉCRIRE, la COMPARAISON décide d'ANNONCER
        #  (18/08/2026). Les deux étaient confondues : le formulaire envoyant
        #  toujours les trois champs — c'est ce qui permet de revenir à « En mon
        #  nom » —, « Saisi pour modifié » apparaissait à chaque enregistrement,
        #  même quand personne n'y avait touché.
        avant = (ticket.saisi_pour_user_id, ticket.saisi_pour_nom, ticket.saisi_pour_email)
        apres = (body.saisi_pour_user_id, body.saisi_pour_nom, body.saisi_pour_email)
        ticket.saisi_pour_user_id, ticket.saisi_pour_nom, ticket.saisi_pour_email = apres
        if avant != apres:
            changes.append("Saisi pour modifié")
    if body.non_relancable is not None:
        ticket.non_relancable = body.non_relancable
    if body.non_relancable_motif is not None:
        ticket.non_relancable_motif = body.non_relancable_motif
    return changes
