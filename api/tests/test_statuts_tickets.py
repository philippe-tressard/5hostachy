"""Une option proposée par un écran est-elle acceptée par l'endpoint qui la reçoit ?

C'est la seule question qui vaille sur une liste de statuts, et c'est celle que
personne ne posait : les **cinq** listes relevées par #415 étaient chacune
cohérente avec elle-même, et aucune n'était juste.

  • le serveur admettait `("ouvert", "en_cours", "résolu", "fermé")` dans
    `POST /tickets/{id}/evolutions` — une liste écrite à la main, sans `annulé`,
    depuis le tout premier commit ;
  • deux écrans sur trois proposaient `annulé` → `422 statut invalide` ;
  • le troisième proposait `fermé`, l'état déprécié — donc le seul qui passait ;
  • le fil d'activité rangeait un ticket annulé parmi les « non résolus », qui
    ne vieillissent jamais.

Deux listes d'accord entre elles ne prouvent rien : ce fichier ne compare jamais
deux copies l'une à l'autre, il compare **ce que l'interface annonce** à **ce que
le serveur accepte**, et fait de `StatutTicket` l'unique arbitre. Même forme que
`test_compteurs_tableau_de_bord.py` (#399).

Il vérifie aussi qu'aucune **sixième** liste ne réapparaît : c'est la recopie qui
fabrique la divergence, pas la faute d'inattention qui la suit.
"""
import pathlib
import re

import pytest
from pydantic import ValidationError

from app.models.core import (
    STATUTS_TICKET_CLOS,
    STATUTS_TICKET_HISTORIQUES,
    StatutTicket,
)
from app.routers.tickets.commun import STATUT_LABELS
from app.schemas import TicketEvolutionCreate, TicketUpdate

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_RACINE = _API_DIR.parent
_FRONT_SRC = _RACINE / "front" / "src"
_MODULE_FRONT = _FRONT_SRC / "lib" / "tickets.ts"

_VALEURS = {s.value for s in StatutTicket}


# ── Ce que l'écran propose ────────────────────────────────────────────────────

def _options_du_front() -> list[str]:
    """Les états proposés par l'interface, lus dans `$lib/tickets.ts`.

    On lit le **fichier**, pas une liste recopiée ici : recopier les quatre
    valeurs dans ce test reviendrait à comparer une constante à elle-même, et
    c'est exactement le mécanisme qui a produit les cinq listes divergentes.
    """
    src = _MODULE_FRONT.read_text(encoding="utf-8")
    bloc = re.search(
        r"export const STATUTS_TICKET\s*:[^=]*=\s*\[(.*?)\];", src, re.S
    )
    assert bloc, "STATUTS_TICKET introuvable dans front/src/lib/tickets.ts"
    return re.findall(r"value:\s*'([^']+)'", bloc.group(1))


def test_le_front_propose_exactement_les_etats_de_lenumeration():
    """Ni plus (`fermé` proposé alors qu'il n'existe plus), ni moins."""
    assert _options_du_front() == [s.value for s in StatutTicket]


@pytest.mark.parametrize("valeur", sorted(_VALEURS))
def test_chaque_option_est_acceptee_par_les_deux_endpoints(valeur):
    """Le même geste doit réussir, quel que soit l'écran d'où il part.

    Les deux chemins de changement d'état — `PATCH /tickets/{id}` et
    `POST /tickets/{id}/evolutions` — valident désormais par le **type**. Avant
    #415, ce test aurait échoué sur `annulé` côté évolutions : la liste blanche
    du routeur le refusait, alors que deux écrans le proposaient.
    """
    TicketUpdate(statut=valeur)
    TicketEvolutionCreate(type="etat", nouveau_statut=valeur)


