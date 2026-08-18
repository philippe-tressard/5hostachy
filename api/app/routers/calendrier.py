"""Router calendrier — événements de la résidence."""
import json
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import Evenement, Notification, TypeEvenement, Utilisateur, RoleUtilisateur, Prestataire, ContratEntretien
from app.models.evenement import EvenementEvolution
from app.routers.calendrier_courriels import notifier_canaux
from app.routers.calendrier_historique import (
    CHAMPS_CORRIGEABLES,
    EvolutionEvenementRead,
    _evolutions_de,
)
from app.utils.liens import lien_element
from app.utils.photos import parse_photos, photos_internes
from app.utils.visibility import evenement_visible

router = APIRouter(prefix="/calendrier", tags=["calendrier"])



class EvenementCreate(BaseModel):
    titre: str
    description: Optional[str] = None
    type: TypeEvenement = TypeEvenement.autre
    lieu: Optional[str] = None
    debut: datetime
    fin: Optional[datetime] = None
    perimetre: str = "résidence"
    batiment_id: Optional[int] = None
    statut_kanban: Optional[str] = None
    prestataire_id: Optional[int] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: bool = True
    epingle: bool = False
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None
    envoyer_cs: Optional[bool] = None
    # Pièces jointes déjà téléversées via POST /uploads/fichier. Les fournir dès
    # la création est ce qui permet à l'e-mail syndic/CS de partir avec.
    photos_urls: list[str] = []
    fichiers_urls: list[str] = []


class EvenementRead(BaseModel):
    id: int
    titre: str
    description: Optional[str] = None
    type: str
    lieu: Optional[str] = None
    debut: datetime
    fin: Optional[datetime] = None
    perimetre: str
    batiment_id: Optional[int] = None
    auteur_id: int
    auteur_nom: Optional[str] = None
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None
    statut_kanban: Optional[str] = None
    prestataire_id: Optional[int] = None
    prestataire_nom: Optional[str] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: bool = True
    archivee: bool = False
    epingle: bool = False
    # Stocké en colonne comme un tableau JSON (convention Ticket.photos_urls) ;
    # exposé en liste pour que le front n'ait rien à désérialiser.
    photos_urls: list[str] = []
    fichiers_urls: list[str] = []
    #  L'HISTORIQUE, livré avec l'événement : le fil est court (quelques entrées)
    #  et la carte l'affiche dès qu'elle est dépliée. Un second appel par
    #  événement aurait fait autant de requêtes que de lignes à l'écran.
    evolutions: list["EvolutionEvenementRead"] = []

    class Config:
        from_attributes = True


class EvenementUpdate(BaseModel):
    titre: Optional[str] = None
    description: Optional[str] = None
    type: Optional[TypeEvenement] = None
    lieu: Optional[str] = None
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    perimetre: Optional[str] = None
    batiment_id: Optional[int] = None
    statut_kanban: Optional[str] = None
    archivee: Optional[bool] = None
    prestataire_id: Optional[int] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: Optional[bool] = None
    epingle: Optional[bool] = None
    # Sert uniquement à RETIRER des photos : l'ajout passe par l'endpoint
    # d'upload, seul capable de valider et de redimensionner le fichier.
    photos_urls: Optional[list[str]] = None
    # Idem pour les documents : POST /uploads/fichier valide le type MIME, ce
    # champ ne fait que fixer la liste finale.
    fichiers_urls: Optional[list[str]] = None


_ROLES_AG = (RoleUtilisateur.propriétaire, RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)


def _ev_to_read(ev: Evenement, session: Session) -> EvenementRead:
    # La colonne stocke un tableau JSON, le schéma expose une liste : on convertit
    # AVANT la validation, sinon pydantic reçoit une chaîne là où il attend une
    # liste et rejette l'événement entier.
    brut = ev.model_dump()
    brut["photos_urls"] = parse_photos(ev.photos_urls)
    brut["fichiers_urls"] = parse_photos(ev.fichiers_urls)
    data = EvenementRead.model_validate(brut)
    data.evolutions = _evolutions_de(ev.id, session)
    auteur = session.get(Utilisateur, ev.auteur_id)
    data.auteur_nom = f"{auteur.prenom} {auteur.nom}" if auteur else "?"
    if ev.prestataire_id:
        prest = session.get(Prestataire, ev.prestataire_id)
        data.prestataire_nom = prest.nom if prest else None
    return data


