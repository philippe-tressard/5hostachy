"""`vigik.perimetre_cible` et `telecommande.perimetre_cible` : ce que le badge OUVRE.

## La demande (14/09/2026, #953)

> « Cette notion d'accès des vigiks n'existe pas. Il faut ajouter un champ
>   **Accès** : par défaut le bâtiment du logement possédé ; exceptionnellement
>   certains badges — ceux du conseil syndical, l'entreprise de ménage — ont accès
>   à **tous les bâtiments**, et sont nommés `4 SAISONS` dans le fichier d'import. »

Puis, confirmé le même jour : *« les vigiks 4 SAISONS sont accessibles à tous les
bâtiments »*. Ce n'est donc pas une mention administrative du classeur, c'est un
**accès**.

## Pourquoi un PÉRIMÈTRE et non un drapeau

Le produit sait déjà dire « ceci concerne le bâtiment 3 » : `perimetre_cible`, une
liste de codes en JSON, portée par les tickets, les actualités, les événements et
les contrats. S'en servir apporte l'affichage (`BadgePerimetre`), le filtrage
(`couvre`) et le libellé (`perimetre_label`) sans écrire une ligne.

🔴 Et surtout, un drapeau `multi_acces` ne saurait pas dire **deux** bâtiments sur
quatre. Le jour où un badge de chaufferie ouvre les bâtiments 1 et 3, le drapeau
devient faux et tout est à reprendre. Le détail vit sur le modèle.

## La reprise, et ses quatre cas

1. **Un lot connu** → le périmètre de son bâtiment (`bat:<id>`), comme
   `perimetreDuBatiment` le fait côté écran.
2. **Pas de lot, mais un porteur dont tous les lots sont dans UN SEUL bâtiment**
   → ce bâtiment. C'est le cas signalé à l'écran : trois badges au même nom, un
   seul rattaché à un appartement, parce que le classeur ne portait l'adresse que
   sur une ligne.
3. **Une ligne d'import portant la mention « tous bâtiments »** → le périmètre par
   défaut de la copropriété, lu dans l'arbre et non écrit ici.
4. **Rien de tout cela** → `NULL`, c'est-à-dire *« on ne sait pas »*. Une valeur
   généreuse par défaut sur un droit d'accès se lirait comme une décision.

⚠️ L'ordre compte : la mention « tous bâtiments » passe **après** le porteur et
l'écrase, parce qu'elle est explicite là où le porteur est déduit.

⚠️ **La mention est une DONNÉE, pas une constante.** « 4 SAISONS » est le nom d'un
lieu de cette copropriété-ci ; l'écrire dans le code serait la faute que le dépôt
a déjà corrigée pour l'AFUL (0189, `hors_copropriete` plutôt qu'un
`if code == "aful"`) et pour son propre nom (v1.36.7). Elle est donc posée dans
`config_site`, où l'administration la modifie — et la valeur initiale est écrite
**ici**, une fois, comme une reprise de données.

⚠️ **Le périmètre par défaut n'est pas la chaîne « résidence »** : c'est la racine
à portée globale, celle que le serveur et l'écran lisent tous deux dans l'arbre.
On la relit donc en base plutôt que de la supposer — une autre copropriété peut
l'avoir renommée.
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0190"
down_revision = "0189"
branch_labels = None
depends_on = None

COLONNE = "perimetre_cible"
TABLES = ("vigik", "telecommande")

#: La clé de configuration qui porte la mention « ce badge ouvre tout ».
CLE_MENTION = "vigik_mention_tous_batiments"

#: Sa valeur pour CETTE copropriété — posée une fois, modifiable ensuite depuis
#: l'administration. Ce n'est pas une constante du produit.
MENTION_INITIALE = "4 SAISONS"


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _normaliser(valeur) -> str:
    """La même comparaison que les imports : majuscules, sans espaces superflus.

    ⚠️ Volontairement PLUS SIMPLE que `import_xlsx.normaliser`, qui retire aussi
    les accents : une migration ne doit pas importer le code de l'application —
    il change, elle non. « 4 SAISONS » n'a pas d'accent, et si une installation
    en avait besoin, l'administration corrigera la valeur.
    """
    return " ".join(str(valeur or "").upper().split())


def upgrade() -> None:
    #  Garde d'idempotence : `start.sh` a `set -e`, une migration qui crashe
    #  laisse le conteneur bloqué.
    for table in TABLES:
        if COLONNE not in _colonnes(table):
            op.add_column(table, sa.Column(COLONNE, sa.Text(), nullable=True))

    lien = op.get_bind()

    #  ── La mention, posée si elle manque ────────────────────────────────────
    existe = lien.execute(
        sa.text("SELECT 1 FROM config_site WHERE cle = :cle").bindparams(cle=CLE_MENTION)
    ).first()
    if not existe:
        lien.execute(
            sa.text("INSERT INTO config_site (cle, valeur) VALUES (:cle, :valeur)")
            .bindparams(cle=CLE_MENTION, valeur=MENTION_INITIALE)
        )

    #  ── 1. Le bâtiment du lot ───────────────────────────────────────────────
    for table in TABLES:
        lien.execute(sa.text(f"""
            UPDATE {table}
               SET {COLONNE} = (
                   SELECT '["bat:' || lot.batiment_id || '"]'
                     FROM lot WHERE lot.id = {table}.lot_id
               )
             WHERE {COLONNE} IS NULL
               AND lot_id IS NOT NULL
               AND (SELECT batiment_id FROM lot WHERE lot.id = {table}.lot_id) IS NOT NULL
        """))  # noqa: S608 — `table` vient de TABLES, jamais d'une entrée

    #  ── 2. Le bâtiment du PORTEUR, quand il ne fait aucun doute ─────────────
    #
    #  Demandé le 14/09/2026 : *« si le vigik est résolu à un propriétaire, alors
    #  étends-le, sauf s'il possède plusieurs appartements »*. C'est le cas
    #  signalé à l'écran — trois badges au même nom, un seul rattaché à un
    #  appartement, parce que le classeur ne portait l'adresse que sur une ligne.
    #
    #  ⚠️ **J'ÉLARGIS LÉGÈREMENT L'INSTRUCTION, et voici pourquoi.** La consigne
    #  dit « plusieurs appartements » ; la condition retenue est « plusieurs
    #  BÂTIMENTS ». Un accès ouvre un bâtiment, pas une porte d'appartement :
    #  quelqu'un qui possède les lots 210 et 212 du bâtiment 2 n'introduit aucune
    #  ambiguïté sur ce que son badge doit ouvrir. Refuser là perdrait une
    #  information pour rien.
    #
    #  À l'inverse, deux lots dans deux bâtiments différents rendent le choix
    #  impossible : on laisse alors VIDE — « on ne sait pas » — plutôt que d'en
    #  choisir un. Dis-le si tu préfères la lettre de la consigne, le `HAVING`
    #  ci-dessous est la seule ligne à changer.
    #
    #  ⚠️ `type_lien` n'est pas filtré : un locataire aussi reçoit un badge de son
    #  bâtiment, et c'est bien le même bâtiment. Ce qui compte est le LIEU, pas le
    #  titre auquel on l'occupe.
    for table in TABLES:
        lien.execute(sa.text(f"""
            UPDATE {table}
               SET {COLONNE} = (
                   SELECT '["bat:' || MIN(lot.batiment_id) || '"]'
                     FROM user_lot
                     JOIN lot ON lot.id = user_lot.lot_id
                    WHERE user_lot.user_id = {table}.user_id
                      AND user_lot.actif = 1
                      AND lot.batiment_id IS NOT NULL
                   HAVING COUNT(DISTINCT lot.batiment_id) = 1
               )
             WHERE {COLONNE} IS NULL
               AND user_id IS NOT NULL
        """))  # noqa: S608 — `table` vient de TABLES, jamais d'une entrée

    #  ── 3. Les badges « tous bâtiments » ────────────────────────────────────
    #
    #  Seul le vigik est concerné : c'est son classeur qui porte la mention, dans
    #  la colonne « bâtiment ». La télécommande n'a pas cette colonne.
    defaut = lien.execute(
        sa.text(
            "SELECT code FROM perimetre "
            "WHERE parent_id IS NULL AND portee_globale = 1 AND actif = 1 "
            "ORDER BY ordre LIMIT 1"
        )
    ).scalar()
    if defaut:
        cible = json.dumps([defaut], ensure_ascii=False)
        lignes = lien.execute(
            sa.text("SELECT vigik_id, batiment_raw FROM vigik_import WHERE vigik_id IS NOT NULL")
        ).all()
        vises = [
            ligne[0] for ligne in lignes
            if _normaliser(ligne[1]) == _normaliser(MENTION_INITIALE)
        ]
        for vigik_id in vises:
            lien.execute(
                sa.text(f"UPDATE vigik SET {COLONNE} = :cible WHERE id = :id")
                .bindparams(cible=cible, id=vigik_id)
            )


def downgrade() -> None:
    for table in TABLES:
        if COLONNE in _colonnes(table):
            op.drop_column(table, COLONNE)
