"""Périmètres — l'arbre en base, lu et parcouru au même endroit partout.

⚠️ **Ce module est la moitié « arbre » du paquet `app.utils.perimetres`.** Il ne
rend aucun libellé : le rendu vit dans `libelles.py`, qui importe celui-ci. La
dépendance est à sens unique, et elle doit le rester — l'arbre n'a pas à savoir
comment on l'affiche.

Le découpage date du 27/08/2026 : le fichier unique passait 500 lignes, seuil de
la règle de modularité (rang 1). La frontière suit celle que ce docstring
énonçait déjà — « Les primitives » ici, « Libellés » là-bas. La surface publique,
elle, N'A PAS BOUGÉ : `from app.utils.perimetres import …` continue de tout
trouver, via `__init__.py`.

## Ce que ce module remplaçait

Un périmètre (« résidence », « bat:3 », « parking ») était une **table de libellés
écrite en dur**, et elle l'était **trois fois** le 08/08/2026 :

- `app/routers/flux/commun.py` — table complète, bâtiments 1 à 9, AFUL ;
- `app/routers/tickets.py` (relance syndic) — table partielle : ni AFUL, ni
  bâtiment au-delà de ce que le préfixe `bat:` produisait ;
- `front/src/lib/utils.ts` — côté interface, arrêtée à `bat:4`.

Les tables Python ne donnaient pas le même libellé pour un même périmètre, et le
front en donnait un troisième : un ticket ciblé AFUL sortait « aful » dans l'e-mail
de relance, « AFUL » dans le fil, et un `bat:5` s'affichait « Bât. 5 » côté API mais
`bat:5` **brut** à l'écran. C'est la divergence typique décrite par
`standards/02-factorisation.md` §2.

## Ce qui gouverne ce module maintenant

**Aucun code de périmètre n'est écrit ici.** Le produit doit servir une autre
copropriété, qui n'a ni AFUL, ni quatre bâtiments, ni forcément de caves — et qui
aura peut-être une piscine et trois entrées. L'arbre vit dans la table `perimetre`,
il est reconstructible depuis l'administration, et **le vider ne casse rien** : un
périmètre vide vaut « concerne tout le monde », ce qui était déjà la règle
(`visibility.perimetre_visible`).

C'est pourquoi `parse_perimetres` ne renvoie plus la chaîne littérale
« résidence » quand le champ est vide, mais le **nœud racine à portée globale**
désigné par les données — voir `code_par_defaut`.

## Les primitives

`a_portee_globale`, `batiments_cibles` et `perimetre_du_batiment` sont les
seules fonctions qui parcourent l'arbre. Leurs
consommateurs — `utils/visibility.py` (qui voit), `utils/destinataires.py` (qui
est notifié), `routers/flux/evenements.py` (le badge « concerne mon bâtiment ») et
`utils/fiche_arrivant.py` (le document imprimé) — portaient auparavant chacun sa
propre copie de la liste des périmètres transverses, ou sa propre convention de
nommage.
"""
from __future__ import annotations

import json
import logging
import time
from typing import NamedTuple, Optional

logger = logging.getLogger("hostachy.perimetres")

#: Durée de vie du cache. Le cache est vidé explicitement à chaque écriture
#: (`invalider_cache`), mais uvicorn peut servir plusieurs *workers* : une
#: invalidation dans l'un n'atteint pas les autres. Ce délai garantit la
#: convergence sans bus de messages — un libellé corrigé dans l'administration
#: apparaît partout en moins d'une demi-minute.
_TTL_SECONDES = 30.0

_PREFIXE_BATIMENT = "bat:"


class Noeud(NamedTuple):
    """Un périmètre, tel que l'arbre le donne. Immuable, sans session attachée."""
    code: str
    libelle: str
    libelle_court: str
    description: str
    icone: Optional[str]
    parent: Optional[str]
    batiment_id: Optional[int]
    portee_globale: bool
    selectionnable: bool
    actif: bool
    ordre: int


_cache: Optional[dict[str, Noeud]] = None
_cache_pose: float = 0.0


def invalider_cache() -> None:
    """À appeler après toute écriture dans la table `perimetre`."""
    global _cache, _cache_pose
    _cache = None
    _cache_pose = 0.0


