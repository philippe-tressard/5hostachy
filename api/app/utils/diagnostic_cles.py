"""Compter les lignes orphelines de la base — la mesure, sans la porte d'entrée.

## Pourquoi cette fonction vit ici (#546, étape 2 bis)

Deux appelants en ont besoin, et ils n'ont **pas la même authentification** :

  • `GET /admin/db/cles-etrangeres` — une session **admin**, pour un diagnostic
    à la main ;
  • `GET /admin/maintenance/cles-etrangeres` — la **clé partagée** des scripts
    d'exploitation, pour la surveillance continue.

🔴 La mesure est donc écrite **une fois**, et chaque porte porte sa propre
vérification. L'alternative — une seule route acceptant « admin OU clé » —
demanderait une dépendance optionnelle et une logique d'auth conditionnelle :
c'est exactement la forme dans laquelle un contournement se glisse sans se voir.
Deux portes explicites valent mieux qu'une porte à deux serrures.

## Ce que la mesure ne rend PAS

`PRAGMA foreign_key_check` donne aussi le **rowid** de chaque ligne fautive. Il
n'est pas renvoyé : le canal des scripts est borné à « aucune donnée de
copropriétaire » (`rapports_scripts.py`), et un rowid désigne une ligne précise.
Noms de tables, noms de colonnes et comptes suffisent à décider.

## Pourquoi jamais un script

Ouvrir `app.db` depuis un process tiers pendant que l'API tourne a corrompu la
base trois fois (05 et 17/06, 17/07/2026). La règle d'or ne souffre aucune
exception, **pas même en lecture**. Cette mesure s'exécute donc dans le process
uvicorn, sur le moteur de l'application — comme le checkpoint et `quick_check`.
"""

from collections import Counter


def compter_orphelins(engine) -> dict:
    """Les lignes qui référencent un parent disparu, groupées par relation.

    Rend toujours un dictionnaire, jamais une exception :

      • `{"ok": False, "inconnu": True, "erreur": …}` si la mesure n'a pas pu
        avoir lieu — **jamais** `orphelins: 0`. Le résultat normal de ce
        contrôle étant zéro, une erreur silencieuse produirait le faux vert
        parfait (`standards/04` §1) ;
      • sinon `{"ok": …, "inconnu": False, "orphelins": N, "par_relation": [...]}`.

    ⚠️ `PRAGMA foreign_key_check` fonctionne **indépendamment** de
    `foreign_keys=ON/OFF` : c'est un outil de diagnostic, pas le mécanisme
    d'application. Il dit donc la vérité sur une base qui tourne encore sans les
    clés — c'est tout l'intérêt.

    ⚠️ Il parcourt la base entière. Sur une copropriété c'est instantané ; le
    noter pour le jour où ce ne le serait plus.
    """
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            lignes = conn.execute(text("PRAGMA foreign_key_check")).fetchall()
            #  Le `fkid` rendu par le PRAGMA est un INDEX dans la liste des clés
            #  de la table : illisible tel quel. On le résout en NOM DE COLONNE,
            #  sinon le rapport nommerait un chiffre là où il faut décider d'une
            #  relation. Interrogé seulement pour les tables en défaut.
            colonnes: dict[tuple[str, int], str] = {}
            for table in {ligne[0] for ligne in lignes}:
                for fk in conn.execute(text(f'PRAGMA foreign_key_list("{table}")')).fetchall():
                    colonnes[(table, fk[0])] = fk[3]
    except Exception as exc:  # pragma: no cover - éprouvé par un moteur simulé
        return {"ok": False, "inconnu": True, "erreur": str(exc)}

    detail = Counter(
        (ligne[0], colonnes.get((ligne[0], ligne[3]), f"fk#{ligne[3]}"), ligne[2])
        for ligne in lignes
    )
    return {
        "ok": not lignes,
        "inconnu": False,
        "orphelins": len(lignes),
        "par_relation": [
            {"table": t, "colonne": c, "table_parente": p, "lignes": n}
            for (t, c, p), n in sorted(detail.items(), key=lambda x: -x[1])
        ],
    }