@router.get("", response_model=list[EvenementRead])
def list_evenements(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    stmt = select(Evenement).order_by(Evenement.debut)
    evenements = session.exec(stmt).all()
    # CS/admin : accès complet (ils gèrent ici les maintenances récurrentes → ne pas
    # les masquer via evenement_visible). Non-CS/admin : filtrage périmètre + AG +
    # maintenance_recurrente interne, aligné sur flux.py — sinon un résident du bât. 2
    # voyait les événements ciblés bât. 1.
    is_cs = user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical)
    if not is_cs:
        evenements = [e for e in evenements if evenement_visible(e, user)]
    return [_ev_to_read(e, session) for e in evenements]


@router.get("/{ev_id}", response_model=EvenementRead)
def get_evenement(
    ev_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ev = session.get(Evenement, ev_id)
    if not ev:
        raise HTTPException(404, "Événement introuvable")
    # Contrôle complet périmètre + rôle AG (cf. list_evenements) : empêche l'accès
    # direct à /calendrier/{id} d'un événement ciblant un autre bâtiment. CS/admin :
    # accès total (gestion des maintenances récurrentes incluse).
    if not user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical) \
            and not evenement_visible(ev, user):
        raise HTTPException(403, "Accès refusé")
    return _ev_to_read(ev, session)


