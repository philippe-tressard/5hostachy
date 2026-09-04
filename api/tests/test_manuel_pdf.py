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
    titres_ancres,
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

    #  🔴 LES ATTRIBUTS SURVIVENT À LA CONVERSION — ajouté après un vrai défaut.
    #
    #  Le remplacement s'écrit avec une référence de groupe. Écrite via un
    #  heredoc, elle est devenue le caractère de contrôle U+0001 : la conversion
    #  produisait un `<div>` SANS SA CLASSE, avec un caractère invisible dedans.
    #  Les assertions ci-dessus passaient toutes — plus de `<details`, le texte
    #  présent — et le bloc se serait imprimé sans son habillage.
    #
    #  ⚠️ C'est l'étape « Aucun caractère de contrôle invisible » de la CI qui
    #  l'a vu, pas ce fichier. Il regarde maintenant ce qu'il aurait dû regarder
    #  dès le début : non pas que la balise a changé, mais que le RÉSULTAT est
    #  celui qu'on veut. Le caractère fautif n'est pas cité ici — l'écrire pour
    #  l'expliquer le réintroduirait, et la CI refuserait ce fichier à son tour.
    assert document.count('<div class="ecran-detail">') == 3, (
        "les blocs convertis ont perdu leurs attributs : ils s'imprimeraient "
        "sans leur habillage"
    )
    #  Les trois seuls caractères de contrôle voulus, désignés par leur code —
    #  les écrire en littéral dans ce fichier serait précisément le défaut.
    voulus = {9, 10, 13}
    assert not any(ord(c) < 32 and ord(c) not in voulus for c in document), (
        "un caractère de contrôle s'est glissé dans le document composé"
    )


# ── Le sommaire est CONSTRUIT, pas recopié ───────────────────────────────────

def test_le_sommaire_suit_les_titres_du_document(manuel, document):
    """Une table des matières recopiée est une table de plus.

    Ce manuel vient précisément de perdre toutes ses tables recopiées (#651) :
    en réintroduire une, tenue à la main, serait le comble.
    """
    corps, releve = titres_ancres(manuel)
    assert len(releve) >= 18, (
        f"seulement {len(releve)} entrées : le sommaire s'arrête au niveau 2 et "
        "ne permet plus de trouver un écran"
    )
    #  Les quinze écrans sont des `<h3>` : sans eux, on ne peut pas chercher
    #  « Accès & badges », c'est-à-dire ce pour quoi on ouvre un sommaire.
    assert sum(1 for niveau, _, _ in releve if niveau == 3) >= 16

    for _niveau, titre, ancre in releve:
        assert f'href="#{ancre}"' in document, f"« {titre} » manque au sommaire"
        assert f'id="{ancre}"' in corps, (
            f"l'ancre de « {titre} » n'est posée nulle part : le lien du "
            "sommaire pointerait dans le vide"
        )

    #  L'ordre du document, pas un ordre inventé.
    positions = [document.index(f'href="#{a}"') for _, _, a in releve]
    assert positions == sorted(positions)


def test_les_numeros_de_page_sont_RESOLUS_a_la_mise_en_page(document):
    """🔴 Jamais écrits — on ne sait pas encore combien de pages fera le document.

    `target-counter()` les résout au moment de la pagination. Un numéro saisi
    serait faux dès la première phrase ajoutée au manuel, et faux en silence :
    rien ne signale un sommaire qui renvoie à la mauvaise page.
    """
    assert "target-counter(attr(href), page)" in document


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


def test_les_mentions_identifient_l_editeur(document):
    """Ce qu'un document distribuable doit porter.

    ⚠️ L'avertissement de péremption a été RETIRÉ le 03/09/2026, à la demande —
    et ce test l'exigeait. Il ne le réclame donc plus : un contrôle qui survit à
    la décision qu'il gardait devient un obstacle, pas un garde-fou.

    Ce qui reste exigé n'a pas bougé : le document dit qui l'édite, et ne nomme
    aucune personne physique. La licence et le renvoi aux mentions légales
    vivent dans le corps du manuel (section « À quoi sert ce site ? »), donc
    dans le PDF par construction.
    """
    assert 'class="mentions"' in document
    assert "conseil syndical de la copropriété" in document, (
        "les mentions ne nomment aucun éditeur"
    )
    assert "Philippe Tressard" not in document, (
        "un nom de personne réapparaît dans un document distribuable"
    )
    #  La licence est annoncée par le manuel lui-même : le PDF la reprend.
    assert "licence MIT" in document
    assert "auto-hébergée" in document


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


