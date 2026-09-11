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
    SyntheseIndisponible,
    consignes,
    construire_requete,
    extraire_objet,
    rendre_html,
)


# ── Le squelette ─────────────────────────────────────────────────────────────

def test_le_squelette_a_des_cles_uniques_et_non_vides():
    """Cas zéro : deux rubriques de même clé feraient perdre la première en silence."""
    cles = [r.cle for r in SQUELETTE]
    assert len(cles) >= 5, "Squelette suspicieusement court — le contrôle ne mesure plus rien."
    assert len(set(cles)) == len(cles), f"Clés en double dans SQUELETTE : {cles}"
    assert all(r.titre.strip() and r.consigne.strip() for r in SQUELETTE)


def test_la_consigne_est_DERIVEE_du_squelette():
    """Elle doit nommer chaque clé — sinon le modèle ne peut pas la rendre.

    C'est le contrôle qui empêche le squelette d'être recopié dans le prompt :
    ajouter une rubrique sans toucher à la consigne fait échouer ici.
    """
    texte = consignes()
    for r in SQUELETTE:
        assert f'"{r.cle}"' in texte, f"La rubrique « {r.cle} » n'est pas demandée au modèle."
    assert NON_PRECISE in texte, "La consigne de non-invention a disparu."


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
    html = rendre_html({SQUELETTE[0].cle: "Entretien des ascenseurs."})
    #  `escape` sur le titre AUSSI : « Durée, prise d'effet » sort en `d&#x27;effet`,
    #  et chercher la forme brute ferait échouer le contrôle sur un rendu correct.
    positions = [html.find(f"<h3>{escape(r.titre)}</h3>") for r in SQUELETTE]
    assert all(p != -1 for p in positions), "Une rubrique du squelette manque au rendu."
    assert positions == sorted(positions), "L'ordre rendu n'est pas celui du squelette."


def test_une_rubrique_absente_se_dit_au_lieu_de_s_inventer():
    html = rendre_html({})
    assert html.count(NON_PRECISE) == len(SQUELETTE)


def test_une_rubrique_inventee_par_le_modele_est_ignoree():
    html = rendre_html({"rubrique_qui_n_existe_pas": "<b>coucou</b>"})
    assert "coucou" not in html, (
        "Le squelette est tenu par CONSTRUCTION : une clé inconnue n'est pas rendue."
    )


def test_une_liste_accepte_aussi_un_texte_a_puces():
    """Le modèle se trompe régulièrement de forme ; perdre les dix autres
    rubriques pour cela serait disproportionné."""
    rubrique = next(r for r in SQUELETTE if r.liste)
    html = rendre_html({rubrique.cle: "- Visite annuelle\n- Pièces d'usure"})
    assert "<li>Visite annuelle</li>" in html
    assert "<li>Pièces d&#x27;usure</li>" in html or "<li>Pièces d'usure</li>" in html


# ── 🔴 Le contrôle central ───────────────────────────────────────────────────

def test_aucun_balisage_du_modele_n_atteint_le_rendu():
    """Ce qui vient du service est du TEXTE, et il le reste jusqu'au bout."""
    poison = '<script>alert(1)</script><img src=x onerror=alert(1)>'
    liste = next(r for r in SQUELETTE if r.liste)
    texte = next(r for r in SQUELETTE if not r.liste)
    html = rendre_html({texte.cle: poison, liste.cle: [poison]})

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


def test_le_rendu_n_emploie_que_des_balises_admises_par_sanitize():
    """Une balise hors liste blanche serait retirée à l'affichage, en silence.

    La liste est celle de `front/src/lib/sanitize.ts` — restreinte ici aux seules
    balises que ce rendu produit : le contrôle dirait autre chose s'il recopiait
    la liste entière.
    """
    html = rendre_html({r.cle: (["a", "b"] if r.liste else "x") for r in SQUELETTE})
    balises = set(re.findall(r"</?([a-z0-9]+)", html))
    assert balises <= {"h3", "p", "ul", "li", "em"}, f"Balises hors charte : {balises}"


def test_la_generation_n_ecrit_rien_en_base():
    """🔴 Le module ne doit contenir AUCUN point d'écriture.

    Contrôle statique, et c'est volontaire : vérifier le comportement
    demanderait de joindre le service. Ce que l'on peut prouver sans lui, c'est
    qu'il n'existe nulle part dans ce module de quoi enregistrer.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "utils" / "synthese_contrat.py").read_text(
        encoding="utf-8"
    )
    for ecriture in ("session.add(", "session.commit(", "session.delete("):
        assert ecriture not in source, (
            f"`{ecriture}` dans synthese_contrat.py : la génération PROPOSE, elle "
            "n'enregistre pas. Écrire dans `notes` écraserait sans filet une "
            "synthèse rédigée à la main."
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
