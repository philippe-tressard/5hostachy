"""Garde-fous du registre « Épinglé » du fil d'activité (01/08/2026).

Deux règles décidées avec l'utilisateur, toutes deux invisibles à la relecture
d'un diff ultérieur — d'où ces tests :

1. **Un élément épinglé ne s'auto-archive pas.** Épingler veut dire « garder en
   vue » : disparaître au bout de 30 jours contredirait le marqueur. La règle vit
   dans `_is_archived`, partagée par /actualités et par le fil, pour que les deux
   vues tranchent pareil (un élément visible dans l'une et pas dans l'autre est
   le bug du 17/07/2026).

2. **Agir sur un marqueur ne republie rien.** Décocher « Épinglé » ou « Urgent »
   écrit `mis_a_jour_le` ; tant que le fil datait ses lignes sur ce champ, un
   simple décochage remontait la publication en tête à la date du jour, pastille
   NEW comprise. Le second test empêche la réintroduction de `mis_a_jour_le`
   dans la date d'une ligne du fil — le correctif ne tient pas si un futur appel
   le remet.
"""
import re
from datetime import datetime, timedelta
from pathlib import Path

from app.models.core import Publication
from app.routers.publications import _is_archived

_FLUX_PY = Path(__file__).resolve().parents[1] / "app" / "routers" / "flux.py"


def _publication(**kwargs) -> Publication:
    """Publication en mémoire — aucune session, aucune base ouverte."""
    defauts = dict(titre="Titre", contenu="Contenu", auteur_id=1)
    defauts.update(kwargs)
    return Publication(**defauts)


# ── 1. L'épinglage résiste au vieillissement ────────────────────────────────

def test_publication_epinglee_ne_s_archive_pas_avec_l_age():
    vieille = datetime.utcnow() - timedelta(days=365)
    pub = _publication(epingle=True, statut="publie", cree_le=vieille, publiee_le=vieille)
    assert _is_archived(pub) is False


def test_publication_epinglee_ne_s_archive_pas_une_fois_resolue():
    pub = _publication(
        epingle=True,
        statut="resolu",
        statut_change_le=datetime.utcnow() - timedelta(days=30),
    )
    assert _is_archived(pub) is False


def test_archivage_manuel_prime_sur_l_epinglage():
    """Archiver est une décision humaine explicite : elle gagne toujours."""
    pub = _publication(epingle=True, archivee=True)
    assert _is_archived(pub) is True


def test_publication_non_epinglee_s_archive_toujours_avec_l_age():
    """Non-régression : l'exemption ne doit valoir QUE pour les épinglés."""
    vieille = datetime.utcnow() - timedelta(days=365)
    pub = _publication(epingle=False, statut="publie", cree_le=vieille, publiee_le=vieille)
    assert _is_archived(pub) is True


def test_publication_recente_reste_visible():
    pub = _publication(statut="publie", cree_le=datetime.utcnow(), publiee_le=datetime.utcnow())
    assert _is_archived(pub) is False


# ── 2. Un marqueur ne redate pas une ligne du fil ───────────────────────────

# `date=` d'un FluxItem construit sur `mis_a_jour_le`, quelle que soit la variable
# (`p.`, `a.`, `dv.`…). Les autres usages de `mis_a_jour_le` restent permis : il
# sert légitimement ailleurs (relance syndic, tri interne).
_DATE_SUR_MISE_A_JOUR = re.compile(r"date\s*=\s*[\w.]*\bmis_a_jour_le\b")


def test_le_fil_ne_date_aucune_ligne_sur_mis_a_jour_le():
    source = _FLUX_PY.read_text(encoding="utf-8")
    fautifs = [
        f"ligne {n}: {ligne.strip()}"
        for n, ligne in enumerate(source.splitlines(), 1)
        if _DATE_SUR_MISE_A_JOUR.search(ligne)
    ]
    assert not fautifs, (
        "Une ligne du fil est datée sur `mis_a_jour_le` : cocher ou décocher un "
        "marqueur (Épinglé, Urgent) la ferait remonter en tête à la date du jour, "
        "pastille NEW comprise. Utiliser `publiee_le or cree_le`.\n"
        + "\n".join(fautifs)
    )
