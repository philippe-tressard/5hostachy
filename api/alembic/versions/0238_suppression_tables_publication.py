"""Les tables `publication` et `publication_evolution` sont supprimées (#1177, 30/09/2026)

## Pourquoi maintenant

La 0210 (23/09/2026) a recopié chaque publication en affaire de catégorie
« Actualité » et **n'a rien supprimé** : garder les lignes une à deux semaines
permettait un retour arrière sans restaurer de sauvegarde. Le délai est passé,
la bascule est constatée en production, et Philippe a donné son accord le
30/09/2026.

## Ce qui a été vérifié avant, sur la sauvegarde du 29/09/2026 (copie, poste)

- 22 publications → 22 affaires `promu_depuis_publication_id`, titres identiques ;
- 9 évolutions → 7 retrouvées à l'identique dans `ticket_evolution` ; les deux
  autres (deux traces « Correction : Épinglage » de l'actualité 24) avaient été
  recopiées par la 0210 PUIS supprimées de l'affaire par un utilisateur ;
- `document.publication_id` et `annonce_hall.publication_id` : aucune valeur ;
- aucune clé étrangère vers `publication` hors de `publication_evolution`.

## Ce qui reste

`ticket.promu_depuis_publication_id` et son index : c'est ce que lit la
redirection des anciens liens `/actualites#pub-N` (410 → l'affaire). Elle ne lit
que lui, et survit donc à cette migration (`test_redirection_publications.py`).

## La descente recrée des tables VIDES

Les lignes ne reviennent pas : elles sont dans les affaires, et dans les
sauvegardes antérieures au 30/09/2026. La descente rend seulement au schéma sa
forme, pour que la 0210 puisse être descendue à son tour.

⚠️ Les identifiants de table et de colonne sont des CONSTANTES du fichier : ils
s'interpolent (SQLite ne lie pas un identifiant), aucune valeur ne l'est.
"""

import sqlalchemy as sa
from alembic import op

revision = "0238"
down_revision = "0237"
branch_labels = None
depends_on = None

#  L'ordre compte : l'évolution référence la publication.
TABLES = ("publication_evolution", "publication")
COLONNES = (("document", "publication_id"), ("annonce_hall", "publication_id"))

#  La forme exacte relevée sur la base de production (sqlite_master, 29/09/2026).
DDL_PUBLICATION = """
CREATE TABLE publication (
    id INTEGER NOT NULL,
    titre VARCHAR NOT NULL,
    contenu VARCHAR NOT NULL,
    perimetre VARCHAR NOT NULL,
    batiment_id INTEGER,
    epingle BOOLEAN NOT NULL,
    urgente BOOLEAN NOT NULL,
    auteur_id INTEGER NOT NULL,
    cree_le DATETIME NOT NULL,
    publiee_le DATETIME,
    image_url VARCHAR,
    perimetre_cible VARCHAR DEFAULT '["résidence"]',
    public_cible VARCHAR DEFAULT '["résidents"]',
    mis_a_jour_le DATETIME,
    statut VARCHAR,
    brouillon BOOLEAN DEFAULT '0' NOT NULL,
    statut_change_le DATETIME,
    archivee BOOLEAN DEFAULT '0' NOT NULL,
    partager_whatsapp BOOLEAN DEFAULT '0' NOT NULL,
    envoyer_syndic BOOLEAN DEFAULT 0 NOT NULL,
    envoyer_cs BOOLEAN DEFAULT 0 NOT NULL,
    annonce_hall BOOLEAN DEFAULT 0 NOT NULL,
    photos_urls VARCHAR,
    confidentiel BOOLEAN DEFAULT 0 NOT NULL,
    saisi_pour_user_id INTEGER,
    saisi_pour_nom VARCHAR,
    saisi_pour_email VARCHAR,
    assiste_ia BOOLEAN DEFAULT '0' NOT NULL,
    debut DATETIME,
    fin DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(auteur_id) REFERENCES utilisateur (id),
    FOREIGN KEY(batiment_id) REFERENCES batiment (id)
)
"""

DDL_PUBLICATION_EVOLUTION = """
CREATE TABLE publication_evolution (
    id INTEGER NOT NULL,
    publication_id INTEGER NOT NULL,
    type VARCHAR NOT NULL,
    contenu TEXT,
    ancien_statut VARCHAR,
    nouveau_statut VARCHAR,
    auteur_id INTEGER NOT NULL,
    cree_le DATETIME NOT NULL,
    fichiers_urls TEXT DEFAULT '[]' NOT NULL,
    assiste_ia BOOLEAN DEFAULT '0' NOT NULL,
    contenu_origine TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY(publication_id) REFERENCES publication (id) ON DELETE CASCADE,
    FOREIGN KEY(auteur_id) REFERENCES utilisateur (id)
)
"""


def _colonne_a_une_cle(inspecteur, table: str, colonne: str) -> bool:
    return any(colonne in fk["constrained_columns"] for fk in inspecteur.get_foreign_keys(table))


def upgrade():
    conn = op.get_bind()
    inspecteur = sa.inspect(conn)
    tables = set(inspecteur.get_table_names())

    for table, colonne in COLONNES:
        if table not in tables:
            continue
        if colonne not in {c["name"] for c in inspecteur.get_columns(table)}:
            continue  # déjà retirée : un redémarrage après échec partiel repasse ici
        if _colonne_a_une_cle(inspecteur, table, colonne):
            #  SQLite refuse `DROP COLUMN` sur une colonne sous clé étrangère :
            #  la table est alors reconstruite. En production, `document` n'en
            #  porte aucune (relevé du 29/09/2026) ; une base créée par les
            #  modèles, si.
            with op.batch_alter_table(table) as lot:
                lot.drop_column(colonne)
        else:
            op.drop_column(table, colonne)

    for table in TABLES:
        if table in tables:
            op.drop_table(table)


def downgrade():
    conn = op.get_bind()
    inspecteur = sa.inspect(conn)
    tables = set(inspecteur.get_table_names())

    if "publication" not in tables:
        op.execute(DDL_PUBLICATION)
    if "publication_evolution" not in tables:
        op.execute(DDL_PUBLICATION_EVOLUTION)
    for table, colonne in COLONNES:
        if table in tables and colonne not in {c["name"] for c in inspecteur.get_columns(table)}:
            op.add_column(table, sa.Column(colonne, sa.Integer, nullable=True))
