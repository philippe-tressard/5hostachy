"""La synthèse assistée d'un contrat : le squelette tient, et rien n'est écrit.

## Ce que ce fichier protège

La génération appelle un service externe payant. **Aucun test ne l'appelle** :
ce qui se teste ici est ce qui porte les décisions — la charge utile composée,
la lecture de la réponse, le rendu HTML, les refus — et le tuyau se branche.
Même coupure que `composer_html` / `html_to_pdf` pour le manuel.

Un test qui joindrait le vrai service coûterait de l'argent à chaque PR et
échouerait sur une coupure réseau, c'est-à-dire pour une raison qui n'a rien à
voir avec le code qu'il prétend vérifier.

## Les trois défauts qu'il rend impossibles

1. **Du balisage écrit par le modèle atteint la page.** Le champ `notes` est
   rendu par `{@html safeHtml(...)}` : le jour où le rendu cesserait
   d'échapper, un `<script>` renvoyé par le service arriverait jusqu'à un
   `{@html}`. DOMPurify le nettoierait — et ce serait quand même la mauvaise
   frontière.
2. **Le squelette dérive.** La consigne, le schéma de lecture et le plan du HTML
   sont trois usages du MÊME `SQUELETTE` ; les laisser se recopier rouvrirait la
   divergence que ce dépôt a déjà payée quatre fois.
3. **La génération écrit dans la base.** Elle ne doit rendre qu'une proposition :
   écraser une synthèse rédigée à la main serait irrattrapable, l'archivage
   n'existant pas sur ce champ.
"""
from __future__ import annotations

import json
import re
from html import escape

import pytest

from app.utils.synthese_contrat import (
    MIME_ACCEPTE,
    NON_PRECISE,
    SQUELETTE,
    SUFFIXE_CITATION,
    SyntheseIndisponible,
    consignes,
    construire_requete,
    extraire_objet,
    rendre_html,
)

#: Les sept titres donnés par le conseil syndical le 11/09/2026, avec une
#: synthèse déjà rédigée à la main et la consigne « respecte uniquement les
#: titres ». Recopiés ici EXPRÈS : c'est la seule façon qu'un contrôle ait de
#: dire qu'ils ont changé. Ailleurs, une liste recopiée est un défaut ; dans un
#: test, c'est l'attendu — et la divergence est précisément ce qu'on cherche.
TITRES_ATTENDUS = [
    "Identification du fournisseur",
    "Dates clés / Validité",
    "Objet du contrat",
    "Prestations incluses",
    "Prestations non incluses",
    "Conditions financières",
    "Points d'attention pour la copropriété",
]


def _une(forme: str):
    return next(r for r in SQUELETTE if r.forme == forme)


# ── Le squelette ─────────────────────────────────────────────────────────────

def test_le_squelette_a_des_cles_uniques_et_non_vides():
    """Cas zéro : deux rubriques de même clé feraient perdre la première en silence."""
    cles = [r.cle for r in SQUELETTE]
    assert len(cles) >= 5, "Squelette suspicieusement court — le contrôle ne mesure plus rien."
    assert len(set(cles)) == len(cles), f"Clés en double dans SQUELETTE : {cles}"
    assert all(r.titre.strip() and r.consigne.strip() for r in SQUELETTE)


def test_les_sept_titres_sont_ceux_du_conseil_syndical():
    """🔴 Ils ne se réécrivent pas « pour faire mieux ».

    Ce sont les intitulés sous lesquels la copropriété lit ses contrats depuis
    avant ce produit. Les changer est une décision qui se prend avec elle — pas
    un raffinement qu'on s'autorise en passant.
    """
    assert [r.titre for r in SQUELETTE] == TITRES_ATTENDUS


def test_la_consigne_est_DERIVEE_du_squelette():
    """Elle doit nommer chaque clé — sinon le modèle ne peut pas la rendre.

    C'est le contrôle qui empêche le squelette d'être recopié dans le prompt :
    ajouter une rubrique sans toucher à la consigne fait échouer ici.
    """
    texte = consignes()
    for r in SQUELETTE:
        assert f'"{r.cle}"' in texte, f"La rubrique « {r.cle} » n'est pas demandée au modèle."
    assert NON_PRECISE in texte, "La consigne de non-invention a disparu."
    for r in SQUELETTE:
        assert f'"{r.cle}{SUFFIXE_CITATION}"' in texte, (
            f"L'extrait qui fonde « {r.cle} » n'est pas demandé."
        )
    for r in SQUELETTE:
        if r.forme == "champs":
            for libelle in r.champs:
                assert f'"{libelle}"' in texte, (
                    f"Le libellé « {libelle} » n'est pas demandé au modèle."
                )


