"""Les règles de reclassement, éprouvées sur les cas qui les ont produites (#821).

⚠️ Ce fichier existe parce que les règles lisent du **texte libre**. Une
proposition fausse posée en silence est pire qu'une catégorie approximative
assumée — et rien, dans un jeu de mots-clés, ne dit tout seul qu'il vise à côté.
"""
from __future__ import annotations

from app.utils.reclassement_tickets import JAMAIS_PROPOSEE, proposer


def _cat(titre, description="", actuelle="panne"):
    p = proposer(titre, description, actuelle)
    return p[0] if p else None


def test_une_FUITE_reste_une_panne():
    """🔴 Le cas qui a corrigé mes règles (07/09/2026).

    *« Une fuite de type goutte-à-goutte dans les communs, tu la qualifies Panne
    ou Sinistre ? »* — Panne. La frontière n'est pas l'eau, c'est le DOMMAGE.
    Mon premier jeu rangeait « fuite » dans les indices de sinistre, et aurait
    proposé de déplacer des réparations vers une procédure d'assurance.
    """
    assert _cat("Fuite goutte-à-goutte dans le local poubelle") != "sinistre"
    assert _cat("Robinet qui fuit au sous-sol") != "sinistre"


def test_une_PANNE_ELECTRIQUE_reste_une_panne():
    """Deuxième cas du même arbitrage : ampoule grillée, interrupteur HS.

    C'est le cœur de « Panne », et c'est pourquoi « Éclairage » a été écartée
    comme catégorie séparée.
    """
    assert _cat("Ampoule grillée dans l'escalier B") is None
    assert _cat("Interrupteur HS au 3ᵉ étage") is None


def test_un_DOMMAGE_est_un_sinistre():
    """Le pendant : ce qui doit bien basculer."""
    assert _cat("Dégât des eaux chez Mme Martin") == "sinistre"
    assert _cat("Infiltration au plafond du hall") == "sinistre"
    assert _cat("Vitre brisée", "effraction cette nuit") == "sinistre"


def test_la_PROPRETE_propose_desormais_nuisance():
    """La fusion du 07/09/2026 (migration 0179) vue du côté du relevé."""
    assert _cat("Encombrants abandonnés dans le hall") == "nuisance"
    assert _cat("Local poubelle jamais nettoyé") == "nuisance"
    assert _cat("Tapage nocturne au 2ᵉ") == "nuisance"


def test_l_accueil_et_les_espaces_verts():
    assert _cat("Nom à corriger sur l'interphone") == "acces_accueil"
    assert _cat("Élagage des haies côté parking") == "espaces_verts"
    assert _cat("Diagnostic d'étanchéité du toit-terrasse") == "etude_travaux"


def test_on_ne_propose_JAMAIS_de_deplacer_vers_panne():
    """« Panne » est la catégorie par défaut : y déplacer, c'est effacer.

    Le cas zéro de cette règle : un ticket rangé ailleurs, dont le texte ne parle
    que de réparation, ne doit produire AUCUNE proposition — surtout pas « panne ».
    """
    assert "panne" in JAMAIS_PROPOSEE
    for actuelle in ("nuisance", "sinistre", "espaces_verts", "acces_accueil"):
        proposition = proposer("Ascenseur bloqué", "il ne monte plus", actuelle)
        assert proposition is None or proposition[0] != "panne", proposition


def test_rien_a_proposer_rend_None():
    """Un ticket déjà bien rangé, et un ticket qui ne dit rien."""
    assert proposer("Dégât des eaux", "", "sinistre") is None
    assert proposer("Problème", "", "panne") is None


def test_les_BALISES_html_ne_produisent_pas_d_indices():
    """Une description est du HTML : rien de ce qui est DANS une balise ne compte.

    ⚠️ Mon premier test attendait que `<img alt="haie">` propose « espaces
    verts ». Il avait tort, et le contrôle a eu raison : un texte alternatif
    d'image n'est pas le contenu du ticket. La proposition doit venir de ce que
    la personne a ÉCRIT, jamais du balisage — sinon un attribut mal choisi
    déplacerait un ticket.
    """
    #  Le texte entre balises, lui, est bien lu.
    assert _cat("Souci", "<p>Élagage des haies côté parking</p>") == "espaces_verts"
    #  Et ce qui est dans une balise ne l'est pas.
    assert _cat("Souci", '<img alt="haie" src="/x.jpg" />') is None
    #  Un nom de balise ne devient jamais un mot.
    assert _cat("Souci", "<p>ampoule grillée</p>") is None


def test_la_CONFIANCE_distingue_l_univoque_de_l_ambigu():
    """Sans elle, on validerait « bruit » aussi vite que « dégât des eaux »."""
    assert proposer("Tapage nocturne", "", "panne")[1] == "haute"
    assert proposer("Un bruit bizarre", "", "panne")[1] == "moyenne"
