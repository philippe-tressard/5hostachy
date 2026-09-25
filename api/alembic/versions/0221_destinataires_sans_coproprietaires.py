"""Le code « copropriétaires » quitte les publics visés (#1301, lot 2)

Arbitré le 25/09/2026 : la pastille « Copropriétaires » du sélecteur de
Destinataires faisait double emploi avec « Copropriétaires occupants » et
« Copropriétaires bailleurs », qu'elle couvrait ensemble. Elle disparaît de
l'écran ; les objets qui la portent passent aux DEUX codes, qui disent
exactement la même chose — mêmes lecteurs, avant comme après.

Sans cette migration, la règle (`public_cible_visible`) continuerait de lire le
code, mais aucun écran ne saurait plus le proposer ni le corriger : un objet
qu'on ne peut plus rééditer sans changer, en silence, qui le lit.

Idempotente : une ligne sans le code n'est pas touchée, donc rejouer ne fait
rien. `downgrade` ne défait rien, et c'est délibéré : les deux codes disent la
même chose que l'ancien, et une ligne qui les portait déjà ne se distingue pas
d'une ligne convertie.

Revision ID: 0221
Revises: 0220
"""

import json

import sqlalchemy as sa

from alembic import op

revision = "0221"
down_revision = "0220"
branch_labels = None
depends_on = None

#: Les tables qui portent un public visé — identifiants, constantes du fichier,
#: jamais des valeurs liées. `test_migration_0221_coproprietaires.py` les
#: confronte au modèle.
TABLES = ("publication", "ticket", "idee", "petite_annonce", "sondage")

ANCIEN = "copropriétaires"
NOUVEAUX = ("copropriétaires_occupants", "bailleurs")


def _codes(valeur: str) -> list[str] | None:
    """Les codes d'une valeur stockée (JSON, ou l'ancien CSV), ou None si illisible."""
    try:
        codes = json.loads(valeur)
    except ValueError:
        return [c.strip() for c in valeur.split(",") if c.strip()]
    return [str(c) for c in codes] if isinstance(codes, list) else None


def convertir(valeur: str | None) -> str | None:
    """La valeur convertie, ou None si la ligne n'a pas à changer."""
    if not valeur:
        return None
    codes = _codes(valeur)
    if codes is None or ANCIEN not in codes:
        return None
    resultat: list[str] = []
    for c in codes:
        for n in NOUVEAUX if c == ANCIEN else (c,):
            if n not in resultat:
                resultat.append(n)
    return json.dumps(resultat, ensure_ascii=False)


def upgrade() -> None:
    conn = op.get_bind()
    existantes = set(sa.inspect(conn).get_table_names())
    for table in TABLES:
        if table not in existantes:
            continue
        #  `table` : identifiant, constante ci-dessus. Les VALEURS sont liées.
        lignes = conn.execute(
            sa.text(f"SELECT id, public_cible FROM {table} WHERE public_cible LIKE :motif")
            .bindparams(motif=f"%{ANCIEN}%")
        ).all()
        for id_, valeur in lignes:
            nouvelle = convertir(valeur)
            if nouvelle is not None:
                conn.execute(
                    sa.text(f"UPDATE {table} SET public_cible = :v WHERE id = :id")
                    .bindparams(v=nouvelle, id=id_)
                )


def downgrade() -> None:
    #  Rien à défaire : les deux codes disent ce que disait l'ancien (voir plus haut).
    pass
