"""Le **parc** de badges — ce que le conseil syndical voit, et ce qu'il en fait.

## Pourquoi ce module (14/09/2026, #953)

`resident.py` portait déjà les deux LECTURES du conseil syndical, et son en-tête
le disait : « les badges vus par leur porteur — et la vue d'ensemble du conseil
syndical ». Les gestes demandés — ajouter, corriger, retirer, exporter — l'ont
fait franchir les 500 lignes, et le plafond de modularité a désigné la couture
qui existait déjà.

🔴 **Deux lecteurs, deux questions.** Un résident demande *« quels sont MES
badges ? »* ; le conseil syndical demande *« qui a le badge 4521 ? »*. Ce n'est
pas la même requête, ce ne sont pas les mêmes droits, et ce ne sont pas les mêmes
gestes.

## Ce qui a changé le 14/09/2026 — et ce que cela renverse

L'écran était **délibérément en lecture seule** depuis le 06/09 (#805) : trois
routes d'écriture avaient été supprimées ce jour-là, au motif qu'enregistrer un
badge était déjà couvert deux fois — l'import en masse, et `declarer-badge` par
le résident.

Ce choix est **renversé, sur demande explicite** :

> « dans Espace CS / Badges & télécommandes : l'export, la suppression, l'ajout
>   ou la modification d'un vigik / télécommande n'est pas (encore) possible ⇒ à
>   mettre en priorité haute »

⚠️ Ce qui aurait été fautif n'était pas d'ouvrir l'écriture, c'était de la
**recopier**. Les gestes passent donc par le descripteur `utils/types_acces`
(v1.36.8), celui-là même dont l'absence avait laissé diverger le report du
`lot_id` entre vigik et télécommande.

🔒 **Les droits vivent dans `auth/deps`**, jamais ici : `require_cs_or_admin`
pour voir et corriger, `require_admin` pour supprimer définitivement.
"""
import csv
import io
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Notification, StatutAcces, Telecommande, Ticket, TicketEvolution,
    Utilisateur, UserLot, Vigik,
)
from app.models.copropriete import Lot
from app.utils.acces_detachement import detacher_acces
from app.utils.acces_perimetre import acces_deduit
from app.utils.batiments import libelle_lot
from app.utils.dates_fr import date_courte
from app.utils.noms import nom_affiche
from app.utils.perimetres import parse_json_perimetres, perimetre_label
from app.utils.types_acces import TYPES_ACCES, TypeAcces

router = APIRouter()


class AccesAdminOut(BaseModel):
    """Un badge tel que le conseil syndical a besoin de le VOIR.

    🔴 Les deux listes rendaient l'objet BRUT (`select(Vigik)`), donc `user_id`
    et `lot_id` — deux nombres. Un écran bâti dessus aurait affiché « badge 4521
    → utilisateur 37 », c'est-à-dire rien : la question qu'on pose à cette liste
    est *« qui a ce badge ? »*, et elle n'y répondait pas.

    C'est pourquoi enrichir la lecture faisait partie du lot qui l'expose : une
    route sans appelant n'est jamais mise à l'épreuve de la question à laquelle
    elle est censée répondre (#805).
    """
    id: int
    code: str
    statut: StatutAcces
    chez_locataire: bool
    porteur_nom: str
    porteur_id: int
    lot_libelle: Optional[str] = None
    lot_id: Optional[int] = None
    #: 🔹 Ce que le badge OUVRE — des CODES de périmètre, pas un libellé.
    #:
    #: ⚠️ L'écran les met en forme lui-même (`BadgePerimetre`), comme partout
    #: ailleurs : envoyer un libellé obligerait le serveur à décider d'un rendu,
    #: et c'est le défaut que le fil d'activité portait jusqu'au 14/09/2026 — il
    #: comparait « Copropriété entière » à une chaîne écrite en dur.
    perimetre_cible: list[str] = []
    cree_le: datetime


