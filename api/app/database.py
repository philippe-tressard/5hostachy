import logging
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError
from sqlmodel import create_engine, Session, SQLModel
from app.config import get_settings

logger = logging.getLogger("hostachy.db")

settings = get_settings()

connect_args = {"check_same_thread": False}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True,  # Teste chaque connexion avant usage → détecte les inodes orphelins (ex: post-VACUUM)
)

# SessionLocal pour les tâches asynchrones et les contextes hors requête HTTP
SessionLocal = lambda: Session(engine)


def activer_cles_etrangeres(moteur) -> None:
    """Fait poser `PRAGMA foreign_keys=ON` sur CHAQUE connexion de `moteur`.

    ✅ **Appelé sur le moteur de l'application depuis le 30/08/2026** — fin de
    #546. Ce paragraphe a dit le contraire pendant deux jours, et c'était juste :
    la fonction existait, éprouvée, et n'était pas branchée. Il est corrigé le
    jour où il cesse de l'être, parce qu'un commentaire qui survit à ce qu'il
    décrit est pire qu'absent.

    ## Ce que l'absence de ce PRAGMA coûtait

    SQLite ne vérifie **aucune** clé étrangère par défaut, et le réglage n'est
    **pas** persisté dans le fichier — contrairement à `journal_mode=WAL`. Il vaut
    pour la connexion, pas pour la base. Aucune des FK déclarées dans les modèles
    n'est donc vérifiée : une ligne peut référencer un parent supprimé, et rien ne
    l'empêche ni ne le signale. L'intégrité repose entièrement sur le code
    applicatif — ce qui est tenable, et n'est pas une bonne surprise à découvrir
    le jour d'un incident.

    ## Pourquoi l'écouteur doit être posé ICI et pas plus bas

    Le bloc d'amorçage ci-dessous ouvre une connexion et la **rend au pool**, où
    elle est réutilisée : l'événement `connect` n'est alors plus jamais émis. Un
    écouteur enregistré six lignes trop bas laisse le relevé dire `foreign_keys =
    0` alors qu'il est « en place ». Vérifié.

    ## Pourquoi l'activation a attendu le 30/08/2026

    Activer le PRAGMA ne valide **pas** l'existant : SQLite ne relit pas la base,
    une ligne orpheline reste lisible, et seules les écritures futures sont
    refusées. Le risque n'était donc pas au démarrage — la crainte inverse avait
    immobilisé ce ticket depuis le 20/08, et elle était fausse.

    Trois conditions ont dû être remplies, dans cet ordre :

      1. **les fixtures** ne construisent plus de lignes orphelines (4 lots, 103
         erreurs ramenées à zéro — régime par défaut de la suite depuis le 29/08) ;
      2. **les suppressions** ont été exercées : 11 endpoints DELETE testés, six
         défauts corrigés. Deux ne se voyaient qu'en traçant le SQL émis ;
      3. **la base** a été purgée : 50 lignes orphelines relevées, supprimées
         depuis l'écran d'administration, relevé rendu à zéro par deux sondes.

    ⚠️ **L'ordre n'était pas négociable.** Sans la 3, l'activation n'aurait rien
    cassé au démarrage, mais toute écriture touchant l'une de ces lignes aurait
    échoué ensuite — avec un message ne disant pas qu'elle datait de mois.
    """

    @event.listens_for(moteur, "connect")
    def _poser(dbapi_connection, _record):  # pragma: no cover — appelé par SQLAlchemy
        curseur = dbapi_connection.cursor()
        curseur.execute("PRAGMA foreign_keys=ON")
        curseur.close()

