"""Une correction ne paraît pas dans le fil, et sa marque s'écrit à UN endroit.

## Le défaut (01/09/2026, signalé à l'écran)

> *« pourquoi cet évènement a été mis à jour, il n'a eu qu'une édition »*

Le fil affichait « ÉVÉNEMENT · NEW — Nettoyage du parking Leclerc — Mise à jour —
Correction : Périmètre ». Une seule édition, une ligne de nouvelle pour toute la
copropriété.

🔴 Une correction dit qu'on s'est trompé, pas qu'il s'est passé quelque chose.
Elle appartient à l'**Historique** de l'objet ; le fil répond à « qu'est-ce qui
est arrivé ? », et se tromper n'est pas arriver.

## Pourquoi ce test et pas une relecture

La marque « Correction : » était écrite **quatre fois** dans `app/`, et le fil
avait besoin d'un cinquième endroit pour la RECONNAÎTRE. C'est le pire cas de
duplication : écrire et reconnaître peuvent diverger, et c'est la reconnaissance
qui se trompe **en silence** — en laissant passer dans le fil ce qu'elle ne sait
plus lire. Personne ne s'en apercevrait avant de voir la carte.

⚠️ Les tickets écrivent une seconde marque, « Correction auteur : », parce que
l'Historique dit QUI a corrigé. Un contrôle qui ne connaîtrait que la première
laisserait passer toutes les corrections d'auteur.
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.utils.corrections import (
    PREFIXE_CORRECTION,
    PREFIXE_CORRECTION_AUTEUR,
    contenu_correction,
    est_correction,
)

_APP = Path(__file__).resolve().parents[1] / "app"
_FLUX = _APP / "routers" / "flux"

#: Le seul module autorisé à écrire la marque en clair.
_SOURCE_UNIQUE = "utils/corrections.py"

#: Les modules du fil qui parcourent des entrées d'historique. Ils DOIVENT
#: écarter les corrections. La liste est explicite : un module ajouté sans y
#: figurer serait un trou, et le cas zéro plus bas vérifie qu'ils existent
#: toujours et parcourent bien des évolutions.
_FLUX_AVEC_HISTORIQUE = ("evenements.py", "tickets.py")


class _Entree:
    """Une entrée d'historique en mémoire — aucune session, aucune base ouverte."""

    def __init__(self, contenu=None, ancien_statut=None, nouveau_statut=None):
        self.contenu = contenu
        self.ancien_statut = ancien_statut
        self.nouveau_statut = nouveau_statut


# ── 1. La décision elle-même ────────────────────────────────────────────────


def test_une_correction_se_reconnait_sous_ses_DEUX_formes():
    assert est_correction(_Entree(contenu_correction(["Périmètre"])))
    assert est_correction(_Entree(PREFIXE_CORRECTION_AUTEUR + "Description"))


def test_une_TRANSITION_reste_une_nouvelle_meme_marquee():
    """Le cas qui se perd si l'on ne regarde que le texte.

    Une entrée qui porte un changement d'état est un fait : le fil doit la
    montrer, quoi que dise son contenu.
    """
    assert not est_correction(
        _Entree(contenu_correction(["Périmètre"]), "ouvert", "en_cours")
    )


def test_un_vrai_commentaire_n_est_pas_ecarte():
    """⚠️ Un contrôle qui écarte du légitime finit désarmé (leçon de C16)."""
    assert not est_correction(_Entree("Le nettoyage est reporté à jeudi."))
    assert not est_correction(_Entree("Corrections à prévoir sur la façade"))
    assert not est_correction(_Entree())
    assert not est_correction(_Entree(""))


# ── 2. La marque ne s'écrit qu'à un endroit ─────────────────────────────────


def _contenus_litteraux() -> list[tuple[str, int, str]]:
    """Les `contenu="…"` littéraux de `app/`, avec fichier et ligne."""
    trouves: list[tuple[str, int, str]] = []
    for fichier in sorted(_APP.rglob("*.py")):
        if "__pycache__" in fichier.parts:
            continue
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            for kw in noeud.keywords:
                if kw.arg != "contenu":
                    continue
                for n in ast.walk(kw.value):
                    if isinstance(n, ast.Constant) and isinstance(n.value, str):
                        trouves.append(
                            (
                                fichier.relative_to(_APP).as_posix(),
                                noeud.lineno,
                                n.value,
                            )
                        )
    return trouves


def test_le_motif_de_lecture_trouve_encore_quelque_chose():
    """Cas zéro : un relevé vide se lirait « aucune écriture en dur »."""
    lus = _contenus_litteraux()
    assert len(lus) >= 3, (
        f"{len(lus)} `contenu=` littéral(aux) lu(s) dans app/ — le motif ne "
        "correspond plus. Ne pas lire ceci comme un succès."
    )


def test_la_marque_ne_s_ecrit_pas_en_dur_hors_de_son_module():
    fautifs = [
        (f, n, v)
        for f, n, v in _contenus_litteraux()
        if f != _SOURCE_UNIQUE and v.startswith("Correction")
    ]
    assert not fautifs, (
        "La marque d'une correction est écrite en dur hors de "
        f"`{_SOURCE_UNIQUE}` :\n"
        + "\n".join(f"  {f}:{n} — {v!r}" for f, n, v in fautifs)
        + "\n\nÉcrire et reconnaître peuvent alors diverger — et c'est la "
        "reconnaissance qui se tromperait en silence, en laissant passer dans le "
        "fil ce qu'elle ne sait plus lire."
    )


# ── 3. Le fil écarte réellement les corrections ─────────────────────────────


def test_les_modules_du_fil_qui_lisent_l_historique_ecartent_les_corrections():
    for nom in _FLUX_AVEC_HISTORIQUE:
        chemin = _FLUX / nom
        assert chemin.exists(), (
            f"{nom} a disparu de flux/ — la portée de ce contrôle est une partie "
            "du contrôle, et elle ne correspond plus."
        )
        source = chemin.read_text(encoding="utf-8")
        #  Cas zéro : le module parcourt-il encore des entrées d'historique ?
        assert "for evol" in source, (
            f"{nom} ne parcourt plus d'évolutions : ce contrôle ne mesure plus "
            "rien. Vérifier si les cartes ont déménagé."
        )
        assert "est_correction(evol)" in source, (
            f"{nom} rend des cartes d'historique sans écarter les corrections. "
            "Une édition y écrirait « Mise à jour » dans le fil de toute la "
            "copropriété — c'est le défaut du 01/09/2026."
        )


def test_le_prefixe_exact_reste_celui_qui_a_ete_ecrit_en_base():
    """⚠️ Les entrées DÉJÀ enregistrées portent cette chaîne, au caractère près.

    La changer rendrait invisibles au contrôle toutes les corrections passées :
    elles reparaîtraient dans le fil, sans qu'aucun test ne le dise.
    """
    assert PREFIXE_CORRECTION == "Correction : "
    assert PREFIXE_CORRECTION_AUTEUR == "Correction auteur : "