def _acces_admin_out(objets, session: Session) -> list[AccesAdminOut]:
    """Sérialise une liste de Vigik OU de Telecommande — les deux ont les mêmes
    champs utiles, et deux fonctions jumelles auraient divergé au premier ajout."""
    sortie = []
    for o in objets:
        porteur = session.get(Utilisateur, o.user_id)
        lot = session.get(Lot, o.lot_id) if o.lot_id else None
        sortie.append(
            AccesAdminOut(
                id=o.id,
                code=o.code,
                statut=o.statut,
                chez_locataire=o.chez_locataire,
                #  Le nom passe par `nom_affiche` : « Prénom NOM », comme partout
                #  ailleurs. Un `f"{prenom} {nom}"` local serait la 35e écriture
                #  de cette règle.
                porteur_nom=nom_affiche(porteur.prenom, porteur.nom) if porteur else "—",
                porteur_id=o.user_id,
                #  🔴 `f"{lot.type}"` rendait « TypeLot.appartement 314 » — la
                #  représentation Python de l'enum, jusque sur l'écran du CS
                #  (12/09/2026, signalé à l'écran). Le libellé est écrit UNE
                #  fois, dans `utils/batiments`, et trois autres endroits le
                #  composaient déjà correctement à la main.
                lot_libelle=libelle_lot(lot),
                lot_id=o.lot_id,
                perimetre_cible=parse_json_perimetres(o.perimetre_cible),
                cree_le=o.cree_le,
            )
        )
    #  Par code : c'est ce qu'on a sous les yeux quand on cherche « à qui est ce
    #  badge ? », un numéro gravé sur un objet physique.
    return sorted(sortie, key=lambda a: a.code)


#  ── Ce que le badge ouvre, et ce qui en découle ────────────────────────────

def _acces_json(session: Session, donne: Optional[list[str]],
                lot_id: Optional[int], porteur_id: int) -> Optional[str]:
    """Le périmètre à enregistrer : celui qu'on a saisi, sinon celui qu'on déduit.

    ⚠️ **Une liste VIDE est une décision**, pas une absence : elle dit « on ne
    sait pas », et on n'essaie alors pas de deviner à la place de qui l'a
    effacée. Seul `None` — le champ non transmis — déclenche la déduction.

    La règle de déduction vit dans `utils/acces_perimetre` : le bâtiment du lot,
    ou celui des lots du porteur s'ils sont tous dans le même. La migration 0190
    en porte l'équivalent SQL, et `test_acces_perimetre.py` vérifie que les deux
    disent la même chose.
    """
    if donne is not None:
        return json.dumps(donne, ensure_ascii=False) if donne else None

    batiments: list = []
    if lot_id:
        lot = session.get(Lot, lot_id)
        if lot:
            batiments.append(lot.batiment_id)
    if not batiments:
        batiments = [
            lot.batiment_id
            for lot in session.exec(
                select(Lot).join(UserLot, UserLot.lot_id == Lot.id)
                .where(UserLot.user_id == porteur_id, UserLot.actif == True)  # noqa: E712
            ).all()
        ]
    deduit = acces_deduit(batiments)
    return json.dumps(deduit, ensure_ascii=False) if deduit else None


def _tracer_sur_ticket(session: Session, ticket, auteur: Utilisateur,
                       type_acces: TypeAcces, objet, verbe: str) -> None:
    """Le geste s'inscrit dans le fil du ticket dont le numéro a été saisi.

    ⚠️ Par une **entrée d'historique**, comme n'importe quel commentaire — pas
    par une écriture directe dans le ticket. Le fil est la mémoire de l'objet, et
    une ligne qui n'y passerait pas serait invisible de l'écran qui le lit.

    ⚠️ Le type est `commentaire` : ce geste ne fait pas avancer le ticket, il
    raconte ce qui a été fait. Choisir `etat` inscrirait une transition qui n'a
    pas eu lieu.
    """
    if ticket is None:
        return
    perimetre = parse_json_perimetres(objet.perimetre_cible)
    portee = perimetre_label(perimetre) if perimetre else "non précisé"
    session.add(TicketEvolution(
        ticket_id=ticket.id,
        type="commentaire",
        contenu=(
            f"{type_acces.libelle} {objet.code} {verbe} — accès : {portee}."
        ),
        auteur_id=auteur.id,
    ))
    session.commit()


