"""Questions au règlement de copropriété — Espace CS › Règlement (03/10/2026).

Le conseil syndical y charge le texte de travail du règlement (Markdown), pose
la question d'un résident, relit l'historique et publie une réponse relue dans
la FAQ. Tout est réservé au conseil syndical et à l'administration : l'appel est
facturé, et la réponse est un avis à relayer après relecture, pas un texte que
le résident lirait seul (`standards/03` §1 — l'écran masque, le serveur refuse).

La logique vit dans `utils/question_reglement/` ; ce routeur ne fait que la servir.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, col, func, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.models.reglement import QuestionReglement, TexteReglement
from app.routers.faq import FaqItemCreate, creer_entree
from app.utils.limiter import LIMITE_APPEL_FACTURE, limiter
from app.utils.lecture import lire_objet
from app.utils.noms import nom_affiche
from app.utils.question_reglement.format import MAX_CARACTERES_QUESTION, VERDICTS
from app.utils.question_reglement.production import disponible, repondre
from app.utils.question_reglement.texte import MAX_CARACTERES_TEXTE, charger, texte_en_vigueur
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/reglement", tags=["reglement"])


# ── Schémas propres à cet écran ────────────────────────────────────────────


class TexteReglementRead(BaseModel):
    id: int
    titre: str
    nom_fichier: str
    nb_caracteres: int
    charge_par: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True


class EtatReglement(BaseModel):
    """Ce que l'onglet lit en arrivant."""

    #: L'assistant peut-il répondre ? — décidé par le serveur.
    disponible: bool
    texte: Optional[TexteReglementRead] = None
    nb_versions: int


class TexteCharge(BaseModel):
    """Le fichier lu par le navigateur, envoyé comme texte."""

    nom_fichier: str = Field(min_length=1, max_length=255)
    contenu: str = Field(max_length=MAX_CARACTERES_TEXTE + 10_000)


class ExtraitRead(BaseModel):
    citation: str
    reference: str = ""
    apport: str = ""
    verifie: bool
    page: Optional[str] = None
    acte: Optional[str] = None


class QuestionCreate(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_CARACTERES_QUESTION)


class QuestionReglementRead(BaseModel):
    id: int
    question: str
    verdict: str
    verdict_libelle: str
    reponse: str
    reserves: Optional[str] = None
    extraits: list[ExtraitRead]
    texte_id: int
    #: La réponse a-t-elle lu le texte EN VIGUEUR ? — sinon l'écran le signale.
    texte_en_vigueur: bool
    texte_charge_le: Optional[datetime] = None
    auteur_nom: Optional[str] = None
    modele: Optional[str] = None
    cout_usd: Optional[str] = None
    faq_item_id: Optional[int] = None
    cree_le: datetime

    class Config:
        from_attributes = True


# ── Lectures ───────────────────────────────────────────────────────────────


def _noms(session: Session, ids: set[Optional[int]]) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    gens = session.exec(select(Utilisateur).where(col(Utilisateur.id).in_(ids))).all()
    return {u.id: nom_affiche(u.prenom, u.nom) for u in gens}


def _lire_texte(session: Session, texte: TexteReglement) -> TexteReglementRead:
    noms = _noms(session, {texte.charge_par_id})
    return lire_objet(
        TexteReglementRead,
        texte,
        nb_caracteres=len(texte.contenu),
        charge_par=noms.get(texte.charge_par_id),
    )


def _lire_questions(
    session: Session, lignes: list[QuestionReglement]
) -> list[QuestionReglementRead]:
    en_vigueur = texte_en_vigueur(session)
    textes = {
        t.id: t.cree_le
        for t in session.exec(
            select(TexteReglement).where(col(TexteReglement.id).in_({q.texte_id for q in lignes}))
        ).all()
    }
    noms = _noms(session, {q.auteur_id for q in lignes})
    return [
        lire_objet(
            QuestionReglementRead,
            q,
            verdict_libelle=VERDICTS.get(q.verdict, q.verdict),
            extraits=[ExtraitRead(**e) for e in json.loads(q.extraits_json or "[]")],
            texte_en_vigueur=bool(en_vigueur and en_vigueur.id == q.texte_id),
            texte_charge_le=textes.get(q.texte_id),
            auteur_nom=noms.get(q.auteur_id),
        )
        for q in lignes
    ]


@router.get("", response_model=EtatReglement)
def etat(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """L'assistant est-il prêt, et quel texte est en vigueur ? — rien de la configuration."""
    texte = texte_en_vigueur(session)
    return EtatReglement(
        disponible=disponible(session),
        texte=_lire_texte(session, texte) if texte else None,
        nb_versions=session.exec(select(func.count()).select_from(TexteReglement)).one(),
    )


@router.get("/questions", response_model=list[QuestionReglementRead])
def lister_questions(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """L'historique, la plus récente d'abord — une question déjà posée ne se repaie pas."""
    lignes = session.exec(
        select(QuestionReglement).order_by(
            col(QuestionReglement.cree_le).desc(), col(QuestionReglement.id).desc()
        )
    ).all()
    return _lire_questions(session, list(lignes))


# ── Gestes ─────────────────────────────────────────────────────────────────


@router.post("/textes", response_model=TexteReglementRead)
def charger_texte(
    body: TexteCharge,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Charge une version du texte. Le même contenu que la version en vigueur
    ne crée rien : elle est rendue telle quelle."""
    version, _ = charger(session, body.contenu, body.nom_fichier, user.id)
    return _lire_texte(session, version)


@router.post(
    "/questions",
    response_model=QuestionReglementRead,
    status_code=201,
    summary="Poser une question au règlement (CS/Admin)",
)
@limiter.limit(LIMITE_APPEL_FACTURE)
async def poser_question(
    request: Request,
    body: QuestionCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """🔴 Le geste est manuel et facturé : rien d'autre n'appelle cette route
    que le bouton « Poser la question » d'un membre du conseil."""
    ligne = await repondre(session, body.question, user.id)
    return _lire_questions(session, [ligne])[0]


@router.post("/questions/{question_id}/faq", response_model=QuestionReglementRead)
def publier_dans_la_faq(
    question_id: int,
    body: FaqItemCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Publie dans la FAQ la réponse RELUE — le texte envoyé est celui que le
    conseil a corrigé, jamais la réponse brute de l'assistant."""
    q = ou_404(session, QuestionReglement, question_id, "Question")
    if q.faq_item_id:
        raise HTTPException(409, "Cette réponse est déjà publiée dans la FAQ.")
    item = creer_entree(session, body)
    q.faq_item_id = item.id
    session.add(q)
    session.commit()
    session.refresh(q)
    return _lire_questions(session, [q])[0]
