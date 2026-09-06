"""Garde-fou — **les deux types d'import d'accès portent les MÊMES gestes** (#576).

## Pourquoi

`remettreEnAttente` n'existait que pour les télécommandes, côté serveur comme
côté écran. Un import Vigik passé en `ignore` — par un clic malheureux sur ⊘, qui
ne demande qu'une confirmation générique — **ne pouvait plus revenir** : la ligne
restait visible sous le filtre « Ignoré » et aucun geste ne la rattrapait. Il
fallait réimporter le fichier Excel.

🔴 **Ce n'était pas une décision, c'était un oubli**, et il est resté invisible
pendant des mois parce que les deux écrans étaient deux fichiers : chacun
paraissait complet. Il n'a été vu qu'en les fusionnant (#453).

⚠️ **Et le combler ne suffit pas.** Rien n'empêche le prochain geste d'être ajouté
d'un seul côté — c'est exactement ce qui s'est produit. Ce test compare les deux
familles d'endpoints et échoue dès que l'une porte un verbe que l'autre n'a pas.

Le contrôle est **statique** : il lit les décorateurs `@router.post("…")` du
routeur sans importer l'application. Pas de base, pas d'effet de bord.

⚠️ Il regarde ce que le SERVEUR expose. Le front est tenu par le type
`ModeleImportAcces`, dont le champ `remettreEnAttente` est redevenu OBLIGATOIRE —
les deux bouts sont donc gardés, chacun par son outil.
"""
import re
from pathlib import Path

import pytest

#  🔴 `acces.py` est devenu un PAQUET le 06/09/2026 (#805) : le contrôle lit
#  donc tous ses modules, concaténés. Il cherchait un fichier ; il cherche
#  maintenant un domaine, ce qui est ce qu'il a toujours voulu dire.
#
#  ⚠️ Son cas zéro tient toujours : si le répertoire disparaissait, la
#  concaténation serait vide et les assertions échoueraient — le contrôle rendrait
#  INCONNU plutôt qu'un vert. C'est ce qu'il a fait le jour du découpage, avant
#  cette correction : « acces.py introuvable, le contrôle ne peut pas conclure ».
PAQUET = Path(__file__).resolve().parent.parent / "app" / "routers" / "acces"
ROUTEUR = PAQUET  # nom historique, conservé pour les messages d'erreur


def _source_du_domaine() -> str:
    """Tous les modules du paquet, concaténés — l'équivalent de l'ancien fichier."""
    fichiers = sorted(PAQUET.glob("*.py"))
    assert fichiers, f"{PAQUET} ne porte aucun module : le contrôle ne peut pas conclure"
    return "\n".join(f.read_text(encoding="utf-8") for f in fichiers)

#  Les gestes qui n'ont volontairement PAS d'équivalent, avec leur raison.
#  ⚠️ Une entrée qui ne sert plus fait échouer le test : une dérogation oubliée
#  est une porte qu'on croit fermée. La liste ne peut que décroître.
ASYMETRIES_ADMISES = {
    #  Une télécommande peut être refusée par le locataire — elle revient alors
    #  au propriétaire. Un badge Vigik n'a pas ce cycle : il est posé sur un lot,
    #  pas remis en main propre.
    "refuser-locataire": "propre au cycle d'une télécommande, remise en main propre",
}


def _verbes(prefixe: str) -> set[str]:
    """Les gestes exposés sous un préfixe, par leur dernier segment d'URL.

    On ne garde que les routes portant `{import_id}` : ce sont les gestes sur UN
    import. `upload`, `stats`, `auto-match` et la liste agissent sur la
    collection et n'ont pas à se correspondre un pour un.
    """
    source = _source_du_domaine()
    motif = re.compile(
        r'@router\.(?:post|patch|delete)\("' + re.escape(prefixe) + r'/\{import_id\}(?:/([\w-]+))?"'
    )
    return {m.group(1) or "" for m in motif.finditer(source)}


def test_le_routeur_est_lisible():
    """Cas zéro — sans lui, deux ensembles VIDES seraient déclarés symétriques.

    C'est la forme d'échec la plus coûteuse : le test passerait au vert en ayant
    cessé de voir (`standards/04` §2).
    """
    assert PAQUET.is_dir(), f"{PAQUET} introuvable — le contrôle ne peut pas conclure"
    tc = _verbes("/admin/imports")
    vigik = _verbes("/admin/imports-vigik")
    assert len(tc) >= 4, f"seulement {len(tc)} geste(s) lus côté télécommandes — motif cassé ?"
    assert len(vigik) >= 4, f"seulement {len(vigik)} geste(s) lus côté Vigik — motif cassé ?"


def test_les_deux_types_portent_les_memes_gestes():
    """Tout geste sur UN import doit exister des deux côtés, ou être déclaré."""
    tc = _verbes("/admin/imports")
    vigik = _verbes("/admin/imports-vigik")

    manque_vigik = {v for v in tc - vigik if v not in ASYMETRIES_ADMISES}
    manque_tc = {v for v in vigik - tc if v not in ASYMETRIES_ADMISES}

    assert not manque_vigik, (
        "geste(s) absent(s) côté VIGIK : "
        + ", ".join(sorted(manque_vigik))
        + ". Les deux objets ont le même cycle d'import, donc les mêmes gestes — "
        "un import Vigik ignoré par erreur serait définitivement perdu (#576). "
        "L'ajouter en miroir, ou déclarer l'asymétrie dans `ASYMETRIES_ADMISES` "
        "avec sa raison."
    )
    assert not manque_tc, (
        "geste(s) absent(s) côté TÉLÉCOMMANDES : "
        + ", ".join(sorted(manque_tc))
        + ". La symétrie vaut dans les deux sens."
    )


def test_aucune_asymetrie_admise_n_est_devenue_inutile():
    """Une dérogation qui ne sert plus est une porte qu'on croit fermée."""
    tc = _verbes("/admin/imports")
    vigik = _verbes("/admin/imports-vigik")
    ecart = (tc - vigik) | (vigik - tc)
    mortes = set(ASYMETRIES_ADMISES) - ecart
    assert not mortes, (
        "asymétrie(s) déclarée(s) qui ne servent plus : "
        + ", ".join(sorted(mortes))
        + ". Les retirer d'`ASYMETRIES_ADMISES` — la liste ne peut que décroître."
    )


@pytest.mark.parametrize("prefixe", ["/admin/imports", "/admin/imports-vigik"])
def test_remettre_en_attente_existe_des_deux_cotes(prefixe):
    """Le geste de #576, nommément — c'est celui qui manquait."""
    assert "remettre-en-attente" in _verbes(prefixe), (
        f"`{prefixe}/{{import_id}}/remettre-en-attente` manque. Sans lui, un import "
        "ignoré par erreur est définitivement perdu."
    )
