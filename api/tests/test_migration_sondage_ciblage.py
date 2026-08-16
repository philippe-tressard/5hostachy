"""La conversion de la migration 0147 ne doit ÉLARGIR aucun accès.

Une migration de données qui se trompe ne lève pas d'erreur : elle rend des
sondages restreints lisibles par des gens qui n'y avaient pas droit, en silence,
et il est trop tard pour le voir quand on le voit. C'est la seule partie de ce
lot qui n'a aucun filet naturel — le reste est vérifié à l'écran ou par
`test_public_cible.py`.

Le point sensible est le statut `copropriétaire_résident` : « copropriétaires »
couvre les DEUX statuts, si bien que le convertir vers ce code ouvrirait le
sondage aux **bailleurs**. C'est pour cela que `copropriétaires_occupants` est
ajouté au vocabulaire dans le même lot — le test ci-dessous est ce qui le
justifie.

⚠️ Ces fonctions sont importées de la migration elle-même, et non recopiées : un
test qui rejoue sa propre version de la règle ne teste que lui-même.
"""
import importlib.util
from pathlib import Path

import pytest

_CHEMIN = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "0147_sondage_ciblage_standard.py"
)
_spec = importlib.util.spec_from_file_location("migration_0147", _CHEMIN)
_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration)

codes_perimetre = _migration._codes_perimetre
codes_public = _migration._codes_public


# ── Axe géographique ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("vide", [None, "", "   ", ",", " , "])
def test_perimetre_vide_reste_vide(vide):
    """Vide = « aucune restriction », des deux côtés. Un `[]` dirait autre chose."""
    assert codes_perimetre(vide) is None


def test_perimetre_un_batiment():
    assert codes_perimetre("3") == '["bat:3"]'


def test_perimetre_plusieurs_batiments_garde_l_ordre():
    assert codes_perimetre("1,2,4") == '["bat:1", "bat:2", "bat:4"]'


def test_perimetre_tolere_les_espaces():
    """`'1, 2'` est une forme réellement présente en base."""
    assert codes_perimetre(" 1 , 2 ") == '["bat:1", "bat:2"]'


# ── Axe public ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("vide", [None, "", "   ", ","])
def test_public_vide_reste_vide(vide):
    assert codes_public(vide) is None


def test_les_deux_statuts_copro_donnent_coproprietaires():
    """Le seul cas où la fusion est juste : les deux statuts ensemble."""
    assert codes_public("copropriétaire_résident,copropriétaire_bailleur") == '["copropriétaires"]'
    #  L'ordre de la base ne doit pas changer le résultat.
    assert codes_public("copropriétaire_bailleur,copropriétaire_résident") == '["copropriétaires"]'


def test_bailleur_seul_ne_devient_pas_coproprietaires():
    assert codes_public("copropriétaire_bailleur") == '["bailleurs"]'


def test_occupant_seul_ne_devient_pas_coproprietaires():
    """⚠️ LE cas qui justifie `copropriétaires_occupants`.

    Convertir vers `copropriétaires` aurait ouvert le sondage aux bailleurs :
    des gens qui n'y avaient pas accès en auraient gagné un, par une migration.
    """
    converti = codes_public("copropriétaire_résident")
    assert converti == '["copropriétaires_occupants"]'
    assert "copropriétaires\"" not in converti


def test_locataire():
    assert codes_public("locataire") == '["locataires"]'


def test_melange_copro_partiel_et_locataire():
    """Un bailleur et un locataire : deux codes distincts, aucun élargissement."""
    converti = codes_public("copropriétaire_bailleur,locataire")
    assert converti == '["bailleurs", "locataires"]'


def test_statut_inconnu_est_conserve_tel_quel():
    """Il ne peut alors que RESTREINDRE : `public_cible_visible` refuse l'inconnu.

    Recopier vaut mieux que deviner — et vaut mieux qu'ignorer, qui rendrait le
    sondage visible de tous.
    """
    assert codes_public("martien") == '["martien"]'


def test_aucune_conversion_ne_produit_coproprietaires_par_accident():
    """Balayage : « copropriétaires » ne sort QUE des deux statuts réunis.

    Ce test est le garde-fou du lot : il échoue si quelqu'un « simplifie » plus
    tard la table de correspondance en repliant les occupants sur le code large.
    """
    STATUTS = ["copropriétaire_résident", "copropriétaire_bailleur", "locataire", "martien"]
    for i in range(1, 1 << len(STATUTS)):
        choisis = {s for j, s in enumerate(STATUTS) if i >> j & 1}
        converti = codes_public(",".join(sorted(choisis)))
        if "copropriétaires\"" in converti.replace("copropriétaires_occupants", ""):
            assert {"copropriétaire_résident", "copropriétaire_bailleur"} <= choisis, choisis