def _prevenir_porteur(session: Session, porteur: Utilisateur,
                      type_acces: TypeAcces, objet) -> None:
    """Le porteur apprend qu'un accès est enregistré à son nom.

    ⚠️ **Une notification dans l'application, pas un courriel** — et c'est une
    limite que je nomme plutôt que de la masquer. Le ticket demande « un mail
    notifie le demandeur s'il a un mail » ; l'envoi passe par un MODÈLE stocké en
    base, et en créer un demande une migration qui le pose (sans quoi il part
    vide : c'est l'incident du modèle BOUCHON, 09/09/2026). Ce lot livre donc la
    notification, et le courriel suit avec son modèle.

    ⚠️ Rien n'est envoyé si le porteur n'a pas d'adresse — la demande le dit
    (« s'il a un mail »), et une notification sans destinataire n'est pas une
    notification.
    """
    perimetre = parse_json_perimetres(objet.perimetre_cible)
    portee = perimetre_label(perimetre) if perimetre else "non précisé"
    session.add(Notification(
        destinataire_id=porteur.id,
        type=type_acces.cle,
        titre=f"{type_acces.libelle} enregistré à votre nom",
        corps=f"{objet.code} — accès : {portee}.",
        lien="/mon-lot",
    ))
    session.commit()

class AccesAdminBody(BaseModel):
    """Ce que le conseil syndical saisit — à la création comme à la correction.

    ⚠️ **Tous les champs sont optionnels**, y compris à la création : c'est un
    `PATCH` partiel qui les réemploie. Le seul vraiment requis à la création est
    le `code`, et c'est le geste qui l'exige, pas le schéma — un schéma qui
    rendrait `code` obligatoire empêcherait de s'en servir pour la correction.
    """
    code: Optional[str] = None
    #: Le copropriétaire pour qui l'accès est enregistré — le « saisi pour » des
    #: tickets, appliqué à un objet physique.
    porteur_id: Optional[int] = None
    lot_id: Optional[int] = None
    #: 🔹 Ce que le badge ouvre. `None` = ne pas changer ; `[]` = « on ne sait pas ».
    perimetre_cible: Optional[list[str]] = None
    statut: Optional[StatutAcces] = None
    #: Le numéro du ticket auquel rattacher ce geste — saisi à la main,
    #: **vérifié** : un numéro inconnu refuse la saisie plutôt que d'enregistrer
    #: le badge sans le lien. Un rattachement silencieusement perdu est pire
    #: qu'une erreur affichée.
    ticket_numero: Optional[str] = None


def _acces_admin(session: Session, type_acces: TypeAcces, objet_id: int):
    """L'objet vu par le conseil syndical — sans condition de propriété.

    🔒 Le pendant de `_acces_du_porteur`, et la différence est tout le sujet : le
    CS voit le parc ENTIER, un résident ne voit que le sien. Deux questions, deux
    fonctions — les fondre en une avec un drapeau `est_cs` ferait de ce drapeau
    la seule chose qui sépare « mes badges » de « tous les badges ».
    """
    objet = session.get(type_acces.modele, objet_id)
    if not objet:
        raise HTTPException(404, f"{type_acces.libelle} introuvable")
    return objet


def _ticket_par_numero(session: Session, numero: Optional[str]):
    """Le ticket dont le numéro a été saisi — ou l'erreur qui le dit.

    ⚠️ Un numéro inconnu **refuse** la saisie. L'alternative — enregistrer le
    badge et ignorer le lien — perdrait le rattachement sans que personne le
    sache, et c'est précisément ce que le ticket #953 demandait d'éviter en
    choisissant la saisie manuelle plutôt qu'un rapprochement deviné.
    """
    if not numero or not numero.strip():
        return None
    ticket = session.exec(
        select(Ticket).where(Ticket.numero == numero.strip())
    ).first()
    if not ticket:
        raise HTTPException(422, f"Aucun ticket ne porte le numéro {numero.strip()}")
    return ticket