def arbre() -> dict[str, Noeud]:
    """L'arbre entier, indexé par code **en minuscules**.

    Renvoie un dictionnaire vide si la table n'existe pas encore (premier
    démarrage, avant `create_db_and_tables`) ou si elle est vide — et c'est un état
    valide, pas une erreur : une copropriété qui n'a pas encore configuré ses
    périmètres n'en restreint aucun.
    """
    global _cache, _cache_pose
    if _cache is not None and (time.monotonic() - _cache_pose) < _TTL_SECONDES:
        return _cache

    #  Imports différés : ce module est importé par `utils/visibility.py`, lui-même
    #  importé très tôt. Charger la base au moment de l'appel, pas de l'import.
    try:
        from sqlmodel import select

        from app.database import SessionLocal
        from app.models.perimetre import Perimetre

        with SessionLocal() as session:
            lignes = session.exec(select(Perimetre)).all()
            #  Le parent est exposé par son CODE et non son id : tout le reste du
            #  produit raisonne en codes, et un cache qui mélangerait les deux
            #  obligerait chaque appelant à faire la conversion.
            code_par_id = {ligne.id: ligne.code.lower() for ligne in lignes}
            construit = {
                ligne.code.lower(): Noeud(
                    code=ligne.code,
                    libelle=ligne.libelle,
                    libelle_court=ligne.libelle_court or ligne.libelle,
                    description=ligne.description or "",
                    icone=ligne.icone,
                    parent=code_par_id.get(ligne.parent_id),
                    batiment_id=ligne.batiment_id,
                    portee_globale=bool(ligne.portee_globale),
                    selectionnable=bool(ligne.selectionnable),
                    actif=bool(ligne.actif),
                    ordre=ligne.ordre or 0,
                )
                for ligne in lignes
            }
    except Exception as exc:
        #  Table absente ou base indisponible. On ne met **pas** le résultat en
        #  cache : la table apparaîtra au prochain démarrage, et figer un arbre
        #  vide pour 30 s masquerait le rétablissement.
        #
        #  Conséquence à connaître, et c'est pourquoi ce journal est en `error` :
        #  un arbre illisible ne permet plus de résoudre un périmètre, donc les
        #  contenus qui en citent un deviennent invisibles des résidents (le
        #  conseil syndical et l'administration continuent de tout voir). C'est le
        #  sens choisi : un contrôle qui ne peut pas s'exécuter ne renvoie pas OK
        #  (`standards/04`). L'inverse aurait rendu lisible, sur un simple hoquet
        #  de base, un document réservé à un autre bâtiment.
        logger.error(
            "Arbre des périmètres illisible (%s) — les contenus à périmètre "
            "deviennent invisibles des résidents jusqu'au rétablissement", exc,
        )
        return {}

    _cache = construit
    _cache_pose = time.monotonic()
    return _cache


# ── Parcours de l'arbre : les trois primitives ────────────────────────────────

def _chaine(code: str, noeuds: dict[str, Noeud]) -> list[Noeud]:
    """Le nœud puis ses ancêtres, du plus proche au plus lointain.

    Renvoie une liste **vide** si le code est inconnu : un contenu qui cite un
    périmètre supprimé n'accorde aucun droit — il n'en retire pas non plus, il ne
    compte simplement pas. Un `parent_id` orphelin ou un cycle arrête la remontée
    sans lever : `visited` est le garde-fou, parce qu'une boucle dans l'arbre ne
    doit jamais pouvoir suspendre une requête (`standards/04` — un contrôle qui ne
    peut pas s'exécuter ne renvoie pas OK).
    """
    depart = noeuds.get(code.strip().lower())
    if depart is None:
        return []
    chaine = [depart]
    vus = {depart.code.lower()}
    courant = depart
    while courant.parent:
        suivant = noeuds.get(courant.parent)
        if suivant is None or suivant.code.lower() in vus:
            break
        chaine.append(suivant)
        vus.add(suivant.code.lower())
        courant = suivant
    return chaine


def a_portee_globale(codes: list[str]) -> bool:
    """L'un de ces périmètres concerne-t-il tous les résidents ?

    Vrai dès qu'un nœud cité — ou l'un de ses ancêtres — porte `portee_globale`.
    L'héritage est ce qui permet de cibler « Parking › Portail d'accès » sans avoir
    à rappeler que le parking concerne tout le monde.
    """
    noeuds = arbre()
    if not noeuds:
        return False
    return any(
        n.portee_globale
        for code in codes
        for n in _chaine(code, noeuds)
    )


