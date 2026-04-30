from sqlalchemy import text
from sqlmodel import create_engine, Session, SQLModel
from app.config import get_settings

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

# WAL mode : lectures et écritures concurrentes sans blocage mutuel
# synchronous=NORMAL : sûr en WAL, bien plus rapide que FULL sur SD card
# busy_timeout=5000 : attend jusqu'à 5s si la DB est verrouillée au lieu d'échouer immédiatement
with engine.connect() as _conn:
    _conn.execute(text("PRAGMA journal_mode=WAL"))
    _conn.execute(text("PRAGMA synchronous=NORMAL"))
    _conn.execute(text("PRAGMA busy_timeout=5000"))
    _conn.commit()


def get_session():
    with Session(engine) as session:
        yield session


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
        data_migrations = [
            "UPDATE ticket SET statut = 'fermé'  WHERE statut = 'ferme'",
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
    """Met \u00e0 jour les cat\u00e9gories de documents existantes pour aligner les droits."""
    with engine.connect() as conn:
        try:
            # Supprimer la cat\u00e9gorie Budget / Comptes annuels
            conn.execute(text(
                "DELETE FROM categorie_document WHERE code = 'budget_comptes'"
            ))
            # PV AG : copropri\u00e9taires_et_cs + b\u00e2timent
            conn.execute(text("""
                UPDATE categorie_document
                SET profil_acces_id = (SELECT id FROM profil_acces_document WHERE code = 'copropri\u00e9taires_et_cs'),
                    perimetre_defaut = 'b\u00e2timent',
                    surcharge_autorisee = 1
                WHERE code = 'pv_ag'
            """))
            # Diagnostic : copropri\u00e9taires_et_cs + b\u00e2timent (\u00e9tait lot_occupants + lot)
            conn.execute(text("""
                UPDATE categorie_document
                SET libelle = 'Diagnostic',
                    profil_acces_id = (SELECT id FROM profil_acces_document WHERE code = 'copropri\u00e9taires_et_cs'),
                    perimetre_defaut = 'b\u00e2timent',
                    surcharge_autorisee = 1
                WHERE code = 'diagnostic_lot'
            """))
            # Contrat fournisseur : p\u00e9rim\u00e8tre b\u00e2timent (\u00e9tait r\u00e9sidence)
            conn.execute(text("""
                UPDATE categorie_document
                SET perimetre_defaut = 'b\u00e2timent',
                    surcharge_autorisee = 1
                WHERE code = 'contrat_fournisseur'
            """))
            conn.commit()
        except Exception:
            pass


def _run_category_migrations():
    """Met \u00e0 jour les cat\u00e9gories de documents existantes pour aligner les droits."""
    with engine.connect() as conn:
        try:
            # Supprimer la cat\u00e9gorie Budget / Comptes annuels
            conn.execute(text("DELETE FROM categorie_document WHERE code = 'budget_comptes'"))
            # PV AG : copropri\u00e9taires_et_cs + b\u00e2timent
            conn.execute(text("""
                UPDATE categorie_document
                SET profil_acces_id = (SELECT id FROM profil_acces_document WHERE code = 'copropri\u00e9taires_et_cs'),
                    perimetre_defaut = 'b\u00e2timent',
                    surcharge_autorisee = 1
                WHERE code = 'pv_ag'
            """))
            # Diagnostic : copropri\u00e9taires_et_cs + b\u00e2timent (\u00e9tait lot_occupants + lot)
            conn.execute(text("""
                UPDATE categorie_document
                SET libelle = 'Diagnostic',
                    profil_acces_id = (SELECT id FROM profil_acces_document WHERE code = 'copropri\u00e9taires_et_cs'),
                    perimetre_defaut = 'b\u00e2timent',
                    surcharge_autorisee = 1
                WHERE code = 'diagnostic_lot'
            """))
            # Contrat fournisseur : p\u00e9rim\u00e8tre b\u00e2timent (\u00e9tait r\u00e9sidence)
            conn.execute(text("""
                UPDATE categorie_document
                SET perimetre_defaut = 'b\u00e2timent',
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
    _run_category_migrations()
