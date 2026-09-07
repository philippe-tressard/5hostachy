"""L'éditeur devient le conseil syndical, plus une personne nommée

## La demande, et pourquoi elle est fondée

Demandé le 03/09/2026 : *« peux-tu enlever mon nom dans les mentions légales »*.

La page `/mentions-legales` est **publique et indexable**. Y publier le nom d'une
personne physique, c'est publier une donnée personnelle sur le web ouvert, pour
un site qui n'est ni commercial ni destiné au public — un outil interne de
copropriété. La minimisation (RGPD art. 5-1-c) dit exactement cela : ne pas
collecter, ni publier, ce dont la fonction n'a pas besoin.

## Ce qui remplace le nom, et pourquoi ce n'est PAS un vide

La LCEN impose d'identifier l'éditeur : retirer le nom sans rien mettre à la
place recréerait le défaut corrigé la veille par la migration 0170 — une page qui
n'identifie personne.

L'éditeur devient donc **le conseil syndical de la copropriété**, avec l'adresse
de contact. C'est une entité, pas une personne ; elle est identifiable, joignable,
et elle correspond à la réalité : le site est l'outil de la copropriété, pas celui
de la personne qui l'administre.

⚠️ **C'est un revirement par rapport à l'arbitrage du matin**, où « personne
physique » avait été retenu contre « le syndicat des copropriétaires ». Il faut le
dire : la conséquence — publier un nom sur une page indexable — n'était pas
visible au moment du choix. Elle l'est devenue en lisant la page.

## Le même geste dans la politique de confidentialité

Le responsable du traitement y était nommé par la migration 0171. Il devient la
même entité : deux pages du même site ne peuvent pas désigner deux responsables
différents — c'est exactement la contradiction qu'on a corrigée hier sur les
transferts hors UE.

⚠️ Le responsable du traitement reste **une personne juridiquement identifiable**
via la copropriété ; l'adresse de contact est le point d'entrée, et elle est
tenue par ceux qui administrent le site.

Revision ID: 0173
Revises: 0172
Create Date: 2026-09-03
"""
from alembic import op
from sqlalchemy import text

revision = "0173"
down_revision = "0172"
branch_labels = None
depends_on = None


#: Chaque substitution est ciblée : le reste de la page, y compris ce qui a pu
#: être retouché depuis l'administration, n'est pas réécrit.
#:
#: ⚠️ NOM CHOISI CONTRE `REMPLACEMENTS`, et c'est un contrôle qui l'a imposé.
#: Ce nom-là est déjà une CONVENTION du dépôt : `test_email_templates` balaie
#: toutes les migrations qui l'exposent et attend des triplets
#: `(code, ancien, nouveau)` pour les modèles d'e-mail. Le réutiliser avec une
#: autre forme faisait échouer ce balayage — et un nom conventionnel détourné
#: aurait fini par tromper un lecteur autant qu'un test.
SUBSTITUTIONS = [
    (
        "<p><strong>Philippe Tressard</strong>, éditeur à titre non professionnel.<br>",
        "<p><strong>Le conseil syndical de la copropriété</strong>, éditeur à titre "
        "non professionnel.<br>",
    ),
    (
        "<h2>Directeur de la publication</h2><p>Philippe Tressard.</p>",
        "<h2>Directeur de la publication</h2>"
        "<p>Le président du conseil syndical, joignable à l'adresse de contact "
        "ci-dessous.</p>",
    ),
    (
        "<p>Le responsable du traitement est <strong>Philippe Tressard</strong>, "
        "éditeur du site.",
        "<p>Le responsable du traitement est <strong>le conseil syndical de la "
        "copropriété</strong>, éditeur du site.",
    ),
]


def upgrade():
    lien = op.get_bind()
    for cle in ("mentions_legales", "politique_confidentialite"):
        ligne = lien.execute(
            text("SELECT valeur FROM config_site WHERE cle = :c"), {"c": cle}
        ).fetchone()
        if ligne is None:
            continue
        texte = ligne[0] or ""
        change = False
        for avant, apres in SUBSTITUTIONS:
            if avant in texte:
                texte = texte.replace(avant, apres)
                change = True
        if change:
            lien.execute(
                text("UPDATE config_site SET valeur = :v WHERE cle = :c"),
                {"v": texte, "c": cle},
            )


def downgrade():
    #  Volontairement inerte. Un downgrade qui REPUBLIE le nom d'une personne
    #  irait contre la demande qui a motivé cette migration — et une donnée
    #  personnelle remise en ligne « par retour arrière » reste une publication.
    pass
