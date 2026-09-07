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


def purger_ligne(session, modele, ligne_id) -> int:
    """Supprime UNE ligne et tout ce qui en dépend, par le code de production.

    🔴 Le pendant de `purger_referentiellement` pour un démontage ciblé. Les
    fixtures écrivaient `session.delete(session.get(Modele, id))` — vingt et une
    fois — ce qui supprime la ligne SANS ce qui la référence. Tant que SQLite ne
    vérifiait rien, ces purges « marchaient » ; sous `foreign_keys=ON` elles
    refusent, et c'est le bon comportement (#546).

    ⚠️ Une fixture ne doit pas énumérer les dépendances : `purge_referentielle`
    lit les MÉTADONNÉES, donc une table créée demain est traitée sans qu'on y
    pense. C'est exactement ce qu'une liste tenue à la main ne sait pas faire —
    et le motif que ce ticket corrige partout ailleurs.

    ⚠️ Tolère une ligne déjà absente : un démontage s'exécute après le test, y
    compris quand celui-ci a lui-même supprimé l'objet. Lever ici masquerait
    l'échec réel derrière une erreur de nettoyage.

    @returns le nombre de lignes supprimées, toutes tables confondues.
    """
    from app.utils.purge_referentielle import purger

    if ligne_id is None or session.get(modele, ligne_id) is None:
        return 0
    total = sum(purger(session, modele.__tablename__, ligne_id).values())
    session.commit()
    return total


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



def monter_batiments(session, numeros=("1", "2", "3", "4")) -> list:
    """Monte une copropriété et ses bâtiments. Rend leurs identifiants, dans l'ordre.

    🔴 Les fixtures posaient des `Perimetre(batiment_id=3)` sur des bâtiments
    qui n'existaient pas — neuf violations de clé étrangère sous
    `foreign_keys=ON` (#546). Elles ne pouvaient pas faire autrement sans
    recopier le montage, qui vit dans la fixture `batiments` de la conftest et
    n'est pas atteignable depuis un test.

    ⚠️ Le montage NE SÈME PAS l'arborescence : c'est ce qui le distingue de la
    fixture `batiments`, et c'est ce dont ces tests ont besoin — ils construisent
    leur propre arbre, et un arbre semé par-dessus fausserait ce qu'ils mesurent.

    ⚠️ **Les identifiants sont RENDUS, jamais devinés.** Une fixture qui écrivait
    `batiment_id=3` pariait sur l'auto-incrément d'une base vide : le pari tient
    tant que le fichier tourne seul, et casse le jour où un autre test a créé un
    bâtiment avant. Le rendre supprime la question.
    """
    from sqlmodel import select

    from app.models.core import Batiment, Copropriete

    copro = session.exec(select(Copropriete)).first()
    if not copro:
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
    ids = []
    for numero in numeros:
        bat = Batiment(copropriete_id=copro.id, numero=str(numero))
        session.add(bat)
        session.flush()
        ids.append(bat.id)
    session.commit()
    return ids

def etat_invalide(session):
    """Suspend la vérification des clés le temps d'un bloc. À n'employer QUE pour
    fabriquer l'état corrompu qu'un test a précisément pour sujet.

    ```python
    with etat_invalide(session):
        session.add(Perimetre(code="orphelin", parent_id=999_999))
        session.commit()
    ```

    🔴 Trois tests du dépôt éprouvent la ROBUSTESSE face à une donnée que la base
    ne devrait pas contenir : un `parent_id` qui ne pointe sur rien, une affiche
    dont la publication a disparu. C'est leur objet — vérifier que la remontée
    s'arrête sans lever, que l'écran ne rend pas 500. Sous `foreign_keys=ON` ces
    lignes deviennent impossibles à créer, et les tests tombaient au montage.

    ⚠️ **La tentation était de les supprimer**, et c'eût été le pire choix : on
    aurait retiré les contrôles qui protègent d'une corruption au moment même où
    l'on active le mécanisme censé la prévenir. Or la production tourne encore à
    `foreign_keys=OFF` (#546 étape 3), les bases existantes portent peut-être
    déjà de telles lignes, et le PRAGMA ne relit pas l'existant : le code doit
    survivre à ce qu'il rencontrera.

    ⚠️ **C'est une porte, donc elle se voit.** Le nom la nomme, l'appel est
    local, et le PRAGMA est rétabli même si le bloc lève. Une suspension globale
    — un interrupteur de session, un réglage de conftest — aurait désarmé la
    vérification partout sans que personne ne le remarque.

    ⚠️ Sans effet quand les clés ne sont pas actives (le régime par défaut de la
    suite) : le bloc s'exécute alors exactement comme avant.
    """
    from contextlib import contextmanager

    from sqlalchemy import text

    @contextmanager
    def _porte():
        #  On ne peut pas suspendre les clés au milieu d'une transaction : SQLite
        #  ignore le PRAGMA tant qu'une transaction est ouverte, en silence.
        session.commit()
        #  🔴 On RELIT l'état avant de le changer, et c'est ce qui manquait au
        #  premier jet : le `finally` reposait `ON` en dur. La suite tourne à
        #  `OFF` par défaut et partage UNE connexion (`sqlite:///:memory:`,
        #  `SingletonThreadPool`) — cette porte activait donc les clés pour tous
        #  les tests suivants, et un fichier sans rapport échouait selon l'ordre
        #  alphabétique. Un helper qui laisse l'environnement autrement qu'il
        #  l'a trouvé est un helper qui déplace le défaut au lieu de le traiter.
        #  ⚠️ `.one()` rend une `Row`, qui n'est PAS une `tuple` au sens de
        #  `isinstance` — mon premier jet testait le type et gardait la Row,
        #  toujours vraie : la porte reposait donc `ON` dans tous les cas, et le
        #  défaut qu'elle venait de corriger revenait à l'identique.
        actif = session.exec(text("PRAGMA foreign_keys")).one()[0]
        session.exec(text("PRAGMA foreign_keys=OFF"))
        try:
            yield
        finally:
            session.commit()
            session.exec(text(f"PRAGMA foreign_keys={'ON' if actif else 'OFF'}"))

    return _porte()
