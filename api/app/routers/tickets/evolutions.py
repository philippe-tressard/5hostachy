"""Tickets — fil de suivi : changements d'état et commentaires du CS.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""
import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import (
    est_moderateur,
    get_current_user,
    peut_commenter,
    require_admin,
    require_cs_or_admin,
)
from app.database import get_session
from app.models.core import (
    STATUTS_TICKET_CLOS,
    Notification,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.schemas import TicketEvolutionCreate, TicketEvolutionRead, TicketEvolutionUpdate
from app.models.tickets import STATUTS_TICKET_SANS_CYCLE
from app.utils.nature_affaire import est_actualite
from .actualite import appliquer_acces, diffuser_actualite
from app.utils.evolutions import TYPES_SAISIS, evolution_modifiable, supprimer_evolution
from app.utils.perimetre_fil import doit_propager
from app.utils.fichiers import chemins_locaux
from app.utils.liens import base_site, lien_ticket
from app.utils.assiste_ia import marquer as marquer_assiste_ia
from app.utils.photos import photos_internes, photos_json
from app.utils.noms import contexte_personne
from app.utils.recuperer import ou_404

from .commun import (
    STATUT_LABELS,
    appliquer_options,
    config_site,
    contexte_site,
    evol_read,
)
from .courriels import envoyer_email_externe, envoyer_email_syndic_cs

router = APIRouter()

#  `_STATUTS_ADMIS = ("ouvert", "en_cours", "résolu", "fermé")` vivait ici, et
#  refusait `annulé` depuis le tout premier commit — le jour où les écrans se
#  sont mis à le proposer, le même geste réussissait depuis la fiche du ticket
#  et échouait depuis la liste (#415). La liste ne revient pas : le type
#  `StatutTicket` porté par `TicketEvolutionCreate.nouveau_statut` valide, et il
#  est le seul à le faire.


@router.get("/{ticket_id}/evolutions", response_model=list[TicketEvolutionRead])
def get_evolutions(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = ou_404(session, Ticket, ticket_id, "Ticket")
    #  🔴 `peut_commenter` ÉLARGIT au « saisi pour » — et c'est une correction :
    #  un résident pour qui le CS a déposé un ticket ne pouvait pas lire
    #  l'historique de sa propre demande. C'est la raison d'être du champ.
    if not peut_commenter(ticket, user):
        raise HTTPException(403, "Accès refusé")
    evols = session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket_id)
        .order_by(TicketEvolution.cree_le)
    ).all()
    return [evol_read(e, session) for e in evols]


@router.patch("/{ticket_id}/evolutions/{evol_id}", response_model=TicketEvolutionRead)
def update_evolution(
    ticket_id: int,
    evol_id: int,
    body: TicketEvolutionUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    evol = evolution_modifiable(
        session, TicketEvolution, evol_id,
        champ_parent="ticket_id", parent_id=ticket_id, user=user,
    )
    if body.contenu is not None:
        evol.contenu = body.contenu
    if body.fichiers_urls is not None:
        evol.fichiers_urls = photos_json(body.fichiers_urls)
    marquer_assiste_ia(evol, body)
    if body.perimetre_cible is not None:
        #  🔴 CORRIGER, pas raturer. La règle et son pourquoi vivent dans
        #  `app/utils/perimetre_fil.py` — elle a son `--selftest`.
        evol.perimetre_cible = (
            json.dumps(body.perimetre_cible, ensure_ascii=False)
            if body.perimetre_cible
            else None
        )
        fil = session.exec(
            select(TicketEvolution)
            .where(TicketEvolution.ticket_id == ticket_id)
            .order_by(TicketEvolution.cree_le)
        ).all()
        #  ⚠️ L'entrée en base porte encore l'ancienne valeur dans `fil` : on la
        #  remplace par l'objet modifié, sinon on compare la correction à
        #  elle-même d'avant.
        fil = [evol if e.id == evol.id else e for e in fil]
        if doit_propager(evol, fil):
            ticket = session.get(Ticket, ticket_id)
            if ticket:
                ticket.perimetre_cible = evol.perimetre_cible
                session.add(ticket)
    session.add(evol)
    session.commit()
    session.refresh(evol)
    return evol_read(evol, session)


@router.delete("/{ticket_id}/evolutions/{evol_id}", status_code=204)
def delete_evolution(
    ticket_id: int,
    evol_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """Retirer une entrée du fil — **administrateur seulement**.

    ## Pourquoi cette capacité existe (18/08/2026)

    Demandée à l'écran après le défaut des corrections auto-tracées : deux entrées
    « Correction : Description modifiée ; Périmètre modifié ; … » s'étaient
    inscrites sur un ticket alors qu'une seule catégorie avait changé. Elles ne
    décrivent rien qui ait eu lieu, et **rien ne permettait de les retirer** — pas
    même à l'administrateur : *« je ne peux le faire »*.

    Le fil est une mémoire ; une mémoire qui garde des faits inventés vaut moins
    qu'une mémoire trouée. La capacité manquait, et son absence obligeait à
    envisager une intervention en base — ce que la règle d'or du projet interdit
    tant que l'API tourne.

    ## Pourquoi `require_admin` et non `require_cs_or_admin`

    La correction d'une entrée (`PATCH`) est ouverte à son auteur : réécrire son
    propre commentaire est un geste ordinaire. **Effacer** ne l'est pas — cela fait
    disparaître une trace que d'autres ont pu lire et sur laquelle ils ont pu agir.
    C'est la même frontière que pour la suppression d'un ticket, et la même règle
    que « archiver n'est pas supprimer » : le geste irréversible reste à l'admin.

    ## Les transitions aussi — arbitrage corrigé le 18/08/2026

    Ce endpoint a d'abord refusé les entrées de type « etat », au motif qu'un
    mouvement de workflow est un fait de la vie du dossier et non un texte qu'on
    rature. **L'arbitrage était le mien, pas celui de l'utilisateur**, qui avait
    demandé « une suppression pour les historiques » sans distinction — et qui a
    constaté l'absence dès la première entrée d'état rencontrée.

    Ce qui le rend acceptable : supprimer l'entrée **ne change pas l'état du
    ticket**. `Ticket.statut` vit dans sa propre colonne ; le fil n'en est que le
    récit. Le coût est donc une perte de TRAÇABILITÉ — on ne saura plus quand le
    ticket est passé « En cours » —, pas une incohérence de données.

    ⚠️ C'est un coût réel, et c'est la raison pour laquelle le geste reste réservé
    à l'administrateur : le fil sert de preuve au conseil syndical face au syndic.
    Une transition effacée ne se retrouve pas.

    ⚠️ **Les RÉPONSES restent inaccessibles** (`type == "reponse"`) : elles
    appartiennent à leur auteur, souvent un résident, et un administrateur qui les
    effacerait supprimerait la parole de quelqu'un d'autre. Ce n'est pas la même
    chose que retirer une ligne que le système a écrite ou qu'on a écrite soi-même.
    """
    #  🔴 La décision a quitté ce fichier (#512) : les actualités et les
    #  événements ont désormais le même geste, et trois copies auraient divergé
    #  au premier ajustement de la liste des types. Ce qui reste ici est le
    #  contrôle d'accès — c'est au routeur de dire qui il laisse entrer.
    supprimer_evolution(
        session, TicketEvolution, evol_id,
        champ_parent="ticket_id", parent_id=ticket_id,
    )
    return None



def _notifier_auteur(
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    ticket: Ticket,
    user: Utilisateur,
    body: TicketEvolutionCreate,
    ancien_statut: str | None,
) -> None:
    """E-mail et notification in-app à l'auteur du ticket, s'il n'agit pas lui-même."""
    from app.utils.email import send_email

    cfg = config_site(session)
    auteur = session.get(Utilisateur, ticket.auteur_id)
    base_ticket = {"id": ticket.id, "numero": ticket.numero, "titre": ticket.titre}

    if auteur and auteur.email:
        if body.type == "etat":
            background_tasks.add_task(
                send_email, code="ticket_statut_change", to=auteur.email,
                context={
                    "ticket": {
                        **base_ticket,
                        "statut": STATUT_LABELS.get(body.nouveau_statut, body.nouveau_statut),
                        "ancien_statut": STATUT_LABELS.get(ancien_statut or "", "Aucun"),
                    },
                    "destinataire": {"prenom": auteur.prenom, "nom": auteur.nom},
                    "auteur_action": contexte_personne(user),
                    **contexte_site(cfg),
                },
                destinataire_id=ticket.auteur_id,
            )
        elif body.type == "commentaire" and body.contenu:
            background_tasks.add_task(
                send_email, code="ticket_nouveau_message", to=auteur.email,
                context={
                    "ticket": base_ticket,
                    "message": {"contenu": body.contenu[:300]},
                    "auteur_action": contexte_personne(user),
                    **contexte_site(cfg),
                },
                destinataire_id=ticket.auteur_id,
            )

    titre_notif = (
        f"Ticket #{ticket.numero} — statut : "
        f"{STATUT_LABELS.get(body.nouveau_statut, body.nouveau_statut)}"
        if body.type == "etat"
        else f"Nouveau commentaire sur le ticket #{ticket.numero}"
    )
    session.add(Notification(
        destinataire_id=ticket.auteur_id,
        type="ticket_update",
        titre=titre_notif,
        corps=(body.contenu or "")[:200],
        lien=lien_ticket(ticket.id),
    ))