@pytest.mark.parametrize("valeur", ["fermé", "ferme", "resolu", "n'importe quoi", ""])
def test_les_deux_endpoints_refusent_ce_qui_nest_pas_un_etat(valeur):
    """Y compris `fermé` : accepté en lecture, jamais en écriture.

    `Ticket` est un modèle `table=True` — SQLModel ne valide rien à
    l'affectation. Tant que `TicketUpdate.statut` était un `str`, `PATCH` écrivait
    en base la chaîne reçue, quelle qu'elle soit.
    """
    with pytest.raises(ValidationError):
        TicketUpdate(statut=valeur)
    with pytest.raises(ValidationError):
        TicketEvolutionCreate(type="etat", nouveau_statut=valeur)


# ── Ce que l'écran affiche ────────────────────────────────────────────────────

def test_tout_etat_affichable_a_un_libelle_des_deux_cotes():
    """Un état sans libellé s'affiche en valeur brute — dans un e-mail compris.

    Les valeurs historiques (`fermé`) en font partie : plus aucun ticket ne les
    porte, mais le fil d'un ticket ancien raconte encore « Ouvert → Fermé ».
    """
    affichables = _VALEURS | set(STATUTS_TICKET_HISTORIQUES)
    assert set(STATUT_LABELS) == affichables, "STATUT_LABELS (api) a dérivé"

    src = _MODULE_FRONT.read_text(encoding="utf-8")
    for valeur in affichables:
        assert re.search(rf"['\"]?{re.escape(valeur)}['\"]?\s*:", src) or (
            f"'{valeur}'" in src
        ), f"{valeur} n'a ni libellé ni pastille côté front"


def test_les_etats_clos_sont_les_memes_des_deux_cotes():
    """Le front tolère en plus les valeurs historiques : l'affichage d'un ticket
    ancien ne doit pas dépendre du succès d'une migration. Le serveur, lui, filtre
    sur ce qui existe."""
    src = _MODULE_FRONT.read_text(encoding="utf-8")
    bloc = re.search(r"STATUTS_TICKET_CLOS[^=]*=\s*\[(.*?)\];", src, re.S)
    assert bloc, "STATUTS_TICKET_CLOS introuvable côté front"
    clos_front = set(re.findall(r"'([^']+)'", bloc.group(1)))
    assert set(STATUTS_TICKET_CLOS) <= clos_front
    assert clos_front - set(STATUTS_TICKET_CLOS) <= set(STATUTS_TICKET_HISTORIQUES)


# ── Qu'aucune sixième liste ne réapparaisse ───────────────────────────────────
#
#  Ces deux contrôles sont de l'analyse statique : le couplage qu'ils surveillent
#  est **implicite** — rien, à l'exécution, ne relie une liste écrite dans un
#  écran à l'énumération du serveur. Cf. `standards/05` sur ce cas précis.

#: Fichiers autorisés à nommer plusieurs états sans passer par la source unique,
#: **avec la raison**. Le contrôle échoue si l'une de ces exceptions devient
#: inutile : une dérogation qui ne sert plus est une porte laissée ouverte.
_EXCEPTIONS_FRONT = {
    #  Badge générique du fil d'activité : il colore AUSSI les publications
    #  (`resolu` sans accent) et les prestations (`réalisé`), qui ne sont pas des
    #  tickets. Le rapatrier dans `$lib/tickets` importerait la notion de ticket
    #  dans un composant qui sert quatre types d'objets.
    #  ⚠️ Il donne `badge-orange` à `ouvert` là où les écrans de tickets donnent
    #  `badge-blue` — écart connu, hors périmètre de #415.
    "lib/components/FluxCard.svelte": "badge générique multi-objets",
}

_MOTIF_STATUT = re.compile(r"['\"](ouvert|en_cours|résolu|annulé|fermé)['\"]")


def _sans_commentaires(src: str) -> str:
    """Le code seul — les commentaires citent les états pour raconter le défaut.

    ⚠️ `//.*` se strippe **sans** `re.S`, et les blocs **avec** : réunir les deux
    dans une seule alternation en DOTALL fait manger tout le fichier à partir du
    premier `//`. Écrit ainsi d'abord, ce contrôle ne voyait plus rien et se
    déclarait vert (`standards/04` §1) — c'est le test des exceptions qui l'a dit.
    """
    src = re.sub(r"/\*.*?\*/|<!--.*?-->", "", src, flags=re.S)
    return re.sub(r"//.*", "", src)


