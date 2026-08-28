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
    for modele in modeles_sup:
        for ligne in session.exec(select(modele)).all():
            session.delete(ligne)
    session.commit()

    #  🔴 `Perimetre` S'AUTO-RÉFÉRENCE (`parent_id`), donc l'ordre de suppression
    #  compte : effacer un nœud avant ses enfants viole la clé étrangère. Ce n'était
    #  visible d'aucune façon tant que SQLite tournait avec `foreign_keys=OFF` — la
    #  purge se faisait dans un ordre arbitraire, et la base l'acceptait (#546).
    #
    #  On efface donc PAR VAGUES, des feuilles vers la racine : à chaque tour, les
    #  nœuds dont plus personne n'est l'enfant. C'est la seule façon correcte sans
    #  connaître la profondeur de l'arbre, qui est une donnée administrée.
    #
    #  ⚠️ ET IL FAUT SAVOIR DÉFAIRE UN CYCLE. `test_cycle_de_parente_…` en crée un
    #  volontairement — c'est son sujet : vérifier que la lecture de l'arbre ne
    #  boucle pas dessus. Une purge par vagues n'y trouve alors plus aucune
    #  feuille et tournerait indéfiniment. On délie donc les restants
    #  (`parent_id = NULL`) avant de les effacer : c'est le seul geste qui rende
    #  la base propre quel que soit l'état où un test l'a laissée.
    #
    #  Une fixture de purge n'a pas le droit de supposer des données saines — elle
    #  s'exécute précisément après les tests qui les abîment exprès.
    restants = session.exec(select(Perimetre)).all()
    while restants:
        parents = {p.parent_id for p in restants if p.parent_id is not None}
        feuilles = [p for p in restants if p.id not in parents]
        if not feuilles:
            #  Plus aucune feuille : il ne reste que des cycles. On les délie.
            for noeud in restants:
                noeud.parent_id = None
                session.add(noeud)
            session.commit()
            feuilles = restants
        for feuille in feuilles:
            session.delete(feuille)
        session.commit()
        restants = session.exec(select(Perimetre)).all()

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


