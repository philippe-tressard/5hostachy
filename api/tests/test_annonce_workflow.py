"""L'archivage d'une annonce : calculé, et mesuré sur le bon horodatage.

## Pourquoi ce garde-fou (18/08/2026)

Demandé : *« les annonces restent à l'état vendu pendant 1 mois et sont archivées
dans une section pliée par défaut »*.

🔴 **Cette règle décide seule, dans un mois, sans que personne ne regarde.** Un
défaut ne se manifestera pas au moment où on la code — il se manifestera en
septembre, sur une annonce qui aurait dû disparaître de la liste et n'en part
pas, ou l'inverse. C'est exactement le profil d'erreur qu'un test attrape et
qu'une relecture ne voit pas.

## Le piège que ces tests protègent

L'archivage se mesure sur `statut_change_le`, **pas** sur `mis_a_jour_le`. Les
deux paraissent interchangeables et ne le sont pas : corriger une faute de frappe
sur une annonce vendue repousserait son archivage d'un mois, indéfiniment, à
chaque retouche. `Publication` porte le même champ pour la même raison — et
`test_flux_epingle.py` existe parce que la confusion inverse (dater une ligne du
fil sur `mis_a_jour_le`) avait fait remonter une actualité de l'an dernier.

⚠️ `est_archivee` est une fonction **pure** : elle ne touche ni session ni base.
C'est ce qui la rend vérifiable sans monter de fixture, donc ce qui rend ces
tests rapides — et un test rapide est un test qu'on garde.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.core import PetiteAnnonce, StatutAnnonce
from app.routers.annonces import ARCHIVAGE_JOURS, STATUTS_TERMINAUX, est_archivee


def _annonce(statut: StatutAnnonce, jours: float | None, **kw) -> PetiteAnnonce:
    """Une annonce dans cet état depuis `jours` jours. `None` = pas d'horodatage."""
    quand = None if jours is None else datetime.utcnow() - timedelta(days=jours)
    return PetiteAnnonce(
        titre="Vélo",
        description="<p>Peu servi.</p>",
        auteur_id=1,
        statut=statut,
        statut_change_le=quand,
        **kw,
    )


# ── Les états qui n'archivent jamais ────────────────────────────────────────

@pytest.mark.parametrize("statut", [StatutAnnonce.en_cours, StatutAnnonce.reserve])
def test_un_etat_non_terminal_ne_s_archive_jamais(statut):
    """Même très ancienne : tant qu'elle est en cours ou réservée, elle est là.

    ⚠️ **Réservé n'est pas terminal, et c'est un arbitrage** : une réservation peut
    tomber. Archiver au bout d'un mois retirerait de la liste une annonce dont
    l'objet est toujours à vendre, sans que son auteur ait rien décidé.
    """
    assert est_archivee(_annonce(statut, 400)) is False


# ── Les états terminaux, et le délai ────────────────────────────────────────

@pytest.mark.parametrize("statut", STATUTS_TERMINAUX)
def test_un_etat_terminal_reste_visible_un_mois(statut):
    """La veille du délai, l'annonce est encore dans la liste principale."""
    assert est_archivee(_annonce(statut, ARCHIVAGE_JOURS - 1)) is False


@pytest.mark.parametrize("statut", STATUTS_TERMINAUX)
def test_un_etat_terminal_s_archive_passe_le_delai(statut):
    assert est_archivee(_annonce(statut, ARCHIVAGE_JOURS + 1)) is True


def test_le_delai_est_atteint_a_la_seconde_pres_pas_apres():
    """Le seuil est inclusif : à J+30 pile, l'annonce EST archivée.

    Un `>` au lieu d'un `>=` laisserait une annonce d'exactement trente jours
    dans la liste — un jour de plus que promis, et surtout un cas limite que
    personne ne reverrait jamais à l'écran.
    """
    assert est_archivee(_annonce(StatutAnnonce.vendu, ARCHIVAGE_JOURS)) is True


# ── 🔴 Le piège : quel horodatage fait foi ──────────────────────────────────

def test_une_correction_recente_ne_repousse_PAS_l_archivage():
    """Le cœur du garde-fou.

    Une annonce vendue il y a deux mois, dont le titre a été corrigé ce matin :
    `mis_a_jour_le` est frais, `statut_change_le` est vieux. Elle doit rester
    archivée — sinon chaque retouche la ferait remonter dans la liste, et une
    annonce vendue en juin traînerait encore en décembre.
    """
    annonce = _annonce(StatutAnnonce.vendu, 60)
    annonce.mis_a_jour_le = datetime.utcnow()
    assert est_archivee(annonce) is True, (
        "l'archivage suit `mis_a_jour_le` au lieu de `statut_change_le` : "
        "corriger une faute de frappe repousse l'archivage d'un mois."
    )


def test_sans_horodatage_le_repli_ne_bloque_pas_l_archivage():
    """Une annonce terminale SANS `statut_change_le` retombe sur `mis_a_jour_le`.

    La migration 0152 renseigne la colonne pour tout l'existant ; ce repli couvre
    ce qui viendrait d'ailleurs. Sans lui, une ligne sans horodatage resterait
    éternellement en tête de liste — le cas zéro appliqué à une donnée manquante.
    """
    annonce = _annonce(StatutAnnonce.annule, None)
    annonce.mis_a_jour_le = datetime.utcnow() - timedelta(days=ARCHIVAGE_JOURS + 5)
    assert est_archivee(annonce) is True


def test_archive_n_est_pas_un_etat():
    """🔴 L'archivage se CALCULE : il ne doit jamais redevenir une pastille.

    En faire un sixième état donnerait deux notions pour la même chose — celle
    qu'on pose et celle qui arrive — libres de se contredire dès la première
    annonce archivée à la main puis rouverte.
    """
    assert not hasattr(StatutAnnonce, "archive"), (
        "`archive` est redevenu un état du workflow ; il doit rester calculé "
        "(`est_archivee`), et la migration 0152 l'a converti en `annule`."
    )
    valeurs = {s.value for s in StatutAnnonce}
    assert valeurs == {"en_cours", "reserve", "vendu", "donne", "annule"}, valeurs
