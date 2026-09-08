"""Tickets — cycle de vie : lister, créer, lire, modifier, supprimer.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import (
    exiger_non_externe,
    get_current_user,
    peut_commander,
    require_admin,
)
from app.database import get_session
from app.models.core import (
    StatutTicket,
    Ticket,
    Utilisateur,
)
from app.schemas import TicketCreate, TicketRead
from app.utils.fichiers import chemins_locaux
from app.utils.suppression_liee import (
    flush_si_necessaire,
    supprimer_documents_de,
    supprimer_lignes_liees,
)
from app.utils.photos import parse_photos, photos_json
from app.utils.courriel_entrant import nouveau_jeton
from app.utils.visibility import ticket_visible

from app.utils.kanban_tickets import suivi_par_defaut
from .commun import (
    appliquer_options,
    generer_numero,
    ticket_read,
    trier_par_activite,
    pieces_du_ticket,
)
from .courriels import (
    _alerter_bug,
    _notifier_cs_creation,
    _partager_sur_le_groupe,
    envoyer_email_externe,
    envoyer_email_syndic_cs,
)
from app.utils.categories_ticket import ticket_urgent

#  Seul sous-router à porter le préfixe : ses deux routes de collection ont un
#  chemin VIDE (`GET /tickets`, `POST /tickets`), et FastAPI refuse un chemin
#  vide sur un router sans préfixe. Les trois autres sous-modules déclarent des
#  chemins nus et reçoivent le préfixe au montage (cf. `__init__.py`).
router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketRead])
def list_tickets(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    #  🔴 UNE SEULE RÈGLE DE VISIBILITÉ, ET ELLE EST EN PYTHON (#710, 02/09/2026).
    #
    #  Ce filtre existait aussi en SQL — `auteur_id == moi OR saisi_pour == moi` —
    #  et disait donc la même chose que `ticket_visible` dans un autre langage.
    #  Tant que la règle tenait en deux colonnes, les deux écritures pouvaient
    #  rester d'accord par chance. Le périmètre y met fin : il demande l'arbre des
    #  périmètres, l'héritage de la portée globale et les lots de l'utilisateur,
    #  qu'aucun `where` ne sait exprimer sans re-dériver la règle une troisième
    #  fois.
    #
    #  Alors la liste passe par la MÊME fonction que la fiche. C'est le motif que
    #  `flux/sante.py` emploie déjà, et pour la même raison : « la liste ramenait
    #  ce que le détail refusait » est un défaut qu'on ne voit jamais depuis la
    #  liste — on ne remarque pas ce qui manque.
    #
    #  ⚠️ Coût assumé : tous les tickets sont chargés puis filtrés. À l'échelle
    #  d'une copropriété c'est quelques centaines de lignes ; le jour où ça ne
    #  l'est plus, la réponse est la pagination, jamais une seconde règle.
    tickets = session.exec(select(Ticket)).all()

    #  Le tri suit l'ACTIVITÉ, pas la date de dépôt (05/09/2026) : la règle et sa
    #  raison vivent dans `commun.py`, avec les autres décisions partagées.
    tickets = trier_par_activite(session, tickets)
    return [
        ticket_read(ticket, session)
        for ticket in tickets
        if ticket_visible(ticket, user)
    ]




@router.post("", response_model=TicketRead, status_code=201)
def create_ticket(
    body: TicketCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_non_externe(user, "créer de tickets")

    #  Tous les champs « de commandement » (destinataires, saisie pour un tiers)
    #  sont neutralisés hors CS/admin. Le contrôle est ici, côté serveur : ce que
    #  l'interface masque n'est qu'un confort (socle 03 §1).
    est_cs = peut_commander(user)
    ticket = Ticket(
        numero=generer_numero(),
        #  L'adresse de réponse est fixée à la CRÉATION (#703) : la poser plus
        #  tard obligerait à savoir quels tickets en ont déjà une, et un ticket
        #  sans jeton part avec un courriel sans `Reply-To` — la réponse du
        #  syndic retomberait alors dans la boîte muette d'avant.
        jeton_courriel=nouveau_jeton(),
        titre=body.titre,
        description=body.description,
        categorie=body.categorie,
        auteur_id=user.id,
        lot_id=body.lot_id,
        batiment_id=body.batiment_id,
        perimetre_cible=json.dumps(body.perimetre_cible) if body.perimetre_cible else '["résidence"]',
        #  Posée juste en dessous par `appliquer_options`, depuis la case
        #  « Urgent » — plus jamais déduite de la catégorie (`CategorieTicket`).
        priorite="normale",
        #  Le workflow est saisissable dès la création, mais en LISTE BLANCHE et
        #  réservé au CS : un résident qui déposerait un ticket déjà « résolu »
        #  le sortirait du suivi. Une valeur inconnue retombe sur « ouvert »
        #  plutôt que d'être refusée — le ticket doit exister même si le client
        #  envoie n'importe quoi (socle 03 §2, liste blanche ancrée).
        statut=(body.statut if est_cs and body.statut in {s.value for s in StatutTicket}
               else StatutTicket.ouvert),
        destinataire_syndic=body.destinataire_syndic if est_cs else False,
        destinataire_cs=body.destinataire_cs if est_cs else False,
        saisi_pour_user_id=body.saisi_pour_user_id if est_cs else None,
        saisi_pour_nom=body.saisi_pour_nom if est_cs else None,
        saisi_pour_email=body.saisi_pour_email if est_cs else None,
        # `photos_internes` écarte toute URL qui n'a pas été produite par notre
        # endpoint d'upload : sans ce filtre, un client pourrait faire pointer une
        # pièce jointe vers un site tiers, servi ensuite à chaque lecteur.
        photos_urls=photos_json(body.photos_urls),
        fichiers_urls=photos_json(body.fichiers_urls),
    )
    session.add(ticket)
    session.flush()
    #  🔴 LES OPTIONS DE PUBLICATION — une écriture, trois chemins (05/09/2026).
    #  `appliquer_options` porte la table et le contrôle de droit ; ce routeur
    #  ne réécrit ni l'une ni l'autre (`commun.OPTIONS_TICKET`).
    #  🔴 Le défaut de CATÉGORIE d'abord, `appliquer_options` peut le
    #  contredire ensuite : poser le défaut APRÈS effacerait un décochage.
    #  (Le droit est dans `OPTIONS_RESERVEES_AU_CS`, pas réécrit ici.)
    ticket.suivi_kanban = suivi_par_defaut(body.categorie)
    appliquer_options(ticket, body, est_cs=est_cs)

    #  ⚠️ APRÈS `appliquer_options` : c'est elle qui pose `priorite`.
    _notifier_cs_creation(
        session, ticket, urgence=ticket_urgent(ticket),
        auteur=user, background_tasks=background_tasks,
    )

    if body.categorie == "bug":
        _alerter_bug(session, ticket, user, background_tasks)

    #  🔴 CE QUI EST RÉSERVÉ AU CONSEIL NE PART PAS SUR LE GROUPE (05/09/2026),
    #  demandé à l'écran : *« si "Visibilité du ticket au seul conseil syndical"
    #  est sélectionné, la diffusion WhatsApp est interdite »*.
    #
    #  L'actualité tenait déjà la règle (`not pub.brouillon` à chaque canal) ; le
    #  ticket, non — un ticket fermé au voisinage pouvait partir en entier sur le
    #  groupe des résidents. La garde est ici plutôt que dans l'écran : une case
    #  masquée ne protège rien, le champ peut être posté directement.
    if body.partager_whatsapp and est_cs and not ticket.confidentiel:
        _partager_sur_le_groupe(session, ticket, background_tasks)

    if ticket.destinataire_syndic or ticket.destinataire_cs:
        envoyer_email_syndic_cs(
            ticket, user, background_tasks, session,
            syndic=ticket.destinataire_syndic,
            cs=ticket.destinataire_cs,
            # Mêmes règles de résolution que partout ailleurs : URL interne →
            # chemin local, hors de /app/uploads on ignore.
            pieces_jointes=chemins_locaux(pieces_du_ticket(ticket)),
            auteur=bool(getattr(body, "envoyer_auteur", False)),
        )

    session.commit()
    session.refresh(ticket)

    # Email externe si adresse fournie (CS/Admin uniquement)
    email_ext = (body.email_externe or "").strip()
    if email_ext and est_cs:
        envoyer_email_externe(
            ticket, user, email_ext, background_tasks, session,
            is_commentaire=False,
            fichiers_urls=parse_photos(ticket.fichiers_urls),
        )

    return ticket_read(ticket, session)


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    if not ticket_visible(ticket, user):
        raise HTTPException(403, "Accès refusé")
    return ticket_read(ticket, session)


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    #  Tout ce qui n'existe que par ce ticket part avec lui. Les DOCUMENTS
    #  manquaient (#546) : un document joint n'a plus d'objet sans son porteur.
    #  Le `flush()` ordonne les DELETE — pourquoi : `utils/suppression_liee.py`.
    enfants = supprimer_lignes_liees(session, ticket.evolutions, ticket.messages)
    docs = supprimer_documents_de(session, "ticket_id", ticket_id)
    flush_si_necessaire(session, enfants, docs)
    session.delete(ticket)
    session.commit()
