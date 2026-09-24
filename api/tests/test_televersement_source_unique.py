"""Un fichier reçu s'écrit sur disque à UN endroit, et il y est contrôlé (#1026).

## 🔴 Ce que ce contrôle refuse, et pourquoi c'est de la sécurité

Le téléversement avait **trois écritures**, et elles n'appliquaient pas les mêmes
règles :

| Chemin | Type MIME | Plafond | Signature |
|---|---|---|---|
| `utils/fichiers.enregistrer_televersement` (documents privés) | **aucun** | **aucun** | oui |
| `routers/uploads._save_image` | oui | oui | réencodage PIL |
| `routers/uploads.upload_fichier`, branche document | oui | oui | oui — **recopiée** de la première, message de journal identique au caractère près |

Et **trois imports Excel n'avaient aucun contrôle du tout** : ni type, ni
taille — `await file.read()` lisait le corps entier en mémoire, puis le passait à
l'analyseur.

**Une duplication de règle de sécurité ne produit aucun signal.** Un fichier
accepté à tort ne fait pas de bruit : il est stocké, servi, et personne ne se
plaint. On ne l'apprend que le jour où quelqu'un s'en sert — c'est le même
raisonnement que `test_regle_acces_source_unique.py` et
`test_appartenance_lot_source_unique.py`.

## Ce que le contrôle vérifie

1. **L'écriture sur disque d'un fichier reçu** n'existe que dans
   `utils/fichiers.py`. Les exceptions sont nommées une par une, et un test
   échoue si l'une cesse de servir.
2. **Les trois règles** — liste blanche de types, plafond de taille, signature —
   ne s'écrivent qu'à cet endroit : aucun routeur ne redéclare de liste MIME ni
   de plafond en mégaoctets.
3. **Chaque famille déclarée porte les trois**, sans exception : une famille
   sans plafond est un téléversement sans plafond.

⚠️ Ce contrôle ne dit pas si les valeurs sont **bien réglées** — un plafond de
500 Mo lui conviendrait. Il dit qu'elles existent, qu'elles sont nommées, et
qu'elles ne sont écrites qu'une fois. Le réglage se relit, il ne se mesure pas.
"""

from __future__ import annotations

import ast
import pathlib
import re

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Le module qui porte le geste — et le seul autorisé à écrire un fichier reçu.
SOURCE = "utils/fichiers.py"

#: Les écritures sur disque qui ne sont **pas** des téléversements, nommées une
#: par une avec leur raison. Le dernier test échoue si l'une ne sert plus.
#:
#: La distinction est celle qui compte : un fichier **produit** par
#: l'application ne peut pas mentir sur son type, puisque c'est nous qui le
#: fabriquons. Un fichier **reçu** vient du réseau.
ECRITURES_NON_TELEVERSEMENT = {
    (
        "routers/annonces_hall.py",
        "write_bytes",
    ): "écrit le PDF d'affiche que l'application vient de PRODUIRE (WeasyPrint) "
    "— rien n'est reçu du client, il n'y a donc ni type à vérifier ni "
    "signature à confronter",
}

#: Un plafond de taille en mégaoctets, écrit en clair.
_MOTIF_PLAFOND = re.compile(r"MAX_[A-Z_]*SIZE_MB|MAX_[A-Z_]*MO\b|1024\s*\*\s*1024")

#: Un type MIME, pour repérer les LISTES qui en contiennent.
_MOTIF_MIME = re.compile(r"^(?:image|application|text)/[a-z0-9.+-]+$")


def _ecritures_disque():
    """(fichier, ligne, appel) pour chaque écriture d'octets sur disque."""
    for fichier in sorted(_APP.rglob("*.py")):
        source = fichier.read_text(encoding="utf-8")
        try:
            arbre = ast.parse(source)
        except SyntaxError:  # pragma: no cover
            continue
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            cible = ast.unparse(noeud.func)
            nom = None
            if cible.endswith("write_bytes"):
                nom = "write_bytes"
            elif cible == "open" and len(noeud.args) > 1:
                mode = noeud.args[1]
                if isinstance(mode, ast.Constant) and "w" in str(mode.value):
                    nom = "open(w)"
            if nom:
                yield fichier.relative_to(_APP).as_posix(), noeud.lineno, nom


def test_le_controle_voit_bien_des_ecritures():
    """Cas zéro de la portée : une liste vide se lirait comme « aucun écart »."""
    vues = list(_ecritures_disque())
    assert vues, (
        "aucune écriture sur disque trouvée dans app/ — le contrôle a perdu sa "
        "portée et rendrait un vert parfait"
    )
    assert (_APP / SOURCE).exists(), f"{SOURCE} a disparu"


