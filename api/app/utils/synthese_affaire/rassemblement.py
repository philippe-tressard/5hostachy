"""Ce que la synthèse lit d'une affaire : ses faits, ses métriques, et le message (#1643).

## Ce qui part à l'assistant, et ce qui ne part pas

Envoyé : le titre, la description, les Suites (réponses du syndic par courriel
comprises), les relances, les états datés, les messages qui ne sont pas
internes au conseil, les métriques calculées et la mention d'une réouverture.

**Exclus** : les messages internes (`MessageTicket.interne`) et toutes les
pièces jointes. Les personnes sont désignées par leur **rôle** (le syndic, le
conseil syndical, l'auteur de l'affaire, un résident), jamais par leur nom : le
modèle n'en a pas besoin pour raconter l'affaire, et la politique de
confidentialité dit ce qui lui est transmis (`seed/contenus_legaux.py`).

## Le syndic

Il se reconnaît à son lien dans la fiche du cabinet (`MembreSyndic.user_id`) ou
à son adresse (`est_adresse_syndic`), jamais à un rôle — `RoleUtilisateur` n'en
a pas. Une Suite venue d'un courriel (texte d'origine conservé, ou versée par un
transfert) compte aussi comme une réponse reçue, arbitré : « 1ʳᵉ Suite d'un
compte syndic ou d'un courriel entrant ».
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from sqlmodel import Session, col, select

from app.models.copropriete import Copropriete
from app.models.core import MessageTicket, Ticket, TicketEvolution, Utilisateur
from app.models.gouvernance import MembreSyndic
from app.models.prestataires import Prestataire
from app.models.roles import RoleUtilisateur
from app.models.tickets import STATUTS_TICKET_CLOS
from app.utils import horloge
from app.utils.annonce_hall import texte_brut
from app.utils.categories_ticket import libelle_categorie
from app.utils.dates_fr import date_courte
from app.utils.destinataires import est_adresse_syndic
from app.utils.jours_ouvres import libelle_jours
from app.utils.synthese_affaire import metriques as m
from app.utils.synthese_affaire.lecture import TYPE_SYNTHESE
from app.utils.valeurs import valeur

#: Une entrée du fil se coupe là : le récit d'une page n'en demande pas plus.
MAX_CARACTERES_ENTREE = 1_500
#: Et le fil entier là — une affaire de deux ans ne doit pas facturer un roman.
MAX_CARACTERES_FIL = 40_000


def reconnaisseur_syndic(session: Session) -> Callable[[int], bool]:
    """« Ce compte est-il celui du syndic ? » — lien dans la fiche du cabinet, ou adresse.

    L'adresse se juge par `est_adresse_syndic`, la règle de la relève des
    courriels : jamais une comparaison recopiée sur `Utilisateur.email`.
    """
    lies = {mb.user_id for mb in session.exec(select(MembreSyndic)).all() if mb.user_id}
    connus: dict[int, bool] = {}

    def est_syndic(user_id: int) -> bool:
        if user_id in lies:
            return True
        if user_id not in connus:
            user = session.get(Utilisateur, user_id)
            connus[user_id] = bool(user and user.email and est_adresse_syndic(session, user.email))
        return connus[user_id]

    return est_syndic


def _evolutions(session: Session, ticket_id: int) -> list[TicketEvolution]:
    """Le fil de l'affaire, sans les Suites de synthèse — elles ne se mesurent pas."""
    return list(
        session.exec(
            select(TicketEvolution)
            .where(TicketEvolution.ticket_id == ticket_id, TicketEvolution.type != TYPE_SYNTHESE)
            .order_by(TicketEvolution.cree_le)
        ).all()
    )


def _fait(e: TicketEvolution, est_syndic: Callable[[int], bool]) -> m.Fait:
    venue_d_un_courriel = bool(e.contenu_origine) or e.versement_id is not None
    return m.Fait(
        quand=e.cree_le,
        type=e.type,
        ancien_statut=e.ancien_statut,
        nouveau_statut=e.nouveau_statut,
        syndic=est_syndic(e.auteur_id) or venue_d_un_courriel,
    )


def _comparaison(
    session: Session, ticket: Ticket, est_syndic: Callable[[int], bool]
) -> Optional[dict]:
    """La moyenne des autres affaires closes de même catégorie sur l'exercice."""
    copro = session.exec(select(Copropriete)).first()
    debut, fin, libelle = m.bornes_exercice(
        horloge.jour_civil(ticket.ferme_le), copro.mois_debut_exercice if copro else None
    )
    autres = session.exec(
        select(Ticket).where(
            Ticket.id != ticket.id,
            Ticket.categorie == ticket.categorie,
            col(Ticket.statut).in_(STATUTS_TICKET_CLOS),
            col(Ticket.ferme_le) >= m.debut_utc(debut),
            col(Ticket.ferme_le) < m.debut_utc(fin),
        )
    ).all()
    mesures = [
        m.mesures_de_base(
            a.cree_le, a.ferme_le, [_fait(e, est_syndic) for e in _evolutions(session, a.id)]
        )
        for a in autres
    ]
    return m.moyenne(mesures, valeur(ticket.categorie), libelle)


