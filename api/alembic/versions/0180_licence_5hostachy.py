"""La licence du projet change : MIT → Licence 5Hostachy (#823).

Décidé le 07/09/2026. Le logiciel passe d'une licence permissive (MIT) à une
licence **source-available** : copyleft fondé sur les principes de l'AGPLv3,
avec une clause d'usage commercial.

## 🔴 Pourquoi une MIGRATION et pas seulement un changement de fichier

Les mentions légales servies aux résidents ne viennent **pas** du dépôt : elles
sont en base, dans `config_site`, posées par la migration 0170. Changer
`LICENSE` et le seed ne toucherait donc **rien** de ce que les gens lisent — le
site continuerait d'annoncer MIT indéfiniment.

C'est la forme d'incohérence la plus durable : le dépôt dit une chose, la page
publique en dit une autre, et rien ne les compare. Le seed, lui, ne rejoue pas
sur une installation existante (`ConfigSite` porte un marqueur depuis #653).

⚠️ Cette migration ne réécrit **que le paragraphe de licence**, en le
substituant dans la valeur existante. Réécrire la page entière effacerait ce que
l'administration y a saisi depuis — éditeur, hébergeur, adresse de contact.

## Ce que la nouvelle mention dit, et pourquoi elle le dit ainsi

Elle ne parle plus de « logiciel libre » ni d'« open source » : la clause
commerciale ajoute une restriction que ni l'OSI ni la FSF n'admettent dans une
licence libre. Écrire « open source » serait inexact, et un professionnel qui
s'y fierait pour un usage payant serait induit en erreur — `standards/14`.

Elle dit donc **« code source accessible »**, et nomme les deux régimes : gratuit
pour les particuliers, associations et copropriétés ; accord préalable pour tout
usage commercial.

Revision ID: 0180
Revises: 0179
"""
import sqlalchemy as sa
from alembic import op

revision = "0180"
down_revision = "0179"
branch_labels = None
depends_on = None

#: Le paragraphe posé par 0170, à remplacer. Repris au caractère près : une
#: substitution qui ne trouve pas sa cible ne doit rien changer, pas deviner.
ANCIEN = (
    "<h2>Propriété intellectuelle</h2>"
    "<p>Le code source de 5Hostachy est distribué sous licence "
    '<a href="https://spdx.org/licenses/MIT.html" target="_blank" '
    "rel=\"noopener noreferrer\">MIT</a>. Les contenus publiés dans l'application "
    "— messages, documents, photographies — restent la propriété de leurs auteurs "
    "et ne sont accessibles qu'aux personnes autorisées à les lire.</p>"
)

DEPOT = "https://github.com/philippe-tressard/5hostachy"

NOUVEAU = (
    "<h2>Propriété intellectuelle</h2>"
    "<p>Le code source de 5Hostachy est <strong>accessible</strong>, sous "
    f'<a href="{DEPOT}/blob/main/LICENSE-5Hostachy.md" target="_blank" '
    'rel="noopener noreferrer">Licence 5Hostachy</a> — copyleft fondé sur les '
    "principes de l'AGPLv3, avec clauses commerciales. Les particuliers, "
    "associations et copropriétés peuvent l'utiliser <strong>gratuitement</strong> ; "
    "tout usage commercial requiert un accord préalable de l'auteur.</p>"
    "<p>⚠️ Ce n'est <em>pas</em> une licence libre au sens de l'OSI : la clause "
    "commerciale ajoute une restriction que l'AGPLv3 n'admet pas.</p>"
    "<p>Les contenus publiés dans l'application — messages, documents, "
    "photographies — restent la propriété de leurs auteurs et ne sont accessibles "
    "qu'aux personnes autorisées à les lire.</p>"
)

#: Les deux formulations qui ont existé pour ce paragraphe. La 0029 posait une
#: version plus courte ; une installation qui n'a jamais reçu la 0170 la porte
#: encore. Les deux se corrigent, sinon l'une des deux resterait à MIT.
ANCIEN_COURT = (
    '<p>Le code source de 5Hostachy est distribué sous licence <a href="https://spdx.org/licenses/MIT.html" '
    'target="_blank" rel="noopener noreferrer">MIT</a> (voir le fichier LICENSE du dépôt). '
    "Les contenus publiés dans l'application restent la propriété de leurs auteurs respectifs.</p>"
)


def upgrade() -> None:
    lien = op.get_bind()
    ligne = lien.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = 'mentions_legales'")
    ).fetchone()
    #  Rien en base : le seed posera la bonne version à la première installation.
    #  Ce n'est pas un échec — c'est le cas d'un déploiement neuf.
    if not ligne or not ligne[0]:
        return

    valeur = ligne[0]
    for ancien in (ANCIEN, ANCIEN_COURT):
        if ancien in valeur:
            valeur = valeur.replace(ancien, NOUVEAU)
            break
    else:
        #  ⚠️ Ni l'une ni l'autre : la page a été réécrite à la main depuis
        #  l'administration. On NE TOUCHE À RIEN — écraser le texte de quelqu'un
        #  pour y glisser une licence serait pire que l'incohérence qu'on corrige.
        #  Le seed et le dépôt disent la nouvelle licence ; cette page-là se
        #  corrige à la main, par celui qui l'a écrite.
        return

    #  🔴 Jamais de f-string dans `op.execute()` (`CLAUDE.md`) : la valeur passe
    #  par `bindparams`, et elle contient du HTML saisi par un humain.
    op.execute(
        sa.text("UPDATE config_site SET valeur = :v WHERE cle = 'mentions_legales'").bindparams(
            v=valeur
        )
    )


def downgrade() -> None:
    #  🔴 Irréversible, et le dire vaut mieux que le faire à moitié : remettre
    #  « MIT » sur une page qui ne l'est plus annoncerait une licence fausse,
    #  ce qui est exactement le défaut que cette migration corrige.
    pass
