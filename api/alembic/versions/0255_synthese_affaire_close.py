"""La synthèse IA d'une affaire close (#1643, 03/10/2026)

Quand une affaire du carnet d'entretien passe en résolu ou annulé, une synthèse
est produite en différé, déposée dans une Suite, validée par le conseil
(`utils/synthese_affaire`). Cette migration pose ce qu'il lui faut :

1. **`synthese_affaire`** — la demande, puis la synthèse : statut, métriques
   figées, trois textes, complément de prompt, validation. Table NEUVE : ses
   clés étrangères sont posées à la création, ce que SQLite accepte.
2. **`tentative_synthese`** — l'historique des productions (texte, complément,
   coût), que « Recommencer » ne touche pas.
3. **`copropriete.mois_debut_exercice`** — le mois où commence l'exercice
   comptable, qui borne la moyenne de comparaison. Colonne simple, sans
   contrainte : un `add_column` ne doit jamais en porter (0117, 0165).
4. **Le cinquième usage de l'assistant**, comme la 0224 pour le troisième :
   le prompt d'origine (`synthese_affaire.format.CONSIGNE`, lu — jamais
   recopié), le modèle de l'usage « description » s'il est réglé, l'effort
   « moyen » arbitré, et l'usage **désactivé** : une transmission automatique
   d'un fil d'affaire ne s'ouvre pas au déploiement, elle s'ouvre par un geste
   de l'administration — c'est ce que la politique annonce. Désactivé, la Suite
   naît vide, en brouillon, et le conseil rédige.
5. **La politique servie le dit** : la phrase « une seule transmission est
   automatique » (`ASSISTANT_SANS_GESTE`, 0223), suivie de celle des courriels
   transférés (0237), est remplacée EXACTEMENT par les deux transmissions
   (`ASSISTANT_DEUX_AUTOMATIQUES` + `SYNTHESE_AFFAIRE_CLOSE`), lues dans le seed.
   Un texte reformulé depuis l'administration n'est pas touché.

Idempotente : une table, une colonne ou une clé qui existe n'est pas recréée ;
une fois la phrase remplacée, elle ne figure plus.

⚠️ Les noms de tables, de colonnes et les clés de configuration sont des
CONSTANTES du fichier.

Revision ID: 0255
Revises: 0254
"""

import sqlalchemy as sa

from alembic import op

revision = "0255"
down_revision = "0254"
branch_labels = None
depends_on = None

SYNTHESE = "synthese_affaire"  # identifiants : constantes du fichier
TENTATIVE = "tentative_synthese"
COPRO = "copropriete"
COLONNE = "mois_debut_exercice"
USAGE = "synthese_affaire"
POLITIQUE = "politique_confidentialite"
FIN_D_ELEMENT = "</li>"


def _lire(conn, cle: str) -> str | None:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :cle").bindparams(cle=cle)
    ).fetchone()
    return None if ligne is None else ligne[0]


def _poser_si_absent(conn, cle: str, valeur: str) -> None:
    if _lire(conn, cle) is None:
        conn.execute(
            sa.text("INSERT INTO config_site (cle, valeur) VALUES (:cle, :valeur)").bindparams(
                cle=cle, valeur=valeur
            )
        )


def _passages() -> list[tuple[str, str]]:
    """(avant, après) — avec puis sans la phrase des courriels transférés."""
    from app.seed.contenus_legaux import (
        ASSISTANT_DEUX_AUTOMATIQUES,
        ASSISTANT_SANS_GESTE,
        COURRIELS_TRANSFERES,
        SYNTHESE_AFFAIRE_CLOSE,
    )

    return [
        (
            ASSISTANT_SANS_GESTE + COURRIELS_TRANSFERES + FIN_D_ELEMENT,
            ASSISTANT_DEUX_AUTOMATIQUES
            + COURRIELS_TRANSFERES
            + SYNTHESE_AFFAIRE_CLOSE
            + FIN_D_ELEMENT,
        ),
        (
            ASSISTANT_SANS_GESTE + FIN_D_ELEMENT,
            ASSISTANT_DEUX_AUTOMATIQUES + SYNTHESE_AFFAIRE_CLOSE + FIN_D_ELEMENT,
        ),
    ]