# ── La charge utile ──────────────────────────────────────────────────────────

def test_la_requete_porte_les_documents_puis_la_consigne():
    charge = construire_requete([("contrat.pdf", b"%PDF-1.4 ...")], "un-modele")
    assert charge["model"] == "un-modele"
    contenu = charge["input"][0]["content"]
    assert [c["type"] for c in contenu] == ["input_file", "input_text"], (
        "Les documents passent AVANT la consigne : elle s'y réfère."
    )
    assert contenu[0]["filename"] == "contrat.pdf"
    assert contenu[0]["file_data"].startswith(f"data:{MIME_ACCEPTE};base64,")


def test_la_requete_conserve_l_ordre_des_documents():
    charge = construire_requete([("a.pdf", b"a"), ("b.pdf", b"b")], "m")
    noms = [c["filename"] for c in charge["input"][0]["content"] if c["type"] == "input_file"]
    assert noms == ["a.pdf", "b.pdf"]


# ── La lecture de la réponse ─────────────────────────────────────────────────

@pytest.mark.parametrize(
    "brut",
    [
        '{"objet": "Entretien"}',
        '```json\n{"objet": "Entretien"}\n```',
        '```\n{"objet": "Entretien"}\n```',
        'Voici la synthèse :\n{"objet": "Entretien"}\nBonne lecture.',
    ],
)
def test_l_objet_se_lit_meme_entoure_de_bavardage(brut):
    """La consigne demande du JSON nu — ce n'est pas une garantie.

    Échouer sur une clôture ``` donnerait une erreur incompréhensible pour un
    défaut purement cosmétique.
    """
    assert extraire_objet(brut) == {"objet": "Entretien"}


@pytest.mark.parametrize("brut", ["", "désolé, je ne peux pas", "[1, 2, 3]"])
def test_une_reponse_sans_objet_leve_un_message_lisible(brut):
    with pytest.raises(SyntheseIndisponible) as e:
        extraire_objet(brut)
    assert "Erreur" not in str(e.value), "Le message doit être une phrase, pas un code."


# ── Le rendu ─────────────────────────────────────────────────────────────────

def test_le_rendu_suit_l_ordre_du_squelette_et_le_complete():
    """Toutes les rubriques sont rendues, y compris celles que le modèle a omises."""
    html = rendre_html({SQUELETTE[2].cle: ["Entretien des ascenseurs."]})
    #  `escape` sur le titre AUSSI : « Dates clés / Validité » n'a rien à échapper
    #  mais « Points d'attention » sort en `d&#x27;attention` — chercher la forme
    #  brute ferait échouer le contrôle sur un rendu correct.
    #
    #  🔴 Le NUMÉRO vient de la position, pas du libellé : c'est ce que vérifie
    #  `enumerate` ici. Un numéro écrit dans le titre survivrait à un
    #  réordonnancement, et deux sections finiraient par porter le même.
    positions = [
        html.find(f"<h3>{rang}. {escape(r.titre)}</h3>")
        for rang, r in enumerate(SQUELETTE, start=1)
    ]
    assert all(p != -1 for p in positions), "Une rubrique du squelette manque au rendu."
    assert positions == sorted(positions), "L'ordre rendu n'est pas celui du squelette."


def test_une_rubrique_absente_se_dit_au_lieu_de_s_inventer():
    """Une réponse vide rend le squelette ENTIER, chaque case dite non précisée.

    Le compte attendu se dérive du squelette : une ligne par section de texte ou
    de liste, une par libellé attendu dans les sections à champs.
    """
    html = rendre_html({})
    attendu = sum(len(r.champs) if r.forme == "champs" else 1 for r in SQUELETTE)
    assert html.count(NON_PRECISE) == attendu


def test_une_rubrique_inventee_par_le_modele_est_ignoree():
    html = rendre_html({"rubrique_qui_n_existe_pas": ["<b>coucou</b>"]})
    assert "coucou" not in html, (
        "Le squelette est tenu par CONSTRUCTION : une clé inconnue n'est pas rendue."
    )