def metriques_de(session: Session, ticket: Ticket, cloture_le: datetime) -> dict:
    """Les métriques de l'affaire, calculées maintenant — ce que la production fige."""
    est_syndic = reconnaisseur_syndic(session)
    faits = [_fait(e, est_syndic) for e in _evolutions(session, ticket.id)]
    return m.calculer(
        cree_le=ticket.cree_le,
        cloture_le=cloture_le,
        issue=valeur(ticket.statut),
        faits=faits,
        comparaison=_comparaison(session, ticket, est_syndic),
    )


def _role(user: Optional[Utilisateur], ticket: Ticket, est_syndic: Callable[[int], bool]) -> str:
    if user is None:
        return "un compte supprimé"
    if est_syndic(user.id):
        return "le syndic"
    if user.has_role(RoleUtilisateur.conseil_syndical):
        return "le conseil syndical"
    if user.has_role(RoleUtilisateur.admin):
        return "l'administration"
    if user.id in (ticket.auteur_id, ticket.saisi_pour_user_id):
        return "l'auteur de l'affaire"
    return "un résident"


def _texte(html: Optional[str]) -> str:
    return texte_brut(html or "")[:MAX_CARACTERES_ENTREE]


def _lignes_metriques(met: dict, libelles: dict[str, str]) -> list[str]:
    etapes = " · ".join(
        f"{libelles.get(e['statut'], 'Close avant réouverture')} {libelle_jours(e['jours'])}"
        for e in met["etapes"]
    )
    lignes = [
        f"- Durée totale : {libelle_jours(met['duree_totale'])}",
        f"- Temps par étape : {etapes or '—'}",
    ]
    if met["etape_plus_longue"]:
        lignes.append(f"- Étape la plus longue : {libelles.get(met['etape_plus_longue'])}")
    lignes += [
        f"- Suites : {met['suites']} · relances au syndic : {met['relances']}",
        f"- Réaction du syndic après la dernière relance : {libelle_jours(met['reaction_relance'])}",
        "- Première réponse du syndic après l'ouverture : "
        + libelle_jours(met["premiere_reponse_syndic"]),
        f"- Semaines sans aucune suite : {met['semaines_muettes']} sur {len(met['semaines'])}",
    ]
    comp = met.get("comparaison")
    if comp:
        lignes.append(
            f"- Moyenne des {comp['nombre']} autres affaires de la même catégorie closes sur "
            f"l'exercice {comp['exercice']} : durée {libelle_jours(comp['duree_totale'])}, "
            f"première réponse {libelle_jours(comp['premiere_reponse_syndic'])}, "
            f"{comp['relances']} relance(s), {comp['suites']} suite(s)"
        )
    return lignes


def construire_message(
    session: Session, ticket: Ticket, met: dict, libelles: dict[str, str]
) -> str:
    """Le message envoyé à l'assistant — écrit par le code, chiffres compris."""
    est_syndic = reconnaisseur_syndic(session)
    issue = "résolue" if met["issue"] == "résolu" else "annulée"
    prestataire = session.get(Prestataire, ticket.prestataire_id) if ticket.prestataire_id else None
    tete = [
        f"Affaire {ticket.numero} — « {ticket.titre} »",
        f"Catégorie : {libelle_categorie(ticket.categorie)}"
        + (f" · équipement : {ticket.equipement.replace('_', ' ')}" if ticket.equipement else ""),
        f"Ouverte le {date_courte(horloge.jour_civil(ticket.cree_le))}, {issue} le "
        f"{date_courte(horloge.jour_civil(ticket.ferme_le))}.",
    ]
    if prestataire and prestataire.nom:
        tete.append(f"Intervenant : {prestataire.nom}")
    if met["reouvertures"]:
        tete.append(
            f"L'affaire a été rouverte {met['reouvertures']} fois : la synthèse couvre toute sa vie."
        )
    tete += ["", "Description :", _texte(ticket.description) or "(aucune)", ""]
    tete.append("Métriques calculées (jours ouvrés, 9 h–17 h, hors week-ends et jours fériés) :")
    tete += _lignes_metriques(met, libelles)

    entrees: list[tuple[datetime, str]] = []
    for e in _evolutions(session, ticket.id):
        qui = _role(session.get(Utilisateur, e.auteur_id), ticket, est_syndic)
        if e.type == "etat":
            avant, apres = (
                libelles.get(e.ancien_statut or "", "?"),
                libelles.get(e.nouveau_statut, "?"),
            )
            ligne = f"État : {avant} → {apres} ({qui})"
            if e.contenu:
                ligne += f" — {_texte(e.contenu)}"
        elif e.type == "relance":
            ligne = "Relance envoyée au syndic"
        elif e.type == "commentaire" and e.contenu:
            ligne = f"Suite ({qui}) : {_texte(e.contenu)}"
        else:
            continue  # « réponse » : son texte est le message, lu ci-dessous
        entrees.append((e.cree_le, ligne))
    for msg in session.exec(
        select(MessageTicket).where(
            MessageTicket.ticket_id == ticket.id,
            MessageTicket.interne == False,  # noqa: E712
        )
    ).all():
        qui = _role(session.get(Utilisateur, msg.auteur_id), ticket, est_syndic)
        entrees.append((msg.cree_le, f"Message ({qui}) : {_texte(msg.contenu)}"))
    entrees.sort(key=lambda x: x[0])
    fil = "\n".join(f"- {date_courte(horloge.jour_civil(q))} — {t}" for q, t in entrees)
    return "\n".join([*tete, "", "Fil daté :", fil[:MAX_CARACTERES_FIL] or "(vide)"])


__all__ = ["construire_message", "metriques_de", "reconnaisseur_syndic"]