@router.post("", response_model=EvenementRead, status_code=201)
def create_evenement(
    body: EvenementCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    champs = body.model_dump(exclude_none=True)
    # Les colonnes stockent un tableau JSON, le schéma reçoit une liste :
    # convertir ici, sinon SQLite reçoit une liste Python et lève à l'insertion.
    # `photos_internes` écarte toute URL qui ne vient pas de notre endpoint
    # d'upload — une pièce jointe pointant vers un site tiers révélerait l'IP de
    # chaque lecteur, avec un contenu hors de notre contrôle.
    for champ in ("photos_urls", "fichiers_urls"):
        champs[champ] = json.dumps(
            photos_internes(champs.get(champ) or []), ensure_ascii=False
        )
    ev = Evenement(**champs, auteur_id=user.id)
    session.add(ev)
    session.flush()

    # Notifier les résidents — urgences immédiates
    if body.type in (TypeEvenement.coupure, TypeEvenement.travaux):
        residents = session.exec(
            select(Utilisateur).where(Utilisateur.actif == True)
        ).all()
        for r in residents:
            session.add(Notification(
                destinataire_id=r.id,
                type="calendrier",
                titre=f"📅 {body.type.value.capitalize()} : {body.titre}",
                corps=body.description or "",
                # `session.flush()` juste au-dessus a attribué l'id : le lecteur
                # arrive sur l'événement annoncé, pas en haut du calendrier.
                lien=lien_element("ev", ev.id),
                urgente=(body.type == TypeEvenement.coupure),
            ))

    session.commit()
    session.refresh(ev)

    #  Les envois vivent dans `calendrier_courriels` : ils servent AUSSI une
    #  entrée d'Historique depuis le 18/08/2026, et une seconde copie du bloc
    #  aurait divergé au premier template modifié.
    notifier_canaux(
        ev, user, session, background_tasks,
        whatsapp=bool(body.partager_whatsapp),
        syndic=bool(body.envoyer_syndic),
        cs=bool(body.envoyer_cs),
    )

    return _ev_to_read(ev, session)


def _next_visit_date(contrat: ContratEntretien, from_date: date) -> date | None:
    """Calcule la prochaine visite à partir de la fréquence du contrat."""
    ft, fv = contrat.frequence_type, contrat.frequence_valeur
    if not ft or not fv:
        return None
    if ft == "semaines":
        return from_date + timedelta(weeks=fv)
    if ft == "mois":
        month = from_date.month + fv
        year = from_date.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(from_date.day, 28)
        return date(year, month, day)
    if ft == "fois_par_an":
        interval_months = max(1, 12 // fv)
        month = from_date.month + interval_months
        year = from_date.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(from_date.day, 28)
        return date(year, month, day)
    return None


def _update_contrat_prochaine_visite(ev: Evenement, session: Session) -> None:
    """Met à jour prochaine_visite du contrat lié quand un événement maintenance_recurrente passe en terminé."""
    if ev.type != TypeEvenement.maintenance_recurrente or not ev.prestataire_id:
        return
    contrats = session.exec(
        select(ContratEntretien).where(
            ContratEntretien.prestataire_id == ev.prestataire_id,
            ContratEntretien.actif == True,
        )
    ).all()
    if not contrats:
        return
    # Match par libellé dans le titre (format "Prestataire — Libellé")
    best = None
    for c in contrats:
        if c.libelle and c.libelle.lower() in ev.titre.lower():
            best = c
            break
    if not best:
        best = contrats[0] if len(contrats) == 1 else None
    if not best:
        return
    next_date = _next_visit_date(best, ev.debut.date() if isinstance(ev.debut, datetime) else ev.debut)
    if next_date:
        best.prochaine_visite = next_date
        session.add(best)


@router.patch("/{ev_id}", response_model=EvenementRead)
def update_evenement(
    ev_id: int,
    body: EvenementUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    ev = session.get(Evenement, ev_id)
    if not ev:
        raise HTTPException(404, "Événement introuvable")
    data = body.model_dump(exclude_unset=True)
    if data.get('archivee') is True and ev.statut_kanban != "termine":
        raise HTTPException(422, "Seuls les événements terminés peuvent être archivés")
    for champ in ("photos_urls", "fichiers_urls"):
        if champ in data:
            # Liste → tableau JSON, en ne conservant que nos propres URLs (cf.
            # photos_internes). Ces champs ne servent qu'à retirer des fichiers.
            data[champ] = json.dumps(photos_internes(data[champ] or []))
    old_statut = ev.statut_kanban
    #  L'état d'AVANT, relevé avant la boucle : c'est lui qui dit ce qui a
    #  réellement changé. Sans ce relevé, réenregistrer une valeur identique
    #  s'inscrirait quand même dans l'Historique.
    avant = {champ: getattr(ev, champ, None) for champ in data}
    for k, v in data.items():
        setattr(ev, k, v)
    ev.mis_a_jour_le = datetime.utcnow()
    # Si le statut passe à "termine", mettre à jour la prochaine visite du contrat
    if data.get('statut_kanban') == 'termine' and old_statut != 'termine':
        _update_contrat_prochaine_visite(ev, session)

    #  🔴 LE CHANGEMENT DE COLONNE EST UNE TRANSITION, LE RESTE UNE CORRECTION.
    #
    #  Le Kanban EST le workflow d'un événement — il répond à « où en est cet
    #  objet ? ». Le faire avancer laisse donc un jalon daté dans l'Historique,
    #  avec son avant et son après ; corriger un titre ou un lieu n'en laisse pas.
    #  C'est la même distinction que sur les tickets (#431) et les publications
    #  (#433), et elle porte ici la même forme de ligne : sans `ancien_statut` ni
    #  `nouveau_statut`, une correction ne dessine aucune étape de suivi.
    if 'statut_kanban' in data and data['statut_kanban'] != old_statut:
        session.add(EvenementEvolution(
            evenement_id=ev.id,
            type="etat",
            ancien_statut=old_statut,
            nouveau_statut=ev.statut_kanban,
            auteur_id=user.id,
            cree_le=datetime.utcnow(),
        ))
    corrections = [
        libelle
        for champ, libelle in CHAMPS_CORRIGEABLES.items()
        if champ in data and data[champ] != avant.get(champ)
    ]
    if corrections:
        session.add(EvenementEvolution(
            evenement_id=ev.id,
            type="commentaire",
            contenu="Correction : " + " ; ".join(corrections),
            auteur_id=user.id,
            cree_le=datetime.utcnow(),
        ))
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return _ev_to_read(ev, session)


@router.delete("/{ev_id}", status_code=204)
def delete_evenement(
    ev_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    ev = session.get(Evenement, ev_id)
    if not ev:
        raise HTTPException(404, "Événement introuvable")
    session.delete(ev)
    session.commit()
