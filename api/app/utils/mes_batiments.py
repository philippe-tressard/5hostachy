"""Les bâtiments d'un utilisateur — au sens large, et la source unique de cette notion.

## Ce que ce module sert, et ce qu'il ne sert pas

Il répond à « quels bâtiments sont les MIENS ? », question posée par la préférence
« n'afficher que les contenus de mes bâtiments » (#339). Un copropriétaire peut
détenir des lots dans plusieurs bâtiments : `Utilisateur.batiment_id`, qui est
unique, ne suffit donc pas à répondre.

⚠️ **Cette liste décide d'un accès depuis le 02/09/2026.** Ce fichier affirmait
l'inverse — « elle ne décide jamais d'un accès », et la règle « continue de
s'appuyer sur le seul `batiment_id` ». C'est faux, et le laisser écrit serait
pire que de ne rien écrire : une consigne fausse est celle qu'on croit.

**Trois** appelants, un seul et même sens de « mes bâtiments » :

| Appelant | Ce qu'il en fait | Cas zéro |
|---|---|---|
| la préférence « n'afficher que les contenus de mes bâtiments » (`visibility.perimetre_visible`, branche restreinte) | retire ce que l'utilisateur a demandé à ne plus voir | « rien à restreindre » → on montre |
| la **règle géographique d'accès** (`visibility.perimetre_visible`) — centralisée là et nulle part ailleurs | décide qui voit un contenu ciblé sur un bâtiment | « pas résident » → on refuse |
| `utils/preferences_mail.classer` | route un e-mail vers « mon bâtiment » ou « autres bâtiments » | « on ne peut pas dire que ça vient d'ailleurs » → on n'y touche pas |

⚠️ Ils appellent tous la même fonction et diffèrent sur le seul **cas zéro** —
c'est la seule chose que cette fonction ne tranche pas à leur place, et c'est
volontaire : une absence d'information ne veut pas dire la même chose selon
qu'on masque, qu'on autorise ou qu'on trie.

## Ce que l'arbitrage du 02/09/2026 a changé, et ce qu'il n'a pas changé

La contrainte du 14/08/2026 — *une agence, un bailleur ou un mandataire qui
n'avaient pas de visibilité n'en gagnent aucune* — est **levée sur l'axe
bâtiment**, dans les mots de l'utilisateur : *« un bailleur sans rattachement
voit les bâtiments de ses lots »*, et à généraliser. Un compte rattaché au
bâtiment A et détenteur d'un lot en B voit désormais B.

🔒 Elle tient **intacte sur l'axe public** : `public_cible`,
`ProfilAccesDocument` et les règles mandataire sont combinés en ET avec la règle
géographique. Détenir un lot donne le bâtiment, jamais le droit de lire ce qui ne
vous est pas adressé. Verrouillé par `tests/test_visibilite_ouverte.py`, qui
vérifie l'élargissement et sa borne **dans le même test** — pour qu'ils ne
puissent pas se séparer.


## Le cache

Même parti pris que `utils/perimetres.arbre()` : une durée courte, et **aucune
mise en cache d'un résultat obtenu sur une base indisponible** — figer une liste
vide masquerait le rétablissement, et une liste vide vaut ici « je ne sais pas ».
"""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger("hostachy.mes_batiments")

#: Assez court pour qu'un lot ajouté se voie vite, assez long pour ne pas
#: interroger la base à chaque élément d'une liste de cinquante actualités.
_TTL_SECONDES = 30.0

_cache: dict[int, tuple[float, frozenset[int]]] = {}


def invalider_cache(user_id: Optional[int] = None) -> None:
    """À appeler après une écriture sur `user_lot` — ou entièrement, sans argument."""
    if user_id is None:
        _cache.clear()
    else:
        _cache.pop(user_id, None)


def batiments_de_l_utilisateur(user) -> frozenset[int]:
    """Les bâtiments de son rattachement **et** de ses lots actifs.

    Renvoie un ensemble **vide** si rien n'est connu. ⚠️ Ce cas zéro n'a PAS le
    même sens pour les deux appelants, et cette fonction ne tranche pas à leur
    place — elle rend un fait, ils en tirent une décision :

    - la **restriction volontaire** le lit « aucune restriction possible » :
      quelqu'un qui coche une case ne doit pas se retrouver devant un fil vide ;
    - la **règle d'accès** le lit « pas résident de la copropriété » : ni
      rattachement ni lot, donc aucun contenu ciblé sur un bâtiment.

    Répondre `True` des deux côtés — ce que faisait le repli permissif de
    `perimetre_visible` jusqu'au 02/09/2026 — ouvrait toute la résidence, et avec
    elle les actualités confidentielles, à des comptes techniques (cas zéro,
    `standards/04` §2 : une absence d'information n'est pas une autorisation).
    """
    user_id = getattr(user, "id", None)
    connus: set[int] = set()
    if getattr(user, "batiment_id", None) is not None:
        connus.add(user.batiment_id)

    if user_id is None:
        return frozenset(connus)

    entree = _cache.get(user_id)
    if entree is not None and (time.monotonic() - entree[0]) < _TTL_SECONDES:
        return entree[1] | frozenset(connus)

    try:
        from sqlmodel import select

        from app.database import SessionLocal
        from app.models.copropriete import Lot
        from app.models.core import UserLot

        with SessionLocal() as session:
            lignes = session.exec(
                select(Lot.batiment_id)
                .join(UserLot, UserLot.lot_id == Lot.id)
                .where(UserLot.user_id == user_id, UserLot.actif == True)  # noqa: E712
            ).all()
        #  `batiment_id` est nul sur un lot de parking : un parking n'est pas un
        #  bâtiment et ne doit pas entrer dans la liste.
        des_lots = frozenset(b for b in lignes if b is not None)
    except Exception as exc:
        #  Pas de mise en cache : la base reviendra, et une liste figée à vide
        #  ferait durer la panne au-delà d'elle-même.
        logger.error(
            "Lots de l'utilisateur %s illisibles (%s) — seul son bâtiment de "
            "rattachement est retenu", user_id, exc,
        )
        return frozenset(connus)

    _cache[user_id] = (time.monotonic(), des_lots)
    return des_lots | frozenset(connus)
