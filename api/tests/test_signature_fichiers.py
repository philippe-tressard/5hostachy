"""Un fichier téléversé doit ÊTRE ce qu'il prétend être — aux quatre points.

## Le défaut (#773, audit du 05/09/2026)

Les documents n'étaient validés que par `file.content_type` : une chaîne
**envoyée par le client**, qu'un `curl` fixe librement. Un exécutable renommé
`.pdf` avec `Content-Type: application/pdf` était stocké, puis servi aux
résidents authentifiés.

Les **images**, elles, étaient réellement vérifiées — PIL les ouvre. Le même
produit avait donc deux niveaux d'exigence pour la même question, et personne ne
pouvait le voir : les deux chemins vivaient dans le même fichier, à trente
lignes d'écart.

## Pourquoi ce test regarde AUSSI la portée

La règle ne vaut que si les **quatre** points de téléversement l'appellent —
`uploads`, `compteurs`, `diagnostics`, `documents`. Une règle centralisée qu'un
seul appelant emploie ne protège qu'un seul chemin, et donne l'illusion des
quatre (`standards/03` §1).
"""
from __future__ import annotations

import pathlib
import re

from app.utils.fichiers import signature_incoherente

_ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"

#: Les quatre endpoints qui écrivent un fichier téléversé sur le disque.
_POINTS = ("uploads.py", "compteurs.py", "diagnostics.py", "documents.py")


def test_un_faux_pdf_est_refuse():
    """Le cas qui motive tout : un exécutable annoncé PDF."""
    motif = signature_incoherente(b"MZ\x90\x00\x03\x00\x00\x00", ".pdf")
    assert motif and ".pdf" in motif, "un exécutable déguisé en PDF passe encore"


def test_les_vrais_fichiers_passent():
    """Un contrôle qui refuse le légitime est désarmé dans la semaine."""
    for donnees, ext in (
        (b"%PDF-1.7\n%\xe2\xe3", ".pdf"),
        (b"PK\x03\x04\x14\x00", ".docx"),
        (b"PK\x03\x04\x14\x00", ".xlsx"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", ".doc"),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", ".jpg"),
        (b"\x89PNG\r\n\x1a\n\x00\x00", ".png"),
        (b"GIF89a\x01\x00", ".gif"),
    ):
        assert signature_incoherente(donnees, ext) is None, f"{ext} légitime refusé"


def test_un_format_SANS_signature_passe_sans_etre_inspecte():
    """🔴 La moitié qui empêche ce contrôle de devenir une restriction.

    `.txt` et `.csv` n'ont pas de signature stable. Refuser faute de savoir
    reconnaître reviendrait à interdire du contenu légitime au nom de la
    sécurité — et à faire désarmer le contrôle par le premier qui en a besoin.
    """
    assert signature_incoherente(b"n'importe quel texte", ".txt") is None
    assert signature_incoherente(b"a;b;c\n1;2;3", ".csv") is None
    assert signature_incoherente(b"peu importe", "") is None


def test_la_casse_de_l_extension_ne_desarme_pas_le_controle():
    """`.PDF` est un `.pdf` — un contrôle sensible à la casse se contourne au clavier."""
    assert signature_incoherente(b"MZ\x90\x00", ".PDF") is not None
    assert signature_incoherente(b"%PDF-1.4", ".PDF") is None


def test_le_motif_est_LISIBLE_et_pas_un_booleen():
    """Un refus sans motif ressemble à une panne, et c'est ainsi qu'on le désarme."""
    motif = signature_incoherente(b"MZ", ".docx")
    assert isinstance(motif, str) and len(motif) > 20
    assert ".docx" in motif


def test_les_QUATRE_points_de_televersement_appellent_la_regle():
    """🔴 La portée fait partie du contrôle.

    Une règle centralisée qu'un seul appelant emploie ne protège qu'un chemin —
    et laisse croire qu'elle les protège tous.
    """
    manquants = [
        nom
        for nom in _POINTS
        if "signature_incoherente" not in (_ROUTERS / nom).read_text(encoding="utf-8")
    ]
    assert not manquants, (
        "ces points de téléversement n'appellent pas `signature_incoherente` : "
        f"{manquants}. Un fichier déguisé y passe encore."
    )


def test_aucun_nouveau_point_de_televersement_hors_du_relevé():
    """Un cinquième point apparaîtrait sans que rien ne le signale.

    Le relevé `_POINTS` est écrit à la main : ce test le confronte au code, pour
    qu'un routeur qui se met à écrire un fichier téléversé soit ajouté ici — et
    donc examiné — plutôt que découvert au prochain audit.
    """
    ecrivains = {
        f.name
        for f in _ROUTERS.rglob("*.py")
        if re.search(
            r"shutil\.copyfileobj\(file\.file|\(dest_dir / filename\)\.write_bytes",
            f.read_text(encoding="utf-8"),
        )
    }
    assert ecrivains <= set(_POINTS), (
        "point(s) de téléversement hors du relevé : "
        f"{sorted(ecrivains - set(_POINTS))}. Les ajouter à `_POINTS` après avoir "
        "vérifié qu'ils valident la signature."
    )