def _politique(conn, sens: int) -> None:
    from app.utils.textes_livres import remplacer_passage

    for avant, apres in _passages():
        if sens < 0:
            avant, apres = apres, avant
        if remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres):
            return


def _colonnes(conn, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(table)}


def upgrade() -> None:
    from app.utils.synthese_affaire.format import CONSIGNE

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if SYNTHESE not in tables:
        op.create_table(
            SYNTHESE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("ticket.id"), nullable=False),
            sa.Column("evolution_id", sa.Integer(), nullable=True),
            sa.Column("statut", sa.String(), nullable=False),
            sa.Column("cloture_le", sa.DateTime(), nullable=True),
            sa.Column("metriques_json", sa.String(), nullable=True),
            sa.Column("synthese", sa.String(), nullable=True),
            sa.Column("difficultes", sa.String(), nullable=True),
            sa.Column("amelioration", sa.String(), nullable=True),
            sa.Column("prompt_complement", sa.String(), nullable=True),
            sa.Column("assiste_ia", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("motif_vide", sa.String(), nullable=True),
            sa.Column("produite_le", sa.DateTime(), nullable=True),
            sa.Column("validee_le", sa.DateTime(), nullable=True),
            sa.Column(
                "validee_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True
            ),
            sa.Column("mail_envoye_le", sa.DateTime(), nullable=True),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
            sa.Column("mis_a_jour_le", sa.DateTime(), nullable=False),
        )
        op.create_index(f"ix_{SYNTHESE}_ticket_id", SYNTHESE, ["ticket_id"])
        op.create_index(f"ix_{SYNTHESE}_evolution_id", SYNTHESE, ["evolution_id"])
        op.create_index(f"ix_{SYNTHESE}_statut", SYNTHESE, ["statut"])
    if TENTATIVE not in tables:
        op.create_table(
            TENTATIVE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "synthese_id", sa.Integer(), sa.ForeignKey(f"{SYNTHESE}.id"), nullable=False
            ),
            sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("statut", sa.String(), nullable=False),
            sa.Column("prompt_complement", sa.String(), nullable=True),
            sa.Column("synthese", sa.String(), nullable=True),
            sa.Column("difficultes", sa.String(), nullable=True),
            sa.Column("amelioration", sa.String(), nullable=True),
            sa.Column("jetons_entree", sa.Integer(), nullable=True),
            sa.Column("jetons_sortie", sa.Integer(), nullable=True),
            sa.Column("cout_usd", sa.String(), nullable=True),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
        )
        op.create_index(f"ix_{TENTATIVE}_synthese_id", TENTATIVE, ["synthese_id"])
    if COPRO in tables and COLONNE not in _colonnes(conn, COPRO):
        op.add_column(COPRO, sa.Column(COLONNE, sa.Integer(), nullable=True))
    if "config_site" in tables:
        _poser_si_absent(conn, f"llm_{USAGE}_prompt", CONSIGNE)
        modele = _lire(conn, "llm_description_modele")
        if modele:
            _poser_si_absent(conn, f"llm_{USAGE}_modele", modele)
        _poser_si_absent(conn, f"llm_{USAGE}_actif", "0")
        _poser_si_absent(conn, f"llm_{USAGE}_effort", "moyen")
        _politique(conn, +1)


def downgrade() -> None:
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if "config_site" in tables:
        _politique(conn, -1)
        for champ in ("prompt", "modele", "actif", "effort"):
            conn.execute(
                sa.text("DELETE FROM config_site WHERE cle = :cle").bindparams(
                    cle=f"llm_{USAGE}_{champ}"
                )
            )
    if COPRO in tables and COLONNE in _colonnes(conn, COPRO):
        with op.batch_alter_table(COPRO) as lot:
            lot.drop_column(COLONNE)
    if TENTATIVE in tables:
        op.drop_table(TENTATIVE)
    if SYNTHESE in tables:
        op.drop_table(SYNTHESE)
