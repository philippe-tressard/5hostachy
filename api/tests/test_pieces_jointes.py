"""Garde-fous des pièces jointes : nommage sur disque, listes blanches, filtrage.

Trois classes d'erreurs sont verrouillées ici.

1. **L'extension du fichier stocké décide du `Content-Type`.** `/uploads/*` est
   servi en statique par Caddy, avec `X-Content-Type-Options: nosniff` : c'est
   donc l'extension posée sur disque, et elle seule, qui décide de ce que le
   navigateur exécute. La dériver du nom fourni par l'appelant permettrait de
   téléverser un `.html` sous un type MIME autorisé — donc du script sur notre
   propre origine, avec le cookie de session.

2. **Une liste blanche recopiée diverge.** Le sélecteur de fichiers du front
   (`front/src/lib/fichiers.ts`) et la validation serveur (`app/routers/uploads.py`)
   décrivent les mêmes formats. Quand ils divergent, l'utilisateur choisit un
   fichier que le serveur refuse — ou pire, le front interdit un format que le
   serveur accepte et personne ne s'en aperçoit.

3. **Une URL de pièce jointe fournie par le client peut pointer n'importe où.**
   `photos_internes` n'accepte que nos propres URLs ; un routeur qui l'oublie
   laisse servir un contenu tiers dans un `<img src>` à chaque lecteur.
"""
import ast
import pathlib
import re

import pytest

from app.routers.uploads import ALLOWED_DOC_MIME, ALLOWED_MIME, DOC_EXTENSIONS
from app.utils.fichiers import extension_assainie, nom_stocke, radical_assaini
from app.utils.photos import photos_internes

RACINE = pathlib.Path(__file__).resolve().parents[2]
FICHIERS_TS = RACINE / "front" / "src" / "lib" / "fichiers.ts"


# ── 1. Nommage sur disque ────────────────────────────────────────────────────

def test_extension_vient_du_parametre_pas_du_nom_fourni():
    """Un `.html` déguisé ne doit pas ressortir en `.html` sur le disque."""
    nom = nom_stocke("piege.html", ".pdf")
    assert nom.endswith(".pdf")
    assert ".html" not in nom


@pytest.mark.parametrize(
    "fourni",
    ["../../etc/passwd", "..\\..\\windows\\system32\\cmd", "/etc/shadow", "a/b/c.pdf"],
)
def test_aucune_traversee_de_chemin(fourni):
    nom = nom_stocke(fourni, ".pdf")
    assert "/" not in nom and "\\" not in nom
    assert ".." not in nom


def test_nom_origine_conserve_et_translittere():
    """Le nom doit rester lisible : c'est tout l'intérêt de le conserver."""
    nom = nom_stocke("Devis chauffage été.pdf", ".pdf")
    assert "Devis_chauffage_ete" in nom
    assert nom.endswith(".pdf")
    # Le préfixe technique est un UUID hexadécimal suivi d'un `_` : le front
    # s'appuie dessus pour réafficher le nom d'origine (`nomFichier`).
    assert re.match(r"^[0-9a-f]{32}_", nom)


def test_nom_absent_ou_vide_reste_exploitable():
    for fourni in (None, "", "   ", "???"):
        nom = nom_stocke(fourni, ".pdf")
        assert nom.endswith("_fichier.pdf"), fourni


def test_prefixe_unique_a_chaque_appel():
    """Deux fichiers de même nom ne doivent pas s'écraser l'un l'autre."""
    assert nom_stocke("rapport.pdf", ".pdf") != nom_stocke("rapport.pdf", ".pdf")


def test_extension_assainie_neutralise_les_caracteres_actifs():
    assert extension_assainie("x.PDF") == ".pdf"
    assert extension_assainie("x.p df") == ".pdf"
    assert extension_assainie("sans_extension") == ""


def test_radical_borne_la_longueur():
    assert len(radical_assaini("a" * 500)) <= 60


# ── 2. Listes blanches front ⇆ serveur ───────────────────────────────────────

def _constante_ts(nom: str) -> str:
    """Valeur d'une constante `export const NOM = '...'` de fichiers.ts."""
    source = FICHIERS_TS.read_text(encoding="utf-8")
    trouve = re.search(rf"export const {nom} = '([^']*)'", source)
    # Un contrôle qui ne trouve pas sa cible renvoie INCONNU, pas OK : sans
    # cette assertion, renommer la constante rendrait le test vert à vide.
    assert trouve, f"{nom} introuvable dans {FICHIERS_TS.name}"
    return trouve.group(1)


def test_liste_blanche_documents_alignee():
    """Chaque extension proposée par le front est acceptée par le serveur."""
    extensions_front = {
        e for e in _constante_ts("ACCEPT_DOCUMENTS").split(",") if e.startswith(".")
    }
    assert extensions_front, "aucune extension listée côté front"
    assert extensions_front == set(DOC_EXTENSIONS.values())

    types_front = {
        e for e in _constante_ts("ACCEPT_DOCUMENTS").split(",") if not e.startswith(".")
    }
    assert types_front <= ALLOWED_DOC_MIME