def _message_pour_le_groupe(ticket: Ticket, body: TicketEvolutionCreate, nb_precedents: int,
                            site_url: str) -> str:
    """Texte WhatsApp d'une évolution, renvoi vers l'historique si besoin."""
    msg = body.contenu or (
        f"Ticket #{ticket.numero} — {ticket.titre} : statut → "
        f"{STATUT_LABELS.get(body.nouveau_statut or '', body.nouveau_statut or '')}"
        if body.type == "etat" else ticket.titre
    )
    if msg and nb_precedents:
        msg += (
            f"\n\n📜 Cet échange comporte {nb_precedents} commentaire(s) précédent(s).\n"
            f"Consultez l'historique complet sur l'application :\n"
            f"👉 {site_url.rstrip('/')}{lien_ticket(ticket.id)}"
        )
    return msg


@router.post("/{ticket_id}/evolutions", response_model=TicketEvolutionRead, status_code=201)
def add_evolution(
    ticket_id: int,
    body: TicketEvolutionCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    #  ⚠️ `get_current_user` et non `require_cs_or_admin` : le droit dépend du
    #  TICKET, qu'une dépendance FastAPI ne connaît pas encore. Il est vérifié
    #  deux lignes plus bas, et refuser ici serait refuser à l'auteur.
    user: Utilisateur = Depends(get_current_user),
):
    ticket = ou_404(session, Ticket, ticket_id, "Ticket")
    #  🔴 Commenter et faire avancer le suivi : l'auteur, le « saisi pour »,
    #  l'admin — et le conseil syndical, qui suit les dossiers (18/08/2026).
    #  Avant, l'AUTEUR de la demande ne pouvait pas commenter sa propre demande.
    if not peut_commenter(ticket, user):
        raise HTTPException(403, "Accès refusé")
    #  La liste vit dans `utils/evolutions` : créer, corriger et effacer
    #  posent la même question, et elle était écrite quatre fois (#779).
    if body.type not in TYPES_SAISIS:
        raise HTTPException(422, "Type invalide (commentaire ou etat)")
    if body.type == "etat" and not body.nouveau_statut:
        raise HTTPException(422, "nouveau_statut requis pour un changement d'état")
    #  Une actualité n'a pas de cycle (#1091) : une Suite y parle, elle ne la
    #  fait pas avancer — et `publie` ne s'atteint par aucune transition.
    if body.type == "etat" and (est_actualite(ticket) or body.nouveau_statut in STATUTS_TICKET_SANS_CYCLE):
        raise HTTPException(422, "Une actualité n'a pas d'état de suivi")

    ancien_statut = ticket.statut if body.type == "etat" else None
    evol = TicketEvolution(
        ticket_id=ticket_id, type=body.type,
        contenu=body.contenu,
        ancien_statut=ancien_statut,
        nouveau_statut=body.nouveau_statut if body.type == "etat" else None,
        auteur_id=user.id, cree_le=datetime.utcnow(),
        fichiers_urls=photos_json(body.fichiers_urls),
        perimetre_cible=(
            json.dumps(body.perimetre_cible, ensure_ascii=False)
            if body.perimetre_cible else None
        ),
        assiste_ia=body.assiste_ia,
    )
    session.add(evol)

    #  🔴 Le périmètre déclaré devient celui du TICKET (#497).
    #
    #  Un ticket se signale avec ce qu'on sait au moment où on le signale — donc
    #  souvent le périmètre le plus large, parce qu'on ignore d'où ça vient. Puis
    #  on cherche : « bâtiment 2 » devient « bât. 2, 3ᵉ étage, cage B ».
    #
    #  Le reporter ici plutôt que de le recalculer à la lecture rend justes, du
    #  même coup et SANS LES TOUCHER, toutes les vues qui lisent déjà
    #  `ticket.perimetre_cible` : les cartes, les listes, les e-mails, et le
    #  message WhatsApp envoyé quelques lignes plus bas. L'historique du
    #  resserrement, lui, reste sur chaque évolution.
    #
    #  ⚠️ `body.perimetre_cible` vide ou absent ne touche à RIEN : une évolution
    #  qui ne parle pas du périmètre ne l'élargit pas à la résidence entière.
    if body.perimetre_cible:
        ticket.perimetre_cible = json.dumps(body.perimetre_cible, ensure_ascii=False)
        ticket.mis_a_jour_le = datetime.utcnow()
        session.add(ticket)
    #  🔴 LES OPTIONS DE PUBLICATION SE CORRIGENT DEPUIS UN COMMENTAIRE
    #  (05/09/2026), demandé à l'écran :
    #
    #  > « tous les autres options de publication doivent être aussi conservé
    #  >   dans l'objet pour les tickets en édition et commentaire »
    #
    #  Même mécanique que le périmètre juste au-dessus, et pour la même raison :
    #  le formulaire montre le DERNIER état, ce qu'on enregistre DEVIENT l'état.
    #  Le reporter sur le ticket rend justes, sans les toucher, toutes les vues
    #  qui le lisent déjà.
    #
    #  ⚠️ La table des options et le contrôle de droit vivent dans
    #  `commun.appliquer_options` — le troisième chemin qui les applique, et le
    #  troisième à ne pas les réécrire.
    if appliquer_options(ticket, body, est_cs=est_moderateur(user)):
        ticket.mis_a_jour_le = datetime.utcnow()
        session.add(ticket)
    #  À qui l'on parle et l'Accès — le conseil seul, comme sur l'ancienne
    #  publication (#1091). Puis l'invariant d'accès : une Suite qui referme
    #  l'actualité archive ses affiches, comme la correction et la création.
    if est_moderateur(user) and (body.public_cible is not None or body.reserve_perimetre is not None):
        if body.public_cible is not None:
            ticket.public_cible = (
                json.dumps(body.public_cible, ensure_ascii=False) if body.public_cible else None
            )
        if body.reserve_perimetre is not None:
            ticket.reserve_perimetre = body.reserve_perimetre
        ticket.mis_a_jour_le = datetime.utcnow()
        session.add(ticket)
    if est_actualite(ticket):
        appliquer_acces(ticket, session)

    if body.type == "etat":
        ticket.statut = body.nouveau_statut
        #  `("résolu", "fermé")` ici contre `(résolu, annulé, fermé)` dans le
        #  PATCH : les deux chemins ne dataient pas la même clôture, et annuler
        #  un ticket depuis le fil ne posait aucun `ferme_le`. Une seule liste,
        #  désormais — celle du modèle.
        if body.nouveau_statut in STATUTS_TICKET_CLOS:
            ticket.ferme_le = datetime.utcnow()
        ticket.mis_a_jour_le = datetime.utcnow()
        session.add(ticket)

    if ticket.auteur_id != user.id:
        _notifier_auteur(
            session, background_tasks,
            ticket=ticket, user=user, body=body, ancien_statut=ancien_statut,
        )

    session.commit()
    session.refresh(evol)

    #  Une ACTUALITÉ diffuse sa Suite par son module (#1091) — une parole vide
    #  ne part nulle part, comme l'ancienne publication.
    if est_actualite(ticket) and est_moderateur(user):
        if body.contenu and body.contenu.strip():
            diffuser_actualite(
                session, ticket, user, background_tasks,
                whatsapp=bool(body.partager_whatsapp),
                syndic=bool(body.envoyer_syndic), cs=bool(body.envoyer_cs),
                auteur=bool(getattr(body, "envoyer_auteur", False)),
                externe=body.email_externe,
                commentaire=body.contenu, fichiers_urls=body.fichiers_urls,
            )
        return evol_read(evol, session)

    # ── Notifications WhatsApp / syndic / CS optionnelles ──────────────────
    #  🔴 Un ticket réservé au conseil ne part pas sur le groupe des résidents
    #  (05/09/2026) : la même règle qu'à la création, au troisième point d'envoi.
    #  Le syndic et le CS, eux, restent joignables — ce sont les destinataires
    #  légitimes d'un dossier fermé au voisinage.
    #
    #  🔴 Et le groupe est un MÉGAPHONE vers tous les résidents : réservé au
    #  conseil, comme à la création (`crud.py`). L'auteur d'une affaire ouvre une
    #  Suite sur la sienne — il ne publie pas au nom du site (#1164, 23/09/2026).
    est_cs = est_moderateur(user)
    partage_whatsapp = body.partager_whatsapp and est_cs and not ticket.confidentiel
    if partage_whatsapp or body.envoyer_syndic or body.envoyer_cs:
        # Évolutions précédentes (hors celle qui vient d'être créée) — le même
        # historique alimente le message WhatsApp et le tableau de l'e-mail.
        evols_hist = session.exec(
            select(TicketEvolution)
            .where(
                TicketEvolution.ticket_id == ticket.id,
                TicketEvolution.id != evol.id,
            )
            .order_by(TicketEvolution.cree_le)
        ).all()

        #  `partage_whatsapp`, pas `body.partager_whatsapp` : c'est CE `if` qui
        #  décide de l'envoi, le précédent pouvant être franchi par le syndic
        #  ou le CS seuls.
        if partage_whatsapp:
            from app.utils.whatsapp import (
                config_whatsapp,
                envoyer_whatsapp_avec_log,
                whatsapp_actif,
            )

            wa_config = config_whatsapp(session)
            if whatsapp_actif(wa_config):
                background_tasks.add_task(
                    envoyer_whatsapp_avec_log,
                    f"🔧 {ticket.titre}",
                    _message_pour_le_groupe(
                        ticket, body,
                        nb_precedents=sum(1 for ev in evols_hist if ev.contenu),
                        site_url=base_site(wa_config.get("site_url")),
                    ),
                    False, ticket.perimetre_cible, None, wa_config,
                )

        if body.envoyer_syndic or body.envoyer_cs:
            envoyer_email_syndic_cs(
                ticket, user, background_tasks, session,
                syndic=bool(body.envoyer_syndic),
                cs=bool(body.envoyer_cs),
                # `photos_internes` avant résolution : même filtre qu'à
                # l'enregistrement, pour ne pas joindre une URL que l'on vient
                # précisément de refuser de stocker.
                pieces_jointes=chemins_locaux(photos_internes(body.fichiers_urls)),
                commentaire=body.contenu,
                evolutions=evols_hist,
                auteur=bool(getattr(body, "envoyer_auteur", False)),
            )

    #  Email externe — CS/Admin uniquement, et ce commentaire le disait sans que
    #  le code le fasse : un résident écrivait, depuis l'adresse du site, à qui
    #  il voulait (#1164).
    if body.email_externe and body.email_externe.strip() and est_cs:
        envoyer_email_externe(
            ticket, user, body.email_externe.strip(), background_tasks, session,
            is_commentaire=True,
            nouveau_message=body.contenu,
            fichiers_urls=body.fichiers_urls,
        )

    return evol_read(evol, session)
