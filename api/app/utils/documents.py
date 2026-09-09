"""Où vit un document — la seule réponse, pour tous ceux qui y renvoient.

## 🔴 Elle était donnée DEUX fois, et les deux ne disaient pas la même chose

Le fil d'actualité savait qu'un document n'est pas toujours affiché là où on
croit : une pièce jointe d'actualité s'ouvre sur **sa publication**, un document
de contrat vit dans la fiche de **son prestataire** — et seulement pour le conseil
et l'administration —, et un document dont la catégorie n'a pas de rubrique
dédiée n'est affiché **nulle part**, donc n'a pas de lien.

La notification et le courriel de publication, eux, écrivaient
`lien_element("doc", doc.id)` **sans condition** : /residence#doc-N, pour tout
document. Un document de contrat partait donc avec un lien vers une page où il
n'apparaît pas, et un résident qui cliquait arrivait sur une liste où rien ne
s'allumait.

C'est la version la plus disante qui est retenue (`standards/02` §4 bis) : celle
du fil, qui connaît les trois cas.

⚠️ La page était bonne, l'élément invisible — exactement le défaut du 28/07/2026
qui a fait naître `utils/liens`, un cran plus loin : là c'était l'onglet qui
manquait, ici c'est l'écran qui ne montre pas ce document-là.

## Pourquoi ici et pas dans `utils/liens`

`liens` ne connaît que des préfixes et des identifiants — aucun modèle, aucune
session. Il reste ainsi éprouvable seul, et `test_liens_front` peut confronter sa
table aux onglets du front. Cette fonction-ci a besoin du document, de la session
et de **qui regarde** : elle a sa propre place.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from app.models.core import ContratEntretien, Document, RoleUtilisateur, Utilisateur
from app.utils.liens import lien_element, page_element

#: Les catégories qui ont une rubrique à elles sur /residence. Un document d'une
#: autre catégorie n'y est pas listé : lui fabriquer un lien enverrait sur une
#: page où rien ne s'allume.
CATEGORIES_AVEC_LIEN = {
    "plan_residence",
    "reglement_copropriete",
    "pv_ag",
}


def lien_document(doc: Document, user: Utilisateur, session: Session) -> Optional[str]:
    """L'endroit exact où CE document est affiché pour CET utilisateur, ou None.

    L'ancre (`#doc-<id>`, `#pub-<id>`, `#presta-<id>`) compte autant que la page :
    /residence enchaîne plans, règlement, PV d'AG et diagnostics — y arriver sans
    viser le document oblige à le chercher dans la bonne section.

    ⚠️ Le résultat dépend de `user` : un document de contrat n'est visible que du
    conseil et de l'administration. Il se calcule donc PAR DESTINATAIRE, jamais
    une fois pour toute une liste d'envoi.
    """
    if doc.publication_id:
        # Pièce jointe d'une actualité : c'est la publication qu'on ouvre.
        return lien_element("pub", doc.publication_id)

    if doc.contrat_id:
        # Les documents de contrat ne sont visibles que dans /prestataires, page
        # réservée au CS et aux admins : pour les autres, pas de lien.
        if not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
            return None
        contrat = session.get(ContratEntretien, doc.contrat_id)
        # Les documents d'un contrat sont listés dans la fiche de son prestataire.
        return (
            lien_element("presta", contrat.prestataire_id)
            if contrat
            else page_element("presta")
        )

    code = doc.categorie.code if doc.categorie else None
    return lien_element("doc", doc.id) if code in CATEGORIES_AVEC_LIEN else None


__all__ = ["CATEGORIES_AVEC_LIEN", "lien_document"]
