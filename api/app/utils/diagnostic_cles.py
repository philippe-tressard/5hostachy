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


def purger_orphelins(engine, *, simuler: bool = True) -> dict:
    """Supprimer les lignes qui référencent un parent disparu.

    ## 🔴 SIMULATION PAR DÉFAUT, et ce n'est pas une politesse

    `simuler=True` rend exactement ce qui SERAIT supprimé, sans rien toucher.
    L'appelant doit demander la suppression explicitement. Une opération
    irréversible dont le mode destructeur est le défaut finit par s'exécuter par
    accident — au premier appel de vérification, au premier rechargement d'un
    écran.

    ## Ce qu'elle supprime, et rien d'autre

    **Uniquement les `rowid` que `PRAGMA foreign_key_check` désigne.** Pas une
    requête « toutes les lignes dont le parent est absent » réécrite à la main :
    c'est SQLite qui dit lesquelles, et on lui obéit ligne par ligne.

    La différence n'est pas théorique. Une jointure écrite à la main se trompe
    sur les clés composites, sur les colonnes nullables (`NULL` ne référence
    rien, donc n'est jamais orpheline), et sur les tables sans clé primaire
    déclarée. Le PRAGMA, lui, applique la définition du moteur.

    ⚠️ **Le `rowid` ne sort jamais de cette fonction** : il sert à supprimer,
    il n'est pas rendu. Le canal des scripts est borné à « aucune donnée de
    copropriétaire », et un rowid désigne une ligne précise.

    ## Pourquoi une seule transaction

    Toutes les suppressions, ou aucune. Une purge à moitié faite laisserait la
    base dans un état que le relevé suivant décrirait mal, et il n'y a aucune
    raison de la fractionner : on parle de dizaines de lignes, pas de millions.

    ## Pourquoi les clés restent DÉSACTIVÉES pendant l'opération

    Supprimer une ligne orpheline ne viole aucune contrainte — mais deux
    orphelines peuvent se référencer l'une l'autre, et l'ordre des suppressions
    deviendrait alors significatif. On ne s'impose pas cette contrainte pour
    retirer des lignes qui, par définition, ne sont plus référencées par rien de
    valide.

    ⚠️ Le PRAGMA est reposé dans un `finally` : il vaut pour la CONNEXION, et
    la laisser modifiée contaminerait tout ce qui la réutilise ensuite. C'est le
    piège qui a désarmé la suite de tests entière le 30/08/2026.
    """
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            lignes = conn.execute(text("PRAGMA foreign_key_check")).fetchall()
            if not lignes:
                return {"ok": True, "inconnu": False, "simule": simuler,
                        "supprimees": 0, "par_table": []}

            #  Ce qui SERAIT (ou vient d'être) supprimé, par table — le compte
            #  que l'appelant lit, avant comme après.
            par_table = Counter(ligne[0] for ligne in lignes)
            resume = [{"table": t, "lignes": n}
                      for t, n in sorted(par_table.items(), key=lambda x: -x[1])]

            if simuler:
                return {"ok": True, "inconnu": False, "simule": True,
                        "supprimees": 0, "seraient_supprimees": len(lignes),
                        "par_table": resume}

            etat_cles = conn.execute(text("PRAGMA foreign_keys")).scalar()
            try:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                for table, rowid, _parent, _fkid in lignes:
                    #  Le nom de table vient des métadonnées de SQLite, pas d'une
                    #  entrée utilisateur — mais il est quand même encadré par des
                    #  guillemets doubles, et le rowid passe en PARAMÈTRE LIÉ.
                    #  Aucune valeur d'appelant n'entre dans cette requête.
                    conn.execute(
                        text(f'DELETE FROM "{table}" WHERE rowid = :r'), {"r": rowid}
                    )
                conn.commit()
            finally:
                #  Rétablir l'état d'ORIGINE, pas « ON » : la production tourne
                #  encore à OFF, et forcer ON ici changerait le régime de la
                #  connexion à l'insu de tout le monde.
                conn.execute(text(f"PRAGMA foreign_keys={'ON' if etat_cles else 'OFF'}"))
                conn.commit()

            return {"ok": True, "inconnu": False, "simule": False,
                    "supprimees": len(lignes), "par_table": resume}
    except Exception as exc:  # pragma: no cover - éprouvé par un moteur simulé
        #  INCONNU, jamais « 0 supprimée » : une purge qui échoue à mi-chemin
        #  doit se dire, sinon l'appelant croirait la base assainie.
        return {"ok": False, "inconnu": True, "erreur": str(exc)}
