"""Router prestataires & contrats d'entretien."""
import os
import re
import shutil
import uuid
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import json

from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin, get_current_user
from app.database import get_session
from app.models.core import CompteurConfig, ContratEntretien, DevisPrestataire, NotationPrestataire, Prestataire, ReleveCompteur, TypeEquipement, TypePrestataire, Utilisateur, RoleUtilisateur

UPLOADS_DIR = os.getenv("UPLOADS_DIR", "/app/uploads")

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

    class Config:
        from_attributes = True


@router.get("/contrats", response_model=list[ContratRead])
def list_contrats(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return session.exec(select(ContratEntretien).where(ContratEntretien.actif == True)).all()


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


# ── Devis prestataires ──────────────────────────────────────────────────

class DevisCreate(BaseModel):
    copropriete_id: int = 1
    prestataire_id: int
    batiment_id: Optional[int] = None
    perimetre: str = "résidence"
    titre: str
    date_prestation: Optional[date] = None
    montant_estime: Optional[float] = None
    statut: str = "en_attente"
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    notes: Optional[str] = None
    affichable: bool = False


class DevisUpdate(BaseModel):
    prestataire_id: Optional[int] = None
    batiment_id: Optional[int] = None
    perimetre: Optional[str] = None
    titre: Optional[str] = None
    date_prestation: Optional[date] = None
    montant_estime: Optional[float] = None
    statut: Optional[str] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    notes: Optional[str] = None
    affichable: Optional[bool] = None


class DevisRead(BaseModel):
    id: int
    copropriete_id: int
    prestataire_id: int
    batiment_id: Optional[int] = None
    perimetre: str = "résidence"
    titre: str
    date_prestation: Optional[date] = None
    montant_estime: Optional[float] = None
    statut: str
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    notes: Optional[str] = None
    fichiers_urls: list[str] = []
    os_fichier_url: Optional[str] = None
    actif: bool
    affichable: bool = False
    cree_le: Optional[datetime] = None
    mis_a_jour_le: Optional[datetime] = None

    @field_validator('fichiers_urls', mode='before')
    @classmethod
    def parse_fichiers_json(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        if isinstance(v, list):
            return v
        return []

    class Config:
        from_attributes = True


@router.get("/devis", response_model=list[DevisRead])
def list_devis(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    stmt = select(DevisPrestataire).where(DevisPrestataire.actif == True)
    if not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        # Résidents et locataires ne voient que les devis marqués affichable
        stmt = stmt.where(DevisPrestataire.affichable == True)
    return session.exec(stmt).all()


@router.post("/devis", response_model=DevisRead, status_code=201)
def create_devis(
    body: DevisCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    d = DevisPrestataire(**body.model_dump())
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


@router.patch("/devis/{d_id}", response_model=DevisRead)
def update_devis(
    d_id: int,
    body: DevisUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    d = session.get(DevisPrestataire, d_id)
    if not d:
        raise HTTPException(404, "Devis introuvable")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    d.mis_a_jour_le = datetime.utcnow()
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


@router.delete("/devis/{d_id}", status_code=204)
def archive_devis(
    d_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    d = session.get(DevisPrestataire, d_id)
    if not d:
        raise HTTPException(404, "Devis introuvable")
    d.actif = False
    session.add(d)
    session.commit()


@router.post("/devis/{d_id}/fichier", response_model=DevisRead)
async def upload_devis_fichier(
    d_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    d = session.get(DevisPrestataire, d_id)
    if not d:
        raise HTTPException(404, "Devis introuvable")
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    raw_name = os.path.basename(file.filename or "fichier")
    safe_name = re.sub(r"[^\w.\-]", "_", raw_name)[:200] or "fichier"
    dest = os.path.join(UPLOADS_DIR, f"{uuid.uuid4().hex}_{safe_name}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        fichiers = json.loads(d.fichiers_urls or "[]")
        if not isinstance(fichiers, list):
            fichiers = []
    except Exception:
        fichiers = []
    fichiers.append(f"/uploads/{os.path.basename(dest)}")
    d.fichiers_urls = json.dumps(fichiers)
    d.mis_a_jour_le = datetime.utcnow()
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


@router.delete("/devis/{d_id}/fichier", response_model=DevisRead)
def delete_devis_fichier(
    d_id: int,
    url: str,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    d = session.get(DevisPrestataire, d_id)
    if not d:
        raise HTTPException(404, "Devis introuvable")
    try:
        fichiers = json.loads(d.fichiers_urls or "[]")
        if not isinstance(fichiers, list):
            fichiers = []
    except Exception:
        fichiers = []
    if url in fichiers:
        fichiers.remove(url)
        filename = os.path.basename(url)
        filepath = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    d.fichiers_urls = json.dumps(fichiers) if fichiers else None
    d.mis_a_jour_le = datetime.utcnow()
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


@router.post("/devis/{d_id}/os", response_model=DevisRead)
async def upload_devis_os(
    d_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Upload de l'ordre de service (OS) signé. Passe automatiquement le devis en 'accepte'."""
    d = session.get(DevisPrestataire, d_id)
    if not d:
        raise HTTPException(404, "Devis introuvable")
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    raw_name = os.path.basename(file.filename or "os")
    safe_name = re.sub(r"[^\w.\-]", "_", raw_name)[:200] or "os"
    dest = os.path.join(UPLOADS_DIR, f"{uuid.uuid4().hex}_{safe_name}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Supprimer l'ancien OS si remplacé
    if d.os_fichier_url:
        old_path = os.path.join(UPLOADS_DIR, os.path.basename(d.os_fichier_url))
        if os.path.exists(old_path):
            os.remove(old_path)
    d.os_fichier_url = f"/uploads/{os.path.basename(dest)}"
    d.statut = "accepte"
    d.mis_a_jour_le = datetime.utcnow()
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


# ── Relevés compteurs ────────────────────────────────────────────────────────

class ReleveCreate(BaseModel):
    type_compteur: str
    date_releve: date
    index: Optional[int] = None
    note: Optional[str] = None
    prestataire_id: Optional[int] = None


class ReleveUpdate(BaseModel):
    date_releve: Optional[date] = None
    index: Optional[int] = None
    note: Optional[str] = None
    prestataire_id: Optional[int] = None


class ReleveRead(BaseModel):
    id: int
    type_compteur: str
    date_releve: date
    index: Optional[int] = None
    note: Optional[str] = None
    photo_url: Optional[str] = None
    prestataire_id: Optional[int] = None
    cree_le: datetime
    cree_par_id: Optional[int] = None

    class Config:
        from_attributes = True


@router.get("/releves", response_model=list[ReleveRead])
def list_releves(
    type_compteur: Optional[str] = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    q = select(ReleveCompteur)
    if type_compteur:
        q = q.where(ReleveCompteur.type_compteur == type_compteur)
    return session.exec(q.order_by(ReleveCompteur.date_releve.desc())).all()


@router.post("/releves", response_model=ReleveRead, status_code=201)
def create_releve(
    body: ReleveCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    r = ReleveCompteur(**body.model_dump(), cree_le=datetime.utcnow(), cree_par_id=user.id)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.patch("/releves/{r_id}", response_model=ReleveRead)
def update_releve(
    r_id: int,
    body: ReleveUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    r = session.get(ReleveCompteur, r_id)
    if not r:
        raise HTTPException(404, "Relevé introuvable")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.delete("/releves/{r_id}", status_code=204)
def delete_releve(
    r_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    r = session.get(ReleveCompteur, r_id)
    if not r:
        raise HTTPException(404, "Relevé introuvable")
    session.delete(r)
    session.commit()


# ── Photo relevé ──────────────────────────────────────────

@router.post("/releves/{r_id}/photo", response_model=ReleveRead)
async def upload_releve_photo(
    r_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    r = session.get(ReleveCompteur, r_id)
    if not r:
        raise HTTPException(404, "Relevé introuvable")
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    raw_name = os.path.basename(file.filename or "photo")
    safe_name = re.sub(r"[^\w.\-]", "_", raw_name)[:200] or "photo"
    dest = os.path.join(UPLOADS_DIR, f"{uuid.uuid4().hex}_{safe_name}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    r.photo_url = f"/uploads/{os.path.basename(dest)}"
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


# ── Compteurs config ──────────────────────────────────────

class CompteurConfigCreate(BaseModel):
    type_compteur: str
    label: str
    prestataire_id: Optional[int] = None
    ordre: int = 0


class CompteurConfigUpdate(BaseModel):
    label: Optional[str] = None
    prestataire_id: Optional[int] = None
    ordre: Optional[int] = None


class CompteurConfigRead(BaseModel):
    id: int
    type_compteur: str
    label: str
    prestataire_id: Optional[int] = None
    actif: bool
    ordre: int

    class Config:
        from_attributes = True


@router.get("/compteurs-config", response_model=list[CompteurConfigRead])
def list_compteurs_config(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return session.exec(
        select(CompteurConfig).where(CompteurConfig.actif == True).order_by(CompteurConfig.ordre)
    ).all()


@router.post("/compteurs-config", response_model=CompteurConfigRead, status_code=201)
def create_compteur_config(
    body: CompteurConfigCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    # Ensure unique type_compteur slug
    existing = session.exec(
        select(CompteurConfig).where(CompteurConfig.type_compteur == body.type_compteur)
    ).first()
    if existing:
        raise HTTPException(400, "Ce type de compteur existe déjà")
    cfg = CompteurConfig(**body.model_dump())
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


@router.patch("/compteurs-config/{cfg_id}", response_model=CompteurConfigRead)
def update_compteur_config(
    cfg_id: int,
    body: CompteurConfigUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    cfg = session.get(CompteurConfig, cfg_id)
    if not cfg:
        raise HTTPException(404, "Compteur introuvable")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


@router.delete("/compteurs-config/{cfg_id}", status_code=204)
def delete_compteur_config(
    cfg_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    cfg = session.get(CompteurConfig, cfg_id)
    if not cfg:
        raise HTTPException(404, "Compteur introuvable")
    cfg.actif = False
    session.add(cfg)
    session.commit()


# ── Notations prestataires ─────────────────────────────────────────────────

class NotationCreate(BaseModel):
    prestataire_id: int
    note: int  # 1-5
    commentaire: Optional[str] = None
    devis_id: Optional[int] = None
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
    devis_id: Optional[int] = None
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
        nr.auteur_nom = f"{auteur.prenom} {auteur.nom}" if auteur else "?"
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
        devis_id=body.devis_id,
        contrat_id=body.contrat_id,
        auteur_id=user.id,
    )
    session.add(n)
    session.commit()
    session.refresh(n)
    nr = NotationRead.model_validate(n)
    nr.auteur_nom = f"{user.prenom} {user.nom}"
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
    devis_list = session.exec(
        select(DevisPrestataire).where(DevisPrestataire.prestataire_id == p_id, DevisPrestataire.actif == True)
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
            "devis_id": n.devis_id, "contrat_id": n.contrat_id,
            "auteur_nom": f"{auteur.prenom} {auteur.nom}" if auteur else "?",
            "cree_le": n.cree_le.isoformat(),
        })

    prest_data = _prest_to_read(p).model_dump()
    return {
        **prest_data,
        "contrats": [ContratRead.model_validate(c).model_dump() for c in contrats],
        "devis": [{
            "id": d.id, "titre": d.titre, "statut": d.statut,
            "date_prestation": d.date_prestation.isoformat() if d.date_prestation else None,
            "montant_estime": d.montant_estime, "perimetre": d.perimetre,
        } for d in devis_list],
        "notations": notations_read,
        "note_moyenne": note_moy,
        "nb_notations": len(notations),
        "nb_contrats": len(contrats),
        "nb_devis": len(devis_list),
        "prochaines_visites": [
            {"contrat": c.libelle, "date": c.prochaine_visite.isoformat()}
            for c in contrats if c.prochaine_visite
        ],
    }