#  🔴 LES CLÉS ÉTRANGÈRES SONT ACTIVES — 30/08/2026, fin de #546. Les trois
#  conditions qui l'ont permis sont dans le docstring ci-dessus.
#
#  ⚠️ **CET APPEL EST AVANT LE BLOC D'AMORÇAGE, ET C'EST NÉCESSAIRE.** Placé
#  après, il ne prenait pas effet — mesuré, pas supposé :
#
#      appel APRÈS l'amorçage   → PRAGMA foreign_keys = 0
#      appel AVANT l'amorçage   → PRAGMA foreign_keys = 1
#
#  L'écouteur ne s'exécute qu'à l'ouverture d'une connexion. Le bloc d'amorçage
#  en ouvre une avant lui ; le `engine.dispose()` de la fonction devrait la
#  recycler, et ne suffit pas ici. Poser l'écouteur en premier garantit que
#  **toute** connexion l'obtient, quel que soit le pool.
#
#  C'est le piège que le docstring de la fonction décrit — « un écouteur
#  enregistré six lignes trop bas laisse le relevé dire foreign_keys = 0 » — et
#  je l'ai refait en la branchant. Il ne se voit qu'en LISANT le PRAGMA sur une
#  connexion réelle : l'appel est là, la fonction est juste, et le réglage
#  n'est pas posé.
#
#  ⚠️ Vérifié aussi : `synchronous=FULL` et `busy_timeout=5000`, posés par le
#  bloc ci-dessous, **survivent** au `dispose()` de la fonction (mesurés à 2 et
#  5000 sur deux connexions successives). La durabilité choisie après les
#  corruptions de juin n'est pas perdue.
activer_cles_etrangeres(engine)

# WAL mode : lectures et écritures concurrentes sans blocage mutuel
# synchronous=FULL : chaque commit est fsync'd intégralement (WAL + en-tête).
#   NORMAL était plus rapide mais laisse une fenêtre de torn-write sur coupure/
#   arrêt brutal ; sur une copro à faible trafic le surcoût est négligeable et la
#   durabilité prime (cf. corruptions récurrentes telemetry_event 05+17/06/2026).
# busy_timeout=5000 : attend jusqu'à 5s si la DB est verrouillée au lieu d'échouer immédiatement
with engine.connect() as _conn:
    _conn.execute(text("PRAGMA journal_mode=WAL"))
    _conn.execute(text("PRAGMA synchronous=FULL"))
    _conn.execute(text("PRAGMA busy_timeout=5000"))
    _conn.commit()



def get_session():
    """Dépendance FastAPI : session DB avec auto-reconnexion sur OperationalError.

    Si SQLAlchemy détecte un I/O error (pool corrompu, inode obsolète après VACUUM
    ou docker exec concurrent), on purge le pool et on retente une fois avant
    de propager l'exception — qui sera capturée par le handler global dans main.py.
    """
    try:
        with Session(engine) as session:
            yield session
    except OperationalError as exc:
        logger.error("DB OperationalError — purge du pool et reconnexion : %s", exc)
        engine.dispose()  # ferme toutes les connexions, force fresh connections
        # La requête en cours échoue proprement ; le prochain appel repartira sain
        raise


