"""La migration 0162 TROUVE ce qu'elle cherche dans un gabarit réel.

## 🔴 Pourquoi ce test existe

Deux pièges se referment sur ce genre de migration, et les deux la rendent
**verte sans avoir rien fait** :

1. `_poser_les_absents` ne pose que ce qui manque. Modifier `EMAIL_TEMPLATES`
   seul ne change donc **rien** en production, où `ticket_syndic` existe déjà.
   Le lot serait parti, le courriel serait resté identique — et le défaut aurait
   été signalé une troisième fois.
2. Le gabarit est du **source Python** : `\\u2014` y est une séquence
   d'échappement, et la base stocke le caractère décodé. Une migration qui
   chercherait la séquence ne trouverait jamais rien, et son
   `instr(corps_html, :ancien) > 0` la rendrait silencieusement inerte.

Aucune exécution de la suite ne révèle ces deux-là : la migration s'applique sans
erreur, et le contrôle des migrations vérifie la CHAÎNE, pas l'effet.

## Ce que ce fichier vérifie

Que les trois fragments cherchés existent **dans le gabarit tel qu'il est semé** —
donc tels que la base les porte.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from app.seed import EMAIL_TEMPLATES

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "0162_ticket_syndic_perimetre.py"
)


def _fragments():
    spec = importlib.util.spec_from_file_location("mig0162", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._FRAGMENTS


def _corps_seme() -> str:
    for code, _libelle, _sujet, corps, _desactivable in EMAIL_TEMPLATES:
        if code == "ticket_syndic":
            return corps
    raise AssertionError("`ticket_syndic` a disparu de EMAIL_TEMPLATES.")


def test_les_trois_fragments_sont_bien_TROIS():
    """Cas zéro : une liste vide passerait toutes les autres assertions."""
    assert len(_fragments()) == 3, (
        "La migration ne porte plus trois fragments — soit elle a changé, soit "
        "ce test surveille autre chose. Ne pas lire ceci comme un succès."
    )


def test_chaque_fragment_APRES_existe_dans_le_gabarit_seme():
    """Le résultat visé doit être exactement ce que le seed produit désormais.

    Sans cela, une base neuve et une base migrée rendraient deux courriels
    différents — et c'est la base migrée, la production, qui aurait tort.
    """
    corps = _corps_seme()
    for _avant, apres in _fragments():
        assert apres in corps, (
            "Le fragment visé par la migration n'est pas dans le gabarit semé :\n"
            f"  {apres!r}\n"
            "Une base neuve et une base migrée divergeraient."
        )


def test_aucun_fragment_ne_cherche_une_SEQUENCE_d_echappement():
    """Le piège n° 2, vérifié sur la forme.

    La base stocke « — », pas « \\u2014 ». Un fragment qui porterait la séquence
    ne correspondrait à rien, et la migration passerait sans rien faire.
    """
    for avant, apres in _fragments():
        for texte, quoi in ((avant, "avant"), (apres, "après")):
            assert "\\u" not in texte and "\\U" not in texte, (
                f"Le fragment « {quoi} » porte une séquence d'échappement :\n"
                f"  {texte!r}\n"
                "La base stocke le caractère décodé : ce fragment ne "
                "correspondra à rien, et la migration sera inerte."
            )


def test_le_seed_ne_met_PAS_a_jour_les_modeles_existants():
    """Le piège n° 1, vérifié sur le mécanisme et non sur la mémoire.

    ⚠️ Si `_modeles_email` se mettait un jour à écraser l'existant, cette
    migration deviendrait inutile — mais surtout, les retouches faites depuis
    Admin → E-mails seraient effacées à chaque déploiement. Le jour où ce test
    échoue, c'est cette question-là qu'il faut rouvrir, pas lui.
    """
    import inspect

    from app.seed import _modeles_email

    source = inspect.getsource(_modeles_email)
    assert "_poser_les_absents" in source, (
        "`_modeles_email` n'emploie plus `_poser_les_absents` : vérifier qu'il "
        "n'écrase pas les modèles retouchés depuis l'administration."
    )
