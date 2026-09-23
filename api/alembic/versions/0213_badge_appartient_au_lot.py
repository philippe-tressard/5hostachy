"""Un badge appartient au LOT (#1194, 23/09/2026).

## Ce que l'utilisateur a tranché

Un badge (Vigik, télécommande) appartient au lot ; ses porteurs se déduisent du
lot (`utils/porteurs_acces`), conjoint compris. Cette migration pose les trois
conditions pour que la règle tienne sur les données réelles :

1. **`user_id` devient facultatif** sur `vigik` et `telecommande` : un badge
   rattaché à un lot sans compte n'est dans la main de personne de connu. C'est
   aussi ce qui permet qu'un compte supprimé laisse ses badges au lot
   (arbitrage 3) — la purge référentielle délie une clé facultative au lieu de
   supprimer la ligne.
2. **Le code d'un badge est unique** : un même objet physique ne peut pas
   exister deux fois. Mesuré le 23/09 sur la sauvegarde : zéro doublon en base.
3. **Tous les lots du fichier des lots existent.** Il n'y en avait que 70 sur
   201 : un lot n'était créé qu'au moment où sa ligne était liée à un compte.
   Or 180 des 182 lignes Vigik retrouvent leur lot par bâtiment + appartement —
   à condition qu'il existe. Créer un lot ne donne accès à rien : l'accès vient
   des liens `user_lot`, que cette migration ne touche pas.

Et elle reprend le lot des badges qui n'en ont pas, **quand il est sûr** : le
porteur a exactement un lot de la nature du badge (appartement pour un Vigik,
parking pour une télécommande). Mesuré : 7 Vigik et 35 télécommandes ; les 19
télécommandes dont le porteur a plusieurs parkings restent à préciser à l'écran.

## ⚠️ Ce que le retour arrière ne défait pas

Les lots créés et les lots repris restent : ce sont des faits du fichier du
syndic, pas une interprétation, et rien ne les distingue après coup d'une
création par l'écran. Le retour arrière rétablit le schéma — et échoue si un
badge sans détenteur existe, plutôt que d'en inventer un.
"""
import sqlalchemy as sa
from alembic import op

revision = "0213"
down_revision = "0212"
branch_labels = None
depends_on = None

#: Les deux tables de badges, et la nature de lot de chacune — identifiants de
#: table interpolés depuis cette constante, jamais depuis une donnée.
BADGES = (("vigik", "appartement"), ("telecommande", "parking"))


def _index(conn, table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(conn).get_indexes(table)}


def upgrade() -> None:
    conn = op.get_bind()
    for table, _nature in BADGES:
        with op.batch_alter_table(table) as lot:
            lot.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
        if f"ix_{table}_code" not in _index(conn, table):
            op.create_index(f"ix_{table}_code", table, ["code"], unique=True)

    _creer_les_lots_du_fichier(conn)

    for table, nature in BADGES:
        conn.execute(sa.text(
            #  `{t}` : identifiant de table, pris dans la constante BADGES — un
            #  identifiant ne se lie pas en SQLite. La nature, elle, est liée.
            "UPDATE {t} SET lot_id = ("
            "  SELECT ul.lot_id FROM user_lot ul JOIN lot l ON l.id = ul.lot_id"
            "  WHERE ul.user_id = {t}.user_id AND ul.actif = 1 AND l.type = :nature"
            ") WHERE lot_id IS NULL AND user_id IS NOT NULL AND ("
            "  SELECT count(*) FROM user_lot ul JOIN lot l ON l.id = ul.lot_id"
            "  WHERE ul.user_id = {t}.user_id AND ul.actif = 1 AND l.type = :nature"
            ") = 1".replace("{t}", table)
        ).bindparams(nature=nature))


def _creer_les_lots_du_fichier(conn) -> None:
    """Chaque ligne du fichier des lots a son `lot` — trouvé, ou créé.

    La règle de lecture d'une ligne (nature, étage) est celle de l'écran,
    `utils/import_xlsx` : la recopier ici ferait deux lectures du même fichier.
    """
    from app.utils.import_xlsx import etage_de_lot, type_de_lot

    lignes = conn.execute(sa.text(
        "SELECT id, batiment_id, numero, type_raw, etage_raw, statut FROM lot_import "
        "WHERE lot_id IS NULL AND statut != 'ignore'"
    )).mappings().all()
    for li in lignes:
        if li["batiment_id"]:
            lot_id = conn.execute(sa.text(
                "SELECT id FROM lot WHERE batiment_id = :b AND numero = :n"
            ).bindparams(b=li["batiment_id"], n=li["numero"])).scalar()
        else:
            lot_id = conn.execute(sa.text(
                "SELECT id FROM lot WHERE batiment_id IS NULL AND numero = :n"
            ).bindparams(n=li["numero"])).scalar()
        if lot_id is None:
            nature, type_appartement = type_de_lot(li["type_raw"])
            conn.execute(sa.text(
                "INSERT INTO lot (batiment_id, numero, type, type_appartement, etage) "
                "VALUES (:b, :n, :t, :ta, :e)"
            ).bindparams(b=li["batiment_id"], n=li["numero"], t=nature.value,
                         ta=type_appartement, e=etage_de_lot(li["etage_raw"])))
            lot_id = conn.execute(sa.text("SELECT last_insert_rowid()")).scalar()
        statut = "lot_lie" if li["statut"] == "en_attente" else li["statut"]
        conn.execute(sa.text(
            "UPDATE lot_import SET lot_id = :lot, statut = :s WHERE id = :id"
        ).bindparams(lot=lot_id, s=statut, id=li["id"]))


def downgrade() -> None:
    conn = op.get_bind()
    for table, _nature in BADGES:
        if f"ix_{table}_code" in _index(conn, table):
            op.drop_index(f"ix_{table}_code", table)
        with op.batch_alter_table(table) as lot:
            lot.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
