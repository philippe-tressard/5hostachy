"""Le manuel PDF est une MISE EN PAGE du manuel, jamais une seconde rédaction.

## 🔴 Ce que ce fichier protège

Demandé le 03/09/2026 : un manuel en PDF, avec page de garde, QR code, sommaire
et mentions. La tentation évidente était de le rédiger — et ce dépôt a déjà payé
**quatre fois** la divergence de deux textes décrivant la même chose (périmètres,
canaux de notification, table des pages, chiffres du manuel).

Un PDF re-rédigé aurait divergé au premier écran modifié, sans que rien ne le
signale. Et c'est le PDF, imprimé et distribué, qu'on aurait lu le plus longtemps
après sa péremption.

Le contenu est donc **lu tel qu'il est servi**, puis transformé. Ce fichier
vérifie que la transformation ne perd rien et n'invente rien.

## Ce qu'il ne peut pas vérifier

Le rendu PDF lui-même : WeasyPrint exige des bibliothèques système que le poste
de développement n'a pas (elles sont dans `api/Dockerfile`). La composition est
donc séparée du rendu — `composer_html` d'un côté, `html_to_pdf` de l'autre — et
c'est la composition qui porte toutes les décisions.

Même coupure que `courriel_ingestion` / `courriel_boite` : la décision se teste,
le tuyau se branche.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from app.utils.manuel_pdf import (
    ManuelIndisponible,
    composer_html,
    corps_du_manuel,
    lire_manuel,
    sommaire,
    version_du_manuel,
)

_MANUEL = Path(__file__).resolve().parents[2] / "docs" / "manuel-utilisateur.html"


@pytest.fixture(scope="module")
def manuel() -> str:
    return _MANUEL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def document(manuel) -> str:
    return composer_html(
        "5Hostachy", "https://5hostachy.fr",
        html_manuel=manuel, edite_le=date(2026, 9, 3),
    )


# ── La source est bien le manuel, et rien d'autre ────────────────────────────

def test_le_contenu_du_manuel_se_retrouve_dans_le_PDF(document, manuel):
    """🔴 Le cœur : une phrase du manuel doit être dans le document composé.

    Si quelqu'un remplaçait un jour la lecture par une rédaction, ce test
    tomberait à la première divergence — c'est le seul moyen de tenir la
    promesse « même contenu » faite au lecteur dans le lien de téléchargement.
    """
    for extrait in (
        "Le menu, écran par écran",
        "Réglez vos notifications",
        "Mini sommaire par profil",
    ):
        assert extrait in manuel, f"le manuel a changé : « {extrait} » a disparu"
        assert extrait in document, (
            f"« {extrait} » est dans le manuel mais pas dans le PDF : la mise en "
            "page perd du contenu"
        )


def test_les_QUINZE_ecrans_sont_dans_le_PDF(document):
    """La grille est l'essentiel du manuel : en perdre une carte le mutilerait."""
    assert document.count('class="ecran-card"') == 15


# ── 🔴 Les blocs dépliables : du contenu invisible serait du contenu perdu ────

def test_les_blocs_depliables_sont_OUVERTS(document):
    """Un `<details>` fermé, sur du papier, est du contenu perdu.

    Et c'est justement celui qu'on a demandé à voir : Tickets, Communauté et Mon
    profil, les trois écrans dont l'usage ne se devine pas au titre.

    ⚠️ La première version s'en remettait au CSS (`display: block !important`).
    Ça ne suffit pas : le repli d'un `<details>` est un comportement natif, pas
    une règle de style — le navigateur l'a confirmé à l'aperçu, et un moteur PDF
    n'a aucune raison de faire mieux. La balise est donc transformée.
    """
    assert "<details" not in document, (
        "un `<details>` subsiste : son contenu pourrait ne pas être imprimé"
    )
    assert "<summary" not in document
    assert document.count("En détail") == 3, "les trois blocs ne sont pas dépliés"
    #  Et leur contenu doit vraiment être là.
    assert "votre réponse rejoint le fil du ticket" in document
    assert "Boîte à idées" in document


# ── Le sommaire est CONSTRUIT, pas recopié ───────────────────────────────────

def test_le_sommaire_suit_les_titres_du_document(manuel, document):
    """Une table des matières recopiée est une table de plus.

    Ce manuel vient précisément de perdre toutes ses tables recopiées (#651) :
    en réintroduire une, tenue à la main, serait le comble.
    """
    titres = sommaire(manuel)
    assert titres, "aucun titre relevé : le sommaire serait vide"
    for titre in titres:
        assert titre in document, f"« {titre} » manque au sommaire composé"
    #  L'ordre du document, pas un ordre inventé.
    positions = [document.index(f"<li>{t}</li>") for t in titres]
    assert positions == sorted(positions)


def test_le_sommaire_decode_les_entites(manuel):
    """« Une question&nbsp;? » ne doit pas s'afficher avec son entité brute.

    Défaut réel, vu au premier essai : un sommaire qui montre `&nbsp;` trahit sa
    fabrication, et la typographie française du manuel en emploie partout.
    """
    titres = sommaire(manuel)
    assert not any("&nbsp;" in t or "&amp;" in t for t in titres), titres
    assert any(t.startswith("Une question") for t in titres)


# ── La page de garde et les mentions ─────────────────────────────────────────

def test_la_page_de_garde_porte_le_QR_code_et_la_date(document):
    assert 'class="garde"' in document
    assert "data:image/png;base64," in document, "le QR code n'a pas été généré"
    assert "3 septembre 2026" in document
    assert "https://5hostachy.fr" in document


def test_la_version_du_manuel_est_reprise_telle_qu_elle_est_ecrite(manuel, document):
    """Elle est LUE dans le manuel, jamais saisie ici — sinon deux versions."""
    version = version_du_manuel(manuel)
    assert re.fullmatch(r"v\d+\.\d+", version), f"version illisible : {version!r}"
    assert version in document


def test_les_mentions_avertissent_de_la_PEREMPTION(document):
    """⚠️ Ce n'est pas une formule de style.

    Un PDF imprimé survit à l'écran qu'il décrit. C'est le seul endroit où l'on
    peut le dire au lecteur qui l'aura sous les yeux dans deux ans — et lui
    indiquer où trouver la version à jour.
    """
    assert 'class="mentions"' in document
    assert "c'est l'écran qui a raison" in document
    assert "conseil syndical de la copropriété" in document, (
        "les mentions ne nomment aucun éditeur"
    )
    assert "Philippe Tressard" not in document, (
        "un nom de personne réapparaît dans un document distribuable"
    )


# ── La lecture de la source ──────────────────────────────────────────────────

def test_un_manuel_illisible_LEVE_au_lieu_de_composer_du_vide():
    """Un PDF d'un manuel qu'on n'a pas pu lire serait une couverture, rien de plus.

    Et personne ne s'en apercevrait avant de l'ouvrir : la page de garde, elle,
    se serait composée normalement.
    """
    with pytest.raises(ManuelIndisponible):
        lire_manuel("http://127.0.0.1:1/introuvable.html", timeout=0.2)


def test_le_manuel_annonce_le_lien_vers_son_PDF(manuel):
    """Le lien vit dans la section « Une question ? », comme demandé."""
    assert "/api/manuel/pdf" in manuel
    corps = corps_du_manuel(manuel)
    apres_aide = corps[corps.index('id="aide"'):]
    assert "/api/manuel/pdf" in apres_aide, (
        "le lien PDF n'est pas dans la section « Une question ? »"
    )
