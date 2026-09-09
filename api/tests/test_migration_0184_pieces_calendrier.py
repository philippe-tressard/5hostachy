"""La 0184 pose vraiment la ligne des pièces, et ne la pose pas deux fois (#852).

## Ce qu'elle rattrape

Le 18/08/2026, `calendrier_evenement_suivi` a gagné « 📎 Pièces jointes
ci-dessous. » dans le seed — et **nulle part ailleurs**. `_poser_les_absents` ne
pose que ce qui manque : le modèle existait déjà en base, il n'a jamais été
repris. Les installations en service ont continué d'envoyer des pièces jointes
dont le message ne parlait pas, pendant trois semaines, avec un dépôt vert.

## Ce que ce fichier vérifie — l'EFFET, pas la présence

`test_email_templates` balaie déjà les quatre propriétés formelles de tout
`REMPLACEMENTS_CORPS`. Ce qu'il ne peut pas dire, c'est ce que la migration
**produit** sur le texte réellement en base. C'est le piège de la 0162 : une
migration dont le `instr(... ) > 0` ne trouve rien s'applique sans erreur et ne
fait rien.

Le texte « d'avant » est reconstitué en retirant la ligne du texte du seed — donc
depuis la source, jamais recopié : une copie ici se périmerait à la première
retouche du modèle, et ce test deviendrait vert sur autre chose que la réalité.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from app.seed import EMAIL_TEMPLATES

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "0184_calendrier_suivi_annonce_ses_pieces.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("mig0184", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _corps_seme() -> str:
    for code, _libelle, _sujet, corps, _desactivable in EMAIL_TEMPLATES:
        if code == "calendrier_evenement_suivi":
            return corps
    raise AssertionError("`calendrier_evenement_suivi` a disparu de EMAIL_TEMPLATES.")


def _avant() -> str:
    """Le corps tel qu'une base en service le porte : le seed, moins la ligne."""
    module = _module()
    corps = _corps_seme()
    assert module._LIGNE in corps, (
        "La ligne des pièces jointes n'est plus dans le seed : la 0184 pose "
        "désormais un texte que les bases neuves n'auront pas."
    )
    return corps.replace(module._LIGNE, "", 1)


def test_elle_TROUVE_ce_qu_elle_cherche_dans_le_texte_dune_base_en_service():
    """Le piège de la 0162 : un `instr()` qui ne trouve rien s'applique en vain."""
    _code, ancien, _nouveau = _module().REMPLACEMENTS_CORPS[0]
    assert ancien in _avant(), (
        "La 0184 cherche un fragment absent du corps servi : elle s'appliquerait "
        "sans erreur et sans effet, et rien ne le signalerait."
    )


def test_elle_produit_EXACTEMENT_le_texte_du_seed():
    """Sinon une base migrée et une base neuve n'enverraient pas le même message."""
    _code, ancien, nouveau = _module().REMPLACEMENTS_CORPS[0]
    assert _avant().replace(ancien, nouveau) == _corps_seme()


def test_la_REJOUER_n_ajoute_pas_la_ligne_une_seconde_fois():
    """Une migration se rejoue : sur une base déjà à jour, elle ne doit rien faire."""
    _code, ancien, nouveau = _module().REMPLACEMENTS_CORPS[0]
    deja_faite = _avant().replace(ancien, nouveau)
    assert deja_faite.replace(ancien, nouveau) == deja_faite
    assert deja_faite.count(_module()._LIGNE) == 1


def test_le_ROLLBACK_rend_le_texte_de_depart():
    """`downgrade` remet le fragment d'origine, sans laisser de trace."""
    _code, ancien, nouveau = _module().REMPLACEMENTS_CORPS[0]
    assert _corps_seme().replace(nouveau, ancien) == _avant()
