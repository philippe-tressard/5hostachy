"""Router copropriété — fiche, bâtiments, lots."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import (
    Batiment, ContratEntretien, Copropriete, Lot, MembreSyndic, Prestataire,
    TypeEquipement, Utilisateur,
)

from app.utils.syndic import nom_du_syndic

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
    #
    #  ✅ Ce que la fiche accepte à nouveau, et qui n'est PAS un retour arrière :
    #  la DÉSIGNATION du contrat. On n'y saisit pas un assureur, on y dit lequel
    #  des contrats existants fait foi. La donnée reste unique, côté contrat.
    assurance_contrat_id: Optional[int] = None
    syndic_contrat_id: Optional[int] = None


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
    #: Enrichissement demandé le 20/08/2026 : la fiche montrait trois champs sur
    #: une notion qui en porte dix. Ce qu'on lit ici vient du prestataire ET du
    #: contrat, jamais d'une saisie propre à la fiche.
    assurance_contrat_id: Optional[int] = None
    assurance_telephone: Optional[str] = None
    assurance_email: Optional[str] = None
    assurance_debut: Optional[date] = None
    assurance_document_id: Optional[int] = None

    #: 🔴 Le SYNDIC, même moule que l'assurance — un contrat de référence.
    #:
    #: ⚠️ `syndic_interlocuteur` vient de `MembreSyndic`, PAS du prestataire :
    #: le cabinet est l'organisation, les personnes restent dans l'annuaire, et
    #: c'est de là que partent les courriels. Deux listes des mêmes gens, c'est
    #: la faute de #490 transposée au circuit des notifications.
    syndic_contrat_id: Optional[int] = None
    syndic_cabinet: Optional[str] = None
    syndic_telephone: Optional[str] = None
    syndic_email: Optional[str] = None
    syndic_numero_mandat: Optional[str] = None
    syndic_debut: Optional[date] = None
    syndic_echeance: Optional[date] = None
    syndic_document_id: Optional[int] = None
    syndic_interlocuteur: Optional[str] = None
    syndic_interlocuteur_email: Optional[str] = None

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




#: Les deux sections de la fiche adossées à un contrat, et ce qui les distingue.
#:
#: 🔴 UNE SEULE FONCTION LES SERT. Écrire `assurance_du_contrat` puis
#: `syndic_du_contrat` aurait donné deux copies du même geste — lire un contrat,
#: lire son prestataire, composer un préfixe — libres de diverger au premier
#: enrichissement demandé d'un seul côté (`standards/02` §2).
#:
#: `champ_id` est la colonne qui DÉSIGNE le contrat ; `type_equipement` sert
#: uniquement au repli et à la liste proposée à l'écran.
SECTIONS_CONTRAT = {
    "assurance": ("assurance_contrat_id", TypeEquipement.assurance),
    "syndic": ("syndic_contrat_id", TypeEquipement.syndic),
}


def contrat_de_reference(session: Session, copro: Copropriete, section: str):
    """Le contrat que la fiche DÉSIGNE pour cette section, ou `None`.

    ## Le choix a remplacé la déduction (20/08/2026)

    L'assurance venait d'une règle implicite — *« le contrat actif le plus récent
    gagne »* (#490). La règle était juste : une copropriété change d'assureur et
    l'ancien contrat reste en base, c'est tout l'intérêt d'en avoir fait un
    contrat. Mais **rien à l'écran ne disait laquelle des lignes faisait foi**,
    et la fiche dépendait d'une comparaison de dates.

    ⚠️ **Le repli sur l'ancienne règle est conservé**, et il n'est pas de la
    prudence : la migration 0157 renseigne `assurance_contrat_id` sur les bases
    existantes, mais une copropriété créée après coup, ou un contrat saisi avant
    qu'on ait pensé à le désigner, laisserait la fiche VIDE alors que le contrat
    existe. Un écran qui dit « aucun contrat » devant un contrat est pire qu'une
    règle implicite.

    Le repli ne s'applique que si aucun contrat n'est désigné — un contrat
    désigné puis supprimé rend `None`, et l'écran le dit.
    """
    champ_id, type_equipement = SECTIONS_CONTRAT[section]
    contrat_id = getattr(copro, champ_id, None)
    if contrat_id:
        return session.get(ContratEntretien, contrat_id)
    return session.exec(
        select(ContratEntretien)
        .where(
            ContratEntretien.copropriete_id == copro.id,
            ContratEntretien.type_equipement == type_equipement,
            ContratEntretien.actif == True,  # noqa: E712
        )
        .order_by(ContratEntretien.date_debut.desc(), ContratEntretien.id.desc())
    ).first()


def assurance_du_contrat(session: Session, copro: Copropriete) -> dict:
    """Ce que la fiche affiche comme « assurance » — lu sur le CONTRAT (#490).

    Les colonnes `assurance_*` de `copropriete` ne sont plus la source : elles
    subsistent pour qu'un retour arrière reste possible, mais plus rien ne les
    lit.

    Rend un dictionnaire vide si aucun contrat n'est trouvé : la fiche masque
    alors la section, exactement comme lorsque le champ texte était vide.
    """
    contrat = contrat_de_reference(session, copro, "assurance")
    if not contrat:
        return {}
    presta = session.get(Prestataire, contrat.prestataire_id)
    return {
        "assurance_contrat_id": contrat.id,
        "assurance_compagnie": presta.nom if presta else None,
        "assurance_telephone": presta.telephone if presta else None,
        "assurance_email": presta.email if presta else None,
        "assurance_numero_police": contrat.numero_contrat,
        "assurance_debut": contrat.date_debut,
        "assurance_echeance": contrat.prochaine_visite,
        "assurance_document_id": contrat.document_id,
    }


def syndic_du_contrat(session: Session, copro: Copropriete) -> dict:
    """Le cabinet de syndic, son mandat, et son interlocuteur principal.

    ## Deux sources, et c'est voulu

    Le **cabinet** vient du prestataire désigné par le contrat de mandat ;
    l'**interlocuteur** vient de `MembreSyndic`, la table de l'annuaire.

    ⚠️ Ce n'est pas une inconséquence : `MembreSyndic` est lu par **dix
    modules**, dont `utils/destinataires.py`, `tickets/commun.py` et les trois
    routeurs de courriels. C'est de là que partent les messages au cabinet.
    Recopier ces personnes dans les contacts du prestataire aurait donné deux
    listes des mêmes gens — la faute de #490 transposée au circuit des
    notifications, où elle ne se verrait que le jour où un courriel ne partirait
    pas.

    Le prestataire porte donc l'ORGANISATION, l'annuaire garde les PERSONNES.
    """
    contrat = contrat_de_reference(session, copro, "syndic")
    principal = session.exec(
        select(MembreSyndic).where(MembreSyndic.est_principal == True)  # noqa: E712
    ).first()

    lu: dict = {}
    if principal:
        lu["syndic_interlocuteur"] = " ".join(
            x for x in (principal.prenom, principal.nom, f"({principal.fonction})" if principal.fonction else "") if x
        ).strip()
        lu["syndic_interlocuteur_email"] = principal.email

    if not contrat:
        #  ⚠️ On rend quand même l'interlocuteur : le cabinet peut n'avoir pas
        #  encore de contrat saisi alors que ses membres sont dans l'annuaire
        #  depuis des mois. Rendre un dictionnaire vide effacerait de la fiche
        #  une information qu'on POSSÈDE.
        return lu

    presta = session.get(Prestataire, contrat.prestataire_id)
    lu.update({
        "syndic_contrat_id": contrat.id,
        "syndic_cabinet": presta.nom if presta else None,
        "syndic_telephone": presta.telephone if presta else None,
        "syndic_email": presta.email if presta else None,
        "syndic_numero_mandat": contrat.numero_contrat,
        "syndic_debut": contrat.date_debut,
        "syndic_echeance": contrat.prochaine_visite,
        "syndic_document_id": contrat.document_id,
    })
    return lu


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
    #  ⚠️ La liste des champs à effacer se DÉDUIT du schéma : les nommer ici en
    #  aurait fait une seconde liste, et l'enrichissement du 20/08 (dix champs de
    #  plus) l'aurait laissée en arrière au premier ajout oublié.
    for cle in CoproprieteRead.model_fields:
        if cle.startswith(("assurance_", "syndic_")):
            setattr(lue, cle, None)
    for source in (assurance_du_contrat, syndic_du_contrat):
        for cle, valeur in source(session, copro).items():
            setattr(lue, cle, valeur)

    #  🔴 LE REPLI, et il n'a sa place qu'ICI.
    #
    #  `syndic_du_contrat` lit ce que porte le CONTRAT — c'est son nom, et le
    #  test `…_meme_SANS_contrat` tient à ce qu'elle n'invente rien. Mais la
    #  règle arbitrée le 29/08/2026 (#535) dit que le nom du syndic a DEUX
    #  sources, le contrat puis la saisie libre, et qu'une seule répond à la
    #  fois. Cette hiérarchie est écrite une seule fois, dans `utils/syndic.py`.
    #
    #  ⚠️ Sans ce repli, la fiche de la résidence n'affichait aucun syndic pour
    #  une copropriété sans contrat désigné, alors que l'ANNUAIRE affichait la
    #  saisie : deux écrans, deux réponses à la même question — exactement le
    #  doublon que #535 ferme, reconstitué un étage plus haut.
    #
    #  ⚠️ Et c'est bien un repli, jamais une seconde vérité : il ne s'applique
    #  que là où la première est absente (`if not lue.syndic_cabinet`).
    if not lue.syndic_cabinet:
        lue.syndic_cabinet = nom_du_syndic(session) or None
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


class ContratCandidat(BaseModel):
    """Un contrat proposable comme référence de la fiche.

    ⚠️ Volontairement PAUVRE : de quoi reconnaître le contrat dans une liste, et
    rien de plus. La fiche lit les détails par `contrat_de_reference` une fois le
    choix fait — deux chemins pour la même donnée en feraient deux vérités.
    """
    id: int
    libelle: str
    prestataire: Optional[str] = None
    numero_contrat: Optional[str] = None
    date_debut: date
    actif: bool


@router.get("/contrats-candidats/{section}", response_model=list[ContratCandidat])
def contrats_candidats(
    section: str,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Les contrats parmi lesquels la fiche désigne sa référence.

    🔴 `section` est validé contre `SECTIONS_CONTRAT` — liste blanche, jamais
    l'entrée brute : sans elle, `TypeEquipement(section)` lèverait un `ValueError`
    rendu en 500, et le paramètre deviendrait un moyen d'énumérer l'énumération
    (`standards/03` §2).

    Les contrats INACTIFS sont rendus, avec leur drapeau. Une copropriété désigne
    parfois un mandat échu le temps d'en signer un nouveau, et les masquer
    obligerait à les réactiver pour les choisir — donc à mentir sur leur état.
    """
    if section not in SECTIONS_CONTRAT:
        raise HTTPException(404, "Section inconnue")
    _, type_equipement = SECTIONS_CONTRAT[section]
    copro = session.exec(select(Copropriete)).first()
    if not copro:
        raise HTTPException(404, "Copropriété non configurée")
    contrats = session.exec(
        select(ContratEntretien)
        .where(
            ContratEntretien.copropriete_id == copro.id,
            ContratEntretien.type_equipement == type_equipement,
        )
        .order_by(ContratEntretien.date_debut.desc(), ContratEntretien.id.desc())
    ).all()
    noms = {
        p.id: p.nom
        for p in session.exec(
            select(Prestataire).where(
                Prestataire.id.in_([c.prestataire_id for c in contrats] or [0])
            )
        ).all()
    }
    return [
        ContratCandidat(
            id=c.id,
            libelle=c.libelle,
            prestataire=noms.get(c.prestataire_id),
            numero_contrat=c.numero_contrat,
            date_debut=c.date_debut,
            actif=c.actif,
        )
        for c in contrats
    ]


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