def batiments_cibles(codes: list[str]) -> set[int]:
    """Les identifiants de bâtiments réellement visés par ces périmètres.

    Pour chaque code, on retient le `batiment_id` du nœud ou, à défaut, celui du
    plus proche ancêtre qui en porte un — c'est ainsi que « Bât. 2 › Hall d'entrée »
    concerne le bâtiment 2 sans le répéter sur chaque espace.
    """
    noeuds = arbre()
    if not noeuds:
        return set()
    cibles: set[int] = set()
    for code in codes:
        for n in _chaine(code, noeuds):
            if n.batiment_id is not None:
                cibles.add(n.batiment_id)
                break
    return cibles


def perimetre_du_batiment(batiment_id: Optional[int]) -> Optional[Noeud]:
    """Le nœud de l'arbre qui **est** ce bâtiment — chemin inverse de `batiments_cibles`.

    Sert à tout ce qui part d'un bâtiment (un membre du conseil syndical, un lot)
    et doit le **nommer** : le nom et l'icône viennent alors de l'arbre, donc de
    l'administration, au lieu d'être fabriqués par un `f"Bât. {numero}"` recopié.
    Cette convention-là existait dans sept fichiers le 14/08/2026 ; le document
    imprimé était le seul endroit où elle produisait un libellé qu'aucun
    renommage ne rattrapait, puisqu'il ne passe par aucun écran.

    Renvoie `None` si l'arbre est vide, si le bâtiment n'y figure pas, ou si son
    nœud est inactif — l'appelant garde alors son propre repli. Ne jamais faire
    lever : un document doit se produire même sur un arbre incomplet.

    Seul le nœud « bâtiment » porte un `batiment_id` ; ses espaces (hall,
    ascenseur…) l'héritent de leur ancêtre, ce que `batiments_cibles` exploite.
    Si plusieurs nœuds actifs le portaient malgré tout — données reprises à la
    main — on retient le plus prioritaire, jamais un au hasard.
    """
    if batiment_id is None:
        return None
    candidats = [
        n for n in arbre().values()
        if n.batiment_id == batiment_id and n.actif
    ]
    if not candidats:
        return None
    return min(candidats, key=lambda n: (n.ordre, n.code))


# ── Analyse des champs stockés ────────────────────────────────────────────────

def code_par_defaut() -> Optional[str]:
    """Le périmètre qu'un contenu sans périmètre explicite désigne implicitement.

    C'est la racine à portée globale la plus prioritaire — « Copropriété entière »
    sur l'arbre livré. Cette fonction existe pour que la valeur par défaut soit une
    **donnée** et non la chaîne « résidence » écrite dans le code : une
    copropriété qui renomme ou supprime ce nœud ne doit pas casser l'application.

    Renvoie `None` sur un arbre vide, et alors `parse_perimetres` rend une liste
    vide — que `perimetre_visible` traite déjà comme « visible de tous ».
    """
    candidats = [
        n for n in arbre().values()
        if n.portee_globale and n.parent is None and n.actif
    ]
    if not candidats:
        return None
    return min(candidats, key=lambda n: (n.ordre, n.code)).code


def _avec_defaut(codes: list[str]) -> list[str]:
    if codes:
        return codes
    defaut = code_par_defaut()
    return [defaut] if defaut else []


def parse_perimetres(perimetre: Optional[str]) -> list[str]:
    """Champ `perimetre` en texte (« résidence », « parking,cave »)."""
    if not perimetre:
        return _avec_defaut([])
    return _avec_defaut([s.strip() for s in perimetre.split(",") if s.strip()])


def parse_json_perimetres(perimetre_cible: Optional[str]) -> list[str]:
    """Champ `perimetre_cible` en JSON (ex. '["bat:1","bat:3"]').

    Un contenu illisible retombe sur le périmètre par défaut plutôt que de lever :
    ce champ alimente un affichage, il ne doit jamais faire échouer une requête.

    ⚠️ Ce repli est **volontairement limité à l'affichage**. Pour décider d'un
    accès, `visibility.perimetre_visible` n'utilise pas ce repli : un JSON corrompu
    ne doit pas ouvrir une visibilité, alors qu'il peut bien rendre un badge
    générique.
    """
    if not perimetre_cible:
        return _avec_defaut([])
    try:
        val = json.loads(perimetre_cible) if isinstance(perimetre_cible, str) else perimetre_cible
        codes = [str(v) for v in val] if isinstance(val, (list, tuple)) else []
    except Exception:
        codes = []
    return _avec_defaut(codes)
