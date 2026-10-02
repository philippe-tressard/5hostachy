"""Les lots IMPORTÉS d'un classeur — `models/lot_import.py` (#1569, #779, #1157).

Table de passage, extraite de `core.py` le 28/09/2026. Le module n'était nommé par
aucun test. Il n'a pas de logique : on tient donc ce qui peut casser SANS bruit —

1. `core` la RÉ-EXPORTE, et c'est cet import qui l'enregistre auprès d'Alembic
   (`alembic/env.py` n'importe que `core`, #1157) : une classe dupliquée ou une table
   non enregistrée ne ferait aucun bruit ;
2. les valeurs par défaut qu'une ligne neuve reçoit (en attente, aucun occupant, date d'import) ;
3. les valeurs de l'énumération, qui sont aussi des chaînes stockées et lues par le front ;
4. un aller-retour en base, `utilisateurs_json` compris.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlmodel import SQLModel

import app.models.core as core
from app.models import lot_import
from app.models.lot_import import LotImport, StatutLotImport
from app.utils import horloge


def test_core_reexporte_les_deux_noms_sans_les_dupliquer():
    assert core.LotImport is lot_import.LotImport
    assert core.StatutLotImport is lot_import.StatutLotImport


def test_la_table_est_enregistree_aupres_de_sqlmodel():
    table = SQLModel.metadata.tables["lot_import"]

    assert table is LotImport.__table__
    assert {"numero", "type_raw", "statut", "lot_id", "utilisateurs_json"} <= set(
        table.columns.keys()
    )


def test_le_lot_est_reference_par_nom_de_table():
    cles = {fk.target_fullname for fk in LotImport.__table__.columns["lot_id"].foreign_keys}

    assert cles == {"lot.id"}


def test_les_statuts_sont_les_cinq_attendus():
    assert {s.name: s.value for s in StatutLotImport} == {
        "en_attente": "en_attente",
        "utilisateur_lie": "utilisateur_lie",
        "lot_lie": "lot_lie",
        "resolu": "resolu",
        "ignore": "ignore",
    }
    assert issubclass(StatutLotImport, str), "stocké et sérialisé comme une chaîne"


def test_une_ligne_neuve_est_en_attente_sans_occupant():
    ligne = LotImport(numero="12", type_raw="AP")

    assert ligne.statut == StatutLotImport.en_attente
    assert json.loads(ligne.utilisateurs_json) == []
    assert ligne.lot_id is None
    assert ligne.resolu_le is None
    assert ligne.notes_admin is None
    assert ligne.batiment_id is None, "None pour les parkings"


def test_la_date_d_import_est_celle_de_l_horloge_en_utc_naif():
    avant = horloge.maintenant()
    ligne = LotImport(numero="12", type_raw="AP")
    apres = horloge.maintenant()

    assert isinstance(ligne.importe_le, datetime) and ligne.importe_le.tzinfo is None
    assert avant <= ligne.importe_le <= apres


def test_le_numero_et_le_type_brut_sont_obligatoires():
    with pytest.raises(ValidationError) as exc:
        LotImport.model_validate({})

    assert {e["loc"][0] for e in exc.value.errors()} == {"numero", "type_raw"}


def test_une_ligne_s_enregistre_et_se_relit(session):
    occupants = [
        {"user_id": 12, "type_lien": "propriétaire"},
        {"user_id": 15, "type_lien": "locataire"},
    ]
    ligne = LotImport(
        numero="314",
        type_raw="T2",
        etage_raw="3",
        no_coproprietaire="C-0042",
        nom_coproprietaire="DUPONT Jean",
        statut=StatutLotImport.utilisateur_lie,
        utilisateurs_json=json.dumps(occupants),
    )
    session.add(ligne)
    session.commit()
    session.refresh(ligne)

    relue = session.get(LotImport, ligne.id)

    assert relue.statut == StatutLotImport.utilisateur_lie
    assert json.loads(relue.utilisateurs_json) == occupants
    assert (relue.numero, relue.type_raw, relue.etage_raw) == ("314", "T2", "3")
    assert relue.nom_coproprietaire == "DUPONT Jean"
    assert relue.importe_le is not None
