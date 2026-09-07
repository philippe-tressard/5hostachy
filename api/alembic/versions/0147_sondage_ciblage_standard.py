"""Sondage : le ciblage rejoint le standard du site (périmètre + public cible).

## Ce que cette migration corrige

Le sondage ciblait avec DEUX colonnes qui n'existaient nulle part ailleurs :

  - `batiments_ids`      — CSV d'identifiants de bâtiments ;
  - `profils_autorises`  — CSV de `StatutUtilisateur`.

Tout le reste du site cible avec `perimetre_cible` (codes de périmètre, arbre en
base) et `public_cible` (résidents, copropriétaires, bailleurs, locataires…).
Résultat visible à l'écran : l'écran Sondages était le seul à ne pas proposer le
parking, l'AFUL ni les espaces d'un bâtiment, et son sélecteur avait sa propre
apparence. Signalé par l'utilisateur le 16/08/2026 — « Périmètre et Destinataires
ne respectent pas le standard » — et tranché par lui : unification complète,
modèle compris.

## La conversion, et pourquoi elle n'élargit AUCUN accès

`batiments_ids` → `perimetre_cible` est une simple mise en forme : l'identifiant
`3` devient le code `bat:3`, convention posée par `utils/perimetres.py`. Un champ
vide reste vide, ce qui vaut « aucune restriction » des deux côtés.

`profils_autorises` → `public_cible` demandait davantage d'attention, et c'est le
point sensible de cette migration :

| Ancienne valeur (statuts)                              | Nouvelle valeur              |
|--------------------------------------------------------|------------------------------|
| `copropriétaire_résident` + `copropriétaire_bailleur`   | `copropriétaires`            |
| `copropriétaire_bailleur` seul                          | `bailleurs`                  |
| `copropriétaire_résident` seul                          | `copropriétaires_occupants`  |
| `locataire`                                             | `locataires`                 |

⚠️ `copropriétaires_occupants` est **ajouté au vocabulaire par ce lot**, et il
n'est pas un confort : sans lui, un sondage réservé aux copropriétaires occupants
serait devenu un sondage ouvert à `copropriétaires`, c'est-à-dire **aussi aux
bailleurs** — une conversion de données qui ÉLARGIT un accès. Le code manquant
côté publications était d'ailleurs la même lacune, invisible parce que personne
ne l'avait demandée.

Une valeur inconnue est conservée telle quelle : `public_cible_visible` refuse ce
qu'elle ne reconnaît pas, donc un résidu ne peut que restreindre.

## Idempotence

Les deux ajouts de colonne sont gardés, comme depuis l'incident du 25/07/2026
(cf. migration 0117) : un ajout interrompu avant l'enregistrement de la révision
laisse la colonne en place, et le rejeu au démarrage suivant échouerait sur
« duplicate column name » — ce qui bloque l'API en boucle de crash.

Les anciennes colonnes sont **supprimées** : les laisser en place ferait vivre
deux ciblages pour la même notion, et c'est exactement ce que ce lot défait.

Revision ID: 0147
Revises: 0146
Create Date: 2026-08-16
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0147"
down_revision = "0146"
branch_labels = None
depends_on = None


#: Statuts → code de public cible. Écrite ici et pas importée : une migration
#: doit rester lisible et rejouable telle qu'elle a été écrite, même si le
#: vocabulaire de l'application évolue ensuite (`standards/06` §3).
_UN_STATUT = {
    "copropriétaire_résident": "copropriétaires_occupants",
    "copropriétaire_bailleur": "bailleurs",
    "locataire": "locataires",
}


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _codes_perimetre(batiments_csv: str | None) -> str | None:
    """CSV d'identifiants de bâtiments → JSON de codes de périmètre."""
    if not batiments_csv:
        return None
    codes = [f"bat:{v.strip()}" for v in batiments_csv.split(",") if v.strip()]
    return json.dumps(codes, ensure_ascii=False) if codes else None


def _codes_public(profils_csv: str | None) -> str | None:
    """CSV de statuts → JSON de codes de public cible, sans élargir l'accès."""
    if not profils_csv:
        return None
    statuts = {v.strip() for v in profils_csv.split(",") if v.strip()}
    if not statuts:
        return None
    #  Les deux statuts de copropriétaire ensemble = « copropriétaires ». Pris
    #  séparément, chacun a son propre code : les fondre élargirait l'accès.
    codes: list[str] = []
    copro = {"copropriétaire_résident", "copropriétaire_bailleur"}
    if copro <= statuts:
        codes.append("copropriétaires")
        statuts -= copro
    for s in sorted(statuts):
        #  Valeur inconnue conservée telle quelle : la règle de lecture refuse ce
        #  qu'elle ne reconnaît pas, donc un résidu ne peut que RESTREINDRE.
        codes.append(_UN_STATUT.get(s, s))
    return json.dumps(codes, ensure_ascii=False) if codes else None


def upgrade():
    colonnes = _colonnes("sondage")
    if "perimetre_cible" not in colonnes:
        op.add_column("sondage", sa.Column("perimetre_cible", sa.String(), nullable=True))
    if "public_cible" not in colonnes:
        op.add_column("sondage", sa.Column("public_cible", sa.String(), nullable=True))

    bind = op.get_bind()
    #  La conversion ne peut avoir lieu que si les anciennes colonnes sont encore
    #  là : un rejeu après un `upgrade` complet doit être sans effet, pas en échec.
    anciennes = _colonnes("sondage")
    if "batiments_ids" in anciennes and "profils_autorises" in anciennes:
        lignes = bind.execute(
            sa.text("SELECT id, batiments_ids, profils_autorises FROM sondage")
        ).fetchall()
        for sid, batiments, profils in lignes:
            bind.execute(
                sa.text(
                    "UPDATE sondage SET perimetre_cible = :p, public_cible = :c WHERE id = :i"
                ).bindparams(
                    p=_codes_perimetre(batiments),
                    c=_codes_public(profils),
                    i=sid,
                )
            )
        with op.batch_alter_table("sondage") as batch:
            batch.drop_column("batiments_ids")
            batch.drop_column("profils_autorises")


def downgrade():
    #  Le retour arrière rétablit les colonnes, VIDES : reconvertir des codes de
    #  périmètre en identifiants de bâtiments perdrait le parking, l'AFUL et les
    #  espaces, qui n'ont pas d'équivalent. Une reconversion partielle rendrait un
    #  sondage restreint accessible à tous — un `downgrade` ne doit jamais ouvrir
    #  ce qu'un `upgrade` avait fermé.
    colonnes = _colonnes("sondage")
    if "batiments_ids" not in colonnes:
        op.add_column("sondage", sa.Column("batiments_ids", sa.String(), nullable=True))
    if "profils_autorises" not in colonnes:
        op.add_column("sondage", sa.Column("profils_autorises", sa.String(), nullable=True))
    with op.batch_alter_table("sondage") as batch:
        batch.drop_column("public_cible")
        batch.drop_column("perimetre_cible")
