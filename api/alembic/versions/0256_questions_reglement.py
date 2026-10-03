"""Les questions au règlement de copropriété (03/10/2026)

Le conseil syndical charge le texte de travail du règlement et pose la question
d'un résident ; l'assistant répond en juriste, extraits à l'appui
(`utils/question_reglement`). Cette migration pose ce qu'il lui faut :

1. **`texte_reglement`** — les versions du texte chargé (Markdown). Table
   NEUVE : sa clé étrangère est posée à la création, ce que SQLite accepte.
2. **`question_reglement`** — les questions, leurs réponses, leurs extraits
   vérifiés et la version du texte lue. Table NEUVE, clés à la création.
3. **Le sixième usage de l'assistant**, comme la 0255 pour le cinquième : le
   prompt d'origine (`question_reglement.format.CONSIGNE`, lu — jamais
   recopié), le modèle de l'usage « description » s'il est réglé, l'effort
   « élevé » (c'est la précision qui est demandée), et l'usage **désactivé** :
   il s'ouvre par un geste de l'administration.
4. **La politique servie le dit** : `QUESTION_REGLEMENT` est inséré juste avant
   `ASSISTANT_DEUX_AUTOMATIQUES`, lus dans le seed. Un texte reformulé depuis
   l'administration n'est pas touché.

Idempotente : une table ou une clé qui existe n'est pas recréée ; la phrase
déjà présente n'est pas insérée deux fois.

⚠️ Les noms de tables et les clés de configuration sont des CONSTANTES du fichier.

Revision ID: 0256
Revises: 0255
"""

import sqlalchemy as sa

from alembic import op

revision = "0256"
down_revision = "0255"
branch_labels = None
depends_on = None

TEXTE = "texte_reglement"  # identifiants : constantes du fichier
QUESTION = "question_reglement"
USAGE = "question_reglement"
POLITIQUE = "politique_confidentialite"


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


def _politique(conn, sens: int) -> None:
    from app.seed.contenus_legaux import ASSISTANT_DEUX_AUTOMATIQUES, QUESTION_REGLEMENT
    from app.utils.textes_livres import remplacer_passage

    avec = QUESTION_REGLEMENT + ASSISTANT_DEUX_AUTOMATIQUES
    if sens > 0:
        actuel = _lire(conn, POLITIQUE) or ""
        if QUESTION_REGLEMENT in actuel:
            return
        remplacer_passage(
            conn, "config_site", {"cle": POLITIQUE}, "valeur", ASSISTANT_DEUX_AUTOMATIQUES, avec
        )
    else:
        remplacer_passage(
            conn, "config_site", {"cle": POLITIQUE}, "valeur", avec, ASSISTANT_DEUX_AUTOMATIQUES
        )


def upgrade() -> None:
    from app.utils.question_reglement.format import CONSIGNE

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if TEXTE not in tables:
        op.create_table(
            TEXTE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("titre", sa.String(), nullable=False),
            sa.Column("nom_fichier", sa.String(), nullable=False),
            sa.Column("contenu", sa.String(), nullable=False),
            sa.Column("empreinte", sa.String(), nullable=False),
            sa.Column(
                "charge_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True
            ),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
        )
        op.create_index(f"ix_{TEXTE}_empreinte", TEXTE, ["empreinte"])
        op.create_index(f"ix_{TEXTE}_cree_le", TEXTE, ["cree_le"])
    if QUESTION not in tables:
        op.create_table(
            QUESTION,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("question", sa.String(), nullable=False),
            sa.Column("verdict", sa.String(), nullable=False),
            sa.Column("reponse", sa.String(), nullable=False),
            sa.Column("reserves", sa.String(), nullable=True),
            sa.Column("extraits_json", sa.String(), nullable=False, server_default="[]"),
            sa.Column("texte_id", sa.Integer(), sa.ForeignKey(f"{TEXTE}.id"), nullable=False),
            sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("modele", sa.String(), nullable=True),
            sa.Column("jetons_entree", sa.Integer(), nullable=True),
            sa.Column("jetons_sortie", sa.Integer(), nullable=True),
            sa.Column("cout_usd", sa.String(), nullable=True),
            sa.Column("faq_item_id", sa.Integer(), sa.ForeignKey("faq_item.id"), nullable=True),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
        )
        op.create_index(f"ix_{QUESTION}_texte_id", QUESTION, ["texte_id"])
        op.create_index(f"ix_{QUESTION}_cree_le", QUESTION, ["cree_le"])
    if "config_site" in tables:
        _poser_si_absent(conn, f"llm_{USAGE}_prompt", CONSIGNE)
        modele = _lire(conn, "llm_description_modele")
        if modele:
            _poser_si_absent(conn, f"llm_{USAGE}_modele", modele)
        _poser_si_absent(conn, f"llm_{USAGE}_actif", "0")
        _poser_si_absent(conn, f"llm_{USAGE}_effort", "eleve")
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
    if QUESTION in tables:
        op.drop_table(QUESTION)
    if TEXTE in tables:
        op.drop_table(TEXTE)
