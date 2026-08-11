"""Courriels — préparation des pièces jointes avant envoi.

Extrait de `email.py` le 11/08/2026. Voir `gabarit.py` pour la règle de partage.
"""
import os
import re as _re
import tempfile

from app.utils.fichiers import nom_lisible


def _preparer_pieces_jointes(paths: list[str]) -> tuple[list[dict], list[str]]:
    """(pièces jointes prêtes pour le message, chemins temporaires à nettoyer).

    Deux renommages techniques faisaient perdre le nom d'origine dans la
    messagerie du destinataire :
      - le préfixe UUID de `nom_stocke` → « 0d41107a6c…lasseurs.pdf » ;
      - `_fix_image_orientations`, qui écrit un fichier `exif_XXXX.jpg`.

    Le nom affiché est donc calculé sur le chemin **d'origine**, avant toute
    correction, et transmis explicitement en `Content-Disposition`.

    Écrit une fois : `send_email` et `send_email_group` faisaient déjà le même
    `_fix_image_orientations` suivi du même nettoyage, chacun de son côté.
    """
    corriges = _fix_image_orientations(paths)
    prets: list[dict] = []
    for origine, chemin in zip(paths, corriges):
        # Le nom vient de `nom_stocke`, donc déjà réduit à [A-Za-z0-9_.-] ; on
        # neutralise malgré tout guillemets et sauts de ligne, qui casseraient
        # l'en-tête pour les fichiers plus anciens, aux noms non assainis.
        affiche = _re.sub(r'["\r\n]', "_", nom_lisible(origine))
        prets.append({
            "file": chemin,
            "headers": {"Content-Disposition": f'attachment; filename="{affiche}"'},
        })
    temporaires = [c for c in corriges if c not in paths]
    return prets, temporaires


def _fix_image_orientations(paths: list[str]) -> list[str]:
    """Applique la rotation EXIF sur les images JPEG et retourne les chemins corrigés."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return paths

    fixed: list[str] = []
    for path in paths:
        ext = os.path.splitext(path)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
            fixed.append(path)
            continue
        try:
            with Image.open(path) as img:
                corrected = ImageOps.exif_transpose(img)
                if corrected is img:
                    # Pas de correction nécessaire
                    fixed.append(path)
                    continue
                tmp = tempfile.NamedTemporaryFile(
                    suffix=ext, prefix="exif_", dir=os.path.dirname(path), delete=False,
                )
                corrected.save(tmp.name, quality=92)
                tmp.close()
                fixed.append(tmp.name)
        except Exception:
            fixed.append(path)
    return fixed
