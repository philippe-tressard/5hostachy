"""Les mentions légales nomment enfin quelqu'un — obligation LCEN

## Le défaut

La page `/mentions-legales` est **publique** — lisible sans compte, indexable — et
elle servait le gabarit générique du produit. On y lisait, en toutes lettres :

> « L'identité de l'éditeur correspond à la copropriété ou au syndic bénévole qui
>   gère cette instance. »
> « L'hébergeur est l'organisation ou la personne physique administrant le serveur
>   sur lequel l'instance est déployée. »

Ce ne sont pas des mentions : ce sont des **instructions pour en rédiger**. Elles
décrivent ce qu'il faudrait écrire au lieu de l'écrire. Un lecteur ne pouvait
identifier ni l'éditeur, ni le directeur de la publication, ni l'hébergeur — les
trois que la LCEN (art. 6 III) impose de pouvoir identifier.

Le défaut n'a pas de symptôme : la page s'affiche, elle a l'air complète, et
personne ne la lit jusqu'à ce que quelqu'un ait une raison de chercher qui
contacter.

## Pourquoi une MIGRATION et non le seed

`app/seed/contenus_legaux.py` est le gabarit du PRODUIT, pas de cette
copropriété : 5Hostachy est sous licence MIT et peut être déployé ailleurs. Y
écrire les coordonnées d'un éditeur les imposerait à tout autre déploiement, qui
publierait alors des mentions fausses — pire que des mentions vagues.

La règle qui en découle, et qui vaut au-delà de ce lot : **le seed porte le
produit, la base porte l'instance.** Le seed reste donc générique, mais il ne
prétend plus être des mentions valides (voir le fichier, réécrit dans le même
lot).

## Les trois décisions, prises par l'éditeur le 03/09/2026

| Question | Réponse retenue |
|---|---|
| Qui édite ? | **Philippe Tressard**, personne physique |
| Adresse postale publiée ? | **Non** — un e-mail de contact seulement |
| Hébergeur ? | auto-hébergement, avec Cloudflare comme intermédiaire technique |

⚠️ **L'absence d'adresse est un écart assumé, et il faut le dire.** La LCEN
dispense de publier son identité complète l'éditeur **non professionnel** qui l'a
communiquée à son hébergeur — ce qui suppose un hébergeur tiers. Ici le site est
auto-hébergé : il n'y a pas de tiers qui détienne cette identité. La page nomme
donc l'éditeur et fournit un moyen de le joindre, sans adresse postale. C'est un
choix de l'éditeur, pris en connaissance de cause, et non un oubli.

⚠️ **`contact@5hostachy.fr` doit exister.** Un contact légal qui ne reçoit rien
est une mention aussi vide que celle qu'on remplace. C'est un alias à créer chez
l'hébergeur de messagerie — la seule action qui reste après cette migration.

## Idempotence

La migration n'écrit QUE si la clé est absente ou porte encore le gabarit. Une
rédaction faite depuis Admin → Légal ne sera donc jamais écrasée par un
redéploiement — c'est le défaut qu'avait le seed des périmètres (13/08/2026), qui
reposait son arborescence à chaque démarrage et annulait les suppressions.

Revision ID: 0170
Revises: 0169
Create Date: 2026-09-03
"""
from alembic import op
from sqlalchemy import text

revision = "0170"
down_revision = "0169"
branch_labels = None
depends_on = None


#: Ce qui trahit le gabarit non renseigné. Si l'un de ces fragments est présent,
#: personne n'a rédigé les mentions — et on peut écrire sans rien écraser.
_MARQUEURS_GABARIT = (
    "correspond à la copropriété ou au syndic bénévole",
    "l'organisation ou la personne physique",
    "À RENSEIGNER",
)

MENTIONS = (
    "<h2>Éditeur du site</h2>"
    "<p><strong>Philippe Tressard</strong>, éditeur à titre non professionnel.<br>"
    "5Hostachy est l'outil interne d'une copropriété : il n'est ni commercialisé, "
    "ni ouvert au public, et son accès est réservé aux résidents inscrits.</p>"
    "<h2>Directeur de la publication</h2>"
    "<p>Philippe Tressard.</p>"
    "<h2>Hébergement</h2>"
    "<p>Le service est <strong>auto-hébergé</strong> sur une infrastructure privée "
    "située en France ; aucune donnée n'est stockée chez un prestataire tiers.<br>"
    "<strong>Cloudflare, Inc.</strong> (101 Townsend St, San Francisco, CA 94107, "
    "États-Unis) intervient comme <em>intermédiaire technique</em> : résolution DNS "
    "et relais des connexions. À ce titre, il voit passer le trafic chiffré mais "
    "n'héberge ni la base de données ni les documents.</p>"
    "<h2>Contact</h2>"
    "<p>Pour toute question relative au site, à son contenu ou à vos données : "
    '<a href="mailto:contact@5hostachy.fr">contact@5hostachy.fr</a>.<br>'
    "Les résidents inscrits peuvent également ouvrir un ticket depuis "
    "l'application.</p>"
    "<h2>Données personnelles</h2>"
    "<p>Les finalités, les durées de conservation et vos droits (accès, "
    "rectification, effacement, opposition) sont détaillés dans la "
    '<a href="/politique-confidentialite">politique de confidentialité</a>. '
    "Chaque compte peut exporter et effacer ses propres données depuis son "
    "profil.</p>"
    "<h2>Propriété intellectuelle</h2>"
    "<p>Le code source de 5Hostachy est distribué sous licence "
    '<a href="https://spdx.org/licenses/MIT.html" target="_blank" '
    'rel="noopener noreferrer">MIT</a>. Les contenus publiés dans l\'application '
    "— messages, documents, photographies — restent la propriété de leurs auteurs "
    "et ne sont accessibles qu'aux personnes autorisées à les lire.</p>"
    "<h2>Responsabilité</h2>"
    "<p>L'éditeur s'efforce de tenir ces informations exactes et à jour. Les "
    "informations publiées par les résidents ou le conseil syndical engagent leurs "
    "auteurs. Toute inexactitude peut être signalée à l'adresse ci-dessus.</p>"
)


def upgrade():
    lien = op.get_bind()
    ligne = lien.execute(
        text("SELECT valeur FROM config_site WHERE cle = 'mentions_legales'")
    ).fetchone()

    if ligne is None:
        lien.execute(
            text("INSERT INTO config_site (cle, valeur) VALUES ('mentions_legales', :v)"),
            {"v": MENTIONS},
        )
        return

    #  Rédigées à la main depuis l'administration : on ne touche à rien.
    actuel = ligne[0] or ""
    if not any(marqueur in actuel for marqueur in _MARQUEURS_GABARIT):
        return

    lien.execute(
        text("UPDATE config_site SET valeur = :v WHERE cle = 'mentions_legales'"),
        {"v": MENTIONS},
    )


def downgrade():
    #  Volontairement inerte : revenir au gabarit remettrait en ligne une page qui
    #  n'identifie personne. Un downgrade ne restaure pas un manquement.
    pass
