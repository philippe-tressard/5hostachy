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


#: Les deux façons ADMISES de vérifier un fichier téléversé.
#:
#: 🔴 La seconde est née le 08/09/2026 (#825) : le geste complet — lire seize
#: octets, rembobiner, vérifier, journaliser, refuser, nommer, copier — était
#: recopié dans TROIS routeurs au caractère près. La règle était factorisée, son
#: emploi non, et c'est l'emploi qui contient les pièges : sans `seek(0)` le
#: fichier écrit perd sa tête, sans le `raise` la vérification ne bloque rien.
#:
#: ⚠️ Ce test a échoué au moment de la factorisation, et il avait raison de le
#: faire : il cherchait `signature_incoherente` en direct, et ne la trouvait plus.
#: Un contrôle qui suit le code sans qu'on le relise cesse de mesurer ce qu'il
#: croit mesurer — celui-ci a exigé qu'on décide, et voilà la décision.
_APPELS_ADMIS = ("signature_incoherente", "enregistrer_televersement")


def test_les_QUATRE_points_de_televersement_appellent_la_regle():
    """🔴 La portée fait partie du contrôle.

    Une règle centralisée qu'un seul appelant emploie ne protège qu'un chemin —
    et laisse croire qu'elle les protège tous.
    """
    manquants = [
        nom
        for nom in _POINTS
        if not any(a in (_ROUTERS / nom).read_text(encoding="utf-8") for a in _APPELS_ADMIS)
    ]
    assert not manquants, (
        "ces points de téléversement ne vérifient pas la signature du fichier : "
        f"{manquants}. Un fichier déguisé y passe encore. "
        "Employer `enregistrer_televersement` (valide ET écrit), ou "
        "`signature_incoherente` si l'écriture est particulière."
    )


def test_le_geste_factorise_REMBOBINE_le_flux():
    """🔴 Sans `seek(0)`, le fichier écrit perd ses seize premiers octets.

    Il n'est pas rejeté : il est **corrompu**, silencieusement, et personne ne
    s'en aperçoit avant de l'ouvrir. C'est le piège que la factorisation retire
    des trois routeurs, et il mérite son propre test — le reste du geste échoue
    bruyamment, celui-ci non.
    """
    import io as _io
    from types import SimpleNamespace

    from app.utils.fichiers import enregistrer_televersement

    from app.utils.fichiers import REPERTOIRE_PRIVE

    #  ⚠️ Le répertoire est créé PAR LE TEST, pas par la fonction : en
    #  production il existe (volume Docker), et le créer à chaque écriture
    #  masquerait un montage manquant — une panne d'infrastructure deviendrait
    #  un fichier écrit dans le vide du conteneur, perdu au redémarrage.
    pathlib.Path(REPERTOIRE_PRIVE).mkdir(parents=True, exist_ok=True)

    contenu = b"%PDF-1.4 contenu de test"
    faux = SimpleNamespace(file=_io.BytesIO(contenu))
    chemin = enregistrer_televersement(faux, "rapport.pdf")
    try:
        assert pathlib.Path(chemin).read_bytes() == contenu, (
            "le fichier écrit ne correspond pas à ce qui a été téléversé : "
            "le flux n'a pas été rembobiné après la lecture de la signature."
        )
    finally:
        pathlib.Path(chemin).unlink(missing_ok=True)


def test_le_geste_factorise_REFUSE_un_fichier_deguise():
    """Le pendant : un exécutable renommé en `.pdf` doit lever une 400.

    ⚠️ Vérifié sur le geste COMPLET, pas seulement sur la règle : c'est
    l'oubli du `raise` qui transformerait le contrôle en simple journal.
    """
    import io as _io
    from types import SimpleNamespace

    import pytest as _pytest
    from fastapi import HTTPException

    from app.utils.fichiers import enregistrer_televersement

    faux = SimpleNamespace(file=_io.BytesIO(b"MZ" + bytes([0x90, 0x00]) + b" un executable"))
    with _pytest.raises(HTTPException) as capture:
        enregistrer_televersement(faux, "innocent.pdf")
    assert capture.value.status_code == 400
    assert ".pdf" in str(capture.value.detail)


def test_aucun_nouveau_point_de_televersement_hors_du_relevé():
    """Un cinquième point apparaîtrait sans que rien ne le signale.

    Le relevé `_POINTS` est écrit à la main : ce test le confronte au code, pour
    qu'un routeur qui se met à écrire un fichier téléversé soit ajouté ici — et
    donc examiné — plutôt que découvert au prochain audit.
    """
    routeurs = list(_ROUTERS.rglob("*.py"))
    #  🔴 CAS ZÉRO DE LA PORTÉE. `ecrivains <= set(_POINTS)` est VRAI quand
    #  `ecrivains` est vide : un `_ROUTERS` devenu faux rendrait donc un vert
    #  parfait, sur zéro fichier lu. C'est `standards/04` §40 appliqué au test
    #  que j'ai écrit ce matin même — sa promesse est « aucun cinquième point de
    #  téléversement », sa portée était « ce que le glob veut bien trouver ».
    assert len(routeurs) > 20, (
        f"{len(routeurs)} routeur(s) lu(s) sous {_ROUTERS} — la portée du relevé "
        "est cassée, et son vert ne veut rien dire (INCONNU, pas OK)."
    )
    ecrivains = {
        f.name
        for f in routeurs
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
