"""Une demande de badge en attente se LIT : qui la demande, pour quel lot (#1679).

## Le défaut (trouvé le 04/10/2026 en typant le client, #1572)

`GET /admin/commandes-acces` rendait la ligne `commande_acces` brute —
`user_id`, `lot_id`, `type`. L'espace CS lisait pourtant `cmd.proprietaire`,
`cmd.lot.batiment.nom` et `cmd.lot.reference`, qu'aucun serveur n'a jamais
rendus : dès qu'une commande attendait, le rendu de l'onglet levait une
exception (`e2e/commandes-acces-espace-cs.spec.ts`).

La route ajoute désormais à la ligne ce qui la rend lisible — comme le fait
déjà `GET /admin/demandes-profil` —, une fois, pour les deux écrans qui la
lisent (l'espace CS et l'onglet « À traiter » de l'administration).
"""

from __future__ import annotations

from fastapi.encoders import jsonable_encoder

from app.models.copropriete import Batiment
from app.models.core import CommandeAcces, StatutCommande
from app.routers.admin.acces import list_commandes_acces
from app.utils.types_acces import TELECOMMANDE
from tests.aides_badges import _compte, _lot


def test_la_ligne_porte_le_demandeur_le_lot_et_le_batiment(session):
    bat = Batiment(copropriete_id=1, numero="4")
    session.add(bat)
    session.commit()
    session.refresh(bat)
    lot = _lot(session, TELECOMMANDE, numero="12", batiment_id=bat.id)
    anne = _compte(session, "Durand")
    anne.prenom = "Anne"
    session.add(anne)
    session.add(CommandeAcces(user_id=anne.id, lot_id=lot.id, type="telecommande", quantite=2))
    session.commit()

    (ligne,) = jsonable_encoder(list_commandes_acces(session=session, _=None))

    #  La ligne elle-même reste entière : l'administration lit `user_id`, `lot_id`.
    assert ligne["user_id"] == anne.id
    assert ligne["lot_id"] == lot.id
    assert ligne["type"] == "telecommande"
    assert ligne["quantite"] == 2
    #  … et ce qui la rend lisible.
    assert ligne["demandeur_nom"] == "Anne DURAND"
    assert ligne["lot"] == "Parking 12"
    assert ligne["batiment"] == "Bât. 4"


def test_cas_zero_un_lot_ou_un_compte_disparu_ne_fait_pas_tomber_la_liste(session):
    """Une commande orpheline reste listée, et dit ce qui manque."""
    session.add(CommandeAcces(user_id=999, lot_id=998, type="vigik"))
    session.add(
        CommandeAcces(user_id=999, lot_id=998, type="vigik", statut=StatutCommande.acceptee)
    )
    session.commit()

    (ligne,) = jsonable_encoder(list_commandes_acces(session=session, _=None))
    assert ligne["demandeur_nom"] == "?"
    assert ligne["lot"] == "?"
    assert ligne["batiment"] is None