def test_une_liste_accepte_aussi_un_texte_a_puces():
    """Le modèle se trompe régulièrement de forme ; perdre les six autres
    sections pour cela serait disproportionné."""
    rubrique = _une("liste")
    html = rendre_html({rubrique.cle: "- Visite annuelle\n- Pièces d'usure"})
    assert "<li>Visite annuelle</li>" in html
    assert "<li>Pièces d&#x27;usure</li>" in html or "<li>Pièces d'usure</li>" in html


# ── 🔴 Le contrôle central ───────────────────────────────────────────────────

def test_aucun_balisage_du_modele_n_atteint_le_rendu():
    """Ce qui vient du service est du TEXTE, et il le reste jusqu'au bout."""
    poison = '<script>alert(1)</script><img src=x onerror=alert(1)>'
    liste, champs = _une("liste"), _une("champs")
    html = rendre_html(
        {
            liste.cle: [poison],
            champs.cle: {champs.champs[0]: poison},
            f"{liste.cle}{SUFFIXE_CITATION}": poison,
        }
    )

    assert "<script" not in html and "<img" not in html, (
        "Une balise du modèle a traversé le rendu."
    )
    assert "&lt;script&gt;" in html, "Le texte doit être échappé, pas supprimé."

    #  🔴 L'invariant qui vaut vraiment : le rendu ne produit AUCUN attribut.
    #  Chercher « onerror » dans la page était trop naïf — le mot survit, échappé,
    #  au milieu d'un texte devenu inerte (`&lt;img src=x onerror=…&gt;`), et le
    #  contrôle refusait alors un rendu correct. Ce qui rend un attribut
    #  dangereux n'est pas son nom, c'est d'être DANS une balise.
    assert not re.search(r"<[a-z0-9]+\s[^>]*>", html), (
        "Le rendu ne pose aucun attribut : en trouver un signifie qu'une balise "
        "vient d'ailleurs que de `rendre_html`."
    )


def _balises_admises() -> set[str]:
    """La liste blanche de DOMPurify, LUE dans `front/src/lib/sanitize.ts`.

    🔴 Recopiée, elle divergerait au premier ajout — et ce dépôt connaît le prix
    de cette recopie : c'est exactement pour cela que `lint:html` lit la liste
    des assainisseurs dans `sanitize.ts` plutôt que de la retaper. Le contrôle
    est donc adossé à la vérité, pas à son écho.
    """
    from pathlib import Path

    fichier = Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "sanitize.ts"
    if not fichier.exists():
        pytest.skip("`sanitize.ts` introuvable — contrôle non mesuré, pas réussi.")
    source = fichier.read_text(encoding="utf-8")
    bloc = source[source.index("const ALLOWED_TAGS = [") :]
    bloc = bloc[: bloc.index("]")]
    admises = set(re.findall(r"'([a-z0-9]+)'", bloc))
    assert admises, "Cas zéro : ALLOWED_TAGS a changé de forme — contrôle inopérant."
    return admises


def test_le_rendu_n_emploie_que_des_balises_admises_par_sanitize():
    """Une balise hors liste blanche serait retirée à l'affichage, EN SILENCE.

    ⚠️ C'est la famille de défauts la plus coûteuse ici : le rendu paraît correct
    au serveur, le test passe, et la page affiche autre chose. Le contrôle compare
    donc ce que `rendre_html` produit à ce que le navigateur laissera passer.
    """
    html = rendre_html(
        {
            r.cle: (
                {c: "x" for c in r.champs}
                if r.forme == "champs"
                else (["a", "b"] if r.forme == "liste" else "x")
            )
            for r in SQUELETTE
        }
        | {f"{r.cle}{SUFFIXE_CITATION}": "extrait" for r in SQUELETTE}
    )
    employees = set(re.findall(r"</?([a-z0-9]+)", html))
    hors_charte = employees - _balises_admises()
    assert not hors_charte, (
        f"Balises que `sanitize.ts` retirerait à l'affichage : {sorted(hors_charte)}"
    )


# ── La forme « champs » : les libellés aussi sont tenus ──────────────────────

def test_les_libelles_d_une_section_a_champs_sont_ceux_du_squelette():
    """Un libellé omis ressort « non précisé », un libellé inventé est ignoré.

    Même garantie que pour les sections, un cran plus bas : c'est ce qui fait que
    « SIRET » figure toujours sur la fiche, même quand le contrat n'en porte pas.
    """
    r = _une("champs")
    html = rendre_html({r.cle: {r.champs[0]: "une valeur", "Libellé inventé": "à jeter"}})

    for libelle in r.champs:
        assert f"<strong>{escape(libelle)}</strong>" in html, f"« {libelle} » manque."
    assert "Libellé inventé" not in html and "à jeter" not in html
    assert html.count(NON_PRECISE) >= len(r.champs) - 1


