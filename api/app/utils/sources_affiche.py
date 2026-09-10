"""Ce qu'on peut reprendre au hall — et d'où.

## Ce qui a été demandé (10/09/2026)

*« Permet la génération d'une affiche à partir de n'importe quelle publication
incluse dans le fil d'actualité, quel que soit le type de publication, et
restreint à celles qui ne sont pas archivées »*, puis, après livraison : *« je ne
vois pas la présélection de toutes les publications, tickets etc. publiés dans le
fil d'actualité »*.

Le premier lot n'avait retiré qu'un **plafond** : le sélecteur proposait toujours
des `Publication`, et rien d'autre. Le fil, lui, agrège trois familles — les
actualités, les tickets et les événements. C'est le fil qui est la référence,
pas la table.

## Ce que ce module porte, et ce qu'il ne porte pas

Il répond à deux questions, et à elles seules :

* **que peut-on reprendre ?** — `sources_disponibles()` ;
* **avec quoi pré-remplir ?** — `prefill_source()`.

Le rendu de l'affiche vit dans `utils/annonce_hall.py` ; la décision d'envoyer,
dans le routeur. Ici, on ne fait que désigner et lire.

## 🔴 Ce qui est EXCLU, et pourquoi

| Exclu | Raison |
|---|---|
| brouillons | un texte que personne n'a validé n'a pas à paraître au hall |
| archivés | c'est la demande : ce qui a quitté le fil a cessé d'être d'actualité |
| **confidentiels** | une affiche de hall est lue par **tout le monde**, y compris des gens qui n'ont pas accès à l'objet. Reprendre un ticket refermé sur son auteur et le CS le publierait au mur — c'est le pire sens de l'erreur, et rien à l'écran ne le rattraperait |
| **réservés au conseil syndical** (🛡️) | même raison, autre mécanisme : la restriction passe par `public_cible`, pas par `confidentiel`. Confirmé à l'écran le 10/09/2026 — *« les publications confidentielles ne sont bien sûr pas affichées, ou celles qui sont réservées au Conseil Syndical »*. Les deux notions coexistent depuis #347 et se combinent en ET : n'en filtrer qu'une laissait l'autre passer |
| tickets **annulés** | ils disparaissent du fil et sont purgés ; les proposer serait proposer ce qui n'existera plus demain |

⚠️ La confidentialité est vérifiée **ici**, à la source, et non à l'affichage du
sélecteur : une liste qui montre ce qu'on ne doit pas reprendre invite à le
reprendre, et le premier qui contournera l'écran passera par l'API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models.core import Publication, Ticket
from app.models.evenement import Evenement
from app.utils.perimetres import parse_json_perimetres

#: Les trois familles reprenables, et leur libellé à l'écran.
FAMILLES: dict[str, str] = {
    "publication": "Actualité",
    "ticket": "Ticket",
    "evenement": "Événement",
}

#: Fenêtre du fil, en jours. Recopiée depuis `routers/flux/__init__.py` —
#: l'importer créerait un cycle (le routeur importe les utilitaires). Le test
#: `test_sources_affiche.py` refuse que les deux divergent.
FENETRE_JOURS = 377


#: Le code du public « conseil syndical », tel que le vocabulaire partagé le
#: nomme. Importé de `visibility` plutôt que retapé : ce vocabulaire est déjà
#: comparé entre le serveur et l'écran par `test_destinataires_vocabulaire.py`,
#: et une troisième écriture échapperait à cette comparaison.
def _code_cs() -> str:
    from app.utils.visibility import CODES_PUBLIC_CIBLE

    return CODES_PUBLIC_CIBLE[-1]


def reserve_au_cs(public_cible: Optional[str]) -> bool:
    """Ce contenu ne s'adresse-t-il qu'au conseil syndical ?

    🔴 **Deux mécanismes, pas un** : `confidentiel` restreint la lecture au
    périmètre visé, `public_cible` désigne à QUI l'on parle. Ils se combinent en
    ET depuis #347, et une affiche de hall doit écarter les deux — ne filtrer que
    le premier laissait passer une publication marquée 🛡️.
    """
    return _code_cs() in parse_json_perimetres(public_cible or "")


@dataclass
class SourceAffiche:
    """Un élément du fil, réduit à ce qu'un sélecteur doit montrer."""

    type: str
    id: int
    titre: str
    date: datetime
    epingle: bool

    @property
    def famille(self) -> str:
        return FAMILLES[self.type]

    def cle(self) -> str:
        """Identifiant stable côté écran — le type SEUL ne suffit pas, et l'id
        non plus : trois familles peuvent porter le même numéro."""
        return f"{self.type}:{self.id}"


