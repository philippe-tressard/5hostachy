# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: LicenseRef-5Hostachy
"""Garde-fou : lire un `perimetre_cible` pour l'AFFICHER passe par une seule fonction.

## Le défaut (06/09/2026, #789)

`parse_json_perimetres` existait depuis longtemps, et quatre routeurs la
réécrivaient à la main :

    routers/idees.py                 `_perimetre_liste`, corps complet recopié
    routers/annonces.py              json.loads(x or '["résidence"]')
    routers/annonces_hall.py         idem — dans un fichier qui l'IMPORTAIT déjà
    routers/publications/commun.py   idem

🔴 **Et elles avaient déjà divergé** : les quatre écrivaient `"résidence"` **en
dur**, là où la fonction partagée lit `code_par_defaut()` — qui existe
précisément « pour que la valeur par défaut soit une donnée et non la chaîne
"résidence" écrite dans le code : une copropriété qui renomme ou supprime ce
nœud ne doit pas casser l'application ».

Autrement dit : la fonction partagée protégeait d'un défaut que ses quatre copies
réintroduisaient. Le badge 🔹 d'une annonce ou d'une idée aurait annoncé un
périmètre inexistant, et lui seul.

⚠️ `_perimetre_liste` est le cas le plus trompeur : une fonction **nommée**, à
l'air factorisé, qui ne partageait rien avec l'originale — exactement ce
qu'était `_can_manage` avant de déléguer à `peut_commenter`.

## Ce que ce test NE demande PAS

Deux sites lisent cette colonne autrement, et **c'est juste** — les factoriser
casserait quelque chose :

* `tickets/commun.py` rend `None` quand l'entrée d'historique ne parle pas du
  périmètre, parce que le front distingue « n'en parle pas » de « plus aucun
  périmètre » (#497). La fonction partagée retomberait sur le défaut, et chaque
  entrée prétendrait parler de toute la résidence ;
* `publications/commun.py` prend une décision d'**accès** (publication
  confidentielle) et **refuse** sur une donnée illisible. Le repli de la fonction
  partagée élargit — bienvenu pour un badge, exactement à l'envers ici.

C'est la leçon du ticket : **factoriser suppose d'avoir tranché**. Cinq copies
identiques (`exiger_non_externe`) se factorisent sans risque ; trois lectures aux
défauts différents demandent d'abord de savoir lequel est le bon, et où.
"""

from __future__ import annotations

from pathlib import Path

from tests.aides_sources import modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#  Les exceptions sont NOMMÉES avec leur raison, et le dernier test vérifie
#  qu'elles écrivent encore le MOTIF refusé — une exception qui ne l'écrit plus
#  n'excuse rien et masquerait la copie suivante dans le même fichier.
#
#  🔴 VIDE depuis le 30/09/2026 (#1496). Trois exceptions y vivaient (la source
#  `perimetres/arbre.py`, `visibility/socle.py`, `tickets/commun.py`), et aucune
#  n'écrivait plus le motif : le test qui devait le dire ne vérifiait que la
#  présence du mot « perimetre », et ne pouvait donc pas échouer. Les deux
#  lectures légitimes décrites plus haut ne l'écrivent pas non plus — elles n'ont
#  pas besoin d'exception. Si l'une en demande une, elle s'écrit ici AVEC sa
#  raison.
EXCEPTIONS: dict[str, str] = {}

#  La forme que prenaient les quatre copies : un `json.loads` dont le repli est la
#  chaîne « résidence » écrite dans le code.
MOTIF = "or '[\"résidence\"]'"


def _sans_commentaires(source: str) -> str:
    """Expliquer la règle ne doit pas la violer — les commentaires posés le
    06/09 dans les deux fichiers exemptés citent le motif qu'ils décrivent."""
    return "\n".join(ligne for ligne in source.splitlines() if not ligne.lstrip().startswith("#"))


def _coupables(modules) -> list[str]:
    """Les modules dont le CODE écrit le motif, hors exceptions."""
    return [
        m.rel for m in modules if m.rel not in EXCEPTIONS and MOTIF in _sans_commentaires(m.source)
    ]


def test_le_defaut_du_perimetre_n_est_pas_ecrit_en_dur():
    coupables = _coupables(modules_app())
    assert not coupables, (
        f"{coupables} écrivent le périmètre par défaut EN DUR. Employer "
        "`parse_json_perimetres` : le défaut est une donnée (`code_par_defaut()`), "
        "et une copropriété qui renomme ce nœud ne doit pas voir des badges mentir."
    )


def test_la_source_unique_lit_bien_le_defaut_configurable():
    """⚠️ Le cas zéro : si `parse_json_perimetres` se mettait à écrire la chaîne
    en dur, le test ci-dessus resterait vert et la protection aurait disparu."""
    source = (RACINE / "utils" / "perimetres" / "arbre.py").read_text(encoding="utf-8")
    assert "def parse_json_perimetres(" in source
    assert "code_par_defaut()" in source


def test_les_quatre_sites_delegent_encore():
    """Retirer la copie SANS appeler la fonction laisserait le premier test vert."""
    attendus = {
        "routers/idees.py",
        "routers/annonces.py",
        "routers/annonces_hall.py",
    }
    manquants = [
        rel
        for rel in sorted(attendus)
        if "parse_json_perimetres" not in (RACINE / rel).read_text(encoding="utf-8")
    ]
    assert not manquants, (
        f"{manquants} n'appellent plus `parse_json_perimetres` : soit la lecture a "
        "disparu, soit elle a été réécrite à la main."
    )


def test_le_controle_refuse_la_copie_forgee():
    """Cas zéro du MOTIF (#1496) : le motif n'apparaît plus nulle part dans
    `app/`, donc seul un extrait forgé prouve qu'il reconnaîtrait la copie — et
    qu'il ignore le commentaire qui la raconte."""
    from types import SimpleNamespace as Faux

    copie = "perimetres = json.loads(x.perimetre_cible or '[\"résidence\"]')"
    forges = [Faux(rel="forge.py", source=copie), Faux(rel="recit.py", source=f"# {copie}")]
    assert _coupables(forges) == ["forge.py"]


def test_chaque_exception_sert_encore():
    """Une exception sert tant que son CODE écrit le motif refusé — pas tant
    qu'il parle de périmètre, ce que tout fichier du domaine fait."""
    inutiles = []
    for rel, raison in EXCEPTIONS.items():
        chemin = RACINE / rel
        if not chemin.is_file():
            inutiles.append(f"{rel} (fichier absent) — {raison}")
            continue
        if MOTIF not in _sans_commentaires(chemin.read_text(encoding="utf-8")):
            inutiles.append(f"{rel} (n'écrit plus le motif) — {raison}")
    assert not inutiles, (
        f"Exceptions devenues inutiles : {inutiles}. Les retirer — une tolérance "
        "qui ne sert plus finit par en couvrir une qui compte."
    )
