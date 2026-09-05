"""Tickets — cycle de vie : lister, créer, lire, modifier, supprimer.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""
import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, peut_commander, peut_commenter, peut_editer
from app.database import get_session
from app.models.core import (
    STATUTS_TICKET_CLOS,
    Notification,
    RoleUtilisateur,
    StatutTicket,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.schemas import TicketCreate, TicketRead, TicketUpdate
from app.utils.fichiers import chemins_locaux
from app.utils.suppression_liee import (
    flush_si_necessaire,
    supprimer_documents_de,
    supprimer_lignes_liees,
)
from app.utils.liens import lien_ticket
from app.utils.photos import parse_photos, photos_internes
from app.utils.courriel_entrant import nouveau_jeton
from app.utils.visibility import ticket_visible

from .commun import (
    appliquer_options,
    STATUT_LABELS,
    generer_numero,
    ticket_read,
    trier_par_activite,
)
from .correction import _appliquer_contenu, _appliquer_relations, _envoye
from .courriels import (
    _alerter_bug,
    _notifier_cs_creation,
    _partager_sur_le_groupe,
    envoyer_email_externe,
    envoyer_email_syndic_cs,
)
from app.utils.corrections import (
    PREFIXE_CORRECTION,
    PREFIXE_CORRECTION_AUTEUR,
    SEPARATEUR_CORRECTION,
)

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
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(
        RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les utilisateurs externes ne peuvent pas créer de tickets",
        )

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
        priorite="haute" if body.categorie == "urgence" else "normale",
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
        photos_urls=json.dumps(photos_internes(body.photos_urls), ensure_ascii=False),
        fichiers_urls=json.dumps(photos_internes(body.fichiers_urls), ensure_ascii=False),
    )
    session.add(ticket)
    session.flush()
    #  🔴 LES OPTIONS DE PUBLICATION — une écriture, trois chemins (05/09/2026).
    #  `appliquer_options` porte la table et le contrôle de droit ; ce routeur
    #  ne réécrit ni l'une ni l'autre (`commun.OPTIONS_TICKET`).
    appliquer_options(ticket, body, est_cs=est_cs)

    _notifier_cs_creation(session, ticket, urgence=body.categorie == "urgence")

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
            pieces_jointes=chemins_locaux(
                parse_photos(ticket.photos_urls) + parse_photos(ticket.fichiers_urls)
            ),
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


#: Les champs qui décrivent la DEMANDE, par opposition à ceux qui décrivent son
#: suivi (`statut`, `priorite`) ou sa diffusion. Un membre du CS peut agir sur
#: les seconds, jamais sur les premiers.
#:
#: ⚠️ Liste BLANCHE inversée : on énumère ce qui est du contenu, et tout champ
#: ajouté demain y échappe par défaut. C'est le sens le moins risqué — un
#: nouveau champ mal classé sera au pire trop ouvert au CS, jamais fermé à
#: l'auteur. Le contraire bloquerait l'auteur en silence.
CHAMPS_DE_CONTENU = (
    "titre", "description", "categorie", "perimetre_cible",
    "photos_urls", "fichiers_urls", "batiment_id",
)


def _touche_au_contenu(body) -> bool:
    """Cette modification porte-t-elle sur la demande elle-même ?"""
    return any(getattr(body, champ, None) is not None for champ in CHAMPS_DE_CONTENU)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")

    #  🔴 DEUX droits, pas un — arbitré le 18/08/2026 : le conseil syndical
    #  commente et fait avancer le suivi, mais **ne réécrit pas** la demande d'un
    #  résident. Il le pouvait : `is_cs_admin` ouvrait TOUT le contenu de
    #  n'importe quel ticket à n'importe quel membre du CS.
    #
    #  ⚠️ Et l'auteur ne pouvait pas toujours : « saisi pour » ne comptait pas.
    #  Un ticket déposé par le CS AU NOM d'un résident échappait donc à ce
    #  résident — le seul à ne pas pouvoir corriger ce qui parle de lui.
    #
    #  Les deux règles vivent dans `auth/deps.py`, jamais ici : l'audit du
    #  26/07/2026 a trouvé trois dérives nées d'un contrôle écrit dans un routeur.
    is_cs_admin = user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
    if not peut_commenter(ticket, user):
        raise HTTPException(403, "Accès refusé")
    #  Le CS franchit la porte pour le statut et la priorité (plus bas), pas pour
    #  le contenu.
    if not peut_editer(ticket, user) and _touche_au_contenu(body):
        raise HTTPException(
            403,
            "Le conseil syndical peut commenter et faire avancer le suivi, "
            "mais seul l'auteur (ou un administrateur) modifie le contenu",
        )

    ancien_statut = ticket.statut
    #  L'etat des CANAUX avant modification. La Diffusion est rouverte a
    #  l'edition depuis le 18/08/2026 (arbitrage utilisateur) : le conseil
    #  syndical doit pouvoir decider d'envoyer au syndic un ticket deja saisi.
    #
    #  Seule la TRANSITION decoche -> coche envoie. Un canal deja coche ne
    #  repart pas a chaque enregistrement : c'est ce qui distingue « je decide
    #  d'envoyer » de « je corrige une faute de frappe », et ce qui evite
    #  l'incident du triple envoi WhatsApp du 14/08/2026.
    #
    #  Sans ce bloc, rouvrir la section serait pire que la fermer : la case
    #  cocherait un drapeau que rien ne consommerait, et l'ecran promettrait un
    #  envoi qui n'aurait pas lieu — le defaut de `non_relancable` (#435).
    syndic_avant = ticket.destinataire_syndic
    cs_avant = ticket.destinataire_cs

    # Statut et priorité : CS/admin uniquement
    if body.statut is not None or body.priorite is not None:
        if not is_cs_admin:
            raise HTTPException(
                403, "Seul le CS ou un administrateur peut modifier le statut ou la priorité"
            )
        if body.statut is not None:
            ticket.statut = body.statut
            if body.statut in STATUTS_TICKET_CLOS:
                ticket.ferme_le = datetime.utcnow()
        if body.priorite is not None:
            ticket.priorite = body.priorite

    #  🔴 CONFIDENTIEL — CS/admin UNIQUEMENT, et posé ici avec le statut et la
    #  priorité parce que c'est la même nature de décision : elle appartient au
    #  conseil, pas à l'auteur (#710).
    #
    #  ⚠️ Il ne passe PAS par `_appliquer_contenu` : un auteur peut corriger son
    #  texte, il ne décide pas qui a le droit de le lire. Le mettre là aurait
    #  ouvert le drapeau à quiconque peut éditer le ticket.
    #  🔴 LES OPTIONS DE PUBLICATION — CS/admin uniquement, et posées ici avec
    #  le statut et la priorité parce que c'est la même nature de décision :
    #  elle appartient au conseil, pas à l'auteur (#710).
    #
    #  ⚠️ Elles ne passent PAS par `_appliquer_contenu` : un auteur peut corriger
    #  son texte, il ne décide pas qui a le droit de le lire.
    #
    #  ⚠️ Le REFUS reste explicite pour un non-CS qui demande `confidentiel` :
    #  `appliquer_options` se contente d'ignorer, ce qui conviendrait mal ici —
    #  ce chemin répondait 403 depuis #710, et un silence ferait croire au client
    #  que sa correction a été prise.
    if body.confidentiel is not None and not is_cs_admin:
        raise HTTPException(
            403, "Seul le CS ou un administrateur peut rendre un ticket confidentiel"
        )
    appliquer_options(ticket, body, est_cs=is_cs_admin)

    #  Champs du CONTENU — le droit a déjà été vérifié plus haut
    #  (`peut_editer`) : auteur, « saisi pour », ou admin.
    changes: list[str] = []
    content_fields = _touche_au_contenu(body)
    if content_fields:
        #  Une contrainte de PLUS, et elle ne vise pas l'admin : celui qui a
        #  déposé la demande ne la réécrit que tant qu'elle est ouverte. Une fois
        #  le suivi engagé, corriger le texte ferait mentir ce que le CS a lu
        #  avant d'agir. L'admin, lui, intervient précisément quand il y a un
        #  problème — c'est sa raison d'être dans cette règle.
        if not user.has_role(RoleUtilisateur.admin) and ticket.statut != StatutTicket.ouvert:
            raise HTTPException(403, "Modification impossible : le ticket n'est plus ouvert")
        changes += _appliquer_contenu(body, ticket)

    # Champs relationnels/destinataires : CS/admin uniquement
    #  ⚠️ `non_relancable` MANQUAIT à cette liste : un `PATCH` qui ne portait
    #  que lui n'entrait jamais dans `_appliquer_relations`, et le bouton « ne
    #  plus relancer » répondait 200 sans rien écrire (#435). Un 200 qui n'écrit
    #  rien est pire qu'un 422 : il fabrique la confiance qu'il devrait retirer.
    #  La liste teste la PRÉSENCE et non la non-nullité — sinon effacer un champ
    #  (le remettre à `null`) n'y entrerait pas davantage.
    extra_fields = any(
        _envoye(body, c)
        for c in (
            'lot_id', 'batiment_id', 'destinataire_syndic', 'destinataire_cs',
            'partager_whatsapp',
            'saisi_pour_user_id', 'saisi_pour_nom', 'saisi_pour_email',
            'non_relancable', 'non_relancable_motif',
        )
    )
    if extra_fields:
        if not is_cs_admin:
            raise HTTPException(403, "Seul le CS ou un administrateur peut modifier ces champs")
        changes += _appliquer_relations(body, ticket)



    ticket.mis_a_jour_le = datetime.utcnow()

    #  🔴 UNE ÉDITION ÉCRIT UNE CORRECTION, PAS UNE TRANSITION (cadre #430, #431)
    #
    #  Ce bloc écrivait une `TicketEvolution(type="etat")` dès que le statut
    #  changeait — la même forme, au même endroit du fil, que le changement d'état
    #  volontaire du conseil syndical. Tant que l'édition ne rouvrait pas le
    #  workflow, cela ne se voyait pas. Depuis que le cadre l'y rouvre — *l'édition
    #  corrige, et l'état s'y corrige comme les autres champs* —, corriger un état
    #  mal saisi apparaîtrait dans l'Historique comme une ÉTAPE DU WORKFLOW : le
    #  ticket aurait « été » en cours, alors qu'il n'y est jamais passé.
    #
    #  La correction reste **visible** — rien ne devient muet — mais elle se
    #  présente pour ce qu'elle est : une ligne de correction parmi les autres,
    #  sans `ancien_statut`/`nouveau_statut`, donc sans jalon de suivi.
    #
    #  La transition, elle, n'a pas disparu : elle passe par
    #  `POST /tickets/{id}/evolutions` (`evolutions.py`), qui l'inscrit avec sa
    #  date, son auteur, son courriel à l'auteur du ticket et ses canaux. C'est
    #  désormais le seul chemin qui la produit — les boutons « Changer le statut »
    #  de la fiche l'empruntent depuis #431.
    if body.statut is not None and body.statut != ancien_statut:
        changes.insert(
            0,
            f"État : {STATUT_LABELS.get(ancien_statut or '', 'Aucun')} → "
            f"{STATUT_LABELS.get(body.statut, body.statut)}",
        )

    #  🔴 CORRIGER UN CHAMP N'ÉCRIT PLUS RIEN DANS L'HISTORIQUE (18/08/2026).
    #
    #  Signalé à l'écran : « j'ai fait une édition d'un ticket pour corriger sa
    #  catégorie et ça m'a créé un historique ! c'est à supprimer ». L'Historique
    #  raconte la VIE du dossier — ce que le conseil syndical a fait, où en est la
    #  demande. Une faute de frappe rattrapée n'en fait pas partie : elle ajoute une
    #  ligne qui n'apprend rien, et pousse vers le bas celles qui apprennent quelque
    #  chose.
    #
    #  ⚠️ Le changement d'ÉTAT, lui, continue de laisser une trace : ce n'est pas une
    #  correction de saisie mais un mouvement de workflow, et savoir quand un ticket
    #  est passé « En cours » est précisément ce que le fil sert à conserver. Il
    #  reste inscrit comme une CORRECTION et non comme une transition — sans
    #  `ancien_statut`/`nouveau_statut`, donc sans jalon de suivi — pour la raison
    #  détaillée juste au-dessus : le ticket n'a pas « été » dans un état qu'on
    #  corrige. C'est ce que `test_correction_pas_transition.py` verrouille.
    #
    #  ⚠️ Ce que ce lot NE fait pas : les publications et le calendrier gardent leur
    #  auto-log de correction. R5 — un écran à la fois, constaté avant d'être
    #  généralisé. La divergence est donc VOULUE et temporaire ; elle est nommée
    #  dans le test, qui vérifie chaque entité séparément.
    etat_a_change = body.statut is not None and body.statut != ancien_statut
    if changes and etat_a_change:
        #  Le préfixe et son assemblage viennent de `app/utils/corrections.py` :
        #  la chaîne était écrite quatre fois, et le fil avait besoin d'un
        #  cinquième pour la RECONNAÎTRE (01/09/2026).
        session.add(TicketEvolution(
            ticket_id=ticket.id, type="commentaire",
            contenu=(PREFIXE_CORRECTION if is_cs_admin else PREFIXE_CORRECTION_AUTEUR)
            + SEPARATEUR_CORRECTION.join(changes),
            auteur_id=user.id, cree_le=datetime.utcnow(),
        ))

    # Notification auteur (in-app) — sauf si c'est l'auteur lui-même qui modifie
    if user.id != ticket.auteur_id:
        session.add(Notification(
            destinataire_id=ticket.auteur_id,
            type="ticket_update",
            titre=f"Ticket #{ticket.numero} mis à jour",
            corps=" ; ".join(changes) if changes else f"Nouveau statut : {ticket.statut}",
            lien=lien_ticket(ticket.id),
        ))
    session.add(ticket)

    #  ⚠️ PLUS DE COURRIEL « changement de statut » ICI (#431).
    #
    #  Ce chemin envoyait `ticket_statut_change` à l'auteur du ticket dès que le
    #  statut bougeait par un `PATCH`. Or un `PATCH` est désormais une
    #  **correction** : la Diffusion est absente de l'édition, motif `geste` —
    #  *une correction n'est pas une nouvelle*, et rejouer un canal à chaque
    #  faute de frappe rattrapée est exactement l'incident du triple envoi
    #  WhatsApp du 14/08/2026.
    #
    #  L'auteur n'est pas laissé dans le noir : la notification in-app ci-dessus
    #  part toujours, et elle porte le détail des corrections. Le courriel, lui,
    #  reste attaché à la vraie transition, dans `evolutions.py::_notifier_auteur`.
    session.commit()
    session.refresh(ticket)

    #  L'ENVOI, et seulement sur la transition decoche -> coche (voir plus haut).
    #  Apres le commit : un courriel qui part sur une transaction annulee annonce
    #  une decision qui n'a pas ete prise.
    #  Le partage WhatsApp est un ACTE, pas un champ : `Ticket` n'a pas cette
    #  colonne. Cocher la case demande un envoi, ici et maintenant — il n'y a rien
    #  à comparer à un état antérieur, et rien ne repart tout seul au prochain
    #  enregistrement puisque la case revient décochée.
    #  Le contrôle de rôle est DANS la condition, et non chez l'appelant :
    #  `test_canaux_notification` lit l'arbre syntaxique et refuse toute condition
    #  portant `partager_whatsapp` sans rôle. Une garde qu'un contrôle ne peut pas
    #  voir ne le protège pas de la refonte qui déplacera l'appel.
    #  Même règle qu'à la création : réservé au conseil ⇒ pas de groupe WhatsApp.
    if body.partager_whatsapp and is_cs_admin and not ticket.confidentiel:
        _partager_sur_le_groupe(session, ticket, background_tasks)

    if (ticket.destinataire_syndic and not syndic_avant) or (
        ticket.destinataire_cs and not cs_avant
    ):
        envoyer_email_syndic_cs(
            ticket, user, background_tasks, session,
            syndic=ticket.destinataire_syndic and not syndic_avant,
            cs=ticket.destinataire_cs and not cs_avant,
            pieces_jointes=chemins_locaux(
                parse_photos(ticket.photos_urls) + parse_photos(ticket.fichiers_urls)
            ),
        )

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
