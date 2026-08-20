"""Router copropriété — fiche, bâtiments, lots."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import (
    Batiment, ContratEntretien, Copropriete, Lot, Prestataire, TypeEquipement, Utilisateur,
)

router = APIRouter(prefix="/copropriete", tags=["copropriété"])


class CoproprieteUpdate(BaseModel):
    nom: Optional[str] = None
    adresse: Optional[str] = None
    annee_construction: Optional[int] = None
    nb_lots_total: Optional[int] = None
    nb_lots_principaux: Optional[int] = None
    nb_parkings_communs: Optional[int] = None
    numero_immatriculation: Optional[str] = None
    #  🔴 `assurance_compagnie`, `assurance_numero_police` et `assurance_echeance`
    #  ont QUITTÉ ce schéma (#490).
    #
    #  Ils décrivaient un contrat avec un prestataire — notion que
    #  `ContratEntretien` porte déjà, avec ses échéances, ses documents et ses
    #  relances. Saisis ici en texte libre, ils créaient un second assureur qui
    #  ne renvoyait à rien : le même nom pouvait exister deux fois, sans que rien
    #  ne dise que c'était le même.
    #
    #  ⚠️ Les laisser acceptés « au cas où » aurait été pire que de les retirer :
    #  l'écran aurait continué d'écrire du texte que plus personne ne lit, et la
    #  fiche aurait affiché un assureur pendant que le contrat en désignait un
    #  autre. Un champ que le serveur ne consomme plus doit disparaître de son
    #  contrat d'entrée, pas y rester par prudence.
    #
    #  L'assurance se modifie désormais là où vivent les contrats.


class CoproprieteRead(BaseModel):
    id: int
    nom: str
    adresse: str
    annee_construction: Optional[int] = None
    nb_lots_total: Optional[int] = None
    nb_lots_principaux: Optional[int] = None
    numero_immatriculation: Optional[str] = None
    #  ⚠️ Ces trois champs restent EN LECTURE, et leur nom ne change pas : c'est
    #  ce que `FicheResidence` affiche, et leur donner un nouveau nom aurait
    #  imposé de toucher l'écran pour un renommage sans gain.
    #
    #  Ce qui change est leur SOURCE : ils ne viennent plus des colonnes de la
    #  copropriété mais du contrat d'assurance (`_assurance_du_contrat`). Une
    #  seule vérité, donc, quel que soit l'écran qui la montre.
    assurance_compagnie: Optional[str] = None
    assurance_numero_police: Optional[str] = None
    assurance_echeance: Optional[date] = None
    photo_url: Optional[str] = None
    nb_parkings_communs: int = 0

    class Config:
        from_attributes = True


class BatimentRead(BaseModel):
    id: int
    numero: str
    nb_etages: int
    specificites: Optional[str] = None
    nb_appartements: int = 0
    nb_caves: int = 0
    nb_parkings: int = 0
    nb_locaux_commerciaux: int = 0

    class Config:
        from_attributes = True


class LotRead(BaseModel):
    id: int
    batiment_id: Optional[int] = None  # None pour les parkings
    batiment_nom: Optional[str] = None  # enrichi à la sérialisation
    numero: str
    type: str
    type_appartement: Optional[str] = None
    etage: Optional[int] = None

    class Config:
        from_attributes = True




def assurance_du_contrat(session: Session, copro: Copropriete) -> dict:
    """Ce que la fiche affiche comme « assurance » — lu sur le CONTRAT (#490).

    Les trois colonnes `assurance_*` de `copropriete` ne sont plus la source :
    elles subsistent pour qu'un retour arrière reste possible, mais plus rien ne
    les lit. La vérité est le contrat de catégorie « assurance » rattaché à cette
    copropriété, avec son prestataire.

    ⚠️ **Le contrat le plus récent gagne**, et c'est délibéré : une copropriété
    change d'assureur, et l'ancien contrat reste en base — c'est même tout
    l'intérêt d'en avoir fait un contrat. Rendre le premier trouvé afficherait
    l'assureur de l'an dernier sans que rien ne le dise.

    Rend un dictionnaire vide si aucun contrat n'existe : la fiche masque alors
    la ligne, exactement comme lorsque le champ texte était vide.
    """
    contrat = session.exec(
        select(ContratEntretien)
        .where(
            ContratEntretien.copropriete_id == copro.id,
            ContratEntretien.type_equipement == TypeEquipement.assurance,
            ContratEntretien.actif == True,  # noqa: E712
        )
        .order_by(ContratEntretien.date_debut.desc(), ContratEntretien.id.desc())
    ).first()
    if not contrat:
        return {}
    presta = session.get(Prestataire, contrat.prestataire_id)
    return {
        "assurance_compagnie": presta.nom if presta else None,
        "assurance_numero_police": contrat.numero_contrat,
        "assurance_echeance": contrat.prochaine_visite,
    }


def copropriete_lue(session: Session, copro: Copropriete) -> CoproprieteRead:
    """`CoproprieteRead` avec l'assurance prise sur le contrat.

    Un seul point de composition : les deux endpoints qui rendent une
    copropriété passent par ici. Les laisser composer chacun de leur côté aurait
    donné deux fiches capables de se contredire — c'est exactement ce que ce lot
    supprime.
    """
    lue = CoproprieteRead.model_validate(copro)
    #  🔴 On EFFACE d'abord, on remplit ensuite.
    #
    #  `from_attributes=True` recopie les colonnes `assurance_*` conservées :
    #  sans cet effacement, une copropriété SANS contrat affichait l'ancienne
    #  saisie en texte libre — donc potentiellement un assureur qui n'est plus
    #  le bon, sans que rien ne le signale. Le repli silencieux remettait en
    #  service les colonnes qu'on venait de retirer du circuit.
    #
    #  ⚠️ Trouvé par `test_sans_contrat_la_fiche_n_invente_rien`, écrit dans le
    #  même lot : le test a attrapé le défaut du code qu'il accompagnait.
    for cle in ("assurance_compagnie", "assurance_numero_police", "assurance_echeance"):
        setattr(lue, cle, None)
    for cle, valeur in assurance_du_contrat(session, copro).items():
        setattr(lue, cle, valeur)
    return lue


@router.get("", response_model=CoproprieteRead)
def get_copropriete(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    copro = session.exec(select(Copropriete)).first()
    if not copro:
        raise HTTPException(404, "Copropriété non configurée")
    return copropriete_lue(session, copro)


@router.patch("", response_model=CoproprieteRead)
def update_copropriete(
    body: CoproprieteUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    copro = session.exec(select(Copropriete)).first()
    if not copro:
        raise HTTPException(404, "Copropriété non configurée")
    donnees = body.model_dump(exclude_none=True)

    #  ⚠️ La conversion de `assurance_echeance` (chaîne ISO → `date`) vivait ici.
    #  Elle a disparu AVEC le champ (#490) : l'échéance est désormais celle du
    #  contrat, saisie par l'écran des contrats, où elle est déjà typée.
    #
    #  Ce qu'elle corrigeait mérite d'être rappelé, parce que la classe d'erreur
    #  reste : affecter une CHAÎNE à une colonne `date` faisait lever SQLAlchemy
    #  et rendait TOUTE la fiche inenregistrable — y compris quand on n'avait
    #  modifié que le nom du syndic. Le défaut a vécu des semaines, personne
    #  n'ayant retouché l'échéance (13/08/2026).

    for k, v in donnees.items():
        setattr(copro, k, v)
    session.add(copro)
    session.commit()
    session.refresh(copro)
    return copropriete_lue(session, copro)


@router.get("/batiments", response_model=list[BatimentRead])
def get_batiments(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    return session.exec(select(Batiment)).all()


@router.get("/lots")
def get_lots(
    batiment_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    stmt = select(Lot)
    if batiment_id:
        stmt = stmt.where(Lot.batiment_id == batiment_id)
    lots = session.exec(stmt).all()
    result = []
    for lot in lots:
        bat = session.get(Batiment, lot.batiment_id) if lot.batiment_id else None
        d = LotRead.model_validate(lot)
        d.batiment_nom = bat.numero if bat else None
        result.append(d)
    return result
