"""Configuration pytest — variables d'environnement minimales avant import de l'app.

L'import de `app.config` exige un SECRET_KEY ≥ 32 caractères et `app.database`
instancie un engine depuis `database_url`. On fournit des valeurs neutres pour
que les tests s'exécutent sans .env ni base réelle (aucun test ici ne se
connecte à la base : ils lisent les templates et la chaîne de migrations).
"""
import os
import tempfile

os.environ.setdefault("SECRET_KEY", "x" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_API_DOCS", "false")

#  Importer `app.main` monte `/uploads` en statique et crée le répertoire au
#  passage. Sans redirection, ce `mkdir` vise un chemin absolu de conteneur —
#  il échoue sur un poste Windows comme sur un exécuteur d'intégration continue,
#  et rendait l'application entière intestable. Cf. tests/test_demarrage.py.
os.environ.setdefault(
    "UPLOADS_DIR", os.path.join(tempfile.gettempdir(), "hostachy-tests-uploads")
)

import pytest  # noqa: E402  (après les variables d'environnement, par construction)


# ── Intégrité référentielle DANS LES TESTS (#546, étape 2) ────────────────────
#
#  🔴 SQLite laisse `foreign_keys` à OFF par défaut, et l'application ne le pose
#  nulle part : AUCUNE des 119 clés étrangères déclarées dans les modèles n'est
#  vérifiée par la base. L'intégrité repose entièrement sur le code applicatif.
#
#  L'activer ici, et ici SEULEMENT, fait deux choses que le ticket demande dans
#  cet ordre :
#
#    • ça mesure — la suite passait de 798 verts à 103 erreurs, toutes des
#      `FOREIGN KEY constraint failed`, et AUCUNE venant d'un chemin de
#      production : ce sont les fixtures qui construisaient des lignes
#      orphelines (`auteur_id=1` sans utilisateur 1, `copropriete_id` NULL…) ;
#    • ça verrouille — une fixture qui décrit un monde impossible teste contre
#      elle-même, et rien ne le disait puisque rien ne vérifiait.
#
#  ⚠️ La PRODUCTION reste à `foreign_keys=OFF` : l'activer là-bas rendrait
#  bloquantes des suppressions aujourd'hui silencieuses, et il faut d'abord
#  décider l'`ON DELETE` des onze relations concernées — cascade, `SET NULL` ou
#  refus. C'est une décision fonctionnelle (#546 étape 3), pas un réglage.
#
#  ⚠️ L'écouteur est posé sur `connect`, seul point qui couvre TOUTES les
#  connexions du pool. Le poser sur une connexion d'amorçage rendue au pool ne
#  marche pas : l'événement n'est alors plus jamais émis — piège vérifié en
#  instruisant ce ticket, et le relevé disait encore `foreign_keys = 0` avec
#  l'écouteur en place, six lignes trop bas.
def _activer_cles_etrangeres() -> None:
    from sqlalchemy import event

    from app.database import engine

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, _record):  # pragma: no cover - branché par SQLAlchemy
        curseur = dbapi_connection.cursor()
        curseur.execute("PRAGMA foreign_keys=ON")
        curseur.close()

    #  🔴 SANS CE `dispose()`, L'ÉCOUTEUR NE SERT À RIEN — et la suite reste
    #  VERTE, ce qui est la pire façon d'échouer. `sqlite:///:memory:` utilise un
    #  `SingletonThreadPool` : une seule connexion, déjà ouverte à l'import de
    #  `app.database`. `connect` n'est donc plus jamais émis, et le PRAGMA n'est
    #  jamais posé. Mesuré ici même :
    #
    #      AVANT                            foreign_keys = 0
    #      APRÈS (connexion recyclée)       foreign_keys = 0   ← l'écouteur est là
    #      APRÈS dispose (connexion NEUVE)  foreign_keys = 1
    #
    #  C'est le piège que #546 décrit pour la production, rencontré ici en le
    #  reproduisant. Recycler la connexion force le prochain `connect`.
    engine.dispose()


def pytest_configure(config):  # noqa: ARG001
    #  ⚠️ DÉSACTIVÉ PAR DÉFAUT, et ce n'est pas une timidité : avec les clés
    #  actives, la suite passe de 798 verts à **83 erreurs et 4 échecs** — toutes
    #  des fixtures qui construisent des lignes orphelines, aucune venant d'un
    #  chemin de production. Les rendre valides est l'étape 2 de #546, un lot à
    #  part entière ; l'activer ici avant qu'elle soit finie rendrait le job rouge
    #  en permanence, donc désarmé dans la semaine (#419).
    #
    #  Ce que l'interrupteur apporte dès maintenant : la mesure se rejoue en une
    #  commande, sans remettre le montage en place à chaque fois —
    #
    #      HOSTACHY_FK_STRICTES=1 pytest tests/ -q
    #
    #  et `test_integrite_referentielle.py` s'en sert pour verrouiller ce qui est
    #  DÉJÀ réparé, sans attendre que tout le soit.
    if os.environ.get("HOSTACHY_FK_STRICTES") == "1":
        _activer_cles_etrangeres()


