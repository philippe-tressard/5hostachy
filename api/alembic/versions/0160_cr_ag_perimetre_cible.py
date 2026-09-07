"""Le CR d'AG cible des PÉRIMÈTRES, plus des identifiants de bâtiments (#470).

Question posée par l'utilisateur le 18/08/2026 : *« la remarque sur l'objet
Périmètre doit être répercutée sur toutes les pages. Ce qui doit être automatique
si l'objet n'est pas copié. Si ce n'est pas le cas, pourquoi ? »*

Le relevé avait répondu : automatique sur **neuf** points d'usage, et **un** écran
y échappait — le compte-rendu d'AG, qui portait un sélecteur écrit à la main et
parlait en `batiments_ids_json`, c'est-à-dire en identifiants de lignes.

## Ce qui rendait la migration impossible jusqu'ici, et qui a changé

`batiments_ids_json` voisinait avec `perimetre` / `batiment_id`, qui **gouvernent
les droits de lecture**. Migrer l'un sans savoir si l'on touchait l'autre était le
vrai blocage.

L'arbitrage du 29/08/2026 (#617) l'a levé : **le périmètre d'un PV d'AG est
descriptif**, il dit de quoi parle le document et non qui peut le lire. Une AG est
visible de tous les copropriétaires. Le ciblage peut donc devenir un vrai
périmètre **sans qu'aucun droit ne bouge**.

## Ce que la migration fait

`document.perimetre_cible` — un tableau JSON de **codes**, la même convention que
`publication.perimetre_cible`. Les valeurs existantes sont converties :

    batiments_ids_json = "[3]"      →  perimetre_cible = '["bat:3"]'
    batiments_ids_json = "[1,2]"    →  perimetre_cible = '["bat:1","bat:2"]'

⚠️ **`batiments_ids_json` n'est PAS supprimée.** Deux raisons, et la seconde
compte plus que la première :

  1. SQLite ne sait pas retirer une colonne sans recréer la table, et recréer
     `document` déplacerait toutes ses clés étrangères ;
  2. surtout, c'est la **trace de ce que le CS avait choisi**. Le jour où un code
     de périmètre est renommé — l'arborescence est administrée, elle bouge —,
     l'identifiant de bâtiment reste vrai. Une conversion qui efface sa source ne
     se rejoue pas.

Le code applicatif ne la lit plus : c'est `perimetre_cible` qui fait foi.

## Ce que la migration NE fait pas

Elle ne touche ni `perimetre`, ni `batiment_id`, ni `lot_id` — l'axe des DROITS.
Un diagnostic ou une attestation de lot continue d'être restreint par son
bâtiment ; seuls les PV d'AG ont un ciblage descriptif.

Revision ID: 0160
Revises: 0159
"""
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0160"
down_revision = "0159"
branch_labels = None
depends_on = None

_CATEGORIE = "pv_ag"


def upgrade() -> None:
    op.add_column("document", sa.Column("perimetre_cible", sa.String(), nullable=True))
    conn = op.get_bind()

    #  ⚠️ On ne convertit QUE les PV d'AG : `batiments_ids_json` ne sert qu'à eux,
    #  et l'écrire ailleurs donnerait un ciblage à des documents qui n'en ont pas.
    lignes = conn.execute(
        text(
            "SELECT d.id, d.batiments_ids_json, d.batiment_id "
            "FROM document d JOIN categorie_document c ON c.id = d.categorie_id "
            "WHERE c.code = :cat"
        ),
        {"cat": _CATEGORIE},
    ).fetchall()

    for doc_id, multi, batiment_id in lignes:
        ids = []
        if multi:
            try:
                valeur = json.loads(multi)
                ids = [int(i) for i in valeur] if isinstance(valeur, list) else []
            except (ValueError, TypeError):
                #  Une liste illisible ne devient pas un ciblage inventé : le
                #  document reste sans périmètre, donc « toute la copropriété ».
                ids = []
        elif batiment_id:
            ids = [batiment_id]
        if not ids:
            continue
        conn.execute(
            text("UPDATE document SET perimetre_cible = :p WHERE id = :i"),
            {"p": json.dumps([f"bat:{i}" for i in ids], ensure_ascii=False), "i": doc_id},
        )


def downgrade() -> None:
    """Retire la colonne. `batiments_ids_json` n'a jamais cessé de porter la source."""
    op.drop_column("document", "perimetre_cible")
