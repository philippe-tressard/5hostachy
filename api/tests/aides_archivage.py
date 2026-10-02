"""Quel modèle porte quel type de `utils/archivage.REGLES` — écrit une fois (#1568).

`test_archivage.py` confronte chaque déclaration de `REGLES` aux champs du modèle
réel ; `test_archivage_colonnes_booleennes.py` s'en sert pour savoir quelles
colonnes booléennes de disparition `REGLES` couvre. Les deux lisaient la même
table : l'un l'aurait recopiée, ou l'aurait importée d'un fichier de tests (ce que
`test_aides_de_tests_source_unique.py` refuse). Elle vit donc ici.
"""

from __future__ import annotations

from app.models.annonce_hall import AnnonceHall
from app.models.communaute import Idee, PetiteAnnonce, Sondage
from app.models.prestataires import ContratEntretien, Prestataire

#  `Ticket` vit dans `models.core` mais son énumération dans `models.tickets` :
#  l'import direct au sommet crée un cycle selon l'ordre de chargement. Résolu
#  ici, après les autres modèles, plutôt qu'en réorganisant les modules pour un test.
from app.models.core import Ticket  # noqa: E402

#: Quel modèle porte quel type. Une entrée manquante ici fait échouer le test de
#: couverture de `test_archivage.py` — on ne peut pas déclarer une règle sans
#: dire sur quoi elle s'applique.
MODELES = {
    "ticket": Ticket,
    #  Une affaire de catégorie « Actualité » (#1091) : même modèle, autre règle.
    "actualite": Ticket,
    "annonce": PetiteAnnonce,
    "idee": Idee,
    "sondage": Sondage,
    "annonce_hall": AnnonceHall,
    "prestataire": Prestataire,
    "contrat": ContratEntretien,
}
