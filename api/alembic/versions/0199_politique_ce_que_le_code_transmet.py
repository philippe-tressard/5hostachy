"""La politique servie ne nommait ni la télémétrie, ni les photos, ni les tiers (#1034).

## 🔴 Rang 1 — `standards/14`

Le texte servi aux résidents ne mentionnait **rien** de ce que le code collecte
ou transmet :

| Ce que le code fait | Occurrences dans le texte |
|---|---|
| télémétrie nominative (`TelemetryEvent.user_id`, page, action) | **0** |
| photos (`photo_url`, `photos_urls`) | **0** |
| badges Vigik et télécommandes rattachés à une personne | **0** |
| relais vers un groupe **WhatsApp** (service de Meta) | **0** |
| descriptions et **contrats transmis à un service de modèle de langage** | **0** |
| sous-traitant, service d'acheminement des courriels | **0** |

Et le paragraphe « Destinataires » affirmait que les données ne sont « ni cédées
à des tiers ». La phrase est **vraie** au sens commercial — rien n'est cédé ni
vendu — et c'est ce qui la rend trompeuse : elle répond à une question que le
lecteur ne pose pas, et laisse croire qu'elle répond à celle qu'il pose.

**Un texte servi aux utilisateurs qui passe sous silence ce qui sort est un
défaut de rang 1**, et celui-ci est public : il se lit sans compte.

## Ce que cette migration ajoute, et ce qu'elle laisse à l'instance

Les paragraphes sont **repris du seed** (`app/seed/contenus_legaux.AJOUTS_1034`),
pas réécrits : deux rédactions parallèles d'un texte juridique divergent au
premier ajustement, et c'est alors le texte servi qui est faux.

Ce qui dépend du déploiement reste « **À RENSEIGNER** » : quel groupe de
messagerie, quel fournisseur de modèle de langage et depuis quel pays, quel
service d'acheminement. Nommer ici un prestataire l'imposerait à tout autre
déploiement, qui publierait alors des mentions **fausses** — c'est la décision
du 03/09/2026 (le seed porte le produit, la base porte l'instance).

## Ce que le texte dit des durées, et pourquoi il est prudent

Les durées annoncées sont celles **réellement appliquées** par le code :
télémétrie brute 30 jours, agrégats journaliers 12 mois, mensuels 10 ans
(`utils/telemetry_aggregation.py`).

⚠️ Pour l'historique des envois de courriels, le texte dit qu'**aucune purge
automatique n'est en place à ce jour**. C'est exact, et c'est inconfortable —
mais inventer une durée que le code n'applique pas serait pire : ce serait
remplacer un silence par une affirmation fausse. La purge manquante est un
travail à faire, elle a son ticket.

## Comment elle s'applique

Même prudence que la 0171 : elle lit le texte servi, insère chaque paragraphe
**avant son ancre** si l'ancre est présente, et **ne fait rien** si aucune ne
l'est — un conseil syndical qui aurait réécrit la page garde la sienne.

Elle est **idempotente** : un paragraphe déjà présent n'est pas réinséré.

Revision ID: 0199
Revises: 0198
Create Date: 2026-09-20
"""
from sqlalchemy import text
from alembic import op

revision = "0199"
down_revision = "0198"
branch_labels = None
depends_on = None

CLE = "politique_confidentialite"


def _ajouts():
    """Les paragraphes, lus dans le seed — jamais recopiés ici."""
    from app.seed.contenus_legaux import AJOUTS_1034

    return AJOUTS_1034


def upgrade() -> None:
    lien = op.get_bind()
    ligne = lien.execute(
        text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=CLE)
    ).fetchone()
    if ligne is None:
        #  Rien en base : le seed sert de repli et porte déjà le texte complet.
        #  Rien à corriger, et rien à inventer.
        return

    texte = ligne[0] or ""
    appliques = 0
    for ancre, ajout in _ajouts():
        if ajout in texte or ancre not in texte:
            continue
        texte = texte.replace(ancre, ajout + ancre, 1)
        appliques += 1

    if appliques == 0:
        #  Aucune ancre reconnue : le texte a été réécrit à la main. C'est le cas
        #  légitime, et il ne doit pas ressembler à un échec.
        return

    lien.execute(
        text("UPDATE config_site SET valeur = :v WHERE cle = :c").bindparams(
            v=texte, c=CLE
        )
    )


def downgrade() -> None:
    #  Symétrique : on retire les paragraphes ajoutés, et eux seuls. Un retour en
    #  arrière ne doit pas défaire une reformulation faite entre-temps.
    lien = op.get_bind()
    ligne = lien.execute(
        text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=CLE)
    ).fetchone()
    if ligne is None:
        return

    texte = ligne[0] or ""
    retires = 0
    for _ancre, ajout in _ajouts():
        if ajout in texte:
            texte = texte.replace(ajout, "", 1)
            retires += 1

    if retires:
        lien.execute(
            text("UPDATE config_site SET valeur = :v WHERE cle = :c").bindparams(
                v=texte, c=CLE
            )
        )
