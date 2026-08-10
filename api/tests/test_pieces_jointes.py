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
import json
import pathlib
import re

import pytest

from app.routers.uploads import ALLOWED_DOC_MIME, ALLOWED_MIME, DOC_EXTENSIONS
from app.utils.fichiers import extension_assainie, nom_stocke, radical_assaini
from app.utils.photos import photos_internes, photos_json

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
    # `tickets.py` est devenu le paquet `tickets/` le 08/08/2026 : les chemins
    # suivent le découpage, pas l'inverse. Le test échouait bruyamment (fichier
    # introuvable), ce qui est la bonne façon de perdre sa cible.
    ("api/app/routers/tickets/crud.py", "create_ticket"),
    # `update_ticket` délègue l'écriture à `_appliquer_contenu` depuis le
    # découpage : c'est cette fonction qui filtre, et donc elle qu'il faut viser.
    # Le test a échoué bruyamment au découpage, ce qui est le comportement voulu.
    ("api/app/routers/tickets/crud.py", "_appliquer_contenu"),
    ("api/app/routers/tickets/messages.py", "add_message"),
    ("api/app/routers/tickets/evolutions.py", "add_evolution"),
    ("api/app/routers/tickets/evolutions.py", "update_evolution"),
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
    ["api/app/routers/tickets/courriels.py", "api/app/routers/publications.py",
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
    #  Deux portes d'entrée légitimes, et deux seulement : `photos_internes`
    #  directement, ou `photos_json` qui l'enveloppe (filtre + sérialisation, pour
    #  ne pas réécrire le même `json.dumps(photos_internes(...))` à cinq endroits).
    #  L'indirection ne serait un trou que si `photos_json` cessait de filtrer :
    #  c'est ce que verrouille `test_photos_json_ecarte_les_urls_etrangeres`.
    assert "photos_internes" in corps or "photos_json" in corps, (
        f"{fonction} écrit fichiers_urls sans passer par photos_internes/photos_json : "
        "une URL arbitraire fournie par le client serait servie à chaque lecteur"
    )


def test_photos_json_ecarte_les_urls_etrangeres():
    """Le helper qui sérialise doit filtrer — sinon l'indirection ci-dessus ment.

    Vérifié sur le COMPORTEMENT : ce qui ressort de la fonction, pas le fait
    qu'elle mentionne `photos_internes` quelque part.
    """
    sortie = photos_json([
        "/uploads/publications/ok.jpg",
        "https://tiers.example/pixel.png",   # traceur : révélerait l'IP de chaque lecteur
        "/uploads/../../etc/passwd",          # traversée
        "javascript:alert(1)",
    ])
    assert json.loads(sortie) == ["/uploads/publications/ok.jpg"]


def test_photos_json_tolere_l_absence():
    """Cas zéro : ni None ni liste vide ne doivent lever — le pire cas est `[]`."""
    assert json.loads(photos_json(None)) == []
    assert json.loads(photos_json([])) == []


# ── 4. Nom des pièces jointes dans l'e-mail ──────────────────────────────────

def test_nom_lisible_retire_le_prefixe_technique():
    """Le destinataire doit lire « devis.pdf », pas « 0d41107a6c…lasseurs.pdf ».

    Constaté le 03/08/2026 sur un e-mail réel : le client de messagerie tronque
    par le milieu, donc c'est précisément la partie porteuse de sens qui
    disparaît.
    """
    from app.utils.fichiers import nom_lisible

    uuid = "0d41107a6c9b4e2f8a1d3c5e7b9f0a2c"
    assert nom_lisible(f"/app/uploads/fichiers/{uuid}_ramonage.pdf") == "ramonage.pdf"
    # Fichiers antérieurs au nommage : aucun nom d'origine à restituer.
    assert nom_lisible(f"/app/uploads/tickets/{uuid}.jpg") == f"{uuid}.jpg"
    assert nom_lisible("") == ""


def test_la_regle_du_nom_est_la_meme_cote_front():
    """`nom_lisible` (Python) et `nomFichier` (TypeScript) sont la même règle.

    Deux langages, un seul comportement attendu : si les motifs divergent, le nom
    affiché dans l'application et celui de la pièce jointe de l'e-mail cessent de
    correspondre, sans que rien ne le signale.
    """
    source_ts = FICHIERS_TS.read_text(encoding="utf-8")
    trouve = re.search(r"PREFIXE_UUID = /(.+?)/i", source_ts)
    assert trouve, "PREFIXE_UUID introuvable dans fichiers.ts"

    py = (RACINE / "api" / "app" / "utils" / "fichiers.py").read_text(encoding="utf-8")
    motif_py = re.search(r'_PREFIXE_UUID = re\.compile\(r"(.+?)"', py)
    assert motif_py, "_PREFIXE_UUID introuvable dans fichiers.py"

    assert trouve.group(1) == motif_py.group(1), (
        f"Motifs divergents — TS: {trouve.group(1)} / Python: {motif_py.group(1)}"
    )


def test_la_piece_jointe_part_avec_son_nom_dorigine(tmp_path):
    """Comportement, pas intention : on inspecte le MIME réellement produit."""
    import asyncio

    from fastapi_mail import MessageSchema
    from fastapi_mail.msg import MailMsg

    from app.utils.email import _preparer_pieces_jointes

    fichier = tmp_path / "0d41107a6c9b4e2f8a1d3c5e7b9f0a2c_devis-ramonage.pdf"
    fichier.write_bytes(b"%PDF-1.4 test")

    prets, temporaires = _preparer_pieces_jointes([str(fichier)])
    assert temporaires == [], "aucune image : rien à nettoyer"

    msg = MessageSchema(subject="s", recipients=["a@b.fr"], body="<p>x</p>",
                        subtype="html", attachments=prets)
    brut = asyncio.run(MailMsg(msg)._message("5Hostachy <no-reply@x.fr>")).as_string()

    assert 'filename="devis-ramonage.pdf"' in brut
    assert "0d41107a6c9b4e2f8a1d3c5e7b9f0a2c" not in brut, (
        "le préfixe technique ne doit plus apparaître dans le message"
    )


# ── 5. Sommaire des pièces jointes dans le corps du message ──────────────────

def test_le_sommaire_annonce_exactement_les_pieces_jointes():
    """Décompte, accord au pluriel, numérotation et noms — sur une liste réelle."""
    from app.utils.email import _bandeau_pieces_jointes

    assert _bandeau_pieces_jointes([]) == "", "aucune pièce jointe : aucun bandeau"

    #  Le libellé annonce la NATURE depuis le 07/08/2026 : « 1 document » plutôt
    #  que « 1 pièce jointe », parce que le décompte seul oblige le destinataire à
    #  ouvrir pour savoir de quoi il s'agit.
    seule = _bandeau_pieces_jointes(["devis.pdf"])
    assert "1 document" in seule and "documents" not in seule

    trois = _bandeau_pieces_jointes(["devis.pdf", "plan.jpg", "constat.docx"])
    assert "1 photo et 2 documents" in trois
    for i, nom in enumerate(["devis.pdf", "plan.jpg", "constat.docx"], start=1):
        assert nom in trois, nom
        assert f">{i}.<" in trois, f"numérotation {i} absente"


def test_le_sommaire_echappe_les_noms():
    """Un nom de fichier est une donnée : il ne doit pas injecter de balise.

    Les noms produits depuis le 03/08/2026 sont assainis, mais les fichiers
    antérieurs ne l'ont pas été — on ne fait pas confiance à la provenance.
    """
    from app.utils.email import _bandeau_pieces_jointes

    bandeau = _bandeau_pieces_jointes(['<img src=x onerror=alert(1)>.pdf'])
    assert "<img src=x" not in bandeau
    assert "&lt;img src=x" in bandeau


def test_le_sommaire_vient_du_meme_endroit_que_les_pieces_jointes():
    """Le sommaire ne peut pas mentir : il est construit sur `attachments`.

    Le drapeau `fichiers` des modèles, lui, était calculé séparément — et deux
    points d'appel se sont trompés (annoncer sans joindre, joindre sans annoncer).
    Ici la source est unique : `send_email` et `send_email_group` dérivent le
    sommaire de la liste qu'ils transmettent au message.
    """
    source = (RACINE / "api" / "app" / "utils" / "email.py").read_text(encoding="utf-8")
    appels = re.findall(r"pieces_jointes=\[nom_lisible\(p\) for p in \(attachments or \[\]\)\]", source)
    assert len(appels) == 2, (
        f"{len(appels)} point(s) d'envoi dérivent le sommaire de `attachments` — "
        "il en faut 2 (send_email et send_email_group)"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Nommage des fichiers téléversés — une seule source, tenue par un contrôle
# ─────────────────────────────────────────────────────────────────────────────

def test_aucun_nom_de_fichier_fabrique_hors_de_nom_stocke():
    """`app/utils/fichiers.py` annonce « écrit une seule fois ». Il faut le vérifier.

    POURQUOI (07/08/2026, signalé par l'utilisateur sur un e-mail réel) : la règle
    était écrite, elle n'était pas tenue. `_save_image()` fabriquait son nom à la
    main — `f"{uuid.uuid4().hex}.jpg"`, sans radical — pendant que tout le reste
    passait par `nom_stocke()`. Conséquence visible : dans le même e-mail, un PDF
    s'affichait « Devis-toiture.pdf » et une photo
    « fb6cb1df94734926bfcd9b7f07e99ded.jpg ».

    Le nom d'origine n'était pas tronqué à l'affichage — il était **détruit au
    téléversement**, donc irrécupérable pour toutes les photos déjà en base.
    C'est ce qui rend la duplication coûteuse ici : elle ne se rattrape pas.

    Un commentaire ne suffisait pas ; ce test échoue si la seconde implémentation
    revient.
    """
    import pathlib
    import re

    racine = pathlib.Path(__file__).resolve().parents[1] / "app"
    #  Un nom de fichier bâti à partir d'un UUID et d'une extension, hors du module
    #  qui a le droit de le faire.
    motif = re.compile(r"""uuid4\(\)\.hex\}?["']?\s*\+?\s*["']?\.[a-z0-9]{2,5}""", re.IGNORECASE)
    #  Fichiers GÉNÉRÉS, pas téléversés : il n'existe aucun nom d'origine à
    #  conserver, donc `nom_stocke` n'aurait rien à quoi s'appliquer. Vérifié dans
    #  les deux sens plus bas — une exception qui n'a plus lieu d'être fait échouer
    #  le test, sinon la liste grossit jusqu'à tout couvrir.
    generes = {"routers/annonces_hall.py"}  # affiche de hall produite par WeasyPrint

    fautifs, vus = [], set()
    for f in sorted(racine.rglob("*.py")):
        if f.name == "fichiers.py" and f.parent.name == "utils":
            continue  # la source unique, seule autorisée
        rel = f.relative_to(racine).as_posix()
        for num, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if ligne.lstrip().startswith("#"):
                continue
            if motif.search(ligne):
                if rel in generes:
                    vus.add(rel)
                    continue
                fautifs.append(f"  {f.relative_to(racine.parent)}:{num}: {ligne.strip()}")

    obsoletes = sorted(generes - vus)
    assert not obsoletes, (
        "Exception(s) devenue(s) inutile(s) dans `generes` — à retirer : " + ", ".join(obsoletes)
    )
    assert not fautifs, (
        "Nom de fichier téléversé fabriqué hors de `nom_stocke()` — le nom d'origine "
        "sera perdu, et perdu définitivement :\n" + "\n".join(fautifs)
    )


def test_libelle_annonce_la_nature_des_pieces_jointes():
    """Le sommaire dit « 1 photo », pas « 1 pièce jointe », quand il peut le dire."""
    from app.utils.fichiers import est_image, libelle_pieces_jointes

    assert est_image("abc_vue.JPG") and est_image("x.png") and est_image("y.webp")
    assert not est_image("devis.pdf") and not est_image("") and not est_image("sans-extension")

    assert libelle_pieces_jointes(["a_vue.jpg"]) == "1 photo"
    assert libelle_pieces_jointes(["a.jpg", "b.png"]) == "2 photos"
    assert libelle_pieces_jointes(["a.pdf"]) == "1 document"
    assert libelle_pieces_jointes(["a.jpg", "b.pdf", "c.docx"]) == "1 photo et 2 documents"
    #  Cas ZÉRO : aucune pièce → chaîne vide, et c'est l'appelant qui décide du
    #  repli. Rendre « 0 pièce jointe » afficherait un bandeau pour rien.
    assert libelle_pieces_jointes([]) == ""


def test_est_image_et_estImage_sont_la_meme_regle():
    """Parité Python / TypeScript, comme `nom_lisible` / `nomFichier`.

    Deux listes d'extensions qui divergent, et une photo est annoncée « document »
    dans l'e-mail tout en s'affichant en vignette dans l'application.
    """
    import pathlib
    import re

    ts = (pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "fichiers.ts")
    m = re.search(r"EXTENSIONS_IMAGE\s*=\s*/\\.\(([^)]+)\)\$/i", ts.read_text(encoding="utf-8"))
    assert m, "EXTENSIONS_IMAGE introuvable dans fichiers.ts — parité invérifiable"

    from app.utils import fichiers
    py = re.search(r"\\.\(([^)]+)\)\$", fichiers._EXTENSIONS_IMAGE.pattern)
    assert py, "motif Python illisible — parité invérifiable"
    assert m.group(1) == py.group(1), (
        f"Les extensions image divergent : TS='{m.group(1)}' vs Python='{py.group(1)}'"
    )


# ── 5. Résolution des chemins d'upload ───────────────────────────────────────
#  Le 10/08/2026, l'unification des galeries a fait passer les photos de
#  publication du dossier `publications/` au dossier générique `fichiers/`. Deux
#  endroits gardaient l'ancien dossier écrit en dur, et les deux ont échoué
#  SANS LA MOINDRE ERREUR : le courriel est parti sans ses photos, et le message
#  WhatsApp a disparu entièrement du groupe (401 sur une URL publique devenue
#  authentifiée). Un chemin fabriqué à la main ne signale jamais qu'il est faux.

def test_aucun_sous_dossier_d_upload_colle_a_la_main():
    """Définir la RACINE des uploads est normal ; y coller un sous-dossier ne l'est pas.

    Le défaut n'était pas de connaître `/app/uploads`, c'était de reconstruire
    `<racine>/<dossier écrit en dur>/<nom de fichier>` alors qu'on avait déjà
    l'URL réelle du fichier. Le jour où le dossier change, le chemin devient faux
    et le fichier « n'existe pas » — sans erreur, donc sans que personne ne le voie.
    """
    racine = RACINE / "api" / "app"
    motif = re.compile(r"os\.path\.join\(\s*[\"']/app/uploads[\"']\s*,\s*[\"']")
    fautifs = [
        f"{f.relative_to(racine).as_posix()}:{n}"
        for f in sorted(racine.rglob("*.py"))
        if "__pycache__" not in f.parts
        for n, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
        if motif.search(ligne)
    ]
    assert not fautifs, (
        f"Sous-dossier d'upload écrit en dur : {fautifs}. Passer par "
        "`chemins_locaux()`, qui résout l'URL réelle du fichier."
    )


def test_whatsapp_n_envoie_plus_d_url_publique_pour_les_medias():
    """Le bridge reçoit des OCTETS, pas une URL qu'il retéléchargerait.

    Lui passer une URL obligeait à servir le dossier en anonyme : c'est ce qui a
    rendu `/uploads/publications/` public, et ce qui a cassé l'envoi quand les
    photos ont rejoint le dossier authentifié.
    """
    source = (RACINE / "api" / "app" / "utils" / "whatsapp.py").read_text(encoding="utf-8")
    assert "imageBase64" in source, "l'image n'est plus transmise en octets"
    lignes_actives = [
        l for l in source.splitlines()
        if "imageUrl" in l and not l.lstrip().startswith("#")
    ]
    assert not lignes_actives, (
        f"whatsapp.py construit encore une URL d'image : {lignes_actives}"
    )
