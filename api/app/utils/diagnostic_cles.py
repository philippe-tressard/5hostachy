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

import logging
from collections import Counter

#  🔴 Le journal n'est PAS décoratif ici. La purge est irréversible, et jusqu'au
#  31/08/2026 elle ne laissait aucune trace de ce qu'elle avait touché : le détail
#  ne vivait que dans la réponse HTTP, donc à l'écran de qui avait cliqué. Quand la
#  perte d'un membre du conseil syndical a été signalée le lendemain, il a fallu
#  remonter à une sauvegarde de la veille pour établir ce qui était parti.
logger = logging.getLogger(__name__)


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
            #  🔴 LE RÉGIME LUI-MÊME, et pas seulement son résultat.
            #
            #  `foreign_key_check` dit ce que la base CONTIENT ; il ne dit rien de
            #  ce qu'elle REFUSERA demain. Les deux questions sont distinctes, et
            #  la seconde est celle qu'on se pose après avoir activé les clés :
            #  « ont-elles vraiment pris ? »
            #
            #  Sans ce champ, un relevé à zéro se lit comme une victoire sur une
            #  base où les clés seraient restées désactivées — l'appel
            #  `activer_cles_etrangeres` ne prenant PAS effet s'il est placé après
            #  le bloc d'amorçage (mesuré le 30/08/2026, cf. `database.py`).
            cles_actives = bool(conn.execute(text("PRAGMA foreign_keys")).scalar())
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
        "cles_actives": cles_actives,
        "orphelins": len(lignes),
        "par_relation": [
            {"table": t, "colonne": c, "table_parente": p, "lignes": n}
            for (t, c, p), n in sorted(detail.items(), key=lambda x: -x[1])
        ],
    }


def _remedes(conn, lignes):
    """Pour chaque orpheline, DÉLIER ou SUPPRIMER — et jamais l'un pour l'autre.

    🔴 CETTE DISTINCTION A COÛTÉ UN MEMBRE DU CONSEIL SYNDICAL, LE 31/08/2026.

    La première version supprimait uniformément. Elle a effacé la ligne
    `membre_cs` de Christine LONGUÈVE : elle pointait vers un `utilisateur`
    supprimé depuis longtemps, et l'outil en a conclu qu'il fallait supprimer la
    membre. C'était le LIEN qui était cassé, pas la MEMBRE — un autre membre du
    CS vit très bien avec `user_id` à NULL.

    ⚠️ Le pire est que la règle était écrite, dans le ticket #546 lui-même :
    *« la décision dépend de ce que la ligne RACONTE, jamais de la nullabilité de
    sa colonne »*. Elle avait été posée pour les suppressions en cascade des
    endpoints. L'outil de purge, lui, ne l'appliquait pas :
    **une règle énoncée pour un chemin ne protège pas l'autre.**

    Ce que le schéma dit, et qui suffit à trancher :

    | La colonne de la clé | Ce que la ligne devient | Remède |
    |---|---|---|
    | `NOT NULL` | impossible : elle ne peut exister sans son parent | suppression |
    | nullable | valide : le parent était facultatif | **mise à NULL** |

    Une clé COMPOSITE se lit d'un bloc : si l'une de ses colonnes est
    obligatoire, la ligne entière l'est. Délier à moitié fabriquerait une ligne
    que le schéma refuse.
    """
    from sqlalchemy import text

    #  Les métadonnées sont relues par table, une seule fois chacune.
    cache: dict = {}

    def meta(table: str):
        if table not in cache:
            fks: dict = {}
            for f in conn.execute(text(f'PRAGMA foreign_key_list("{table}")')):
                fks.setdefault(f[0], []).append(f[3])
            colonnes = {
                c[1]: bool(c[3])  # notnull
                for c in conn.execute(text(f'PRAGMA table_info("{table}")'))
            }
            cache[table] = (fks, colonnes)
        return cache[table]

    remedes = []
    for table, rowid, _parent, fkid in lignes:
        fks, colonnes = meta(table)
        cols = fks.get(fkid, [])
        #  ⚠️ Sans colonne identifiée, on ne DEVINE pas : on supprime, qui est le
        #  remède qu'appliquait la version précédente. Ne rien faire laisserait
        #  une orpheline que le relevé suivant compterait encore, indéfiniment.
        obligatoire = (not cols) or any(colonnes.get(c, True) for c in cols)
        remedes.append((table, rowid, cols, "suppression" if obligatoire else "deliaison"))
    return remedes


