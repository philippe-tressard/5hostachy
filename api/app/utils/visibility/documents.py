"""Accès aux documents — l'algorithme en cinq étapes.

⚠️ Fragment de `app/utils/visibility/` — **la règle reste unique**, elle a seulement
cessé de tenir dans un seul fichier (#547, 20/08/2026). Le paquet expose la même
surface qu'avant : `from app.utils.visibility import …` ne change pas d'une ligne
pour ses seize importateurs.

Le découpage suit une couture réelle, pas la ligne où le compteur a dépassé :
`socle` porte les deux primitives que tout le reste compose (géographie et public
visé), `objets` les règles par entité, `documents` l'algorithme d'accès en cinq
étapes — le seul qui interroge la base, et le seul adossé à un modèle de profil
d'accès.
"""
from __future__ import annotations

import json

from app.models.core import (
    Document,
    ProfilAccesDocument,
    Publication,
    RoleUtilisateur,
    Ticket,
    Utilisateur,
)
from app.models.evenement import Evenement

from .objets import evenement_visible, publication_visible, ticket_visible

# ── Règles document ───────────────────────────────────────────────────────────

def document_visible(user: Utilisateur, doc: Document, session) -> bool:
    """Retourne True si l'utilisateur a le droit de lire ce document.

    Algorithme d'accès en 5 étapes (specs modele-donnees.md). Un document tire sa
    protection soit de l'objet qui le porte (contrat, actualité), soit de son profil
    d'accès de catégorie — jamais des deux, jamais d'aucun.

    Cette règle vivait dans `routers/documents.py`, et `flux.py` l'importait depuis
    ce router. Une règle de sécurité hors du module central, c'est une règle qu'un
    durcissement ultérieur peut manquer : c'est exactement ce qui est arrivé aux
    pièces jointes d'actualité, autorisées sans consulter l'actualité porteuse
    (cf. `tests/test_documents_acces.py`). Elle est ici, avec les autres.

    `session` n'est typé que par usage (`.get`) pour ne pas faire dépendre ce module
    de SQLModel : seuls `Publication` et `ProfilAccesDocument` sont chargés.
    """
    # Admin et CS voient tout
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True

    # Documents liés à un contrat (sans catégorie) : CS/admin uniquement
    if doc.contrat_id and not doc.categorie_id:
        return False

    # Pièce jointe d'actualité : elle suit EXACTEMENT la visibilité de son actualité.
    # Un document n'a pas de ciblage propre (ni `public_cible`, ni `perimetre_cible`) ;
    # sa seule protection légitime est celle de la publication qui le porte.
    if doc.publication_id and not doc.categorie_id:
        pub = session.get(Publication, doc.publication_id)
        # Publication introuvable → on refuse : aucune règle à appliquer.
        # Brouillon → rien n'est publié, la pièce jointe non plus (CS/admin sont
        # déjà sortis plus haut et gardent l'accès à leurs brouillons).
        if not pub or pub.brouillon:
            return False
        return publication_visible(pub, user)

    #  Pièce jointe de TICKET ou d'ÉVÉNEMENT (#390) : même règle, même raison.
    #
    #  🔴 « Qui voit le porteur », et rien d'autre — décision prise le 27/08/2026.
    #  Le régime actuel de ces fichiers est celui de l'objet qui les porte ; leur
    #  donner au passage le contrôle à trois couches des documents casserait des
    #  accès qui marchent aujourd'hui, sans que personne soit prévenu. Le gain de
    #  #390 est de fermer l'URL BRUTE, pas de changer qui voit quoi.
    #
    #  ⚠️ Porteur introuvable → on REFUSE. Une pièce jointe dont le ticket a été
    #  supprimé n'a plus de règle à appliquer, et « aucune règle » n'est jamais une
    #  autorisation (`standards/04` — un contrôle qui ne peut pas s'exécuter ne
    #  rend pas OK). C'est la même branche que pour la publication ci-dessus.
    if doc.ticket_id and not doc.categorie_id:
        ticket = session.get(Ticket, doc.ticket_id)
        if not ticket:
            return False
        return ticket_visible(ticket, user)

    if doc.evenement_id and not doc.categorie_id:
        ev = session.get(Evenement, doc.evenement_id)
        if not ev:
            return False
        return evenement_visible(ev, user)

    #  🔴 UN DOCUMENT SANS SOURCE DE PROTECTION NE SE LIT PAS.
    #
    #  Cette ligne s'écrivait `doc.profil_acces_override_id or doc.categorie.profil_acces_id`,
    #  et déréférençait `doc.categorie` sans le tester. Un document sans catégorie
    #  NI contrat NI publication y arrive — les trois branches précédentes l'ont
    #  laissé passer — et `None.profil_acces_id` lève un `AttributeError`, donc un
    #  **500 sur la liste des documents** pour tout utilisateur non CS/admin.
    #
    #  ⚠️ Le cas est INATTEIGNABLE aujourd'hui : `POST /documents` exige l'un des
    #  trois, `PATCH` ne peut pas les vider, et aucun endpoint ne supprime une
    #  catégorie. C'est un invariant tenu à UN endroit (la création) et SUPPOSÉ à
    #  un autre (ici), sans rien qui relie les deux — la forme d'invariant qui se
    #  brise au premier appelant nouveau.
    #
    #  Et cet appelant est déjà écrit : l'étape 1 de #390 crée justement une ligne
    #  `Document` « sans publication_id, rattachée ensuite ». Elle aurait donc
    #  produit exactement ce document-là, et le 500 avec.
    #
    #  Le repli est le REFUS, jamais l'autorisation : une pièce jointe dont on ne
    #  sait pas de qui elle tire sa protection n'en a aucune (`standards/03` — en
    #  cas de doute sur un droit, on refuse).
    profil_id = doc.profil_acces_override_id or (
        doc.categorie.profil_acces_id if doc.categorie else None
    )
    if not profil_id:
        return False
    profil: ProfilAccesDocument = session.get(ProfilAccesDocument, profil_id)
    if not profil:
        return False

    # Vérifier le rôle (supporte valeurs de rôles ET de statuts pour compatibilité)
    roles_autorises = json.loads(profil.roles_autorises)
    user_idents = set(user.roles) | {user.statut.value}
    if not any(r in roles_autorises for r in user_idents):
        return False

    # Vérifier le périmètre
    if doc.perimetre == "bâtiment" and doc.batiment_id:
        user_batiments = {
            ul.lot.batiment_id for ul in user.user_lots if ul.actif and ul.lot
        }
        if doc.batiment_id not in user_batiments:
            return False

    if doc.perimetre == "lot" and doc.lot_id:
        user_lots = {ul.lot_id for ul in user.user_lots if ul.actif}
        if doc.lot_id not in user_lots:
            return False

    return True