def test_une_section_a_champs_rendue_en_texte_par_le_modele_ne_casse_rien():
    """Le modèle se trompe de forme ; la section ressort vide, pas en erreur."""
    r = _une("champs")
    html = rendre_html({r.cle: "SARL ROSARIO, 78360 Montesson"})
    assert f"<h3>1. {escape(SQUELETTE[0].titre)}</h3>" in html
    assert html.count(NON_PRECISE) >= len(r.champs)


# ── La citation : ce qui permet de vérifier sans rouvrir le PDF ──────────────

def test_la_citation_est_rendue_en_exergue_avec_ses_guillemets():
    r = SQUELETTE[0]
    html = rendre_html({f"{r.cle}{SUFFIXE_CITATION}": "SARL ROSARIO… Siret 480 297 621 00017"})
    assert "<blockquote>" in html
    assert "SARL ROSARIO… Siret 480 297 621 00017" in html
    assert "«" in html and "»" in html


@pytest.mark.parametrize("brut", ["", "   ", NON_PRECISE, '"«  »"', None, 42])
def test_une_citation_vide_ne_rend_pas_de_bloc(brut):
    """Une section que rien ne fonde n'a pas d'exergue — pas un exergue vide."""
    r = SQUELETTE[0]
    assert "<blockquote>" not in rendre_html({f"{r.cle}{SUFFIXE_CITATION}": brut})


def test_les_guillemets_ne_sont_pas_doubles():
    """Ils sont posés par le rendu ; ceux que le modèle ajoute sont retirés.

    Sans cela, la moitié des sections en porterait deux paires et l'autre aucune —
    selon l'humeur du modèle, ce qui n'est pas une mise en forme.
    """
    r = SQUELETTE[0]
    html = rendre_html({f"{r.cle}{SUFFIXE_CITATION}": '« un extrait »'})
    assert html.count("«") == 1 and html.count("»") == 1


def test_la_generation_n_ecrit_rien_en_base():
    """🔴 Le module ne doit contenir AUCUN point d'écriture.

    Contrôle statique, et c'est volontaire : vérifier le comportement
    demanderait de joindre le service. Ce que l'on peut prouver sans lui, c'est
    qu'il n'existe nulle part dans ce module de quoi enregistrer.
    """
    from pathlib import Path

    #  ⚠️ Les DEUX modules, depuis la coupe du 11/09/2026 : n'en lire qu'un
    #  laisserait l'écriture s'installer dans l'autre — c'est exactement la
    #  famille « le contrôle existe et ne mesure plus ce qu'il croit ».
    utils = Path(__file__).resolve().parents[1] / "app" / "utils"
    modules = ["synthese_contrat.py", "synthese_contrat_squelette.py"]
    for nom in modules:
        fichier = utils / nom
        assert fichier.exists(), f"Cas zéro : {nom} a disparu — contrôle inopérant."
        source = fichier.read_text(encoding="utf-8")
        for ecriture in ("session.add(", "session.commit(", "session.delete("):
            assert ecriture not in source, (
                f"`{ecriture}` dans {nom} : la génération PROPOSE, elle n'enregistre "
                "pas. Écrire dans `notes` écraserait sans filet une synthèse "
                "rédigée à la main."
            )


def test_la_cle_d_api_n_est_lue_qu_a_l_appel():
    """Importer le module sur une installation sans clé ne doit rien lever."""
    import importlib

    module = importlib.import_module("app.utils.synthese_contrat")
    importlib.reload(module)
    assert module.synthese_active() in (True, False)


# ── Ce que l'endpoint promet ─────────────────────────────────────────────────

def test_l_endpoint_est_reserve_au_conseil_syndical():
    """Le contrat et ses documents ne sont pas publics ; l'appel coûte de l'argent."""
    from app.routers import contrats_synthese

    for route in contrats_synthese.router.routes:
        dependances = json.dumps(str(route.dependant.dependencies))
        assert "require_cs_or_admin" in dependances, (
            f"{route.path} n'exige pas le rôle CS ou admin."
        )
