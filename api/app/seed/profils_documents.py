"""Profils d'accès documentaire et catégories de documents.

Ces deux tables décident QUI voit QUOI dans la bibliothèque : un profil liste
les rôles autorisés, une catégorie s'y rattache. `visibility.document_visible`
les lit à chaque consultation — les modifier change des droits, pas un affichage.
"""
import json

PROFILS = [
    {
        "code": "résidence_tous",
        "libelle": "Tous les résidents",
        "description": "Copropriétaires, bailleurs, locataires, syndic",
        #  ⚠️ `syndic` est un STATUT, pas un rôle — et c'est voulu :
        #  `document_visible` compare `roles ∪ {statut}` à cette liste, et le
        #  syndic ne porte aucun rôle de copropriétaire. C'est déjà ainsi que
        #  fonctionne `cs_syndic_uniquement` plus bas.
        #
        #  🔴 Il manquait, et le syndic ne voyait donc RIEN des quatre catégories
        #  qui s'appuient sur ce profil — règlement de copropriété, PV d'AG, fiche
        #  synthétique, plan de la résidence. Pas même le PV de l'assemblée de
        #  toute la copropriété. Mesuré le 29/08/2026 ; migration 0159 pour les
        #  bases existantes, puisque le seed ne pose que les profils ABSENTS.
        "roles_autorises": json.dumps(["propriétaire", "résident", "syndic"]),
        "require_cs": True,
    },
    {
        "code": "copropriétaires_et_cs",
        "libelle": "Copropriétaires et CS",
        "description": "Propriétaires uniquement — exclut les locataires",
        "roles_autorises": json.dumps(["propriétaire"]),
        "require_cs": True,
    },
    {
        "code": "cs_syndic_uniquement",
        "libelle": "CS et syndic uniquement",
        "description": "Conseil syndical, syndic et admin uniquement",
        "roles_autorises": json.dumps(["syndic"]),  # statut syndic ; CS bypassé en amont
        "require_cs": True,
    },
    {
        "code": "lot_occupants",
        "libelle": "Occupants du lot",
        "description": "Propriétaire + locataire actif du lot + CS + syndic",
        "roles_autorises": json.dumps(["propriétaire", "résident"]),
        "require_cs": True,
    },
    {
        "code": "lot_propriétaires",
        "libelle": "Propriétaires du lot",
        "description": "Propriétaire du lot uniquement + CS + syndic — exclut le locataire",
        "roles_autorises": json.dumps(["propriétaire"]),
        "require_cs": True,
    },
]

CATEGORIES = [
    ("reglement_copropriete", "Règlement de copropriété", "résidence_tous", "résidence", False),
    ("pv_ag",               "PV d'Assemblée Générale",  "résidence_tous", "bâtiment",  True),
    ("fiche_synthetique",   "Fiche synthétique annuelle",  "résidence_tous",   "résidence", False),
    ("plan_residence",      "Plan de la résidence",        "résidence_tous",   "résidence", False),
    ("attestation_lot",     "Attestation (lot)",           "lot_occupants",    "lot",        True),
    ("diagnostic_lot",      "Diagnostic",                  "copropriétaires_et_cs", "bâtiment", True),
    ("contrat_fournisseur", "Contrat fournisseur",         "copropriétaires_et_cs", "bâtiment", True),
    ("contrat_assurance",   "Contrat assurance",           "copropriétaires_et_cs", "résidence", True),
    ("devis_travaux",       "Devis travaux",               "cs_syndic_uniquement", "bâtiment", True),
    ("document_interne_cs", "Document interne CS",         "cs_syndic_uniquement", "résidence", False),
]
