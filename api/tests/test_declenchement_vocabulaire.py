"""« Déclenchée par » ne dit que deux mots, et ils s'écrivent à UN endroit.

## Ce que ce contrôle protège (18/09/2026)

La colonne `declenchee_par` est **affichée telle quelle** par l'écran des tâches
planifiées. Trois vocabulaires y coexistaient — `manuelle`, `automatique`,
`cron` — selon la tâche et selon le chemin, sans qu'aucune différence ne le
justifie. Et le repli de `run_maintenance`, qui est le chemin du planificateur,
posait `manuelle` : une maintenance automatique s'affichait comme déclenchée à
la main, sans nœud.

Le vocabulaire vit désormais dans `utils/declenchement`. Ce fichier refuse
qu'un quatrième mot apparaisse, et vérifie que le geste de lancement manuel
reste unique.
"""

from __future__ import annotations

import pathlib
import re

from app.utils.declenchement import AUTOMATIQUE, MANUELLE, normaliser

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"
SOURCE = "utils/declenchement.py"

#: Une affectation littérale du champ : `declenchee_par="cron"`. C'est la forme
#: qui a produit les trois vocabulaires.
LITTERAL = re.compile(r"""declenchee_par\s*=\s*["'][^"']+["']""")


def _fichiers() -> list[pathlib.Path]:
    return [p for p in RACINE.rglob("*.py") if "__pycache__" not in p.parts]


def test_le_vocabulaire_tient_en_deux_mots():
    """Cas zéro : sans valeurs, tout ce fichier serait vert sur du vide."""
    assert MANUELLE == "manuelle" and AUTOMATIQUE == "automatique"
    assert MANUELLE != AUTOMATIQUE


def test_les_anciens_mots_se_traduisent():
    """Un script d'infra déployé continue d'envoyer « cron » — il doit arriver traduit."""
    assert normaliser("cron") == AUTOMATIQUE
    assert normaliser("CRON") == AUTOMATIQUE
    assert normaliser("auto") == AUTOMATIQUE
    assert normaliser("manuelle") == MANUELLE
    assert normaliser("manual") == MANUELLE


def test_l_inconnu_devient_AUTOMATIQUE_et_non_manuelle():
    """🔴 Le sens du repli compte.

    Une tâche dont on ignore l'origine n'a pas été déclenchée par quelqu'un
    qu'on pourrait nommer. Répondre « manuelle » inventerait un auteur.
    """
    assert normaliser(None) == AUTOMATIQUE
    assert normaliser("") == AUTOMATIQUE
    assert normaliser("n'importe quoi") == AUTOMATIQUE


def test_aucun_module_n_ecrit_le_champ_EN_DUR():
    """Le vocabulaire vient des constantes, jamais d'une chaîne posée sur place.

    C'est ainsi que trois mots ont coexisté : chacun était juste là où il était
    écrit, et personne ne les voyait ensemble.
    """
    fautifs = {}
    for chemin in _fichiers():
        rel = chemin.relative_to(RACINE).as_posix()
        if rel == SOURCE:
            continue
        lignes = [
            n + 1
            for n, ligne in enumerate(chemin.read_text(encoding="utf-8").split(chr(10)))
            if LITTERAL.search(ligne) and not ligne.lstrip().startswith(("#", "*"))
        ]
        if lignes:
            fautifs[rel] = lignes

    assert not fautifs, (
        f"Ces modules écrivent « déclenchée par » en dur : {fautifs}. Employer "
        "`MANUELLE` / `AUTOMATIQUE` de `app.utils.declenchement`, ou "
        "`normaliser()` quand le mot vient de l'extérieur."
    )


def test_cas_zero_le_motif_reconnait_bien_une_affectation():
    """Sans quoi le test ci-dessus serait vert sur n'importe quelle source."""
    assert LITTERAL.search('declenchee_par="cron"')
    assert LITTERAL.search("declenchee_par = 'manuelle'")
    #  Une affectation depuis une CONSTANTE n'est pas visée : c'est la bonne forme.
    assert not LITTERAL.search("declenchee_par=AUTOMATIQUE")
    assert not LITTERAL.search("declenchee_par=normaliser(body.declenchee_par)")
    assert len(_fichiers()) > 50, "le parcours ne décrit plus `app/`"


def test_le_lancement_manuel_passe_par_le_geste_commun():
    """Les trois endpoints tracent leur lancement au même endroit.

    Six lignes qui se recopient — créer l'entrée, committer, rafraîchir,
    planifier, répondre — ont déjà coûté un gestionnaire entier : ajouté en
    doublon d'un autre sur le même chemin, il n'a jamais répondu (v1.44.10).
    """
    import inspect

    from app.routers.admin import exploitation

    for nom in ("backup_now", "maintenance_now", "agreger_telemetrie_maintenant"):
        source = inspect.getsource(getattr(exploitation, nom))
        assert "tracer_lancement_manuel" in source, (
            f"`{nom}` ne trace plus son lancement par le geste commun : il a "
            "repris les six lignes pour lui."
        )
