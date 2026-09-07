"""Router prestataires & contrats d'entretien.

⚠️ Les RELEVÉS DE COMPTEURS et leur configuration vivent dans `compteurs.py`.
Ils partagent le préfixe d'URL `/prestataires` — l'écran est le même onglet, et
déplacer les routes aurait cassé les liens et le client TypeScript pour un gain
nul. Ce qui les sépare est le SUJET : un relevé d'eau ne parle ni d'un
prestataire ni d'un contrat, il parle d'un compteur. Coupé le 29/08/2026, la
modularité (rang 1) refusant que ce fichier grossisse encore.
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
import json

from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

#  ⚠️ `get_current_user` n'est plus importé : il ne servait qu'à `list_devis`,
#  le SEUL endpoint de ce router ouvert à tous les comptes (les résidents y
#  voyaient les devis marqués `affichable`). Tous ceux qui restent exigent le
#  rôle CS ou admin — la page qu'ils servent leur est réservée (#603).
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import ContratEntretien, NotationPrestataire, Prestataire, TypeEquipement, TypePrestataire, Utilisateur

from app.utils.echeance_contrat import poser_echeance
from app.utils.noms import nom_affiche

router = APIRouter(prefix="/prestataires", tags=["prestataires"])


# ── Prestataires ─────────────────────────────────────────────────────────────

class PrestataireContact(BaseModel):
    telephone: Optional[str] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    fonction: Optional[str] = None
    email: Optional[str] = None


class PrestataireCreate(BaseModel):
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.ponctuel
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: Optional[list[PrestataireContact]] = None


class PrestataireUpdate(BaseModel):
    nom: Optional[str] = None
    specialite: Optional[str] = None
    type_prestataire: Optional[TypePrestataire] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: Optional[list[PrestataireContact]] = None


class PrestataireRead(BaseModel):
    id: int
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.ponctuel
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: list[PrestataireContact] = []
    actif: bool

    class Config:
        from_attributes = True

    @field_validator('contacts', mode='before')
    @classmethod
    def parse_contacts(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        if v is None:
            return []
        return v


def _prest_to_read(p: Prestataire) -> PrestataireRead:
    """Construit un PrestataireRead en parsant contacts_json."""
    data = PrestataireRead.model_validate(p)
    if p.contacts_json:
        try:
            data.contacts = json.loads(p.contacts_json)
        except Exception:
            data.contacts = []
    return data


@router.get("", response_model=list[PrestataireRead])
def list_prestataires(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    prests = session.exec(select(Prestataire).where(Prestataire.actif == True)).all()
    return [_prest_to_read(p) for p in prests]


@router.post("", response_model=PrestataireRead, status_code=201)
def create_prestataire(
    body: PrestataireCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    data = body.model_dump(exclude={'contacts'})
    if body.contacts is not None:
        data['contacts_json'] = json.dumps([c.model_dump() for c in body.contacts], ensure_ascii=False)
    p = Prestataire(**data)
    session.add(p)
    session.commit()
    session.refresh(p)
    return _prest_to_read(p)


@router.patch("/{p_id}", response_model=PrestataireRead)
def update_prestataire(
    p_id: int,
    body: PrestataireUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    p = session.get(Prestataire, p_id)
    if not p:
        raise HTTPException(404, "Prestataire introuvable")
    data = body.model_dump(exclude_unset=True, exclude={'contacts'})
    if 'contacts' in body.model_fields_set:
        data['contacts_json'] = json.dumps([c.model_dump() for c in (body.contacts or [])], ensure_ascii=False)
    for k, v in data.items():
        setattr(p, k, v)
    session.add(p)
    session.commit()
    session.refresh(p)
    return _prest_to_read(p)


@router.delete("/{p_id}", status_code=204)
def archive_prestataire(
    p_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    p = session.get(Prestataire, p_id)
    if not p:
        raise HTTPException(404, "Prestataire introuvable")
    p.actif = False
    session.add(p)
    session.commit()


# ── Contrats d'entretien ──────────────────────────────────────────────────────

class ContratCreate(BaseModel):
    copropriete_id: int
    batiment_id: Optional[int] = None
    prestataire_id: int
    type_equipement: TypeEquipement = TypeEquipement.autre
    libelle: str
    numero_contrat: Optional[str] = None
    date_debut: date
    duree_initiale_valeur: Optional[int] = None
    duree_initiale_unite: Optional[str] = None  # "mois" ou "ans"
    frequence_type: Optional[str] = None  # "semaines", "mois", "fois_par_an"
    frequence_valeur: Optional[int] = None
    prochaine_visite: Optional[date] = None
    notes: Optional[str] = None
    document_id: Optional[int] = None


class ContratRead(BaseModel):
    id: int
    copropriete_id: int
    batiment_id: Optional[int] = None
    prestataire_id: int
    type_equipement: str
    libelle: str
    numero_contrat: Optional[str] = None
    date_debut: date
    duree_initiale_valeur: Optional[int] = None
    duree_initiale_unite: Optional[str] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    prochaine_visite: Optional[date] = None
    actif: bool
    notes: Optional[str] = None
    document_id: Optional[int] = None

    #: L'échéance DÉDUITE, et `reconduit` quand le terme initial est passé.
    #: Non stockées : elles se reportent avec le temps, et une colonne figerait
    #: la valeur au jour du calcul — c'est le défaut corrigé le 29/08/2026, où
    #: « échéance » désignait trois valeurs différentes selon l'écran.
    #: 📖 La règle, ses cas et son historique : `app/utils/echeance_contrat.py`.
    date_fin: Optional[date] = None
    reconduit: bool = False
    #: Terme passé sans reconduction — un mandat de syndic qui a CESSÉ.
    echu: bool = False

    class Config:
        from_attributes = True


@router.get("/contrats", response_model=list[ContratRead])
def list_contrats(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    contrats = session.exec(select(ContratEntretien).where(ContratEntretien.actif == True)).all()
    return [poser_echeance(ContratRead.model_validate(c), c) for c in contrats]


@router.post("/contrats", response_model=ContratRead, status_code=201)
def create_contrat(
    body: ContratCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    c = ContratEntretien(**body.model_dump())
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@router.patch("/contrats/{c_id}", response_model=ContratRead)
def update_contrat(
    c_id: int,
    body: ContratCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    c = session.get(ContratEntretien, c_id)
    if not c:
        raise HTTPException(404, "Contrat introuvable")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@router.delete("/contrats/{c_id}", status_code=204)
def archive_contrat(
    c_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    c = session.get(ContratEntretien, c_id)
    if not c:
        raise HTTPException(404, "Contrat introuvable")
    c.actif = False
    session.add(c)
    session.commit()


# ── Notations prestataires ─────────────────────────────────────────────────

class NotationCreate(BaseModel):
    #  ⚠️ `devis_id` a disparu avec la prestation ponctuelle (#603). La COLONNE,
    #  elle, reste en base : les notations deja posees sur un devis gardent leur
    #  rattachement, et un retour arriere du code doit les retrouver. Le schema
    #  ne l'expose simplement plus — on ne peut plus en creer, on n'efface rien.
    prestataire_id: int
    note: int  # 1-5
    commentaire: Optional[str] = None
    contrat_id: Optional[int] = None

    @field_validator('note')
    @classmethod
    def validate_note(cls, v):
        if v < 1 or v > 5:
            raise ValueError('La note doit être entre 1 et 5')
        return v


class NotationRead(BaseModel):
    id: int
    prestataire_id: int
    note: int
    commentaire: Optional[str] = None
    contrat_id: Optional[int] = None
    auteur_id: int
    auteur_nom: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True


@router.get("/notations", response_model=list[NotationRead])
def list_notations(
    prestataire_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    q = select(NotationPrestataire)
    if prestataire_id is not None:
        q = q.where(NotationPrestataire.prestataire_id == prestataire_id)
    q = q.order_by(NotationPrestataire.cree_le.desc())
    notations = session.exec(q).all()
    result = []
    for n in notations:
        auteur = session.get(Utilisateur, n.auteur_id)
        nr = NotationRead.model_validate(n)
        nr.auteur_nom = nom_affiche(auteur.prenom, auteur.nom) if auteur else "?"
        result.append(nr)
    return result


@router.post("/notations", response_model=NotationRead, status_code=201)
def create_notation(
    body: NotationCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    p = session.get(Prestataire, body.prestataire_id)
    if not p:
        raise HTTPException(404, "Prestataire introuvable")
    n = NotationPrestataire(
        prestataire_id=body.prestataire_id,
        note=body.note,
        commentaire=body.commentaire,
        contrat_id=body.contrat_id,
        auteur_id=user.id,
    )
    session.add(n)
    session.commit()
    session.refresh(n)
    nr = NotationRead.model_validate(n)
    nr.auteur_nom = nom_affiche(user.prenom, user.nom)
    return nr


@router.delete("/notations/{n_id}", status_code=204)
def delete_notation(
    n_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    n = session.get(NotationPrestataire, n_id)
    if not n:
        raise HTTPException(404, "Notation introuvable")
    session.delete(n)
    session.commit()


@router.get("/synthese/{p_id}")
def get_prestataire_synthese(
    p_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Synthèse complète d'un prestataire pour le reporting CS."""
    p = session.get(Prestataire, p_id)
    if not p:
        raise HTTPException(404, "Prestataire introuvable")

    contrats = session.exec(
        select(ContratEntretien).where(ContratEntretien.prestataire_id == p_id, ContratEntretien.actif == True)
    ).all()
    notations = session.exec(
        select(NotationPrestataire).where(NotationPrestataire.prestataire_id == p_id).order_by(NotationPrestataire.cree_le.desc())
    ).all()

    note_moy = round(sum(n.note for n in notations) / len(notations), 1) if notations else None
    notations_read = []
    for n in notations:
        auteur = session.get(Utilisateur, n.auteur_id)
        notations_read.append({
            "id": n.id, "note": n.note, "commentaire": n.commentaire,
            "contrat_id": n.contrat_id,
            "auteur_nom": nom_affiche(auteur.prenom, auteur.nom) if auteur else "?",
            "cree_le": n.cree_le.isoformat(),
        })

    prest_data = _prest_to_read(p).model_dump()
    return {
        **prest_data,
        "contrats": [ContratRead.model_validate(c).model_dump() for c in contrats],
        "notations": notations_read,
        "note_moyenne": note_moy,
        "nb_notations": len(notations),
        "nb_contrats": len(contrats),
        "prochaines_visites": [
            {"contrat": c.libelle, "date": c.prochaine_visite.isoformat()}
            for c in contrats if c.prochaine_visite
        ],
    }