def _listes_detats(code: str) -> list[list[str]]:
    """Les **collections littérales** du code portant deux états ou plus.

    C'est cette forme-là qui diverge : `('ouvert', 'en_cours')`, un tableau
    d'options, une table de libellés. Comparer un statut à UNE valeur
    (`if nouveau === 'résolu'`) reste légitime — c'est une question sur un cas,
    pas une table de vérité parallèle à l'énumération.

    ⚠️ Ce test s'est d'abord contenté d'exiger un `import '$lib/tickets'` dans
    tout fichier nommant deux états. Il passait au vert sur une sixième liste
    écrite dans un écran **qui importait déjà** le module — vérifié en injectant
    le défaut, pas en relisant le contrôle.
    """
    trouvees = []
    for collection in re.findall(r"[\(\[\{][^()\[\]{}]*[\)\]\}]", code):
        etats = sorted(set(_MOTIF_STATUT.findall(collection)))
        if len(etats) >= 2:
            trouvees.append(etats)
    return trouvees


def _fichiers_front():
    for chemin in _FRONT_SRC.rglob("*"):
        if chemin.suffix in (".svelte", ".ts") and chemin != _MODULE_FRONT:
            yield chemin


def test_aucun_ecran_ne_reecrit_une_liste_detats():
    """Options, libellés, pastilles, états clos : tout vient de `$lib/tickets`."""
    coupables = []
    for chemin in _fichiers_front():
        rel = chemin.relative_to(_FRONT_SRC).as_posix()
        if rel in _EXCEPTIONS_FRONT:
            continue
        for etats in _listes_detats(_sans_commentaires(chemin.read_text(encoding="utf-8"))):
            coupables.append(f"{rel} → {etats}")
    assert not coupables, (
        "ces fichiers écrivent leur propre liste d'états de ticket au lieu de "
        f"la tenir de $lib/tickets : {coupables}"
    )


def test_les_exceptions_declarees_servent_encore():
    """Cas zéro : une dérogation devenue inutile doit être retirée, pas oubliée."""
    for rel, raison in _EXCEPTIONS_FRONT.items():
        chemin = _FRONT_SRC / rel
        assert chemin.exists(), f"exception sur un fichier disparu : {rel} ({raison})"
        code = _sans_commentaires(chemin.read_text(encoding="utf-8"))
        assert _listes_detats(code), (
            f"{rel} n'écrit plus de liste d'états : retirer son exception ({raison})"
        )


def test_aucun_routeur_ne_reecrit_une_liste_detats():
    """Côté serveur, la liste blanche `_STATUTS_ADMIS` ne doit pas repousser.

    Elle a survécu à trois découpages de `tickets.py` sans que personne la
    relise : c'est le propre d'une constante qui a l'air d'une évidence.
    """
    autorises = {
        #  La table des libellés : les seuls états écrits en toutes lettres, et
        #  ils y sont vérifiés par `test_tout_etat_affichable_a_un_libelle…`.
        "app/routers/tickets/commun.py",
    }
    coupables = []
    for chemin in (_API_DIR / "app" / "routers").rglob("*.py"):
        rel = chemin.relative_to(_API_DIR).as_posix()
        if rel in autorises:
            continue
        #  Même précaution qu'au-dessus : les docstrings en DOTALL, les
        #  commentaires `#` ligne à ligne.
        code = chemin.read_text(encoding="utf-8")
        code = re.sub(r'\"\"\".*?\"\"\"', "", code, flags=re.S)
        code = re.sub(r"#.*", "", code)
        for etats in _listes_detats(code):
            coupables.append(f"{rel} → {etats}")
    assert not coupables, (
        "ces routeurs réécrivent une liste d'états au lieu d'utiliser "
        f"StatutTicket / STATUTS_TICKET_CLOS : {coupables}"
    )