def sources_disponibles(session: Session, *, maintenant: Optional[datetime] = None
                        ) -> list[SourceAffiche]:
    """Tout ce que le fil montre aujourd'hui et qu'on peut reprendre au hall.

    Trié comme le fil : les épinglés d'abord, puis du plus récent au plus ancien.
    """
    maintenant = maintenant or datetime.utcnow()
    depuis = maintenant - timedelta(days=FENETRE_JOURS)
    sources: list[SourceAffiche] = []

    #  ── Actualités ──────────────────────────────────────────────────────────
    #  L'archivage d'une publication est CALCULÉ (résolue, ou trop ancienne) :
    #  la règle vit dans le routeur qui sert le fil, et on l'appelle plutôt que
    #  de la refaire — deux copies divergeraient sur le cas limite.
    from app.routers.publications.crud import _is_archived, seuil_archivage_jours

    seuil = seuil_archivage_jours(session)
    for pub in session.exec(select(Publication)).all():
        if pub.brouillon or pub.archivee or pub.confidentiel:
            continue
        if reserve_au_cs(pub.public_cible):
            continue
        if _is_archived(pub, seuil):
            continue
        sources.append(SourceAffiche("publication", pub.id, pub.titre, pub.cree_le,
                                     bool(pub.epingle)))

    #  ── Tickets ─────────────────────────────────────────────────────────────
    for tk in session.exec(select(Ticket).where(Ticket.cree_le >= depuis)).all():
        if tk.confidentiel or (tk.statut and str(getattr(tk.statut, "value", tk.statut)) == "annule"):
            continue
        sources.append(SourceAffiche("ticket", tk.id, tk.titre, tk.cree_le,
                                     bool(getattr(tk, "epingle", False))))

    #  ── Événements ──────────────────────────────────────────────────────────
    for ev in session.exec(select(Evenement).where(Evenement.cree_le >= depuis)).all():
        if ev.archivee:
            continue
        sources.append(SourceAffiche("evenement", ev.id, ev.titre, ev.cree_le, False))

    sources.sort(key=lambda s: (not s.epingle, -s.date.timestamp()))
    return sources


def prefill_source(session: Session, type_source: str, id_source: int) -> Optional[dict]:
    """Les champs d'un élément du fil, prêts à alimenter le formulaire d'affiche.

    Rend `None` quand l'élément n'existe pas **ou qu'il n'est pas reprenable** :
    l'appelant répond alors 404, sans distinguer les deux cas. Dire « il existe
    mais vous ne pouvez pas le reprendre » renseignerait sur un contenu
    confidentiel.
    """
    reprenable = {s.cle() for s in sources_disponibles(session)}
    if f"{type_source}:{id_source}" not in reprenable:
        return None

    if type_source == "publication":
        from app.routers.annonces_hall import images_de_publication

        pub = session.get(Publication, id_source)
        return {
            "titre": pub.titre,
            "message": pub.contenu,
            "perimetre_cible": parse_json_perimetres(pub.perimetre_cible),
            "images": images_de_publication(pub, session),
        }

    if type_source == "ticket":
        tk = session.get(Ticket, id_source)
        #  ⚠️ Les photos d'un ticket sont des CONSTATS — une fuite, une porte
        #  cassée. On ne les reprend pas : une affiche de hall montre ce qu'on
        #  annonce, pas l'état des lieux, et le CS les ajoutera s'il les veut.
        return {
            "titre": tk.titre,
            "message": tk.description,
            "perimetre_cible": parse_json_perimetres(tk.perimetre_cible),
            "images": [],
        }

    ev = session.get(Evenement, id_source)
    #  Un événement porte `perimetre` (une chaîne) et non `perimetre_cible` :
    #  `parse_json_perimetres` accepte les deux formes.
    return {
        "titre": ev.titre,
        "message": ev.description or "",
        "perimetre_cible": parse_json_perimetres(ev.perimetre),
        "images": [],
    }
