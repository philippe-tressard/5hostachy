"""Flux — indicateurs « santé résidence » et agenda des prochaines échéances.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

Ce module ne produit **aucune** ligne de fil : il répond à l'autre question du
tableau de bord — « où en est-on ? » et « quoi ensuite ? ». C'est pour cela qu'il
date les événements sur `debut` là où le fil les date sur `cree_le`
(cf. `evenements.py`).
"""
from datetime import timedelta

from sqlalchemy import func
from sqlmodel import select

from app.models.core import (
    CommandeAcces,
    ConfigSite,
    ContratEntretien,
    Copropriete,
    Evenement,
    Prestataire,
    RoleUtilisateur,
    Sondage,
    StatutCommande,
    Ticket,
    Utilisateur,
)
from app.utils.visibility import evenement_visible

from app.utils.perimetres import perimetre_label
from .commun import ContexteFlux
from .evenements import TYPE_EMOJI, perimetres_evenement
from .schemas import FluxSante

#: Délai par défaut, en jours, avant qu'un ticket syndic soit relançable.
_RELANCE_SYNDIC_DEFAUT_J = 30
#: Bornes de l'agenda : par source, puis au total.
_MAX_EVENEMENTS = 15
_MAX_VISITES = 5
_MAX_PROCHAINS = 12


def _prochains(ctx: ContexteFlux) -> list[dict]:
    """Agenda « Prochaines échéances » : événements, visites de contrat, assurance."""
    prochains: list[dict] = []

    evts = ctx.session.exec(
        select(Evenement)
        .where(Evenement.debut >= ctx.now, ~Evenement.archivee)
        .order_by(Evenement.debut.asc())
    ).all()
    #  Filtrer AVANT de tronquer : la troncature portait sur la liste brute, donc
    #  15 événements invisibles en tête (les maintenances récurrentes générées par
    #  le Kanban le sont pour TOUS, y compris admin) suffisaient à vider l'agenda.
    visibles = [ev for ev in evts if evenement_visible(ev, ctx.user)]
    for ev in visibles[:_MAX_EVENEMENTS]:
        prest_nom = None
        if ev.prestataire_id:
            prest = ctx.session.get(Prestataire, ev.prestataire_id)
            if prest:
                prest_nom = prest.nom
        prochains.append({
            "id": f"ev_{ev.id}",
            "date": ev.debut.isoformat(),
            "titre": ev.titre,
            "type": "evenement",
            "icon": TYPE_EMOJI.get(ev.type, "📌"),
            "ev_type": ev.type,
            "description": ev.description,
            "lieu": ev.lieu,
            "perimetre": perimetre_label(perimetres_evenement(ev)),
            "prestataire": prest_nom,
            "fin": ev.fin.isoformat() if ev.fin else None,
            "statut_kanban": ev.statut_kanban,
        })

    visites = ctx.session.exec(
        select(ContratEntretien, Prestataire)
        .join(Prestataire, ContratEntretien.prestataire_id == Prestataire.id)
        .where(ContratEntretien.actif, ContratEntretien.prochaine_visite.is_not(None))
        .order_by(ContratEntretien.prochaine_visite.asc())
    ).all()
    for ct, prest in visites[:_MAX_VISITES]:
        prochains.append({
            "id": f"ct_{ct.id}",
            "date": ct.prochaine_visite.isoformat() if ct.prochaine_visite else "",
            "titre": f"{ct.libelle} — {prest.nom}",
            "type": "contrat",
            "icon": "🔧",
            "description": ct.notes,
            "prestataire": prest.nom,
        })

    copro = ctx.session.exec(select(Copropriete)).first()
    if copro and copro.assurance_echeance:
        prochains.append({
            "id": "assurance",
            "date": copro.assurance_echeance.isoformat(),
            "titre": f"Échéance assurance {copro.assurance_compagnie or ''}".strip(),
            "type": "assurance",
            "icon": "🛡️",
        })

    prochains.sort(key=lambda x: x.get("date", ""))
    return prochains[:_MAX_PROCHAINS]


def _validations_et_relances(ctx: ContexteFlux) -> tuple[int, int]:
    """Compteurs réservés au CS et aux admins — (validations en attente, relances syndic)."""
    if not ctx.user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        return 0, 0

    comptes_attente = ctx.session.exec(
        select(func.count(Utilisateur.id)).where(~Utilisateur.actif)
    ).one()
    commandes_attente = ctx.session.exec(
        select(func.count(CommandeAcces.id))
        .where(CommandeAcces.statut == StatutCommande.en_attente)
    ).one()

    # Tickets syndic éligibles à la relance (pas de modif depuis > délai)
    cfg_delai = ctx.session.exec(
        select(ConfigSite).where(ConfigSite.cle == "relance_syndic_delai_jours")
    ).first()
    delai_jours = int(cfg_delai.valeur) if cfg_delai else _RELANCE_SYNDIC_DEFAUT_J
    seuil = ctx.now - timedelta(days=delai_jours)
    relances = ctx.session.exec(
        select(func.count(Ticket.id)).where(
            Ticket.destinataire_syndic == True,  # noqa: E712  (colonne SQL, pas un booléen Python)
            Ticket.statut.notin_(["résolu", "annulé", "fermé"]),
            Ticket.non_relancable == False,  # noqa: E712
            Ticket.mis_a_jour_le < seuil,
        )
    ).one() or 0

    return (comptes_attente or 0) + (commandes_attente or 0), relances


def calculer(ctx: ContexteFlux) -> FluxSante:
    tous = ctx.session.exec(select(Ticket)).all()
    ouverts = [t for t in tous if t.statut in ("ouvert", "en_cours")]
    urgents = [t for t in ouverts if t.categorie == "urgence"]

    # Temps moyen de résolution sur les 30 derniers jours
    depuis_30j = ctx.now - timedelta(days=30)
    resolus = [
        t for t in tous
        if t.statut == "résolu" and t.ferme_le and t.cree_le and t.ferme_le >= depuis_30j
    ]
    resolution_moy = None
    if resolus:
        durees = [(t.ferme_le - t.cree_le).total_seconds() / 3600 for t in resolus]
        resolution_moy = round(sum(durees) / len(durees), 1)

    sondages_actifs = ctx.session.exec(
        select(func.count(Sondage.id)).where(~Sondage.cloture_forcee)
    ).one()

    validations_cs, relances_syndic = _validations_et_relances(ctx)

    return FluxSante(
        tickets_ouverts=len(ouverts),
        tickets_urgents=len(urgents),
        resolution_moyenne_heures=resolution_moy,
        sondages_actifs=sondages_actifs,
        validations_cs=validations_cs,
        tickets_relance_syndic=relances_syndic,
        prochains=_prochains(ctx),
    )
