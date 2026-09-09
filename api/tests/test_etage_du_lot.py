"""L'étage d'un lot, écrit par son occupant depuis le profil (#835).

## L'arbitrage, et ce qu'il accepte

`Lot.etage` est une donnée de **patrimoine** : elle sert aux imports, aux fiches
et aux affiches. Deux écrans l'écrivent désormais — l'administration et le profil
— avec deux niveaux de contrôle. Tranché par Philippe le 09/09/2026, l'alternative
(lecture seule + « signaler une erreur ») ayant été posée : c'est l'occupant qui
sait à quel étage il vit, et passer par un ticket pour corriger un chiffre était
la friction de trop.

Ce que ces tests verrouillent, c'est donc la **portée** de cette ouverture :

1. on n'écrit que l'étage — le reste du lot n'est pas dans le schéma ;
2. on n'écrit que le lot **rattaché**, et le repli par rôle de `get_lot` ne
   s'applique PAS à une écriture : un conseiller a l'écran du patrimoine ;
3. les bornes de l'étage sont vérifiées côté serveur, un champ borné côté client
   se postant directement ;
4. 🔴 le cas zéro : une modification légitime passe — sans quoi les trois refus
   ci-dessus resteraient verts sur un endpoint qui refuse tout.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers.lots import EtageLotUpdate, maj_etage_de_mon_lot
from app.utils.etages import ETAGE_MAX, ETAGE_MIN


class _Lot:
    def __init__(self, id_: int, etage=None):
        self.id = id_
        self.numero = f"A{id_}"
        self.type = "appartement"
        self.type_appartement = None
        self.superficie = None
        self.etage = etage
        self.tantiemes = None
        self.batiment = None
        self.batiment_id = None


class _UserLot:
    def __init__(self, lot_id: int, actif: bool = True):
        self.lot_id = lot_id
        self.actif = actif


class _Utilisateur:
    def __init__(self, user_lots):
        self.id = 7
        self.user_lots = user_lots

    def has_role(self, *_roles):
        #  Le repli par rôle de `get_lot` n'a pas sa place sur une écriture :
        #  s'il était consulté ici, ce test le montrerait en rendant True.
        raise AssertionError("l'écriture ne doit PAS consulter le rôle")


class _Session:
    def __init__(self, lots):
        self._lots = {l.id: l for l in lots}
        self.commits = 0

    def get(self, _classe, id_):
        return self._lots.get(id_)

    def add(self, _o):
        pass

    def commit(self):
        self.commits += 1

    def refresh(self, _o):
        pass


def _appeler(lot_id, etage, lots, rattaches):
    user = _Utilisateur([_UserLot(i) for i in rattaches])
    session = _Session(lots)
    return maj_etage_de_mon_lot(lot_id, EtageLotUpdate(etage=etage), session, user), session


def test_l_occupant_ecrit_l_etage_de_SON_lot():
    """🔴 Le cas zéro : sans lui, un endpoint qui refuse tout passerait."""
    lot = _Lot(1)
    _resultat, session = _appeler(1, 3, [lot], [1])
    assert lot.etage == 3
    assert session.commits == 1


def test_un_lot_qui_n_est_PAS_le_mien_est_refuse():
    lot = _Lot(2)
    with pytest.raises(HTTPException) as leve:
        _appeler(2, 3, [lot], [1])
    assert leve.value.status_code == 403
    assert lot.etage is None


def test_une_association_INACTIVE_ne_donne_aucun_droit():
    """Un ancien locataire ne modifie plus le lot qu'il a quitté."""
    lot = _Lot(1)
    user = _Utilisateur([_UserLot(1, actif=False)])
    with pytest.raises(HTTPException) as leve:
        maj_etage_de_mon_lot(1, EtageLotUpdate(etage=3), _Session([lot]), user)
    assert leve.value.status_code == 403


def test_un_lot_INCONNU_rend_404_et_non_403():
    with pytest.raises(HTTPException) as leve:
        _appeler(99, 3, [_Lot(1)], [1])
    assert leve.value.status_code == 404


@pytest.mark.parametrize("valeur", [ETAGE_MIN - 1, ETAGE_MAX + 1, 999])
def test_un_etage_hors_bornes_est_refuse_par_l_API(valeur):
    """Un champ borné côté client se poste directement."""
    lot = _Lot(1, etage=2)
    with pytest.raises(HTTPException) as leve:
        _appeler(1, valeur, [lot], [1])
    assert leve.value.status_code == 400
    assert lot.etage == 2, "la valeur refusée a quand même été écrite"


@pytest.mark.parametrize("valeur", [ETAGE_MIN, 0, ETAGE_MAX])
def test_les_bornes_elles_memes_sont_acceptees(valeur):
    """`0` est le rez-de-chaussée : le refuser serait un test de vérité."""
    lot = _Lot(1)
    _appeler(1, valeur, [lot], [1])
    assert lot.etage == valeur


def test_un_etage_VIDE_efface_la_valeur():
    """La charge utile ne porte que ce champ : `None` n'y est pas ambigu."""
    lot = _Lot(1, etage=4)
    _appeler(1, None, [lot], [1])
    assert lot.etage is None


def test_le_schema_ne_porte_QUE_l_etage():
    """La liste blanche est le schéma lui-même : le reste du lot n'entre pas."""
    assert set(EtageLotUpdate.model_fields) == {"etage"}
