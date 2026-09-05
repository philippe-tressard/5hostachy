"""Les options de publication d'un ticket : UNE écriture, TROIS chemins.

## Le besoin (05/09/2026, demandé à l'écran)

> « tous les autres options de publication doivent être aussi conservé dans
>   l'objet pour les tickets en édition et commentaire »
> « pas que Visibilité du ticket »

Le ticket ne portait qu'une option (🛡️ « au seul conseil syndical »), et
seulement à la création et à la correction. L'actualité en montre quatre, dans
les quatre états, et ce qu'on y enregistre devient l'état.

## 🔴 Ce que ces tests protègent

La création, le `PATCH` et le commentaire écrivent les mêmes options. Écrite
trois fois, la règle diverge au premier ajout — c'est ce qui était arrivé aux
destinataires, en quatre exemplaires (`commun.py`, en-tête). Ces tests vérifient
donc **le fait par les trois portes**, et refusent qu'une quatrième option
apparaisse dans la table sans que quelqu'un décide ce qu'elle écrit.
"""
from __future__ import annotations

import ast
import pathlib

from app.routers.tickets.commun import (
    OPTIONS_TICKET,
    appliquer_options,
    options_du_ticket,
)


class _Corps:
    """Un corps de requête minimal — seuls comptent les attributs présents."""

    def __init__(self, **champs):
        for cle in OPTIONS_TICKET:
            setattr(self, cle, champs.get(cle))


class _Ticket:
    """Un ticket en mémoire : ces règles ne touchent pas la base."""

    def __init__(self, **champs):
        self.epingle = champs.get("epingle", False)
        self.confidentiel = champs.get("confidentiel", False)
        self.priorite = champs.get("priorite", "normale")


def test_les_trois_options_s_appliquent():
    t = _Ticket()
    changees = appliquer_options(
        t, _Corps(epingle=True, urgente=True, confidentiel=True), est_cs=True
    )
    assert t.epingle is True
    assert t.confidentiel is True
    assert t.priorite == "haute", "🚨 pilote la priorité, il n'y a pas de colonne `urgente`"
    assert set(changees) == set(OPTIONS_TICKET)


def test_None_ne_touche_a_RIEN():
    """🔴 La convention qui rend le même code utilisable par un commentaire.

    Un commentaire qui ne parle que d'une case ne doit pas remettre les autres à
    leur défaut. C'est la même règle que `perimetre_cible` (#497) : `None` veut
    dire « cette entrée ne dit rien de cette option ».
    """
    t = _Ticket(epingle=True, confidentiel=True, priorite="haute")
    changees = appliquer_options(t, _Corps(), est_cs=True)
    assert changees == []
    assert (t.epingle, t.confidentiel, t.priorite) == (True, True, "haute")


def test_un_non_CS_ne_peut_RIEN_poser():
    """Ces options ordonnent la liste du conseil et décident qui lit : elles lui
    appartiennent (#710). Le contrôle est dans la règle, pas chez l'appelant."""
    t = _Ticket()
    changees = appliquer_options(
        t, _Corps(epingle=True, urgente=True, confidentiel=True), est_cs=False
    )
    assert changees == []
    assert (t.epingle, t.confidentiel, t.priorite) == (False, False, "normale")


def test_decocher_marche_aussi():
    """Une option se retire comme elle se pose — sinon elle serait à sens unique."""
    t = _Ticket(epingle=True, confidentiel=True, priorite="haute")
    appliquer_options(
        t, _Corps(epingle=False, urgente=False, confidentiel=False), est_cs=True
    )
    assert (t.epingle, t.confidentiel, t.priorite) == (False, False, "normale")


def test_la_lecture_et_l_ecriture_couvrent_les_MEMES_options():
    """Les deux sens de la même table.

    Si `options_du_ticket` oubliait une option qu'`appliquer_options` écrit,
    l'écran rouvrirait le formulaire avec une case décochée sur un ticket qui la
    porte — et l'enregistrement suivant la retirerait sans que personne l'ait
    demandé.
    """
    t = _Ticket(epingle=True, confidentiel=True, priorite="haute")
    assert set(options_du_ticket(t)) == set(OPTIONS_TICKET)
    assert options_du_ticket(t) == {
        "epingle": True,
        "urgente": True,
        "confidentiel": True,
    }


def test_les_TROIS_chemins_appellent_la_regle_commune():
    """🔴 Le contrôle qui empêche la quatrième copie.

    Création, `PATCH` et commentaire doivent passer par `appliquer_options`. Une
    règle d'autorisation recopiée ne se durcit pas : on en corrige deux sur
    trois (`standards/03-securite.md` §1).
    """
    racine = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "tickets"
    for module, attendus in (("crud.py", 2), ("evolutions.py", 1)):
        source = (racine / module).read_text(encoding="utf-8")
        arbre = ast.parse(source)
        appels = [
            n
            for n in ast.walk(arbre)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "appliquer_options"
        ]
        assert len(appels) == attendus, (
            f"{module} : {len(appels)} appel(s) à `appliquer_options`, {attendus} attendu(s). "
            "Soit un chemin ne pose plus les options, soit un quatrième est apparu "
            "sans passer par la règle commune."
        )


def test_aucune_option_muette_dans_la_table():
    """Une option déclarée doit écrire quelque chose.

    `OPTIONS_TICKET` est la table ; si on y ajoute une clé sans lui donner de
    colonne, `appliquer_options` la traverserait en silence et l'écran
    proposerait une case sans effet — la « promesse vide » que 🔒 aurait été.
    """
    for option in OPTIONS_TICKET:
        t = _Ticket()
        changees = appliquer_options(t, _Corps(**{option: True}), est_cs=True)
        assert changees == [option], (
            f"L'option « {option} » est déclarée mais n'écrit rien : une case "
            "sans effet derrière elle."
        )
