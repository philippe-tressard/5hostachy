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
from app.utils.archivage import est_archivable, seuil_archivage_jours
from app.utils.liens import lien_element
from app.utils.suppression_liee import flush_si_necessaire, supprimer_documents_de
from app.utils.photos import parse_photos, photos_internes
from app.utils.visibility import evenement_visible
from app.utils.noms import nom_affiche
from app.utils.corrections import contenu_correction

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
    #  La SOURCE d'une visite pré-remplie — le rapprochement se faisait sur le
    #  titre littéral, qu'un renommage faisait perdre (#605, point 2).
    contrat_id: Optional[int] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: bool = True
    epingle: bool = False
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None
    envoyer_cs: Optional[bool] = None
    #  « Envoyer une copie à … » — la 4e case de la Diffusion (31/08/2026).
    #  Elle s'affichait sur cet écran sans être lue nulle part. Le destinataire
    #  est l'auteur de l'OBJET, pas celui qui écrit : le CS qui reprend un
    #  ticket décide alors de notifier le résident qui l'a ouvert.
    envoyer_auteur: Optional[bool] = None
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
    contrat_id: Optional[int] = None
    prestataire_nom: Optional[str] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: bool = True
    #: État EFFECTIF : archivé à la main, **ou** par la règle du site — 30 jours
    #: après la fin de l'événement, immédiat s'il est annulé, jamais s'il est
    #: épinglé (`utils/archivage`, #515). C'est ce que l'écran emploie.
    #:
    #: 🔴 Le calendrier le calculait LUI-MÊME, et divergeait sur trois points :
    #: l'annulation n'y était pas immédiate, l'épinglage n'y protégeait pas, et
    #: surtout le délai réglé en administration ne l'atteignait jamais — la clé
    #: `archivage_delai_jours` n'est pas dans la liste blanche de `GET /config`,
    #: donc l'écran tournait depuis toujours sur son défaut en dur.
    archivee: bool = False
    #: La DÉCISION HUMAINE, seule — la colonne. Même séparation que l'affiche de
    #: hall : elle dit si « désarchiver » aurait un effet.
    archivee_manuellement: bool = False
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
    #  La colonne d'abord — `model_validate` a déjà posé `archivee` depuis elle —
    #  puis l'état effectif par-dessus. L'ordre compte : l'inverse écraserait le
    #  calcul par la colonne.
    data.archivee_manuellement = ev.archivee
    data.archivee = est_archivable("evenement", ev, seuil_jours=seuil_archivage_jours(session))
    data.evolutions = _evolutions_de(ev.id, session)
    auteur = session.get(Utilisateur, ev.auteur_id)
    data.auteur_nom = nom_affiche(auteur.prenom, auteur.nom) if auteur else "?"
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
        auteur=bool(getattr(body, "envoyer_auteur", False)),
    )

    return _ev_to_read(ev, session)


#  Plafond d'un lot. Le pré-remplissage des prestataires en crée au plus quatre
#  par contrat, et le site en compte quelques dizaines : cent laisse une marge
#  large sans qu'une requête forgée puisse écrire dix mille lignes.
LOT_MAX = 100


class EvenementsLot(BaseModel):
    """Un pré-remplissage : plusieurs événements, tout ou rien."""

    evenements: list[EvenementCreate]


