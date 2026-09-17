"""L'assistant IA par usage, et la marque « rédigé avec l'assistant » (#984, #985).

## Ce que cette migration fait

1. **Déplace** la configuration de l'usage unique vers l'usage nommé
   `synthese_contrat` : `llm_modele` → `llm_synthese_contrat_modele`,
   `llm_max_jetons` → `llm_synthese_contrat_max_jetons`, et l'activation de
   l'usage reprend celle du commun (`llm_actif`). Les anciennes clés sont
   **retirées** : deux clés pour un même réglage seraient deux vérités.

2. **Initialise le prompt** de chaque usage depuis sa valeur d'origine dans le
   code (`llm_usages.USAGES[…].prompt_defaut`) — **une fois** : c'est ce que
   Philippe a demandé (*« initialise le prompt à partir de ce qui a déjà été
   défini pour le use case 1, la 1ère fois, et sers-toi de ce prompt »*). La
   valeur en base fait ensuite foi, `standards/06` §4 : une donnée de référence
   semée n'est plus tenue par le code, et c'est voulu ici.

   ⚠️ « Poser si absent » et non « poser si vide » : un administrateur qui
   VIDE le prompt retombe sur l'origine par le repli de `config_llm` — sans
   qu'une migration rejouée ne le lui réécrive.

3. **Amorce le second usage** (`description`) avec le modèle du premier — pour
   qu'il fonctionne dès l'activation —, mais **désactivé** : une capacité
   facturée ne s'ouvre pas au déploiement, elle s'ouvre par un geste de
   l'administrateur.

4. Pose la colonne `assiste_ia` sur les neuf tables qui portent une section
   Description — idempotente, table par table, comme la 0193.

## ⚠️ Importer le code applicatif depuis une migration

`app.utils.llm_usages` est importé pour lire les prompts d'origine. C'est
délibéré : la valeur posée est celle du code AU MOMENT du déploiement, et
c'est exactement le sens de « la première fois ». Le module est pur (des
chaînes), il n'ouvre ni base ni réseau.

Revision ID: 0194
Revises: 0193
Create Date: 2026-09-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0194"
down_revision = "0193"
branch_labels = None
depends_on = None

#: Les tables qui portent une section Description, donc la marque.
TABLES_ASSISTE_IA = (
    "ticket",
    "publication",
    "evenement",
    "ticket_evolution",
    "publication_evolution",
    "evenement_evolution",
    "sondage",
    "idee",
    "petite_annonce",
)

USAGE_1 = "synthese_contrat"
USAGE_2 = "description"

#: Ancienne clé → nouvelle clé de l'usage 1.
DEPLACEMENTS = {
    "llm_modele": f"llm_{USAGE_1}_modele",
    "llm_max_jetons": f"llm_{USAGE_1}_max_jetons",
}


def _colonnes_existantes(conn, table: str) -> set[str]:
    return {
        ligne[1]
        for ligne in conn.execute(sa.text(f"PRAGMA table_info('{table}')"))  # noqa: S608
    }


def _lire(conn, cle: str):
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


def _retirer(conn, cle: str) -> None:
    conn.execute(sa.text("DELETE FROM config_site WHERE cle = :cle").bindparams(cle=cle))


def upgrade():
    from app.utils.llm_usages import USAGES

    conn = op.get_bind()

    #  1. L'usage 1 reprend ce que le commun portait.
    for ancienne, nouvelle in DEPLACEMENTS.items():
        valeur = _lire(conn, ancienne)
        if valeur is not None:
            _poser_si_absent(conn, nouvelle, valeur)
            _retirer(conn, ancienne)
    actif = _lire(conn, "llm_actif")
    if actif is not None:
        _poser_si_absent(conn, f"llm_{USAGE_1}_actif", actif)

    #  2. Les prompts d'origine, une fois.
    for code, u in USAGES.items():
        _poser_si_absent(conn, f"llm_{code}_prompt", u.prompt_defaut)

    #  3. Le second usage : amorcé sur le modèle du premier, désactivé.
    modele_1 = _lire(conn, f"llm_{USAGE_1}_modele")
    if modele_1:
        _poser_si_absent(conn, f"llm_{USAGE_2}_modele", modele_1)
    _poser_si_absent(conn, f"llm_{USAGE_2}_actif", "0")

    #  4. La marque, sur les neuf tables.
    for table in TABLES_ASSISTE_IA:
        if "assiste_ia" in _colonnes_existantes(conn, table):
            continue
        #  `server_default="0"` : les lignes existantes n'ont pas été assistées,
        #  et une colonne NOT NULL sans défaut ferait échouer l'ajout.
        op.add_column(
            table,
            sa.Column("assiste_ia", sa.Boolean(), nullable=False, server_default="0"),
        )


def downgrade():
    conn = op.get_bind()
    for ancienne, nouvelle in DEPLACEMENTS.items():
        valeur = _lire(conn, nouvelle)
        if valeur is not None:
            _poser_si_absent(conn, ancienne, valeur)
            _retirer(conn, nouvelle)
    for code in (USAGE_1, USAGE_2):
        for champ in ("actif", "prompt"):
            _retirer(conn, f"llm_{code}_{champ}")
    _retirer(conn, f"llm_{USAGE_2}_modele")
    _retirer(conn, f"llm_{USAGE_2}_max_jetons")
    for table in TABLES_ASSISTE_IA:
        with op.batch_alter_table(table) as lot:
            lot.drop_column("assiste_ia")
