"""Purge de la base de test — les helpers partagés par la conftest et les tests.

Sortis de `conftest.py` le 28/08/2026 (#546) : un module de conftest n'est **pas
importable** par un test (`ModuleNotFoundError: No module named 'conftest'`), si
bien qu'un fichier qui avait besoin de `vider_patrimoine` en gardait une COPIE —
et cette copie avait divergé, comme la conftest le prédisait elle-même.

Ils vivent donc ici, importables par les deux.
"""

def delier_references(session, modele) -> int:
    """Met à NULL toutes les colonnes NULLABLES qui pointent vers `modele`.

    Les colonnes sont **déduites des métadonnées SQLModel**, jamais énumérées :
    une liste tenue à la main diverge au premier champ ajouté, et c'est justement
    celui-là qui manquerait (`standards/05` §9).

    ⚠️ **Les colonnes NOT NULL sont laissées telles quelles, et c'est délibéré.**
    On ne peut pas les délier ; les porteurs doivent partir avant. Le taire
    donnerait une purge qui « marche » jusqu'au jour où la clé mord — et le
    diagnostic serait alors à refaire. Le compte rendu permet à l'appelant de
    savoir ce qui a bougé.

    @returns le nombre de lignes déliées.
    """
    from sqlalchemy import update
    from sqlmodel import SQLModel

    cible = modele.__tablename__
    deliees = 0
    for table in SQLModel.metadata.tables.values():
        for colonne in table.columns:
            if not colonne.nullable:
                continue
            if not any(fk.column.table.name == cible for fk in colonne.foreign_keys):
                continue
            resultat = session.exec(
                update(table).where(colonne.isnot(None)).values({colonne.name: None})
            )
            deliees += resultat.rowcount or 0
    session.commit()
    return deliees


def purger_referentiellement(session, modele) -> int:
    """Supprime TOUTES les lignes de `modele`, avec ce qui en dépend.

    🔴 Elle appelle `app.utils.purge_referentielle.purger` — **le code de
    production**, celui qui sert à supprimer un compte depuis l'administration.
    Les fixtures réécrivaient cette logique à la main, et c'est ce qui produisait
    la moitié des refus de clés étrangères (#546) : `DELETE FROM utilisateur`
    (16 refus) et `UPDATE publication` (13, tentative de délier une colonne
    `NOT NULL`).

    Le module lit les MÉTADONNÉES : une table créée demain est traitée sans
    qu'on y pense. C'est précisément ce qu'une purge écrite à la main ne peut pas
    faire — `supprimer_utilisateur` en énumérait onze familles quand le modèle en
    comptait cinquante-six.

    ⚠️ Il ne fait pas de `commit` : c'est l'appelant qui décide de la
    transaction. On le fait ici, la fixture n'ayant rien à annuler ensuite.

    @returns le nombre de lignes supprimées, toutes tables confondues.
    """
    from sqlmodel import select

    from app.utils.purge_referentielle import purger

    total = 0
    for ligne in session.exec(select(modele)).all():
        for compte in purger(session, modele.__tablename__, ligne.id).values():
            total += compte
    session.commit()
    return total


def vider_perimetres(session) -> None:
    """Vide `perimetre` en respectant son AUTO-RÉFÉRENCE (`parent_id`).

    🔴 `session.exec(delete(Perimetre))` ne marche pas : la table se référence
    elle-même, et supprimer tous les nœuds d'un coup viole la clé sur les enfants
    dès que `foreign_keys=ON`. Quatre fixtures l'écrivaient ainsi (#546), et rien
    ne le signalait tant que SQLite ne vérifiait rien.

    On efface PAR VAGUES, des feuilles vers la racine : à chaque tour, les nœuds
    dont plus personne n'est l'enfant. C'est la seule façon correcte sans
    connaître la profondeur de l'arbre, qui est une donnée administrée.

    ⚠️ ET IL FAUT SAVOIR DÉFAIRE UN CYCLE. `test_cycle_de_parente_…` en crée un
    volontairement — c'est son sujet. Une purge par vagues n'y trouve alors plus
    aucune feuille et tournerait indéfiniment. On délie donc les restants avant
    de les effacer : une fixture de purge n'a pas le droit de supposer des
    données saines, elle s'exécute précisément après les tests qui les abîment.
    """
    from sqlmodel import select

    from app.models.perimetre import Perimetre

    restants = session.exec(select(Perimetre)).all()
    while restants:
        parents = {p.parent_id for p in restants if p.parent_id is not None}
        feuilles = [p for p in restants if p.id not in parents]
        if not feuilles:
            for noeud in restants:
                noeud.parent_id = None
                session.add(noeud)
            session.commit()
            feuilles = restants
        for feuille in feuilles:
            session.delete(feuille)
        session.commit()
        restants = session.exec(select(Perimetre)).all()


def vider_patrimoine(session, modeles_sup=()) -> None:
    """Purge copropriété, bâtiments et périmètres — plus les modèles demandés.

    Le marqueur de semis part avec : sans lui, `poser_arborescence` se croirait
    déjà passée et laisserait les tests sur une base vide.
    """
    from sqlmodel import select

    from app.models.core import Batiment, ConfigSite, Copropriete
    from app.models.perimetre import Perimetre
    from app.seed.patrimoine import CLE_SEMEE

    marqueur = session.get(ConfigSite, CLE_SEMEE)
    if marqueur:
        session.delete(marqueur)
    #  🔴 `purger_referentiellement` et non `session.delete` : supprimer une ligne
    #  sans ce qui la référence est exactement ce que les clés étrangères
    #  refusent (#546). Le module de production sait le faire, et il lit les
    #  métadonnées — la fixture n'a pas à connaître le graphe.
    for modele in modeles_sup:
        purger_referentiellement(session, modele)

    #  Les périmètres partent par vagues — voir `vider_perimetres`, qui porte
    #  la raison et le cas du cycle.
    vider_perimetres(session)

    #  🔴 Les bâtiments sont référencés par ONZE colonnes — utilisateur, ticket,
    #  document, lot, publication, événement, contrat, devis, membre CS, périmètre,
    #  demande de modification. La purge les effaçait sans s'en soucier : c'est la
    #  famille la plus nombreuse du relevé de #546, **132 violations**.
    #
    #  Les onze sont NULLABLES : on délie, on ne supprime pas. Supprimer les
    #  porteurs serait faux — un ticket ne cesse pas d'exister parce que le
    #  patrimoine de test est démonté, et une fixture qui l'effacerait retirerait
    #  des données que le test suivant attend peut-être.
    #
    #  ⚠️ La liste des colonnes est DÉDUITE des métadonnées, jamais écrite ici :
    #  une liste tenue à la main diverge au premier champ ajouté, et c'est
    #  justement le champ ajouté qui manquerait (`standards/05` §9).
    delier_references(session, Batiment)
    for ligne in session.exec(select(Batiment)).all():
        session.delete(ligne)
    session.commit()

    #  Les trois colonnes qui pointent vers `copropriete` sont NOT NULL : on ne
    #  peut pas les délier. Les porteurs (bâtiment, contrat, devis) doivent donc
    #  partir avant — les bâtiments viennent de le faire ; les deux autres ne sont
    #  pas montés par cette fixture, et le jour où ils le seraient, la clé le dira
    #  au lieu de laisser une ligne orpheline en silence.
    for ligne in session.exec(select(Copropriete)).all():
        session.delete(ligne)
    session.commit()


