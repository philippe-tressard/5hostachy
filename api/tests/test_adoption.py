"""Le taux d'adoption rapporte les comptes VENUS aux comptes qui POUVAIENT venir (#1628).

Jeu fictif : quatre comptes ouverts au bâtiment A (dont un membre du conseil et
un qui a refusé la mesure), un locataire sans bâtiment, un compte fermé qui est
venu quand même. Trois sont venus dans les 30 jours, un seul avant.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from app.models.copropriete import Batiment
from app.models.core import RoleUtilisateur, StatutUtilisateur, TelemetryEvent
from app.utils import horloge
from app.utils.adoption import JOURS, SANS_BATIMENT, adoption
from tests.aides_base import compte, moteur_memoire


def _jeu(s: Session) -> None:
    bat = Batiment(copropriete_id=1, numero="A")
    s.add(bat)
    s.commit()
    copro = StatutUtilisateur.copropriétaire_résident
    venu = compte(s, statut=copro, batiment_id=bat.id)
    conseil = compte(
        s, statut=copro, batiment_id=bat.id, roles_json=RoleUtilisateur.conseil_syndical.value
    )
    absent = compte(s, statut=copro, batiment_id=bat.id)
    refus = compte(s, statut=copro, batiment_id=bat.id, opt_out_telemetrie=True)
    locataire = compte(s, statut=StatutUtilisateur.locataire)
    ferme = compte(s, statut=copro, batiment_id=bat.id, actif=False)

    maintenant = horloge.maintenant()
    for u, age in [(venu, 1), (conseil, 29), (locataire, 0), (ferme, 0), (absent, JOURS + 1)]:
        s.add(TelemetryEvent(user_id=u.id, page="/", cree_le=maintenant - timedelta(days=age)))
    #  Le refus n'a pas d'événement (la collecte l'ignore) ; on en pose un quand
    #  même : il ne doit compter nulle part, ni en haut ni en bas.
    s.add(TelemetryEvent(user_id=refus.id, page="/", cree_le=maintenant))
    s.commit()


def _resultat() -> dict:
    moteur = moteur_memoire()
    with Session(moteur) as s:
        _jeu(s)
        return adoption(s)


def test_le_denominateur_exclut_les_refus_et_les_comptes_fermes():
    r = _resultat()
    assert r["global"] == {"libelle": "Tous les comptes", "actifs": 3, "comptes": 4, "taux": 75}
    assert r["refus"] == 1
    assert r["jours"] == JOURS


def test_ventilation_par_type_de_resident():
    lignes = {ligne["libelle"]: ligne for ligne in _resultat()["par_type"]}
    assert set(lignes) == {"Copropriétaire résident", "Locataire"}
    copro = lignes["Copropriétaire résident"]
    assert (copro["actifs"], copro["comptes"], copro["taux"]) == (2, 3, 67)
    assert (lignes["Locataire"]["actifs"], lignes["Locataire"]["comptes"]) == (1, 1)


def test_ventilation_par_profil_roles_cumules_libelles_partages():
    """Un compte compte sous CHACUN de ses rôles ; le libellé vient de `roles_libelles`."""
    lignes = {ligne["libelle"]: ligne for ligne in _resultat()["par_profil"]}
    assert set(lignes) == {"Résident", "Conseil syndical"}
    assert (lignes["Résident"]["actifs"], lignes["Résident"]["comptes"]) == (2, 3)
    assert (lignes["Conseil syndical"]["actifs"], lignes["Conseil syndical"]["comptes"]) == (1, 1)


def test_ventilation_par_batiment_et_sans_batiment():
    lignes = {ligne["libelle"]: ligne for ligne in _resultat()["par_batiment"]}
    assert set(lignes) == {"Bât. A", SANS_BATIMENT}
    assert (lignes["Bât. A"]["actifs"], lignes["Bât. A"]["comptes"], lignes["Bât. A"]["taux"]) == (
        2,
        3,
        67,
    )


def test_aucun_compte_ne_divise_pas_par_zero():
    moteur = moteur_memoire()
    with Session(moteur) as s:
        r = adoption(s)
    assert (
        r["global"]["taux"] is None
        and r["par_profil"] == []
        and r["par_type"] == []
        and r["par_batiment"] == []
    )