def test_un_fichier_recu_ne_s_ecrit_que_dans_la_source():
    """Le défaut exact : deux routeurs écrivaient les octets reçus eux-mêmes."""
    fautes = []
    for fichier, ligne, appel in _ecritures_disque():
        if fichier == SOURCE:
            continue
        if (fichier, appel) in ECRITURES_NON_TELEVERSEMENT:
            continue
        fautes.append(f"  {fichier}:{ligne} — {appel}")

    assert not fautes, (
        "Ces lignes écrivent un fichier sur disque hors de la source unique :\n"
        + "\n".join(fautes)
        + "\n\n"
        f"Un fichier REÇU passe par `{SOURCE}`, qui porte la liste blanche de "
        "types, le plafond de taille et la vérification de signature. Un fichier "
        "PRODUIT par l'application est une autre notion : l'inscrire dans "
        "ECRITURES_NON_TELEVERSEMENT, avec sa raison."
    )


def test_aucun_routeur_ne_redeclare_un_plafond_ou_une_liste_de_types():
    """Les trois règles sont des NOTIONS, pas des valeurs à recopier.

    C'est la moitié du défaut que le premier test ne voit pas : un routeur peut
    déléguer l'écriture et garder sa propre liste MIME, donc décider seul de ce
    qu'il accepte.

    ⚠️ **Une liste blanche, pas un type de réponse.** La première version de ce
    contrôle cherchait un type MIME n'importe où dans une ligne : elle accusait
    `media_type="application/pdf"` (le type d'une réponse que nous *servons*) et
    `mime_type=file.content_type or "application/octet-stream"` (une valeur de
    repli stockée en base). Cinq faux positifs, tous légitimes.

    Un motif trop large ne rend pas un verdict prudent — il rend un verdict
    faux, et un contrôle qui accuse le code correct finit désarmé. Le critère
    porte donc sur ce qui se recopie vraiment : un **littéral d'ensemble ou de
    dictionnaire** dont les entrées sont des types MIME.
    """
    fautes = []
    for fichier in sorted((_APP / "routers").rglob("*.py")):
        source = fichier.read_text(encoding="utf-8")
        nom = fichier.relative_to(_APP).as_posix()
        try:
            arbre = ast.parse(source)
        except SyntaxError:  # pragma: no cover
            continue

        for noeud in ast.walk(arbre):
            #  Une liste blanche : `{"image/jpeg", …}` ou `{"application/pdf": ".pdf", …}`
            if isinstance(noeud, (ast.Set, ast.Dict)):
                valeurs = noeud.elts if isinstance(noeud, ast.Set) else noeud.keys
                types = [
                    v.value
                    for v in valeurs
                    if isinstance(v, ast.Constant)
                    and isinstance(v.value, str)
                    and _MOTIF_MIME.match(v.value)
                ]
                if types:
                    fautes.append(
                        f"  {nom}:{noeud.lineno} — liste de types : {', '.join(types[:3])}…"
                    )

        #  Le plafond, lui, se lit bien en texte : c'est une constante nommée ou
        #  une multiplication, jamais une structure.
        for i, ligne in enumerate(source.split("\n"), 1):
            nue = ligne.strip()
            if nue.startswith("#") or nue.startswith('"""') or nue.startswith("*"):
                continue
            if _MOTIF_PLAFOND.search(ligne):
                fautes.append(f"  {nom}:{i} — plafond de taille : {nue[:70]}")

    assert not fautes, (
        "Ces routeurs déclarent eux-mêmes ce qu'ils acceptent :\n" + "\n".join(fautes) + "\n\n"
        f"Les familles de téléversement sont déclarées dans `{SOURCE}` "
        "(FAMILLES), avec leur liste de types, leur plafond et leurs extensions. "
        "Un routeur nomme la famille, il ne redéfinit pas ses règles."
    )


