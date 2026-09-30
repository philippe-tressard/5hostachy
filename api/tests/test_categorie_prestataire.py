"""La catégorie d'un prestataire dit son MÉTIER, jamais le cadre (#1444).

« Contrat récurrent » et « Dépannage » ont été fondues en « Maintenance &
dépannage » : le cadre — sous contrat ou non — appartient à chaque
intervention, et se déduit des contrats de la fiche. Ces tests tiennent deux
choses que rien d'autre ne verrait :

- les anciennes valeurs ne reviennent pas dans l'énumération ;
- une fiche créée sans catégorie reçoit la nouvelle valeur par défaut.
"""

from app.models.prestataires import Prestataire, TypePrestataire
from app.routers.prestataires_schemas import PrestataireCreate


def test_le_cadre_n_est_plus_une_categorie():
    valeurs = {t.value for t in TypePrestataire}
    assert "contrat_recurrent" not in valeurs
    assert "ponctuel" not in valeurs
    assert "maintenance_depannage" in valeurs


def test_le_defaut_est_la_nouvelle_categorie():
    assert Prestataire(nom="x", specialite="ascenseur").type_prestataire == (
        TypePrestataire.maintenance_depannage
    )
    assert PrestataireCreate(nom="x", specialite="ascenseur").type_prestataire == (
        TypePrestataire.maintenance_depannage
    )
