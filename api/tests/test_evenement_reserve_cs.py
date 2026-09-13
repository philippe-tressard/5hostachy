"""Un événement **réservé au conseil syndical** ne se voit ni ne se diffuse.

## Pourquoi cette option existe (#939, 13/09/2026)

Question posée à l'utilisateur — *« les autres options de publication ont-elles
un sens pour le calendrier ? »* — et arbitrage rendu :

> « Oui pour la visibilité CS, laisse les deux autres. »

Un événement était **tout ou rien** : visible de tous, ou inexistant. Préparer
une assemblée, noter une visite de contrôle avant d'en informer les résidents —
rien ne permettait de le faire, et le conseil syndical le faisait donc ailleurs.

🔴 **Les deux autres ne sont pas livrées, et ce fichier ne les teste donc pas** :
🚨 doublerait la date (qui dit déjà l'urgence, et pourrait la contredire), et 🔒
n'aurait rien à restreindre — la lecture d'un événement suit déjà son périmètre.

## Pourquoi un test, et pas une relecture

Une règle d'accès qui s'ouvre **ne produit aucun signal** : personne ne se plaint
de voir quelque chose. C'est la classe de défaut de `standards/03` et de l'audit
du 26/07/2026 — trois dérives installées sans que rien ne les signale.

Et la réserve traverse **deux** surfaces qu'on ne relit jamais ensemble : la
LECTURE (`evenement_visible`, appelée par la liste, le fil et les documents) et
la DIFFUSION (`notifier_canaux`). Une réserve qui tiendrait à l'écran et
laisserait partir un message WhatsApp au groupe des résidents serait pire
qu'absente : elle promettrait.
"""
from __future__ import annotations

import pytest

from app.models.core import RoleUtilisateur, StatutUtilisateur, Utilisateur
from app.models.evenement import Evenement, TypeEvenement
from app.utils.visibility import evenement_visible


def _utilisateur(roles: str, statut: str) -> Utilisateur:
    return Utilisateur(
        nom="X",
        prenom="Y",
        email=f"{roles}-{statut}@test.fr",
        roles_json=roles,
        statut=statut,
        batiment_id=None,
        actif=True,
    )


def _evenement(*, reserve_cs: bool, type_ev: str = TypeEvenement.autre) -> Evenement:
    return Evenement(
        titre="T",
        type=type_ev,
        debut="2026-09-20T10:00:00",
        auteur_id=1,
        perimetre=None,
        reserve_cs=reserve_cs,
    )


#: Les profils qui ne sont NI conseil syndical NI admin. Énumérés plutôt que
#: résumés à « un résident » : la réserve doit tenir pour chacun, et c'est
#: précisément le genre de règle qu'on croit vraie pour tous après l'avoir
#: vérifiée sur un seul.
PROFILS_NON_CS = [
    (RoleUtilisateur.propriétaire.value, StatutUtilisateur.copropriétaire_résident.value),
    (RoleUtilisateur.résident.value, StatutUtilisateur.locataire.value),
    (RoleUtilisateur.propriétaire.value, StatutUtilisateur.copropriétaire_bailleur.value),
]


@pytest.mark.parametrize("roles,statut", PROFILS_NON_CS)
def test_un_evenement_reserve_est_invisible_hors_du_conseil(roles, statut):
    """🔴 Le cœur de la règle."""
    user = _utilisateur(roles, statut)
    assert evenement_visible(_evenement(reserve_cs=True), user) is False


@pytest.mark.parametrize("roles,statut", PROFILS_NON_CS)
def test_le_meme_evenement_non_reserve_reste_visible(roles, statut):
    """Le contre-exemple, sans lequel le test ci-dessus passerait aussi si
    `evenement_visible` rendait `False` pour tout le monde."""
    user = _utilisateur(roles, statut)
    assert evenement_visible(_evenement(reserve_cs=False), user) is True


def test_le_conseil_syndical_voit_ce_qu_il_a_reserve():
    """Sans quoi la réserve serait une suppression."""
    cs = _utilisateur(
        RoleUtilisateur.conseil_syndical.value,
        StatutUtilisateur.copropriétaire_résident.value,
    )
    assert evenement_visible(_evenement(reserve_cs=True), cs) is True


def test_l_admin_aussi():
    admin = _utilisateur(
        RoleUtilisateur.admin.value, StatutUtilisateur.copropriétaire_résident.value
    )
    assert evenement_visible(_evenement(reserve_cs=True), admin) is True


def test_la_reserve_prime_sur_le_type_ag():
    """⚠️ La réserve est posée AVANT la règle d'AG, et ce test le fige.

    Un propriétaire voit les AG. Si la réserve était placée après, un événement
    d'AG réservé lui resterait visible — la réserve dépendrait alors du type, et
    l'une des deux règles finirait par bouger sans l'autre.
    """
    proprio = _utilisateur(
        RoleUtilisateur.propriétaire.value, StatutUtilisateur.copropriétaire_résident.value
    )
    ag_ouverte = _evenement(reserve_cs=False, type_ev=TypeEvenement.ag)
    ag_reservee = _evenement(reserve_cs=True, type_ev=TypeEvenement.ag)
    assert evenement_visible(ag_ouverte, proprio) is True
    assert evenement_visible(ag_reservee, proprio) is False


def test_la_garde_whatsapp_est_posee_au_point_de_passage_des_envois():
    """🔴 Le groupe WhatsApp rassemble TOUS les résidents.

    Y partager ce qu'on vient de réserver au conseil annulerait la réserve au
    moment même où on la pose. La garde vit dans `notifier_canaux` — le point de
    passage unique — et non chez ses appelants : une garde chez l'appelant se
    serait recopiée au troisième, et le troisième l'aurait oubliée.

    ⚠️ Le test lit la SOURCE, parce que déclencher un envoi réel demanderait un
    bridge WhatsApp et une base : ce qu'on vérifie est que la garde est au bon
    endroit, et le contrôle le dit s'il ne peut plus la trouver (jamais un vert
    par défaut).
    """
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[1]
        / "app"
        / "routers"
        / "calendrier_courriels.py"
    ).read_text(encoding="utf-8")

    corps = source.split("def notifier_canaux(", 1)
    assert len(corps) == 2, "`notifier_canaux` est introuvable — le contrôle ne peut pas conclure"
    garde = "if ev.reserve_cs:"
    assert garde in corps[1], "la garde WhatsApp a quitté `notifier_canaux`"
    #  Elle doit précéder le premier envoi : posée après, elle ne garderait rien.
    assert corps[1].index(garde) < corps[1].index("if not (whatsapp or syndic or cs):")


def test_le_syndic_et_le_cs_restent_joignables():
    """⚠️ La réserve borne ce que les RÉSIDENTS voient, pas la correspondance
    interne : seul le canal WhatsApp est coupé, jamais les deux courriels."""
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[1]
        / "app"
        / "routers"
        / "calendrier_courriels.py"
    ).read_text(encoding="utf-8")
    bloc = source.split("if ev.reserve_cs:", 1)[1].split("\n\n", 1)[0]
    assert "whatsapp = False" in bloc
    assert "syndic = False" not in bloc
    assert "cs = False" not in bloc
