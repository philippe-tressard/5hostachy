"""Le carnet d'entretien — l'histoire du bâti, rassemblée depuis ce qui existe.

Obligatoire depuis le **décret n° 2001-477** : le syndic le tient, tout
copropriétaire peut le consulter, et un acquéreur peut le réclamer via son
vendeur. Il n'était nulle part — mais il était déjà **écrit**, en morceaux, dans
quatre écrans qui ne se parlent pas.

## 🔴 Une VUE, pas un module

Aucun modèle, aucune migration, aucune saisie nouvelle. Trois tables déjà
alimentées répondent chacune à une moitié de la question *« qu'est-il arrivé à ce
bâtiment ? »* :

| Source | Ce qu'elle apporte | Filtre |
|---|---|---|
| `ContratEntretien` | l'équipement suivi, son prestataire, sa périodicité | `actif` |
| `Evenement` | l'intervention réellement faite | `statut_kanban == termine` |
| `Ticket` | l'incident résolu sur le bâti | `ferme_le` + catégorie technique |

Créer une table `carnet` aurait produit une **quatrième** version de faits déjà
enregistrés trois fois, à ressaisir à la main et libre de diverger dès le premier
oubli. Le carnet n'a rien à retenir : il a à *relire*.

## Ce qu'il montre et que rien d'autre ne montre : les TROUS

Ranger par équipement fait apparaître ce qui manque. Un contrat dont la
`prochaine_visite` est dépassée porte une alerte — aujourd'hui, rien ne le dit :
la date existe en base, aucun écran ne la compare à aujourd'hui.

⚠️ **Ce n'est pas une alerte de plus**, c'est la même donnée lue à l'endroit où
elle veut dire quelque chose. Un contrôle réglementaire non fait depuis deux ans
ne se voit dans aucune liste triée par date de création.

## Ce qui n'est PAS ici

Les montants. Ils vivent dans les documents et les devis, et les faire remonter
demanderait de décider qui les voit — une question distincte de celle du carnet.
Le lot suivant, s'il est demandé.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from sqlmodel import Session, select

from app.models.core import Ticket
from app.models.evenement import Evenement
from app.models.prestataires import ContratEntretien, Prestataire
from app.models.tickets import CategorieTicket, StatutTicket
from app.utils.liens import lien_element, lien_ticket
from app.utils.perimetres import couvre, parse_json_perimetres

#: Les catégories de ticket qui parlent du **bâti**. Les autres — une question,
#: un signalement de bug, une nuisance de voisinage, une demande d'accès — sont
#: de la vie de la copropriété, pas de son entretien. Les inclure noierait le
#: carnet dans des faits qu'un acquéreur ou un syndic n'y cherche pas.
CATEGORIES_BATI = frozenset({
    CategorieTicket.panne,
    CategorieTicket.espaces_verts,
    CategorieTicket.sinistre,
    CategorieTicket.etude_travaux,
})

#: Le `statut_kanban` d'un événement réellement réalisé. La colonne est une
#: chaîne libre en base ; la valeur vient de `StatutKanban.termine`.
KANBAN_TERMINE = "termine"


@dataclass
class EntreeCarnet:
    """Un fait daté qui concerne le bâti.

    `equipement` porte la **valeur** de `TypeEquipement` (`"ascenseur"`), jamais
    son libellé : la table des libellés vit côté front (`$lib/prestataires`,
    `EQUIPEMENTS`) et `test_types_equipement.py` la compare déjà à l'énumération
    du serveur. En rendre une seconde ici en ferait une troisième écriture.
    """

    date_fait: date
    libelle: str
    origine: str  # contrat | intervention | incident
    detail: str = ""
    equipement: Optional[str] = None
    #: Les codes de périmètre de la ligne — l'écran les rend par `perimetreLabel`,
    #: comme partout ailleurs. Remplace `batiment_id` (10/09/2026) : un contrat
    #: sur « Parking » n'a pas de bâtiment, et n'en est pas moins situé.
    perimetre: list[str] = field(default_factory=list)
    lien: str = ""
    alerte: Optional[str] = None

    def en_dict(self) -> dict:
        return {
            #  ISO : c'est une clé de tri et de comparaison, pas un affichage.
            #  Le format français est appliqué par l'écran, qui a `fmtDate`.
            "date": self.date_fait.isoformat(),
            "libelle": self.libelle,
            "origine": self.origine,
            "detail": self.detail,
            "equipement": self.equipement,
            "perimetre": self.perimetre,
            "lien": self.lien,
            "alerte": self.alerte,
        }


def _jour(valeur) -> Optional[date]:
    """La date d'un fait, que la colonne soit `date` ou `datetime`.

    ⚠️ `datetime` est une sous-classe de `date` : tester `date` en premier
    rendrait un `datetime` tel quel, et deux entrées du carnet ne se compareraient
    plus entre elles (`'<' not supported between datetime and date`).
    """
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    return None


def _codes_de(valeur: Optional[str]) -> list[str]:
    """Le périmètre d'une ligne, quelle que soit la forme de sa colonne.

    `Ticket` et `ContratEntretien` portent un tableau JSON, `Evenement` une
    chaîne simple (`"résidence"`, `"bat:3"`). Une seule lecture pour les trois :
    trois lectures auraient divergé sur le JSON illisible, et c'est toujours la
    troisième qui oublie le `try`.
    """
    if not valeur:
        return []
    texte = valeur.strip()
    if texte.startswith("["):
        return parse_json_perimetres(texte)
    return [texte]


def alerte_visite(echeance: Optional[date], aujourdhui: date) -> Optional[str]:
    """« visite attendue depuis N jours », ou rien.

    Fonction à part, et publique, pour une raison : c'est **la seule décision** de
    ce module — tout le reste est de la lecture de tables. Une décision se teste
    sans base ni session, et celle-ci a trois bords qui méritent d'être fixés :
    l'échéance absente, l'échéance du jour même, et l'accord du pluriel.

    ⚠️ Le jour même n'est **pas** un retard. Une visite attendue aujourd'hui peut
    encore avoir lieu cet après-midi ; l'annoncer en retard ferait crier le carnet
    sur un contrat parfaitement tenu — et une alerte qui crie sur du normal finit
    ignorée (`standards/04` §7).
    """
    if echeance is None or echeance >= aujourdhui:
        return None
    retard = (aujourdhui - echeance).days
    #  Le nombre de JOURS, pas « en retard » : un contrôle en retard de trois
    #  jours et un de deux ans ne demandent pas le même geste, et c'est l'écart
    #  qui le dit.
    return f"visite attendue depuis {retard} jour{'s' if retard > 1 else ''}"


def type_equipement_resolu(contrat, specialite_prestataire: Optional[str]) -> Optional[str]:
    """La catégorie d'un contrat — celle qu'il porte, ou celle de son prestataire.

    🔴 **Le carnet lisait le champ BRUT et l'écran Contrats la valeur DÉDUITE.**
    Un contrat de VMC enregistré en « autre », confié à un prestataire de
    spécialité `vmc`, apparaissait donc « VMC » dans l'onglet Contrats et
    « Autre » dans le carnet. Signalé à l'écran le 10/09/2026.

    La règle vit côté front depuis longtemps (`$lib/reporting`,
    `typeEquipementDuContrat`) et servait quatre écrans. Le carnet est le premier
    lecteur SERVEUR de cette notion : la copie est obligatoire — les contextes de
    build sont `./api` et `./front` —, et `test_type_equipement_resolu.py` refuse
    qu'elles divergent, comme pour le libellé d'étage et celui des périmètres.

    ⚠️ « autre » n'est pas une catégorie, c'est une ABSENCE de catégorie : c'est
    pour cela qu'elle laisse la spécialité du prestataire prendre le relais. Une
    catégorie réelle, elle, n'est jamais remplacée.
    """
    brut = getattr(contrat, "type_equipement", None)
    propre = brut.value if hasattr(brut, "value") else (str(brut) if brut else None)
    if propre and propre != "autre":
        return propre
    return specialite_prestataire or propre or "autre"


def _entrees_contrats(session: Session, perimetre: Optional[str]) -> list[EntreeCarnet]:
    """Un contrat en cours est un fait du carnet : il dit ce qui est SUIVI.

    Et sa `prochaine_visite` dépassée est le seul endroit du produit où une
    échéance d'entretien manquée devient visible.
    """
    requete = select(ContratEntretien).where(ContratEntretien.actif == True)  # noqa: E712

    aujourdhui = date.today()
    entrees: list[EntreeCarnet] = []
    for contrat in session.exec(requete).all():
        debut = _jour(contrat.date_debut)
        if debut is None:
            continue
        codes = _codes_de(contrat.perimetre_cible)
        if not couvre(codes, perimetre):
            continue
        prestataire = session.get(Prestataire, contrat.prestataire_id)
        detail = prestataire.nom if prestataire and prestataire.nom else "prestataire inconnu"
        if contrat.numero_contrat:
            detail = f"{detail} · contrat {contrat.numero_contrat}"

        alerte = alerte_visite(_jour(contrat.prochaine_visite), aujourdhui)

        entrees.append(EntreeCarnet(
            date_fait=debut,
            libelle=contrat.libelle,
            origine="contrat",
            detail=detail,
            equipement=type_equipement_resolu(
                contrat, prestataire.specialite if prestataire else None
            ),
            perimetre=codes,
            lien=lien_element("contrat", contrat.id),
            alerte=alerte,
        ))
    return entrees


def _entrees_interventions(session: Session, perimetre: Optional[str]) -> list[EntreeCarnet]:
    """Ce qui a été FAIT — un événement arrivé au bout de son kanban."""
    requete = select(Evenement).where(Evenement.statut_kanban == KANBAN_TERMINE)

    entrees: list[EntreeCarnet] = []
    for evenement in session.exec(requete).all():
        quand = _jour(evenement.debut)
        if quand is None:
            continue
        codes = _codes_de(evenement.perimetre)
        if not couvre(codes, perimetre):
            continue
        detail = ""
        if evenement.prestataire_id:
            prestataire = session.get(Prestataire, evenement.prestataire_id)
            if prestataire and prestataire.nom:
                detail = prestataire.nom
        if evenement.lieu:
            detail = f"{detail} · {evenement.lieu}" if detail else evenement.lieu

        #  L'équipement vient du CONTRAT rattaché quand il y en a un : un
        #  événement ne porte pas de type d'équipement, et le deviner d'après son
        #  titre donnerait une réponse plausible et parfois fausse.
        equipement = None
        if evenement.contrat_id:
            contrat = session.get(ContratEntretien, evenement.contrat_id)
            if contrat is not None:
                presta = session.get(Prestataire, contrat.prestataire_id)
                equipement = type_equipement_resolu(
                    contrat, presta.specialite if presta else None
                )

        entrees.append(EntreeCarnet(
            date_fait=quand,
            libelle=evenement.titre,
            origine="intervention",
            detail=detail,
            equipement=equipement,
            perimetre=codes,
            lien=lien_element("ev", evenement.id),
        ))
    return entrees


def _entrees_incidents(session: Session, perimetre: Optional[str]) -> list[EntreeCarnet]:
    """Un incident résolu sur le bâti — ce que le carnet appelle un sinistre."""
    requete = select(Ticket).where(
        Ticket.statut == StatutTicket.résolu,
        Ticket.ferme_le.isnot(None),
    )

    entrees: list[EntreeCarnet] = []
    for ticket in session.exec(requete).all():
        if ticket.categorie not in CATEGORIES_BATI:
            continue
        if not couvre(_codes_de(ticket.perimetre_cible), perimetre):
            continue
        quand = _jour(ticket.ferme_le)
        if quand is None:
            continue
        categorie = ticket.categorie.value if hasattr(ticket.categorie, "value") else str(ticket.categorie)
        entrees.append(EntreeCarnet(
            date_fait=quand,
            libelle=ticket.titre,
            origine="incident",
            detail=f"ticket {ticket.numero} · {categorie}",
            perimetre=_codes_de(ticket.perimetre_cible),
            lien=lien_ticket(ticket.id),
        ))
    return entrees


def construire_carnet(session: Session, *, perimetre: Optional[str] = None) -> list[dict]:
    """Le carnet complet, du fait le plus récent au plus ancien.

    ⚠️ Le tri est **décroissant sur la date du fait**, pas sur la date de saisie :
    un contrat signé en 2019 et enregistré hier appartient à 2019. C'est la
    distinction que le fil d'activité fait déjà — *dater du dernier fait, jamais
    du premier* —, appliquée à l'envers : ici on date de ce qui s'est passé.
    """
    entrees = (
        _entrees_contrats(session, perimetre)
        + _entrees_interventions(session, perimetre)
        + _entrees_incidents(session, perimetre)
    )
    entrees.sort(key=lambda e: e.date_fait, reverse=True)
    return [entree.en_dict() for entree in entrees]