def purger_orphelins(engine, *, simuler: bool = True) -> dict:
    """Réparer les lignes qui référencent un parent disparu — **sans en perdre**.

    ## 🔴 SIMULATION PAR DÉFAUT, et ce n'est pas une politesse

    `simuler=True` rend exactement ce qui SERAIT fait, sans rien toucher.
    L'appelant doit demander l'écriture explicitement. Une opération irréversible
    dont le mode destructeur est le défaut finit par s'exécuter par accident.

    ## Deux remèdes, et c'est le SCHÉMA qui choisit — voir `_remedes`

    Une clé **obligatoire** rend la ligne impossible : elle part. Une clé
    **nullable** ne casse que le lien : la colonne passe à NULL, la ligne reste.
    Supprimer dans le second cas, c'est jeter l'objet pour réparer sa référence —
    et c'est ce qui a coûté un membre du conseil syndical le 31/08/2026.

    ## Ce sur quoi elle agit, et rien d'autre

    **Uniquement les `rowid` que `PRAGMA foreign_key_check` désigne.** Pas une
    requête « toutes les lignes dont le parent est absent » réécrite à la main :
    c'est SQLite qui dit lesquelles, et on lui obéit ligne par ligne.

    La différence n'est pas théorique. Une jointure écrite à la main se trompe
    sur les clés composites, sur les colonnes nullables (`NULL` ne référence
    rien, donc n'est jamais orpheline) et sur les tables sans clé primaire.

    ⚠️ **Le `rowid` ne sort jamais de cette fonction** : il sert à agir, il n'est
    pas rendu. Le canal des scripts est borné à « aucune donnée de
    copropriétaire », et un rowid désigne une ligne précise.

    ## Ce qu'elle JOURNALISE, et pourquoi elle le doit

    🔴 La version précédente ne journalisait **rien**. Le détail de ce qu'elle
    détruisait n'existait que dans la réponse HTTP — donc à l'écran de qui avait
    cliqué, et il partait avec l'onglet. Quand la perte du membre du CS a été
    signalée le lendemain, **aucune trace ne disait ce qui avait disparu** : il a
    fallu remonter à une sauvegarde de la veille pour l'établir.

    Une opération irréversible qui ne laisse pas de trace n'est pas
    diagnosticable. Le détail par table et par remède part donc dans le journal
    de l'API — sans aucun rowid ni contenu de ligne.

    ## Pourquoi une seule transaction

    Tout, ou rien. Une réparation à moitié faite laisserait la base dans un état
    que le relevé suivant décrirait mal.

    ## Pourquoi les clés restent DÉSACTIVÉES pendant l'opération

    Réparer une ligne orpheline ne viole aucune contrainte — mais deux
    orphelines peuvent se référencer l'une l'autre, et l'ordre deviendrait alors
    significatif.

    ⚠️ Le PRAGMA est reposé dans un `finally` : il vaut pour la CONNEXION, et la
    laisser modifiée contaminerait tout ce qui la réutilise. C'est le piège qui a
    désarmé la suite de tests entière le 30/08/2026.
    """
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            lignes = conn.execute(text("PRAGMA foreign_key_check")).fetchall()
            if not lignes:
                return {"ok": True, "inconnu": False, "simule": simuler,
                        "supprimees": 0, "deliees": 0, "par_table": []}

            remedes = _remedes(conn, lignes)
            par_table = Counter((t, r) for t, _rowid, _c, r in remedes)
            resume = [{"table": t, "remede": r, "lignes": n}
                      for (t, r), n in sorted(par_table.items(), key=lambda x: -x[1])]
            a_supprimer = sum(1 for _t, _r, _c, r in remedes if r == "suppression")
            a_delier = len(remedes) - a_supprimer

            if simuler:
                return {"ok": True, "inconnu": False, "simule": True,
                        "supprimees": 0, "deliees": 0,
                        "seraient_supprimees": a_supprimer,
                        "seraient_deliees": a_delier,
                        "par_table": resume}

            etat_cles = conn.execute(text("PRAGMA foreign_keys")).scalar()
            try:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                for table, rowid, cols, remede in remedes:
                    #  Les noms de table et de colonne viennent des métadonnées de
                    #  SQLite, pas d'une entrée utilisateur — ils sont quand même
                    #  encadrés par des guillemets doubles, et le rowid passe en
                    #  PARAMÈTRE LIÉ. Aucune valeur d'appelant n'entre ici.
                    if remede == "deliaison":
                        mise_a_null = ", ".join(f'"{c}" = NULL' for c in cols)
                        conn.execute(
                            text(f'UPDATE "{table}" SET {mise_a_null} WHERE rowid = :r'),
                            {"r": rowid},
                        )
                    else:
                        conn.execute(
                            text(f'DELETE FROM "{table}" WHERE rowid = :r'), {"r": rowid}
                        )
                conn.commit()
            finally:
                #  Rétablir l'état d'ORIGINE, pas « ON » : forcer ON ici changerait
                #  le régime de la connexion à l'insu de tout le monde.
                conn.execute(text(f"PRAGMA foreign_keys={'ON' if etat_cles else 'OFF'}"))
                conn.commit()

            #  🔴 La trace, sans laquelle l'incident du 31/08/2026 n'aurait pas pu
            #  être diagnostiqué. Aucun rowid, aucun contenu : table, remède, compte.
            for e in resume:
                logger.warning(
                    "Integrite — %s : %d ligne(s) en %s",
                    e["table"], e["lignes"], e["remede"],
                )

            return {"ok": True, "inconnu": False, "simule": False,
                    "supprimees": a_supprimer, "deliees": a_delier,
                    "par_table": resume}
    except Exception as exc:  # pragma: no cover - éprouvé par un moteur simulé
        #  INCONNU, jamais « 0 traitée » : une réparation qui échoue à mi-chemin
        #  doit se dire, sinon l'appelant croirait la base assainie.
        return {"ok": False, "inconnu": True, "erreur": str(exc)}