@router.post("/lot", response_model=list[EvenementRead], status_code=201)
def create_evenements_lot(
    body: EvenementsLot,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Crée plusieurs événements en UNE transaction — ou aucun (#605, point 3).

    🔴 POURQUOI. Le pré-remplissage du kanban écrivait en boucle depuis le
    navigateur :

        for (const ev of plan.aCreer) await calApi.create(ev);

    Un échec au 7ᵉ sur 20 laissait **six** événements créés, et l'écran affichait
    « Erreur lors de l'initialisation » sans dire lesquels. Le second passage en
    ignorait une partie — mais seulement si aucun titre n'avait bougé, la clé
    anti-doublon étant le titre littéral (point 2 du ticket, encore ouvert).

    Ici, `session.commit()` est appelé **une fois** : soit les vingt existent,
    soit aucun. Le geste redevient rejouable.

    ## 🔴 Ce que ce point d'entrée REFUSE, et pourquoi c'est le cœur du sujet

    **Aucune notification, aucune diffusion, jamais.** Un lot est un
    pré-remplissage silencieux ; en faire un canal, c'est offrir l'envoi de cent
    courriels ou messages WhatsApp en une requête.

    Deux refus, donc, plutôt qu'un silence :

    - un événement portant `partager_whatsapp`, `envoyer_syndic`, `envoyer_cs` ou
      `envoyer_auteur` est **rejeté** (422). Les ignorer serait pire : l'appelant
      croirait avoir diffusé.
    - un `coupure` ou un `travaux` est **rejeté** lui aussi. La création unitaire
      notifie tous les résidents pour ces deux types ; les créer ici sans
      notification produirait deux comportements pour un même type, selon le
      point d'entrée employé — exactement la divergence que ce dépôt traque.
    """
    if not body.evenements:
        raise HTTPException(422, "Aucun événement à créer.")
    if len(body.evenements) > LOT_MAX:
        raise HTTPException(422, f"Lot trop grand : {len(body.evenements)} > {LOT_MAX}.")

    canaux = ("partager_whatsapp", "envoyer_syndic", "envoyer_cs", "envoyer_auteur")
    for i, item in enumerate(body.evenements, start=1):
        if any(getattr(item, c, None) for c in canaux):
            raise HTTPException(
                422,
                f"Événement {i} : un lot ne diffuse pas. Retirer les canaux, ou "
                "créer cet événement un par un.",
            )
        if item.type in (TypeEvenement.coupure, TypeEvenement.travaux):
            raise HTTPException(
                422,
                f"Événement {i} : « {item.type.value} » notifie tous les résidents "
                "à la création unitaire. Le créer en lot le rendrait silencieux — "
                "passer par la création un par un.",
            )

    crees: list[Evenement] = []
    for item in body.evenements:
        champs = item.model_dump(exclude_none=True)
        #  Même conversion que la création unitaire, et pour la même raison :
        #  les colonnes stockent un tableau JSON, et `photos_internes` écarte
        #  toute URL qui ne vient pas de notre endpoint d'upload.
        for champ in ("photos_urls", "fichiers_urls"):
            champs[champ] = json.dumps(
                photos_internes(champs.get(champ) or []), ensure_ascii=False
            )
        for c in canaux:
            champs.pop(c, None)
        ev = Evenement(**champs, auteur_id=user.id)
        session.add(ev)
        crees.append(ev)

    #  UN seul commit — c'est tout l'objet de ce point d'entrée.
    session.commit()
    for ev in crees:
        session.refresh(ev)
    return [_ev_to_read(ev, session) for ev in crees]


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
            contenu=contenu_correction(corrections),
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
    #  🔴 L'ÉVÉNEMENT PARTAIT SEUL (#546, 30/08/2026). Deux tables le
    #  référencent, aucune n'était nettoyée : `evenement_evolution` (**NOT
    #  NULL** — tout l'historique) et `document`. Sans les clés — le régime
    #  actuel de la production — la suppression réussit et laisse des lignes
    #  orphelines ; celles de l'historique sont même irrécupérables, leur
    #  `evenement_id` étant obligatoire. Rien ne le signalait.
    #  Le `flush()` ordonne les DELETE ; le pourquoi vit dans
    #  `utils/suppression_liee.py`.
    evolutions = session.exec(
        select(EvenementEvolution).where(EvenementEvolution.evenement_id == ev_id)
    ).all()
    for evol in evolutions:
        session.delete(evol)
    n_docs = supprimer_documents_de(session, "evenement_id", ev_id)
    flush_si_necessaire(session, len(evolutions), n_docs)
    session.delete(ev)
    session.commit()