def test_chaque_famille_porte_les_TROIS_regles():
    """Une famille sans plafond est un téléversement sans plafond.

    Le défaut d'origine est exactement là : la famille des documents privés
    n'avait ni liste de types ni plafond, seulement la signature — et personne ne
    pouvait le voir, puisqu'il n'existait **aucune table** à comparer.

    ⚠️ Ce test lit la table **importée**, pas le texte du fichier. Une première
    version comptait les occurrences de `types=` dans le code source : elle
    échouait sur une table construite par une fabrique — c'est-à-dire sur la
    forme la mieux factorisée, celle où `extensions` est *dérivée* de `types` au
    lieu d'être recopiée. Vérifier le **comportement**, jamais l'artefact.
    """
    from app.utils.fichiers import FAMILLES, FamilleFichier

    assert len(FAMILLES) >= 3, f"seulement {len(FAMILLES)} famille(s) déclarée(s)"

    for nom, regles in FAMILLES.items():
        assert isinstance(regles, FamilleFichier), (
            f"la famille « {nom} » n'est pas un FamilleFichier : les trois règles "
            "ne sont plus garanties par le type"
        )
        assert regles.types, (
            f"la famille « {nom} » n'a **aucune liste de types** : elle accepte "
            "ce que le client annonce, c'est le défaut de #1026 à sa source"
        )
        assert regles.plafond_mo > 0, (
            f"la famille « {nom} » n'a **aucun plafond** : un envoi de n'importe "
            "quelle taille est accepté, et il est lu en mémoire avant de l'être"
        )
        assert regles.extensions, f"la famille « {nom} » ne produit aucune extension connue"
        #  🔴 L'extension écrite sur disque doit venir de la table, jamais du nom
        #  fourni : `/uploads/*` est servi en statique, et Caddy pose le
        #  `Content-Type` d'après l'extension du fichier.
        assert set(regles.extensions) == set(regles.types.values()), (
            f"la famille « {nom} » déclare des extensions qui ne correspondent "
            "pas à ses types : les deux listes ont divergé, donc l'une des deux "
            "est recopiée"
        )


def test_une_famille_inconnue_est_refusee_et_ne_passe_pas_en_silence():
    """Le cas zéro de la fabrique : un nom de famille fautif doit LEVER.

    Un `FAMILLES.get(famille)` qui rendrait `None` sans lever ferait sauter les
    trois contrôles d'un coup — le défaut le plus permissif possible, sur une
    simple faute de frappe dans un routeur.
    """
    import pytest

    from app.utils.fichiers import verifier_fichier_recu

    with pytest.raises(ValueError):
        verifier_fichier_recu(b"%PDF-1.4", "x.pdf", "application/pdf", "famille-absente")


def test_les_trois_regles_refusent_VRAIMENT(tmp_path):
    """Chacune, éprouvée séparément — sinon « type et taille contrôlés » reste
    une affirmation sans contenu.
    """
    import pytest
    from fastapi import HTTPException

    from app.utils.fichiers import FAMILLES, enregistrer_fichier_recu

    #  Un PDF minimal, dont la signature est cohérente.
    pdf = b"%PDF-1.4\n%%EOF\n"

    #  1. le type annoncé n'est pas dans la famille
    with pytest.raises(HTTPException) as refus:
        enregistrer_fichier_recu(pdf, "x.pdf", "application/x-msdownload", "document", tmp_path)
    assert refus.value.status_code == 400

    #  2. le plafond
    trop_gros = b"%PDF-1.4" + b"0" * (FAMILLES["document"].plafond_mo * 1024 * 1024)
    with pytest.raises(HTTPException) as refus:
        enregistrer_fichier_recu(trop_gros, "x.pdf", "application/pdf", "document", tmp_path)
    assert refus.value.status_code == 413

    #  3. la signature : un exécutable annoncé PDF — le défaut de #773
    with pytest.raises(HTTPException) as refus:
        enregistrer_fichier_recu(
            b"MZ\x90\x00" + b"0" * 20, "x.pdf", "application/pdf", "document", tmp_path
        )
    assert refus.value.status_code == 400

    #  Et le cas qui doit PASSER, sans quoi les trois refus ne prouvent rien :
    #  un contrôle qui refuse tout est aussi faux qu'un contrôle qui accepte tout.
    nom = enregistrer_fichier_recu(
        pdf, "Devis toiture.pdf", "application/pdf", "document", tmp_path
    )
    assert nom.endswith(".pdf")
    assert "toiture" in nom, "le radical du nom d'origine est perdu"
    assert (tmp_path / nom).read_bytes() == pdf


def test_aucune_exception_ne_survit_a_son_motif():
    """Une exception qui ne sert plus finit par couvrir autre chose."""
    vues = {(f, a) for f, _, a in _ecritures_disque()}
    perimees = [
        f"  {f} / {a} — « {raison} »"
        for (f, a), raison in ECRITURES_NON_TELEVERSEMENT.items()
        if (f, a) not in vues
    ]
    assert not perimees, (
        "Ces exceptions ne correspondent plus à rien :\n"
        + "\n".join(perimees)
        + "\n\nLes retirer de ECRITURES_NON_TELEVERSEMENT."
    )