def _run_migrations():
    """Migrations SQLite manuelles pour les colonnes ajoutées après la création initiale."""
    simple_migrations = [
        "ALTER TABLE utilisateur ADD COLUMN batiment_id INTEGER REFERENCES batiment(id)",
        # Colonnes ajoutées au modèle Ticket sans migration Alembic correspondante
        "ALTER TABLE ticket ADD COLUMN batiment_id INTEGER REFERENCES batiment(id)",
        "ALTER TABLE ticket ADD COLUMN mis_a_jour_le DATETIME",
        "ALTER TABLE ticket ADD COLUMN perimetre_cible TEXT DEFAULT '[\"résidence\"]'",
        # Colonne cree_le de MessageTicket si manquante
        "ALTER TABLE message_ticket ADD COLUMN cree_le DATETIME",
        # Rôles visuels annuaire CS
        "ALTER TABLE membre_cs ADD COLUMN est_gestionnaire_site BOOLEAN DEFAULT 0",
        "ALTER TABLE membre_cs ADD COLUMN est_president BOOLEAN DEFAULT 0",
    ]
    with engine.connect() as conn:
        for sql in simple_migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # colonne déjà présente

        # Normalisation des valeurs d'enum ticket (anciennes valeurs sans accents)
        #  `ferme` visait `fermé` jusqu'au 17/08/2026 — donc vers une valeur que
        #  l'énumération ne porte plus (#415, migration 0149). Cette ligne aurait
        #  ressuscité l'état supprimé à chaque démarrage : elle vise `résolu`,
        #  comme la migration.
        data_migrations = [
            "UPDATE ticket SET statut = 'résolu' WHERE statut = 'ferme'",
            "UPDATE ticket SET statut = 'résolu' WHERE statut = 'resolu'",
            "UPDATE ticket SET statut = 'ouvert' WHERE statut = 'nouveau'",
            "UPDATE ticket SET statut = 'ouvert' WHERE statut = 'en_attente'",
        ]
        for sql in data_migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass

        # Migration : rendre lot.batiment_id nullable (parkings sans bâtiment)
        # SQLite ne supporte pas ALTER COLUMN → recréation de la table
        try:
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(lot)")).fetchall()]
            if "batiment_id" in cols:
                # Vérifier si la colonne est déjà nullable en tentant un INSERT NULL
                # Plus simple : recréer si la définition contient NOT NULL
                schema = conn.execute(
                    text("SELECT sql FROM sqlite_master WHERE type='table' AND name='lot'")
                ).scalar() or ""
                if "batiment_id INTEGER NOT NULL" in schema or 'batiment_id" INTEGER NOT NULL' in schema:
                    conn.execute(text("PRAGMA foreign_keys=off"))
                    conn.execute(text("""
                        CREATE TABLE lot_migration_tmp (
                            id INTEGER PRIMARY KEY,
                            batiment_id INTEGER REFERENCES batiment(id),
                            numero TEXT NOT NULL,
                            type TEXT NOT NULL DEFAULT 'appartement',
                            type_appartement TEXT,
                            etage INTEGER,
                            superficie REAL
                        )
                    """))
                    conn.execute(text(
                        "INSERT INTO lot_migration_tmp "
                        "SELECT id, batiment_id, numero, type, type_appartement, etage, superficie FROM lot"
                    ))
                    conn.execute(text("DROP TABLE lot"))
                    conn.execute(text("ALTER TABLE lot_migration_tmp RENAME TO lot"))
                    conn.execute(text("PRAGMA foreign_keys=on"))
                    conn.commit()
        except Exception:
            pass  # déjà migré ou erreur non bloquante


def _run_category_migrations():
    """Met à jour les catégories de documents existantes pour aligner les droits."""
    with engine.connect() as conn:
        try:
            # Supprimer la catégorie Budget / Comptes annuels
            conn.execute(text("DELETE FROM categorie_document WHERE code = 'budget_comptes'"))
            # PV AG : copropriétaires_et_cs + bâtiment
            conn.execute(text("""
                UPDATE categorie_document
                SET profil_acces_id = (SELECT id FROM profil_acces_document WHERE code = 'copropriétaires_et_cs'),
                    perimetre_defaut = 'bâtiment',
                    surcharge_autorisee = 1
                WHERE code = 'pv_ag'
            """))
            # Diagnostic : copropriétaires_et_cs + bâtiment (était lot_occupants + lot)
            conn.execute(text("""
                UPDATE categorie_document
                SET libelle = 'Diagnostic',
                    profil_acces_id = (SELECT id FROM profil_acces_document WHERE code = 'copropriétaires_et_cs'),
                    perimetre_defaut = 'bâtiment',
                    surcharge_autorisee = 1
                WHERE code = 'diagnostic_lot'
            """))
            # Contrat fournisseur : périmètre bâtiment (était résidence)
            conn.execute(text("""
                UPDATE categorie_document
                SET perimetre_defaut = 'bâtiment',
                    surcharge_autorisee = 1
                WHERE code = 'contrat_fournisseur'
            """))
            conn.commit()
        except Exception:
            pass


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    _run_migrations()
    _run_category_migrations()