def test_liste_blanche_photos_alignee():
    types_front = set(_constante_ts("ACCEPT_PHOTOS").split(","))
    assert types_front == ALLOWED_MIME


def test_toute_image_acceptee_est_reconnue_comme_image_par_le_front():
    """Sinon un `.gif` téléversé s'affiche en pastille de document, sans vignette."""
    source = FICHIERS_TS.read_text(encoding="utf-8")
    trouve = re.search(r"EXTENSIONS_IMAGE = /(.+?)/i", source)
    assert trouve, "EXTENSIONS_IMAGE introuvable dans fichiers.ts"
    motif = re.compile(trouve.group(1).replace("\\.", r"\."), re.IGNORECASE)
    for mime in ALLOWED_MIME:
        extension = mime.split("/")[1]
        assert motif.search(f"photo.{extension}"), mime


# ── 3. Filtrage des URLs fournies par le client ──────────────────────────────

def test_photos_internes_ecarte_les_urls_externes():
    interne = "/uploads/fichiers/abc_devis.pdf"
    assert photos_internes([
        interne,
        "https://exemple.test/pixel.gif",
        "/uploads/../etc/passwd",
        "//evil.test/x.png",
    ]) == [interne]


#: Toute fonction qui écrit `fichiers_urls` depuis une entrée client. Ajouter une
#: rubrique sans l'inscrire ici est le scénario que ce test ne peut pas couvrir :
#: la liste est donc volontairement explicite, pour se relire.
ECRITURES_CLIENT = [
    ("api/app/routers/tickets.py", "create_ticket"),
    ("api/app/routers/tickets.py", "update_ticket"),
    ("api/app/routers/tickets.py", "add_message"),
    ("api/app/routers/tickets.py", "add_evolution"),
    ("api/app/routers/tickets.py", "update_evolution"),
    ("api/app/routers/publications.py", "add_evolution"),
    ("api/app/routers/publications.py", "update_evolution"),
    ("api/app/routers/calendrier.py", "create_evenement"),
    ("api/app/routers/calendrier.py", "update_evenement"),
]


#: Noms des variables qui contiennent des chemins RÉSOLUS (sortis de
#: `chemins_locaux`), donc réellement joignables à un e-mail.
_LISTES_RESOLUES = {"pieces_jointes", "photo_paths", "all_attachments", "attachments"}

_DRAPEAU_FICHIERS = re.compile(r'"fichiers":\s*bool\(([A-Za-z_][\w.]*)\)')


@pytest.mark.parametrize(
    "chemin",
    ["api/app/routers/tickets.py", "api/app/routers/publications.py",
     "api/app/routers/calendrier.py"],
)
def test_le_drapeau_fichiers_decrit_ce_qui_est_vraiment_joint(chemin):
    """« Pièces jointes disponibles ci-dessous » ne doit pas mentir.

    Les modèles `ticket_syndic`, `publication_syndic` et
    `calendrier_evenement_cree` affichent cette phrase derrière
    `{% if fichiers %}`. Deux points d'appel calculaient le drapeau sur
    l'INTENTION (`bool(body.fichiers_urls)`) au lieu de la liste réellement
    transmise : le commentaire de ticket envoyé au syndic annonçait des pièces
    jointes sans en attacher aucune, et l'actualité faisait l'inverse — elle les
    attachait sans les annoncer. Le drapeau se calcule sur la liste résolue,
    jamais sur la requête.
    """
    source = (RACINE / chemin).read_text(encoding="utf-8")
    references = _DRAPEAU_FICHIERS.findall(source)
    assert references, f"aucun drapeau `fichiers` trouvé dans {chemin}"
    for ref in references:
        assert ref in _LISTES_RESOLUES, (
            f'{chemin} : "fichiers" calculé sur `{ref}`, qui n\'est pas une liste '
            f"de chemins résolus ({sorted(_LISTES_RESOLUES)})"
        )


@pytest.mark.parametrize("chemin, fonction", ECRITURES_CLIENT)
def test_ecriture_de_pieces_jointes_passe_par_le_filtre(chemin, fonction):
    arbre = ast.parse((RACINE / chemin).read_text(encoding="utf-8"))
    noeuds = [
        n for n in ast.walk(arbre)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fonction
    ]
    # Fonction renommée ou supprimée → INCONNU, donc échec, jamais un vert vide.
    assert len(noeuds) == 1, f"{fonction} introuvable dans {chemin}"

    corps = ast.dump(noeuds[0])
    assert "fichiers_urls" in corps, f"{fonction} n'écrit plus de pièces jointes"
    assert "photos_internes" in corps, (
        f"{fonction} écrit fichiers_urls sans passer par photos_internes : "
        "une URL arbitraire fournie par le client serait servie à chaque lecteur"
    )
