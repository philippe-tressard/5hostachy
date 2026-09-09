"""Un document a QUATRE rendus, et un champ ajouté doit les atteindre tous.

## Ce qui s'est passé deux fois de suite

La `description` a été ajoutée au document le 08/09/2026. Elle est arrivée sur
**un** des quatre rendus — l'écran Résidence — et y est restée. Le fil
d'actualité, la notification dans l'application et le courriel de publication
continuaient d'ignorer un champ que quelqu'un venait de remplir. Trouvé par
Philippe, le lendemain, à l'écran.

Le même jour, la mise en page de ce seul rendu cassait pour les documents qui
portaient une description — trouvé à l'écran lui aussi.

🔴 **C'est `standards/11` §14** : un objet a plusieurs rendus, et personne ne les
compare, parce qu'ils vivent sur des écrans différents. Le rendu qu'on oublie
n'est pas celui qu'on connaît mal — c'est celui qu'on ne regardait pas ce jour-là.

## Ce que ce fichier fait, et ce qu'il ne peut pas faire

Il **nomme les quatre rendus** et vérifie que chacun porte les champs déclarés.
Il ne peut pas deviner qu'un CINQUIÈME rendu apparaît — aucun test ne le peut.
Sa valeur est ailleurs : le jour où l'on ajoute un champ à `Document`, ce fichier
est la liste qui dit où il doit aller, et il échoue tant qu'il n'y est pas.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[1]

#: Les champs d'un document qui doivent PARAÎTRE partout où le document paraît.
#:
#: `titre` y est autant que `description` : c'est le couple qui dit ce qu'est le
#: document. Un champ purement technique (`mime_type`, `taille_octets`) n'a rien
#: à faire ici — la liste décrit ce qu'un lecteur doit voir, pas ce que la table
#: contient.
CHAMPS_RENDUS = ("titre", "description")


def test_le_FIL_rend_les_champs_du_document():
    """`detail` dit ce qui s'est passé, `meta.description` ce que le document couvre."""
    from app.routers.flux import ressources

    source = inspect.getsource(ressources._collecter_documents)
    for champ in CHAMPS_RENDUS:
        assert f"d.{champ}" in source, (
            f"le fil d'actualité ne rend pas `{champ}` : une carte de document dit "
            "moins que la ligne de l'écran Résidence, sans que personne l'ait décidé."
        )


def test_la_NOTIFICATION_et_le_COURRIEL_rendent_les_champs_du_document():
    """Les deux partent du même point d'appel, et se lisent ensemble."""
    from app.routers.documents import _notifier_document_publie

    source = inspect.getsource(_notifier_document_publie)
    for champ in CHAMPS_RENDUS:
        assert f"doc.{champ}" in source, (
            f"ni la notification ni le courriel ne portent `{champ}`."
        )


def test_l_ECRAN_rend_les_champs_du_document():
    """Le rendu d'origine — celui par lequel le champ est arrivé."""
    source = (
        RACINE.parent / "front" / "src" / "lib" / "components" / "SectionDocuments.svelte"
    ).read_text(encoding="utf-8")
    for champ in CHAMPS_RENDUS:
        assert f"doc.{champ}" in source, f"l'écran Résidence ne rend plus `{champ}`."


def test_le_MODELE_de_courriel_rend_les_champs_du_document():
    """Le gabarit doit les afficher, pas seulement les recevoir.

    ⚠️ Ce test lit le SEED. Que le modèle SERVI les porte aussi est la question
    de `sante_modeles_email`, qui compare la base au code — les deux sont
    nécessaires, et c'est ce qui a manqué pendant des mois sur les canaux externes.
    """
    from app.seed import EMAIL_TEMPLATES

    _c, _l, _sujet, corps, _d = next(
        t for t in EMAIL_TEMPLATES if t[0] == "document_publie"
    )
    for champ in CHAMPS_RENDUS:
        assert f"document.{champ}" in corps, (
            f"le modèle `document_publie` n'affiche pas `{champ}` : le destinataire "
            "doit ouvrir le fichier pour savoir s'il le concerne."
        )


def test_le_LIEN_du_document_n_est_calcule_qu_a_UN_endroit():
    """🔴 Il l'était à deux, et les deux ne disaient pas la même chose.

    Le fil savait qu'une pièce jointe d'actualité s'ouvre sur sa publication,
    qu'un document de contrat vit dans la fiche du prestataire, et que sept des
    dix catégories n'ont **aucune** rubrique — donc aucun lien. La notification et
    le courriel écrivaient `lien_element("doc", doc.id)` sans condition : la page
    bonne, l'élément invisible.
    """
    fautifs = []
    for chemin in (RACINE / "app").rglob("*.py"):
        if "__pycache__" in chemin.parts:
            continue
        if chemin.name == "documents.py" and chemin.parent.name == "utils":
            continue  # la source
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "lien_element"
                and n.args
                and isinstance(n.args[0], ast.Constant)
                and n.args[0].value == "doc"
            ):
                fautifs.append(chemin.relative_to(RACINE).as_posix())

    assert not fautifs, (
        "Ces fichiers fabriquent eux-mêmes le lien d'un document : "
        + ", ".join(sorted(set(fautifs)))
        + ". Employer `lien_document` de `app.utils.documents` — il sait où le "
        "document est RÉELLEMENT affiché, et pour qui."
    )