# ── Patrimoine de test ────────────────────────────────────────────────────────
#
#  Monter une copropriété de quatre bâtiments et semer l'arbre des périmètres :
#  ce montage était écrit **deux fois** à l'identique (`test_perimetres_arbre.py`
#  et `test_perimetres_router.py`), et un troisième fichier venait d'en avoir
#  besoin (14/08/2026). Une fixture recopiée diverge comme n'importe quel autre
#  code — les deux `_vider` avaient d'ailleurs déjà divergé sur les modèles
#  qu'ils purgent.
#
#  Les imports sont **différés dans le corps** et non en tête de ce fichier :
#  `conftest.py` est chargé avant tous les tests, y compris ceux qui ne touchent
#  jamais la base, et importer l'application ici changerait leur ordre d'import.


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

    for modele in (Batiment, Copropriete):
        for ligne in session.exec(select(modele)).all():
            session.delete(ligne)
    session.commit()


@pytest.fixture()
def batiments() -> list[int]:
    """Arbre semé sur quatre bâtiments réels. Renvoie leurs identifiants."""
    from sqlmodel import Session, SQLModel, select

    from app.database import engine
    from app.models.core import Batiment, Copropriete
    from app.seed.patrimoine import poser_arborescence
    from app.utils import perimetres as P

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session)
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        for numero in ("1", "2", "3", "4"):
            session.add(Batiment(copropriete_id=copro.id, numero=numero))
        session.commit()
        ids = list(session.exec(select(Batiment.id).order_by(Batiment.id)).all())
        poser_arborescence(session)
        session.commit()
    P.invalider_cache()
    yield ids
    #  Le patrimoine repart AUSSI à la sortie. Il ne partait qu'à l'entrée, si
    #  bien que la copropriété et ses quatre bâtiments survivaient au test et
    #  attendaient le suivant : `test_copropriete_fiche.py` supprime toutes les
    #  copropriétés dans sa propre fixture, et SQLAlchemy dénoue alors les
    #  bâtiments orphelins (`UPDATE batiment SET copropriete_id = NULL`) — la
    #  colonne est NOT NULL, six tests tombaient en erreur de montage.
    #  Le défaut ne s'est vu qu'en ajoutant un fichier qui trie AVANT
    #  `test_copropriete_fiche` (15/08/2026) : jusque-là, les deux seuls usagers
    #  de cette fixture passaient après lui. Un test dont le résultat dépend de
    #  l'ordre alphabétique des fichiers n'est pas un test.
    with Session(engine) as session:
        vider_patrimoine(session)
    P.invalider_cache()


@pytest.fixture()
def arbre_vide():
    """Aucun périmètre configuré — l'état d'une copropriété qui n'a rien saisi.

    C'est un état **valide** et non une panne : le produit doit servir une
    copropriété qui n'a ni AFUL, ni quatre bâtiments. Tout ce qui lit l'arbre doit
    donc se comporter correctement quand il est vide.
    """
    from sqlmodel import Session, SQLModel

    from app.database import engine
    from app.utils import perimetres as P

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session)
    P.invalider_cache()
    yield
    P.invalider_cache()


# ── Où vivent les scripts versionnés ─────────────────────────────────────────
#
#  Quatre tests scannaient les scripts, chacun avec son propre `RACINE.glob("*.sh")`.
#  Le rangement du 15/08/2026 (#337) a déplacé l'outillage du poste dans
#  `scripts/poste/` : les quatre globs ont cessé de le voir **en même temps**, et
#  trois d'entre eux sont devenus faux sans rien dire de compréhensible — « aucun
#  script ne poste export_hors_site », « endpoint orphelin ».
#
#  La leçon n'est pas « corriger quatre chemins » mais « il n'y en avait pas un
#  seul » (`standards/02-factorisation.md`). La portée du scan est une notion :
#  elle s'écrit ici, et les tests la lisent.

def racine_depot():
    from pathlib import Path
    return Path(__file__).resolve().parents[2]


def scripts_shell_versionnes() -> list:
    """Tous les `.sh` du dépôt, où qu'ils soient rangés — plus les hooks git.

    Les scripts d'exploitation (cron) sont restés à la racine : leurs chemins
    absolus vivent dans des crontabs non versionnés, que ce dépôt ne peut pas
    mettre à jour tout seul. Cette fonction ne fait aucune hypothèse là-dessus,
    et c'est le but : elle survivra au jour où ils bougeront.
    """
    racine = racine_depot()
    trouves = list(racine.glob("*.sh"))
    trouves += list(racine.glob("scripts/**/*.sh"))
    trouves += [p for p in racine.glob(".githooks/*") if p.is_file()]
    return sorted(set(trouves))
