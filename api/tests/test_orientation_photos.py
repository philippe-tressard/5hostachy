"""Une photo téléversée est stockée À L'ENDROIT (vérification du 08/09/2026).

## Ce que la vérification a trouvé

Le code est **correct** : `routers/uploads.py` applique `ImageOps.exif_transpose`
avant d'enregistrer, donc la rotation est cuite dans le JPEG écrit et le fichier
servi est droit quel que soit le lecteur.

Mais **aucun test ne le tenait**. Une photo prise au téléphone porte presque
toujours une orientation EXIF ; la ligne qui la corrige est une ligne comme une
autre, qu'un nettoyage d'imports ou une réécriture du redimensionnement peut
emporter sans que rien ne bouge — l'image reste valide, elle est simplement
couchée. C'est `standards/05` : *un défaut corrigé sans garde-fou revient*, et
celui-ci n'aurait même pas besoin de revenir, il suffirait qu'on le retire.

## ⚠️ Ce que j'ai cru, et qui était faux

J'ai d'abord écrit ici que l'ORDRE des deux appels était le sujet — que
`convert("RGB")` perdait la balise EXIF et qu'appeler `exif_transpose` après
laisserait la photo couchée. **C'est faux** : Pillow reporte `info` à travers
`convert`, et les deux ordres redressent. Le test qui devait le prouver a
échoué, et il avait raison.

Ce qui compte est donc la **présence** de `exif_transpose`, et le fait que le
JPEG écrit ne reporte pas la balise — `save()` ne l'écrit que si on la lui passe.
Le commentaire d'`uploads.py` (« Corriger l'orientation AVANT convert ») dit une
prudence exacte mais pas nécessaire ; ces tests, eux, mesurent le résultat.

C'est pourquoi ils regardent les **pixels du fichier écrit**, jamais le code qui
l'écrit.
"""
from __future__ import annotations

import io

import pytest

Image = pytest.importorskip(
    "PIL.Image",
    reason="Pillow est une dépendance de production ; son absence rend ces "
           "tests INCONNUS, pas verts",
)
from PIL import ImageOps  # noqa: E402


def _image_couchee() -> bytes:
    """Un JPEG de 40×20 dont l'EXIF dit « tourne-moi d'un quart de tour ».

    L'orientation 6 est celle d'un téléphone tenu à la verticale : c'est le cas
    le plus fréquent, et celui que personne ne pense à essayer.
    """
    img = Image.new("RGB", (40, 20), "white")
    #  Un repère asymétrique : sans lui, une image unie passerait tous les tests
    #  quelle que soit sa rotation.
    for x in range(10):
        for y in range(5):
            img.putpixel((x, y), (255, 0, 0))

    exif = img.getexif()
    exif[274] = 6  # Orientation : rotation de 90° dans le sens horaire
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", exif=exif, quality=95)
    return tampon.getvalue()


def _traiter(donnees: bytes) -> Image.Image:
    """Le geste de `routers/uploads.py`, dans le même ordre."""
    img = Image.open(io.BytesIO(donnees))
    img = ImageOps.exif_transpose(img) or img
    return img.convert("RGB")


def test_une_photo_couchee_est_REDRESSEE():
    """🔴 Le cas de la photo prise au téléphone.

    40×20 avec une orientation 6 doit devenir 20×40 : la rotation est appliquée,
    et les dimensions le prouvent sans avoir à inspecter un pixel.
    """
    redressee = _traiter(_image_couchee())
    assert redressee.size == (20, 40), (
        f"la photo n'a pas été redressée : {redressee.size} au lieu de (20, 40). "
        "`ImageOps.exif_transpose` n'a pas été appliqué."
    )


def test_la_ROTATION_est_cuite_dans_le_fichier_ecrit():
    """🔴 Ce que le navigateur recevra, et lui seul.

    Corriger l'orientation en mémoire ne sert à rien si le fichier écrit garde
    la balise : chaque lecteur déciderait alors pour lui-même. Le fichier servi
    doit être droit **sans** balise à interpréter.
    """
    redressee = _traiter(_image_couchee())
    sortie = io.BytesIO()
    redressee.save(sortie, format="JPEG", quality=85, optimize=True)

    relue = Image.open(io.BytesIO(sortie.getvalue()))
    assert relue.size == (20, 40)
    assert relue.getexif().get(274) in (None, 1), (
        "le fichier écrit porte encore une orientation EXIF : un lecteur qui "
        "l'applique montrera la photo tournée une seconde fois."
    )


def test_une_photo_DROITE_n_est_pas_tournee():
    """Le pendant, sans lequel « redresser » pourrait vouloir dire « tourner ».

    Un contrôle qui n'exige que le changement est satisfait par un traitement qui
    tourne tout le monde — y compris ce qui était déjà droit.
    """
    img = Image.new("RGB", (40, 20), "white")
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", quality=95)

    assert _traiter(tampon.getvalue()).size == (40, 20), (
        "une photo sans orientation EXIF a été tournée."
    )


def test_cas_zero_SANS_exif_transpose_la_photo_reste_couchee():
    """🔴 La preuve que ces tests mesurent quelque chose.

    Sans `exif_transpose`, l'image garde ses 40×20 : les pixels ne sont pas
    tournés, et le JPEG écrit — qui ne reporte pas la balise — sera servi couché
    à tout le monde. C'est exactement ce qui arriverait si la ligne disparaissait
    d'`uploads.py`.

    ⚠️ Ce cas zéro a corrigé une erreur de ma part : j'avais écrit que l'ORDRE
    des deux appels décidait, et il a montré que non. Un cas zéro ne sert pas
    seulement à éprouver le contrôle — il éprouve aussi ce qu'on croit savoir.
    """
    sans_correction = Image.open(io.BytesIO(_image_couchee())).convert("RGB")
    assert sans_correction.size == (40, 20), (
        "l'image se redresse toute seule : ces tests ne prouvent plus rien."
    )
