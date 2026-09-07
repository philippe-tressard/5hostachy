"""Une pièce jointe s'écrit par `photos_json`, jamais à la main (#820).

## Le défaut, et pourquoi il est de SÉCURITÉ

Écrire une galerie en base demande deux gestes, toujours ensemble :

    json.dumps(photos_internes(urls), ensure_ascii=False)

`photos_internes` écarte toute URL qui n'a pas été produite par l'endpoint
d'upload. Sans lui, une requête forgée fait entrer en base une URL étrangère,
servie ensuite dans un `<img src>` **chez chaque résident** — une fuite de
référent, un pixel espion, ou pire selon ce que sert l'hôte distant.

`app/utils/photos.py` porte donc `photos_json`, avec cet avertissement écrit
au-dessus depuis sa création :

> *« Toujours passer par ici pour ÉCRIRE : le filtre n'est pas une précaution de
> confort. Écrite deux fois dans le même routeur, elle aurait fini par n'être
> filtrée qu'une fois. »*

## 🔴 Elle l'était DOUZE fois, dans sept fichiers

Relevé du 07/09/2026 : `crud.py`, `apercu.py` (tickets), `correction.py`,
`evolutions.py` (deux fois), `messages.py`, `calendrier.py`,
`calendrier_historique.py` (deux fois), `publications/apercu.py`.

Aucune n'avait oublié le filtre — la duplication n'avait pas encore coûté. Mais
c'est exactement ce que le commentaire annonçait, et rien n'empêchait la
treizième de l'oublier. **Le composant existait, et rien n'obligeait à s'en
servir** : c'est la leçon de `project_le_composant_existait_deja`, et la
troisième fois de la journée.

⚠️ Mon premier relevé n'en avait vu que six. Les six autres sont apparues
**après** la correction des premières, parce que je cherchais dans les seuls
fichiers que je venais de lire. C'est pourquoi ce contrôle balaie `app/` en
entier et non une liste que j'aurais dressée.
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
SOURCE = APP / "utils" / "photos.py"

#  Les deux gestes accolés — la signature d'une écriture faite à la main.
MOTIF = re.compile(r"json\.dumps\(\s*photos_internes\(")


def _lignes_fautives(source: str) -> list[int]:
    """Les lignes qui sérialisent une galerie sans passer par `photos_json`.

    ⚠️ Les commentaires sont ignorés : ce fichier-ci cite le motif qu'il refuse,
    et `photos.py` l'écrit dans sa propre docstring. Deux contrôles se sont déjà
    pris eux-mêmes le 06/09/2026 (`standards/04` §39).
    """
    fautives = []
    for numero, ligne in enumerate(source.splitlines(), 1):
        nue = ligne.strip()
        if nue.startswith(("#", '"""', "'''", "*", ">")):
            continue
        if MOTIF.search(ligne):
            fautives.append(numero)
    return fautives


def test_aucune_ecriture_de_galerie_ne_contourne_photos_json():
    fautifs = []
    for fichier in APP.rglob("*.py"):
        if fichier == SOURCE:
            continue
        for numero in _lignes_fautives(fichier.read_text(encoding="utf-8")):
            fautifs.append(f"{fichier.relative_to(APP)}:{numero}")

    assert not fautifs, (
        "une galerie est sérialisée à la main, hors de `photos_json` :\n  "
        + "\n  ".join(fautifs)
        + "\n  → `from app.utils.photos import photos_json` puis `photos_json(urls)`.\n"
        "    Le filtre `photos_internes` est ce qui empêche une URL étrangère "
        "d'être servie à chaque résident."
    )


def test_photos_json_FILTRE_vraiment_une_url_etrangere():
    """Le cas zéro du contrôle : la fonction qu'il impose doit protéger.

    Un garde-fou qui exige l'emploi d'une fonction sans vérifier ce qu'elle fait
    déplace le défaut sans le corriger. On l'exerce donc sur l'attaque même.
    """
    from app.utils.photos import photos_json

    rendu = photos_json(["/uploads/photo.jpg", "https://exemple-hostile.test/pixel.gif"])
    assert "/uploads/photo.jpg" in rendu
    assert "exemple-hostile" not in rendu, rendu
    #  Et l'accentuation survit : `ensure_ascii=False` fait partie du contrat.
    assert "é" in photos_json(["/uploads/façade-été.jpg"])


def test_le_garde_fou_REFUSE_bien_une_ecriture_a_la_main():
    """Cas zéro, les deux sens — la prose qui cite le motif doit passer."""
    fautif = "    photos_urls=json.dumps(photos_internes(body.photos_urls), ensure_ascii=False),"
    assert _lignes_fautives(fautif) == [1]
    #  Sur plusieurs lignes, comme le formateur peut l'écrire.
    assert _lignes_fautives("    x = json.dumps(\n        photos_internes(urls)\n    )") == []
    #  Un commentaire qui cite la forme ne la pose pas.
    assert _lignes_fautives("#  json.dumps(photos_internes(u)) vivait ici avant #820") == []
    #  L'appel correct passe.
    assert _lignes_fautives("    photos_urls=photos_json(body.photos_urls),") == []