@router.post("/admin/{type_cle}", response_model=AccesAdminOut, status_code=201)
def creer_acces_admin(
    type_cle: str,
    body: AccesAdminBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Le conseil syndical enregistre un accès POUR un copropriétaire.

    🔴 Troisième voie d'écriture, et elle est assumée (#953) : l'import en masse
    et `declarer-badge` ne couvrent pas le cas d'un badge remis en main propre
    par le conseil. Ce qui aurait été fautif, c'est de la RECOPIER — elle passe
    donc par le même descripteur que les deux autres.

    ⚠️ L'accès est **déduit** quand il n'est pas donné : le bâtiment du lot, ou
    celui des lots du porteur s'il n'y en a qu'un. La règle vit dans
    `utils/acces_perimetre`, et la migration 0190 en porte l'équivalent SQL.
    """
    type_acces = TYPES_ACCES.get(type_cle)
    if type_acces is None:
        raise HTTPException(422, "Type invalide : " + " ou ".join(TYPES_ACCES))
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(422, "Code vide")
    if not body.porteur_id:
        raise HTTPException(422, "Porteur requis")
    porteur = session.get(Utilisateur, body.porteur_id)
    if not porteur:
        raise HTTPException(404, "Porteur introuvable")

    doublon = session.exec(
        select(type_acces.modele).where(
            type_acces.modele.code == code,
            type_acces.modele.user_id == porteur.id,
        )
    ).first()
    if doublon:
        raise HTTPException(400, f"{type_acces.libelle} déjà enregistré pour cette personne")

    ticket = _ticket_par_numero(session, body.ticket_numero)

    objet = type_acces.modele(
        code=code,
        user_id=porteur.id,
        lot_id=body.lot_id,
        statut=body.statut or StatutAcces.actif,
        perimetre_cible=_acces_json(session, body.perimetre_cible, body.lot_id, porteur.id),
    )
    session.add(objet)
    session.commit()
    session.refresh(objet)

    _tracer_sur_ticket(session, ticket, user, type_acces, objet, "enregistré")
    _prevenir_porteur(session, porteur, type_acces, objet)
    return _acces_admin_out([objet], session)[0]


@router.patch("/admin/{type_cle}/{objet_id}", response_model=AccesAdminOut)
def modifier_acces_admin(
    type_cle: str,
    objet_id: int,
    body: AccesAdminBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Corriger un accès — tous ses champs, code compris (arbitré le 14/09/2026).

    ⚠️ Corriger le CODE revient presque toujours à désigner **un autre objet
    physique**. C'est accordé, et l'historique n'en dira rien : la ligne aura
    simplement changé. Si cela pose question un jour, le remède sera de tracer le
    changement de code, pas de retirer le geste.
    """
    type_acces = TYPES_ACCES.get(type_cle)
    if type_acces is None:
        raise HTTPException(422, "Type invalide : " + " ou ".join(TYPES_ACCES))
    objet = _acces_admin(session, type_acces, objet_id)
    ticket = _ticket_par_numero(session, body.ticket_numero)

    if body.code is not None:
        code = body.code.strip()
        if not code:
            raise HTTPException(422, "Code vide")
        objet.code = code
    if body.porteur_id is not None:
        if not session.get(Utilisateur, body.porteur_id):
            raise HTTPException(404, "Porteur introuvable")
        objet.user_id = body.porteur_id
    if body.lot_id is not None:
        objet.lot_id = body.lot_id or None
    if body.statut is not None:
        objet.statut = body.statut
    if body.perimetre_cible is not None:
        objet.perimetre_cible = (
            json.dumps(body.perimetre_cible, ensure_ascii=False)
            if body.perimetre_cible else None
        )

    session.add(objet)
    session.commit()
    session.refresh(objet)
    _tracer_sur_ticket(session, ticket, user, type_acces, objet, "corrigé")
    return _acces_admin_out([objet], session)[0]


@router.delete("/admin/{type_cle}/{objet_id}", status_code=204)
def supprimer_acces_admin(
    type_cle: str,
    objet_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """🔒 Suppression DÉFINITIVE — administrateur seulement (arbitré le 14/09/2026).

    Le conseil syndical, lui, passe un badge en « perdu » ou « suspendu » par le
    `PATCH` ci-dessus. La distinction n'est pas administrative, elle est
    factuelle : **un badge perdu a existé**, et le parc doit pouvoir dire qu'il
    circule dans la nature. Une ligne saisie par erreur, elle, n'a jamais existé.
    Les confondre ferait disparaître des badges réels.

    C'est la règle déjà déployée partout — archiver sur la vue principale,
    supprimer réservé à l'admin (`ux-patterns` §8).
    """
    type_acces = TYPES_ACCES.get(type_cle)
    if type_acces is None:
        raise HTTPException(422, "Type invalide : " + " ou ".join(TYPES_ACCES))
    _acces_admin(session, type_acces, objet_id)
    detacher_acces(
        session, objet_id,
        type_acces.modele_attribution, type_acces.colonne_attribution,
        type_acces.modele_import, type_acces.colonne_import,
    )
    session.delete(session.get(type_acces.modele, objet_id))
    session.commit()


@router.get("/admin/vigiks", response_model=list[AccesAdminOut])
def list_vigiks(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Tous les badges Vigik de la copropriété, avec leur porteur."""
    return _acces_admin_out(session.exec(select(Vigik)).all(), session)


@router.get("/admin/telecommandes", response_model=list[AccesAdminOut])
def list_telecommandes(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Toutes les télécommandes de parking, avec leur porteur."""
    return _acces_admin_out(session.exec(select(Telecommande)).all(), session)


#  🔴 TROIS ROUTES D'ÉCRITURE SUPPRIMÉES ICI le 06/09/2026 (#805), sur arbitrage :
#
#      PATCH  /acces/admin/vigiks/{id}      (changer le statut)
#      POST   /acces/admin/vigiks           (créer un badge)
#      POST   /acces/admin/telecommandes    (créer une télécommande)
#
#  Aucune n'avait d'appelant, et surtout : le besoin qu'elles servaient est déjà
#  couvert DEUX fois.
#
#  | Enregistrer des badges | par où |
#  |---|---|
#  | en masse | l'import Excel + `resoudre_import_*` |
#  | à l'unité | `POST /acces/declarer-badge`, par le résident lui-même |
#
#  Une troisième voie de création, jamais exercée, est du code qui dérive sans
#  qu'on le voie : `changer-role` était dans cet état et avait accumulé un
#  passe-droit que les gestes vivants n'ont pas (#801, même journée).
#
#  ⚠️ Elles n'étaient PAS défectueuses — vérifié : `create_vigik` appelait bien
#  `_create_user_vigiks`, comme la résolution d'import. C'est leur redondance qui
#  les condamne, pas un défaut. Les retirer sur un défaut supposé aurait été un
#  mauvais motif pour une bonne décision.
#
#  Ce qui RESTE, et pourquoi : les deux LECTURES ci-dessus répondent à une
#  question qu'aucun autre écran ne sait poser — « quels badges circulent, et
#  chez qui ? ». C'est le seul trou réel qu'avait ce domaine.

#: Les colonnes de l'export, dans l'ordre — un seul fichier pour les deux types
#: (arbitré le 14/09/2026). Un fichier se trie et se filtre dans un tableur ;
#: deux obligent à les rapprocher à la main.
COLONNES_EXPORT = ["Type", "Code", "Porteur", "Lot", "Accès", "Statut", "Créé le"]


@router.get("/admin/export.csv")
def exporter_parc(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Le parc entier, en CSV — une ligne par accès.

    ⚠️ **Séparateur `;` et BOM UTF-8**, et ce n'est pas un détail de confort :
    Excel en configuration française lit la virgule comme un séparateur décimal
    et ouvre alors tout le fichier dans une seule colonne. Le BOM lui dit que le
    fichier est en UTF-8 — sans lui, « Bâtiment » s'affiche « BÃ¢timent ». Le
    fichier est destiné à être ouvert dans un tableur, pas relu par une machine.

    ⚠️ Les dates passent par `date_courte` : c'est la règle du dépôt, et un
    `strftime` local ici serait la trente-deuxième écriture d'un format.
    """
    lignes = []
    for type_acces in TYPES_ACCES.values():
        objets = session.exec(select(type_acces.modele)).all()
        for fiche, objet in zip(_acces_admin_out(objets, session), objets):
            perimetre = parse_json_perimetres(objet.perimetre_cible)
            lignes.append([
                type_acces.libelle,
                fiche.code,
                fiche.porteur_nom,
                fiche.lot_libelle or "",
                perimetre_label(perimetre) if perimetre else "",
                fiche.statut.value if hasattr(fiche.statut, "value") else str(fiche.statut),
                date_courte(fiche.cree_le),
            ])

    tampon = io.StringIO()
    graveur = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    graveur.writerow(COLONNES_EXPORT)
    graveur.writerows(lignes)

    #  ⚠️ `\ufeff` en tête : c'est le BOM. Il est écrit ICI et nulle part
    #  ailleurs — le dépôt refuse les BOM dans ses SOURCES, ce qui est une autre
    #  question : là il est une donnée du fichier produit, pas un artefact
    #  d'éditeur.
    contenu = "\ufeff" + tampon.getvalue()
    horodatage = datetime.utcnow().strftime("%Y-%m-%d")
    return StreamingResponse(
        iter([contenu]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="parc-acces-{horodatage}.csv"',
        },
    )
