"""Les réponses d'une rubrique de communauté — UNE écriture, deux rubriques.

## Le défaut (05/09/2026, relevé par comparaison des corps de fonctions)

`annonces.py` et `idees.py` portaient chacun **trois** routes de réponses —
lister, créer, supprimer — mesurées identiques à **99 %**, **94 %** et **99 %**.
Six fonctions pour deux fois la même chose. Ne variaient que :

* le modèle de la cible (`PetiteAnnonce` / `Idee`) ;
* le mot dans les messages (« Annonce introuvable » / « Idée introuvable ») ;
* le libellé de notification (« votre annonce » / « votre idée ») ;
* le préfixe du lien (`annonce` / `idee`) et le discriminant `rubrique`.

C'est-à-dire **rien qui tienne à la logique**, et tout ce qui tient au sujet.

🔴 Une règle recopiée ne se durcit pas : celle qui compte ici est
`if user.has_role(externe) and not has_role(cs, admin)` — le refus opposé aux
comptes externes. Écrite deux fois, elle se corrige une fois sur deux. C'est
exactement ce qui était arrivé aux destinataires d'e-mail, en quatre exemplaires
(`utils/destinataires.py`).

## Ce que ce module est

Une **fabrique de routes** : `enregistrer_routes_reponses()` pose les trois
routes sur le routeur qu'on lui donne, adaptées par ses paramètres. L'objet est
donc enrichi et adapté, pas recopié — un troisième sujet de communauté
n'écrirait pas une ligne de logique, seulement sa déclaration.

⚠️ **Le nom du paramètre de chemin devient `cible_id`** partout. Il n'apparaît
pas dans l'URL appelée (`/annonces/12/reponses` est inchangée) : il ne se voyait
que dans le schéma OpenAPI, lui-même fermé en production.

⚠️ Ce module ne porte PAS l'affichage d'une réponse (`enrich_reponse`,
`tri_reponses`, `auteur_meta`) : ces fonctions vivaient déjà dans
`utils/communaute.py`, partagées. On ne déplace que ce qui était en double.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, peut_commenter
from app.database import get_session
from app.models.core import ReponseCommunaute, RoleUtilisateur, Utilisateur
from app.utils.communaute import exiger_acces
from app.utils.reponses import (
    auteur_meta,
    enrich_reponse,
    notifier_nouvelle_reponse,
    tri_reponses,
)
from app.utils.liens import lien_element


class ReponseCreate(BaseModel):
    """Le corps d'une réponse — écrit deux fois jusqu'au 05/09/2026.

    `annonces.py` et `idees.py` le déclaraient chacun, à l'identique. Un schéma
    d'entrée recopié est une validation qui se durcit d'un seul côté.
    """

    contenu: str


def reponses_de(rubrique: str, cible_id: int, session: Session) -> list[dict]:
    """Les réponses d'une cible : CS/admin en tête (plus de poids), puis chronologique.

    Écrite une fois : `annonces` et `idees` en avaient chacune leur copie, sous
    le même nom `_reponses_for`, à la rubrique près.
    """
    reps = session.exec(
        select(ReponseCommunaute).where(
            ReponseCommunaute.rubrique == rubrique,
            ReponseCommunaute.cible_id == cible_id,
        )
    ).all()
    return tri_reponses([enrich_reponse(r, session) for r in reps])


def enregistrer_routes_reponses(
    router: APIRouter,
    *,
    rubrique: str,
    modele: type,
    libelle: str,
    rubrique_label: str,
    prefixe_lien: str,
    titre_de: Callable[[Any], str] = lambda cible: cible.titre,
) -> None:
    """Pose `GET`, `POST` et `DELETE .../{cible_id}/reponses` sur `router`.

    * `rubrique` — le discriminant stocké dans `ReponseCommunaute.rubrique` ;
    * `modele` — la table de la cible, pour vérifier qu'elle existe ;
    * `libelle` — le mot des messages d'erreur (« Annonce », « Idée ») ;
    * `rubrique_label` — ce que lit l'auteur notifié (« votre annonce ») ;
    * `prefixe_lien` — le premier segment du lien construit vers le front.

    ⚠️ `titre_de` est un paramètre et non un attribut supposé : toutes les cibles
    portent aujourd'hui un `titre`, mais l'écrire en dur ferait de cette fabrique
    une promesse que la première cible sans titre briserait — silencieusement,
    puisque l'erreur ne surviendrait qu'à la première notification.
    """

    @router.get("/{cible_id}/reponses")
    def list_reponses(
        cible_id: int,
        session: Session = Depends(get_session),
        user: Utilisateur = Depends(get_current_user),
    ):
        exiger_acces(user)
        if not session.get(modele, cible_id):
            raise HTTPException(404, f"{libelle} introuvable")
        return reponses_de(rubrique, cible_id, session)

    @router.post("/{cible_id}/reponses", status_code=201)
    def create_reponse(
        cible_id: int,
        body: ReponseCreate,
        background_tasks: BackgroundTasks,
        session: Session = Depends(get_session),
        user: Utilisateur = Depends(get_current_user),
    ):
        exiger_acces(user)
        #  🔴 LE REFUS OPPOSÉ AUX COMPTES EXTERNES — la règle qui justifie à elle
        #  seule cette factorisation. Écrite deux fois, elle se serait durcie une
        #  fois sur deux.
        if user.has_role(RoleUtilisateur.externe) and not user.has_role(
            RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin
        ):
            raise HTTPException(403, "Les utilisateurs externes ne peuvent pas répondre")
        contenu = (body.contenu or "").strip()
        if not contenu:
            raise HTTPException(422, "La réponse ne peut pas être vide")
        cible = session.get(modele, cible_id)
        if not cible:
            raise HTTPException(404, f"{libelle} introuvable")

        rep = ReponseCommunaute(
            rubrique=rubrique, cible_id=cible_id, auteur_id=user.id, contenu=contenu
        )
        session.add(rep)
        notifier_nouvelle_reponse(
            session,
            background_tasks,
            createur_id=cible.auteur_id,
            auteur=user,
            rubrique_label=rubrique_label,
            sujet=titre_de(cible),
            extrait=contenu,
            lien_path=lien_element(prefixe_lien, cible_id),
        )
        session.commit()
        session.refresh(rep)
        return {
            "id": rep.id,
            "cible_id": rep.cible_id,
            "auteur_id": rep.auteur_id,
            "contenu": rep.contenu,
            "cree_le": rep.cree_le,
            **auteur_meta(user, session),
        }

    @router.delete("/{cible_id}/reponses/{rep_id}", status_code=204)
    def delete_reponse(
        cible_id: int,
        rep_id: int,
        session: Session = Depends(get_session),
        user: Utilisateur = Depends(get_current_user),
    ):
        """Supprimer une réponse : son auteur, ou un CS/admin."""
        exiger_acces(user)
        rep = session.get(ReponseCommunaute, rep_id)
        if not rep or rep.rubrique != rubrique or rep.cible_id != cible_id:
            raise HTTPException(404, "Réponse introuvable")
        if not peut_commenter(rep, user):
            raise HTTPException(403, "Vous ne pouvez supprimer que vos propres réponses")
        session.delete(rep)
        session.commit()
