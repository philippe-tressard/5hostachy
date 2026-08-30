"""Garde-fou : « qui reçoit un e-mail interne » ne s'écrit qu'à UN endroit.

## Le défaut (31/08/2026)

La règle « syndic principal, puis les membres du CS, dédoublonnés par adresse »
existait en **quatre exemplaires**, identiques à la variable près :

    app/routers/tickets/commun.py
    app/routers/calendrier_courriels.py
    app/routers/publications/courriels.py
    app/routers/sondages/crud.py

🔴 **Et celui des tickets portait, en toutes lettres :** *« Cette fonction décide
qui reçoit un e-mail de ticket. Elle est le seul endroit où cette règle
s'écrit. »* Une affirmation d'unicité au milieu de quatre copies.

⚠️ C'est la forme la plus coûteuse de la duplication. Les trois autres n'avaient
**aucun** commentaire : rien ne signalait leur existence, et le seul fichier qui
parlait du sujet disait que le problème n'existait pas. Une relecture qui ouvrait
celui-là en repartait rassurée.

Ce que ça coûtait concrètement : ajouter un destinataire, changer la
déduplication, ou corriger le gagnant du doublon chez l'un laissait les trois
autres en arrière — et l'écart ne se voit **jamais** à l'écran. Un e-mail qui ne
part pas ne laisse pas de trace ailleurs que dans `historique_email`.

## Ce que ce test vérifie, et ce qu'il ne peut pas vérifier

Il vérifie la **forme** : plus aucun routeur ne rédige la requête à la main. Il ne
peut pas vérifier qu'un cinquième appelant emploie la fonction *correctement* —
c'est le rôle des tests d'envoi de chaque entité.

Les deux motifs sont cherchés séparément parce qu'ils se réintroduisent
séparément : on recopie d'abord le syndic, la liste du CS vient après.
"""
from __future__ import annotations

import io
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1] / "app"
SOURCE = RACINE / "utils" / "destinataires.py"

#  🔴 Les exceptions sont NOMMÉES, avec leur raison — une tolérance sans raison
#  devient un dépotoir, et le test échoue si l'une cesse de servir (voir plus bas).
EXCEPTIONS = {
    #  Le seul endroit où la règle a le droit de s'écrire.
    "utils/destinataires.py": "la source unique elle-même",
}

MOTIFS = {
    "est_principal == True": "le syndic principal — `syndic_principal(session)`",
    'roles_json.contains("conseil_syndical")':
        "la liste du CS par le rôle — `membres_cs_avec_email(session)` "
        "ou `destinataires_syndic_cs(...)`",
}

#  ⚠️ Les notifications IN-APP visent « CS **ou** admin » et rendent des
#  `Utilisateur`, pas des couples (id, e-mail) : ce n'est pas la même décision,
#  et les confondre enverrait des courriels aux administrateurs. Elles sont
#  reconnues par la présence de `contains("admin")` dans le même appel, et non
#  listées fichier par fichier — une liste de fichiers se périme, une
#  caractéristique du code se vérifie.
MARQUEUR_IN_APP = 'roles_json.contains("admin")'


def _fichiers_python() -> list[Path]:
    return sorted(p for p in RACINE.rglob("*.py") if "__pycache__" not in p.parts)


def _sans_commentaires(source: str) -> str:
    """Retire les lignes de commentaire : expliquer la règle ne doit pas la violer.

    Ce test-ci en est le premier bénéficiaire — les commentaires posés le
    31/08/2026 dans `tickets/commun.py` CITENT le motif qu'ils décrivent.
    """
    return "\n".join(l for l in source.splitlines() if not l.lstrip().startswith("#"))


def test_la_regle_des_destinataires_ne_s_ecrit_qu_a_un_endroit():
    fichiers = _fichiers_python()
    #  Cas zéro : un relevé légitimement vide ne peut pas se relire lui-même
    #  (`standards/04` §27). Le témoin est le nombre de fichiers LUS.
    assert len(fichiers) > 60, (
        f"{len(fichiers)} fichier(s) analysé(s) — l'arborescence a changé, "
        "le contrôle ne mord plus. Ne pas lire ceci comme un succès."
    )

    fautifs: list[str] = []
    exceptions_utiles: set[str] = set()

    for chemin in fichiers:
        rel = chemin.relative_to(RACINE).as_posix()
        source = _sans_commentaires(io.open(chemin, encoding="utf-8").read())
        for motif, remede in MOTIFS.items():
            if motif not in source:
                continue
            if motif == 'roles_json.contains("conseil_syndical")' and MARQUEUR_IN_APP in source:
                continue  # notification in-app : autre décision, autre destinataire
            if rel in EXCEPTIONS:
                exceptions_utiles.add(rel)
                continue
            fautifs.append(f"{rel} — écrit « {motif} » à la main → {remede}")

    assert not fautifs, (
        "La règle « qui reçoit un e-mail interne » est réécrite hors de sa source :\n  "
        + "\n  ".join(fautifs)
        + "\n\n  Elle a déjà existé en quatre exemplaires, dont un qui affirmait être"
        "\n  le seul. Un e-mail qui ne part pas ne laisse aucune trace à l'écran."
    )

    inutiles = set(EXCEPTIONS) - exceptions_utiles
    assert not inutiles, (
        f"Exception(s) devenue(s) inutile(s) : {sorted(inutiles)} — retirer l'entrée "
        "de EXCEPTIONS. Une tolérance qui ne sert plus fait croire que la règle "
        "a des trous qu'elle n'a pas."
    )


def test_le_motif_cherche_correspond_encore_a_la_source():
    """Éprouve le contrôle par ce qu'il DOIT trouver, pas seulement par son vide.

    ⚠️ Sans ceci, renommer la colonne ou la valeur du rôle rendrait les deux
    motifs muets, et le test ci-dessus passerait au vert en ne lisant plus rien.
    C'est le faux vert de `check-formulaire-creation` (30/08) et du motif
    `modal-overlay` de #561 : un contrôle dont le résultat normal est zéro ne
    peut pas se relire lui-même.
    """
    source = io.open(SOURCE, encoding="utf-8").read()
    for motif in MOTIFS:
        assert motif in source, (
            f"« {motif} » ne figure plus dans {SOURCE.name} : soit la source unique "
            "a changé de forme, soit le motif est périmé. Dans les deux cas le "
            "contrôle ci-dessus ne cherche plus rien."
        )