def test_le_PDF_est_atteignable_depuis_TROIS_endroits(manuel):
    """🔴 Un document qu'on ne trouve pas n'existe pas.

    Signalé à l'écran le 03/09/2026 : *« je ne vois pas où générer le pdf du
    manuel »*. Le lien existait — au BAS du manuel, une page qu'on ouvre déjà
    rarement. Il est désormais posé là où l'œil arrive.

    ⚠️ Ce test regarde les fichiers plutôt que le rendu : il ne prouve pas qu'un
    lecteur verra les liens, seulement qu'ils n'ont pas disparu d'un des trois
    endroits. C'est ce qu'un test peut tenir ; le reste se constate à l'écran.
    """
    front = _MANUEL.resolve().parents[1] / "front" / "src"

    #  ⚠️ On découpe sur le BALISAGE, pas sur un nom de classe : la première
    #  occurrence de « quick-start » est dans la feuille de style, bien avant le
    #  bandeau. Le premier découpage s'y est fait prendre, et le test accusait un
    #  lien pourtant présent.
    debut_hero = manuel.index('<section class="hero"')
    hero = manuel[debut_hero : manuel.index("</section>", debut_hero)]

    endroits = {
        "en haut du manuel (bandeau d'accueil)": hero,
        "en bas du manuel (Une question ?)": manuel[manuel.index('id="aide"') :],
        #  Les deux entrées de guide ont été extraites de `Nav.svelte` le
        #  03/09/2026 : elles y étaient écrites DEUX fois, menu latéral et menu
        #  mobile. Le lien vit donc dans le composant, pas dans la page.
        "menu du site": (front / "lib" / "components" / "LiensGuide.svelte").read_text(
            encoding="utf-8"
        ),
        "FAQ": (front / "routes" / "(app)" / "faq" / "+page.svelte").read_text(
            encoding="utf-8"
        ),
    }
    manquants = [ou for ou, texte in endroits.items() if "/api/manuel/pdf" not in texte]
    assert not manquants, "le lien vers le PDF a disparu de : " + ", ".join(manquants)


# ── Le cache : servir vite, sans jamais servir périmé ────────────────────────

def test_le_cache_sert_le_MEME_pdf_et_ne_recompose_pas(manuel, monkeypatch):
    """🔴 Signalé à l'écran : *« plus de 10 secondes avec une page vide »*.

    WeasyPrint recomposait tout le document à chaque clic. Le résultat ne dépend
    pourtant que du manuel, du site et de la date — aucun ne change entre deux
    clics.
    """
    from app.utils import manuel_pdf as m

    m._CACHE.clear()
    appels = []
    monkeypatch.setattr(m, "html_to_pdf", lambda doc: appels.append(doc) or b"%PDF-x")

    a = m.generer_manuel_pdf("5Hostachy", "https://x.fr", html_manuel=manuel,
                             edite_le=date(2026, 9, 4))
    b = m.generer_manuel_pdf("5Hostachy", "https://x.fr", html_manuel=manuel,
                             edite_le=date(2026, 9, 4))
    assert a == b
    assert len(appels) == 1, "le document a été recomposé alors qu'il n'a pas changé"


def test_un_manuel_MODIFIE_produit_un_pdf_neuf(manuel, monkeypatch):
    """⚠️ La clé est l'EMPREINTE du manuel, jamais sa version.

    Une retouche livrée sans bump de version doit produire un PDF neuf. Se fier
    au numéro aurait servi un document périmé sans que rien ne le signale — le
    défaut qu'on corrige partout ailleurs dans ce dépôt.
    """
    from app.utils import manuel_pdf as m

    m._CACHE.clear()
    appels = []
    monkeypatch.setattr(m, "html_to_pdf", lambda doc: appels.append(doc) or b"%PDF-x")

    m.generer_manuel_pdf("5Hostachy", "https://x.fr", html_manuel=manuel,
                         edite_le=date(2026, 9, 4))
    m.generer_manuel_pdf("5Hostachy", "https://x.fr",
                         html_manuel=manuel + "<!-- retouche -->",
                         edite_le=date(2026, 9, 4))
    assert len(appels) == 2, "un manuel modifié a servi le PDF de l'ancien"


def test_le_cache_est_BORNE(manuel, monkeypatch):
    """Une boucle anormale ne doit pas gonfler la mémoire d'un conteneur.

    La date change à minuit : deux entrées suffisent en régime normal. La borne
    existe pour l'anormal, pas pour le nominal.
    """
    from app.utils import manuel_pdf as m

    m._CACHE.clear()
    monkeypatch.setattr(m, "html_to_pdf", lambda doc: b"%PDF-x")
    for jour in range(1, 12):
        m.generer_manuel_pdf("5Hostachy", "https://x.fr", html_manuel=manuel,
                             edite_le=date(2026, 9, jour))
    assert len(m._CACHE) <= m._CACHE_MAX
