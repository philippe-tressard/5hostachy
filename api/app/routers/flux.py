"""Router flux — agrégation temps réel pour le tableau de bord « pouls »."""
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import (
    ContratEntretien,
    Copropriete,
    DevisPrestataire,
    Evenement,
    Notification,
    OptionSondage,
    Prestataire,
    Publication,
    PublicationEvolution,
    RoleUtilisateur,
    Sondage,
    Ticket,
    TicketEvolution,
    Utilisateur,
    VoteSondage,
)

router = APIRouter(prefix="/flux", tags=["flux"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_perimetres(perimetre: Optional[str]) -> list[str]:
    if not perimetre:
        return ["résidence"]
    return [s.strip() for s in perimetre.split(",") if s.strip()]


def _user_bat_codes(user: Utilisateur) -> set[str]:
    codes: set[str] = set()
    if user.batiment_id:
        codes.add(f"bat:{user.batiment_id}")
    return codes


def _is_visible(perimetres: list[str], user: Utilisateur) -> bool:
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    if any(p.lower() in ("résidence", "parking", "cave", "aful") for p in perimetres):
        return True
    bat_codes = _user_bat_codes(user)
    return bool(bat_codes & {p.lower() for p in perimetres})


def _auteur_nom(session: Session, uid: Optional[int]) -> Optional[str]:
    if not uid:
        return None
    u = session.get(Utilisateur, uid)
    return f"{u.prenom} {u.nom}" if u else None


def _strip_html(text: Optional[str], max_len: int = 120) -> Optional[str]:
    """Retire les balises HTML et tronque pour un résumé texte."""
    if not text:
        return None
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0] + "…"
    return clean


# ── endpoint ─────────────────────────────────────────────────────────────────

class FluxItem(BaseModel):
    type: str            # ticket_resolu, ticket_ouvert, publication, evenement, devis, sondage_clos, sondage_ouvert
    date: datetime
    titre: str
    detail: Optional[str] = None
    badges: list[str] = []
    icon: str = ""
    lien: Optional[str] = None
    meta: dict = {}


class FluxSante(BaseModel):
    tickets_ouverts: int = 0
    tickets_urgents: int = 0
    resolution_moyenne_heures: Optional[float] = None
    sondages_actifs: int = 0
    prochains: list[dict] = []


class FluxResponse(BaseModel):
    items: list[FluxItem] = []
    sante: FluxSante = FluxSante()


@router.get("", response_model=FluxResponse)
def get_flux(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    items: list[FluxItem] = []
    now = datetime.utcnow()
    since = now - timedelta(days=30)
    can_see_ag = user.has_role(
        RoleUtilisateur.propriétaire,
        RoleUtilisateur.conseil_syndical,
        RoleUtilisateur.admin,
    )

    # ── 1. Tickets : changements de statut récents ──────────────────────────
    evols = session.exec(
        select(TicketEvolution, Ticket)
        .join(Ticket, TicketEvolution.ticket_id == Ticket.id)
        .where(TicketEvolution.type == "etat", TicketEvolution.cree_le >= since)
        .order_by(TicketEvolution.cree_le.desc())
    ).all()
    for evol, tk in evols:
        perims = _parse_perimetres(
            ",".join(tk.perimetre_cible) if tk.perimetre_cible else None
        ) if tk.perimetre_cible else (
            [f"bat:{tk.batiment_id}"] if tk.batiment_id else ["résidence"]
        )
        if not _is_visible(perims, user):
            continue
        nouveau = evol.nouveau_statut or ""
        if nouveau == "résolu":
            duree = None
            if tk.ferme_le and tk.cree_le:
                duree = round(
                    (tk.ferme_le - tk.cree_le).total_seconds() / 3600, 1
                )
            items.append(FluxItem(
                type="ticket_resolu",
                date=evol.cree_le,
                titre=tk.titre,
                detail=f"Résolu{f' en {duree}h' if duree else ''}",
                icon="✅",
                badges=[f"#{tk.numero}", tk.categorie],
                lien=f"/tickets",
                meta={"ticket_id": tk.id, "duree_h": duree},
            ))
        elif nouveau in ("ouvert", "en_cours"):
            items.append(FluxItem(
                type="ticket_ouvert",
                date=evol.cree_le,
                titre=tk.titre,
                detail=f"{'Ouvert' if nouveau == 'ouvert' else 'Pris en charge'}",
                icon="🎫" if nouveau == "ouvert" else "🔧",
                badges=[f"#{tk.numero}", tk.categorie],
                lien=f"/tickets",
                meta={"ticket_id": tk.id},
            ))

    # Tickets récemment créés (sans évolution)
    new_tickets = session.exec(
        select(Ticket)
        .where(Ticket.cree_le >= since)
        .order_by(Ticket.cree_le.desc())
    ).all()
    evol_ticket_ids = {tk.id for _, tk in evols}
    for tk in new_tickets:
        if tk.id in evol_ticket_ids:
            continue
        perims = (
            list(tk.perimetre_cible) if tk.perimetre_cible
            else ([f"bat:{tk.batiment_id}"] if tk.batiment_id else ["résidence"])
        )
        if not _is_visible(perims, user):
            continue
        items.append(FluxItem(
            type="ticket_ouvert",
            date=tk.cree_le,
            titre=tk.titre,
            detail="Nouveau ticket",
            icon="🎫",
            badges=[f"#{tk.numero}", tk.categorie],
            lien="/tickets",
            meta={"ticket_id": tk.id},
        ))

    # ── 2. Publications ─────────────────────────────────────────────────────
    pubs = session.exec(
        select(Publication)
        .where(Publication.cree_le >= since, Publication.brouillon == False, Publication.archivee == False)
        .order_by(Publication.cree_le.desc())
    ).all()
    for p in pubs:
        perims = (
            list(p.perimetre_cible) if p.perimetre_cible
            else (
                [f"bat:{p.batiment_id}"] if p.batiment_id
                else _parse_perimetres(p.perimetre)
            )
        )
        if not _is_visible(perims, user):
            continue
        badges = []
        if p.epingle:
            badges.append("📌 Épinglé")
        if p.urgente:
            badges.append("🔴 Urgent")
        if p.statut:
            labels = {"en_cours": "En cours", "resolu": "Résolu", "annule": "Annulé"}
            badges.append(labels.get(p.statut, p.statut))
        auteur = _auteur_nom(session, p.auteur_id)
        contenu_extrait = _strip_html(p.contenu) if hasattr(p, 'contenu') and p.contenu else ""
        detail_parts = [x for x in [auteur, contenu_extrait] if x]
        items.append(FluxItem(
            type="publication",
            date=p.publiee_le or p.cree_le,
            titre=p.titre,
            detail=" — ".join(detail_parts) if detail_parts else None,
            icon="📰",
            badges=badges,
            lien="/actualites",
            meta={"pub_id": p.id, "epingle": p.epingle, "urgente": p.urgente},
        ))

    # ── 3. Événements calendrier ────────────────────────────────────────────
    evts = session.exec(
        select(Evenement)
        .where(Evenement.archivee == False, Evenement.affichable == True)
        .where(Evenement.debut >= since)
        .order_by(Evenement.debut.desc())
    ).all()
    type_emoji = {
        "travaux": "🔨", "coupure": "⚡", "ag": "🏛️",
        "maintenance": "🔧", "maintenance_recurrente": "🔧", "autre": "📌",
    }
    PERIMETRE_LABELS = {
        "résidence": "Copropriété entière",
        "parking": "Parking", "cave": "Cave", "aful": "AFUL",
    }
    for i in range(1, 10):
        PERIMETRE_LABELS[f"bat:{i}"] = f"Bât. {i}"

    def _perimetre_label(perims: list[str]) -> str:
        return " · ".join(PERIMETRE_LABELS.get(p, p) for p in perims)

    for ev in evts:
        if ev.type == "ag" and not can_see_ag:
            continue
        perims = _parse_perimetres(ev.perimetre)
        if not _is_visible(perims, user):
            continue
        prest_name = None
        if ev.prestataire_id:
            p = session.get(Prestataire, ev.prestataire_id)
            if p:
                prest_name = p.nom
        badges_ev = [ev.type]
        if prest_name:
            badges_ev.append(prest_name)
        # Déterminer si l'événement concerne le bâtiment de l'utilisateur
        user_bat = user.batiment_id
        concerne_bat = False
        if user_bat:
            bat_codes = {f"bat:{user_bat}"}
            concerne_bat = bool(bat_codes & {p.lower() for p in perims}) or any(
                p.lower() in ("résidence", "parking", "cave", "aful") for p in perims
            )
        items.append(FluxItem(
            type="evenement",
            date=ev.debut,
            titre=ev.titre,
            detail=_strip_html(ev.description),
            icon=type_emoji.get(ev.type, "📌"),
            badges=badges_ev,
            lien="/calendrier",
            meta={
                "ev_id": ev.id, "type": ev.type, "lieu": ev.lieu,
                "perimetre": _perimetre_label(perims),
                "prestataire": prest_name,
                "debut": ev.debut.isoformat() if ev.debut else None,
                "fin": ev.fin.isoformat() if ev.fin else None,
                "concerne_mon_batiment": concerne_bat,
            },
        ))

    # ── 4. Devis (changements de statut) ────────────────────────────────────
    devis_list = session.exec(
        select(DevisPrestataire, Prestataire)
        .join(Prestataire, DevisPrestataire.prestataire_id == Prestataire.id)
        .where(DevisPrestataire.actif == True, DevisPrestataire.affichable == True)
        .order_by(DevisPrestataire.id.desc())
    ).all()
    devis_labels = {
        "en_attente": "En attente", "accepte": "Accepté",
        "refuse": "Refusé", "realise": "Réalisé",
    }
    devis_icons = {
        "en_attente": "📋", "accepte": "✅", "refuse": "❌", "realise": "🏁",
    }
    for dv, prest in devis_list:
        perims = _parse_perimetres(dv.perimetre)
        if not _is_visible(perims, user):
            continue
        montant = f"{dv.montant_estime:,.0f} €".replace(",", " ") if dv.montant_estime else None
        items.append(FluxItem(
            type="devis",
            date=datetime.combine(dv.date_prestation, datetime.min.time()) if dv.date_prestation else now,
            titre=dv.titre,
            detail=f"{prest.nom}{f' · {montant}' if montant else ''}",
            icon=devis_icons.get(dv.statut, "📋"),
            badges=[devis_labels.get(dv.statut, dv.statut)],
            lien="/prestataires",
            meta={"devis_id": dv.id, "statut": dv.statut, "montant": dv.montant_estime},
        ))

    # ── 5. Sondages ─────────────────────────────────────────────────────────
    sondages = session.exec(
        select(Sondage).where(Sondage.cree_le >= since).order_by(Sondage.cree_le.desc())
    ).all()
    for s in sondages:
        cloture = s.cloture_forcee or (s.cloture_le is not None and s.cloture_le < now)
        nb_votants = session.exec(
            select(func.count(func.distinct(VoteSondage.user_id)))
            .where(VoteSondage.sondage_id == s.id)
        ).one()
        if cloture:
            # Résultat : trouver l'option gagnante
            top_option = session.exec(
                select(OptionSondage.libelle, func.count(VoteSondage.id).label("cnt"))
                .join(VoteSondage, VoteSondage.option_id == OptionSondage.id)
                .where(OptionSondage.sondage_id == s.id)
                .group_by(OptionSondage.libelle)
                .order_by(func.count(VoteSondage.id).desc())
            ).first()
            gagnant = top_option[0] if top_option else None
            items.append(FluxItem(
                type="sondage_clos",
                date=s.cloture_le or s.cree_le,
                titre=s.question,
                detail=f"Clos · {nb_votants} vote{'s' if nb_votants > 1 else ''}{f' · Résultat : {gagnant}' if gagnant else ''}",
                icon="🗳️",
                badges=["Clôturé"],
                lien=f"/sondages/{s.id}",
                meta={"sondage_id": s.id, "nb_votants": nb_votants, "gagnant": gagnant},
            ))
        else:
            items.append(FluxItem(
                type="sondage_ouvert",
                date=s.cree_le,
                titre=s.question,
                detail=f"{nb_votants} vote{'s' if nb_votants > 1 else ''}{f' · Clôture le {s.cloture_le.strftime('%d/%m')}' if s.cloture_le else ''}",
                icon="📊",
                badges=["En cours"],
                lien=f"/sondages/{s.id}",
                meta={"sondage_id": s.id, "nb_votants": nb_votants},
            ))

    # ── Tri global par date décroissante ────────────────────────────────────
    items.sort(key=lambda x: x.date, reverse=True)

    # ── Santé résidence ─────────────────────────────────────────────────────
    all_tickets = session.exec(select(Ticket)).all()
    ouverts = [t for t in all_tickets if t.statut in ("ouvert", "en_cours")]
    urgents = [t for t in ouverts if t.categorie == "urgence"]

    # Temps moyen de résolution sur les 30 derniers jours
    resolus_recents = [
        t for t in all_tickets
        if t.statut == "résolu" and t.ferme_le and t.cree_le
        and t.ferme_le >= since
    ]
    resolution_moy = None
    if resolus_recents:
        durees = [(t.ferme_le - t.cree_le).total_seconds() / 3600 for t in resolus_recents]
        resolution_moy = round(sum(durees) / len(durees), 1)

    sondages_actifs = session.exec(
        select(func.count(Sondage.id)).where(
            Sondage.cloture_forcee == False,
        )
    ).one()

    # Prochains événements
    prochains_evts = session.exec(
        select(Evenement)
        .where(Evenement.debut >= now, Evenement.archivee == False)
        .order_by(Evenement.debut.asc())
    ).all()
    # Prochaines échéances contrats
    prochaines_visites = session.exec(
        select(ContratEntretien, Prestataire)
        .join(Prestataire, ContratEntretien.prestataire_id == Prestataire.id)
        .where(ContratEntretien.actif == True, ContratEntretien.prochaine_visite != None)
        .order_by(ContratEntretien.prochaine_visite.asc())
    ).all()
    # Échéance assurance
    copro = session.exec(select(Copropriete)).first()

    prochains: list[dict] = []
    for ev in prochains_evts[:5]:
        if ev.type == "ag" and not can_see_ag:
            continue
        prochains.append({
            "date": ev.debut.isoformat(),
            "titre": ev.titre,
            "type": "evenement",
            "icon": type_emoji.get(ev.type, "📌"),
        })
    for ct, prest in prochaines_visites[:3]:
        prochains.append({
            "date": ct.prochaine_visite.isoformat() if ct.prochaine_visite else "",
            "titre": f"{ct.libelle} — {prest.nom}",
            "type": "contrat",
            "icon": "🔧",
        })
    if copro and copro.assurance_echeance:
        prochains.append({
            "date": copro.assurance_echeance.isoformat(),
            "titre": f"Échéance assurance {copro.assurance_compagnie or ''}".strip(),
            "type": "assurance",
            "icon": "🛡️",
        })
    prochains.sort(key=lambda x: x.get("date", ""))
    prochains = prochains[:8]

    sante = FluxSante(
        tickets_ouverts=len(ouverts),
        tickets_urgents=len(urgents),
        resolution_moyenne_heures=resolution_moy,
        sondages_actifs=sondages_actifs,
        prochains=prochains,
    )

    return FluxResponse(items=items, sante=sante)
