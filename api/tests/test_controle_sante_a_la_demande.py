"""Le contrôle de 06:00 se rejoue à la demande — et mesure LA MÊME chose (#852).

## Pourquoi cet endpoint existe

Le 09/09/2026, le contrôle quotidien a émis une alerte dont la cause était fausse.
Le correctif est parti le matin même, et **rien ne permettait de le vérifier avant
le lendemain 06:00**. Un contrôle qu'on ne peut pas rejouer ne sert pas à
constater sa propre correction.

## Le piège que ces tests ferment

Deux appelants, une seule liste de contrôles. Si l'endpoint reconstituait la
sienne, un `_check_*` ajouté d'un côté manquerait à l'autre — et ce serait le
**bouton** qui se tairait sur un problème réel, le job quotidien étant le seul
dont on voit le résultat.

`test_alerte_systeme` garde l'autre moitié : que tout `_check_*` du module soit
branché dans `collecter_problemes`.
"""
from __future__ import annotations

from app.routers.admin.exploitation import relancer_controle_sante


class _Utilisateur:
    id = 1


def test_il_rend_ce_que_la_COLLECTE_COMMUNE_a_trouve(monkeypatch):
    """La forme rendue est celle de l'e-mail d'alerte : titre + détails."""
    from app.utils import health_monitor

    monkeypatch.setattr(
        health_monitor,
        "collecter_problemes",
        lambda _session: ["Titre du problème\nUn détail\nUn autre"],
    )
    resultat = relancer_controle_sante(session=None, _=_Utilisateur())

    assert resultat["nb"] == 1
    assert resultat["problemes"] == [
        {"titre": "Titre du problème", "details": ["Un détail", "Un autre"]}
    ]


def test_zero_probleme_rend_une_liste_VIDE_et_non_une_absence(monkeypatch):
    """🔴 Vide ≠ absent : l'écran doit pouvoir dire « lancé, rien trouvé ».

    Rendre `null` ferait afficher « jamais lancé » après un contrôle qui vient
    de passer — c'est-à-dire INCONNU à la place d'OK (`standards/04` §1, dans
    l'autre sens).
    """
    from app.utils import health_monitor

    monkeypatch.setattr(health_monitor, "collecter_problemes", lambda _s: [])
    resultat = relancer_controle_sante(session=None, _=_Utilisateur())
    assert resultat == {"nb": 0, "problemes": []}


def test_il_n_ENVOIE_rien():
    """L'alerte est le geste du job de 06:00, pas celui d'un bouton.

    Poster un e-mail à qui vient de lire le résultat à l'écran est le bruit qui
    fait cesser de lire les alertes (`standards/07`).
    """
    import inspect

    source = inspect.getsource(relancer_controle_sante)
    assert "send_email" not in source and "_send_alert" not in source


def test_il_ne_reconstitue_PAS_la_liste_des_controles():
    """Une seconde liste diverge, et c'est le bouton qui se tairait.

    ⚠️ Le test lit le CODE, pas la prose : la docstring de l'endpoint parle des
    `_check_*` pour expliquer qu'elle ne les appelle pas, et une recherche
    littérale se déclenchait sur cette explication même — un garde-fou qui
    s'alarme du récit de sa propre application (`standards/04` §39).
    """
    import ast
    import inspect
    import textwrap

    arbre = ast.parse(textwrap.dedent(inspect.getsource(relancer_controle_sante)))
    appels = {
        n.func.id
        for n in ast.walk(arbre)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "collecter_problemes" in appels
    directs = {n for n in appels if n.startswith("_check_")}
    assert not directs, (
        f"l'endpoint appelle {sorted(directs)} en direct : il vient de fabriquer "
        "une seconde liste, qui divergera de celle du job quotidien."
    )
