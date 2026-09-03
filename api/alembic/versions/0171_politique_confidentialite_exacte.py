"""La politique de confidentialité nomme un responsable et cesse d'être fausse

## Trois défauts, de gravité très différente

La politique était bien plus complète que les mentions légales : finalités, bases
légales, durées, droits, cookies — tout y était. C'est ce qui rendait ses trois
défauts discrets.

### 1. 🔴 « Aucun transfert hors UE » était FAUX

La phrase existait depuis toujours. Elle est devenue *visiblement* fausse le
03/09/2026, quand les mentions légales ont déclaré **Cloudflare, Inc.** (Californie)
comme intermédiaire technique — deux pages du même site se contredisaient alors,
l'une disant qu'un tiers américain relaie les connexions, l'autre qu'aucune donnée
ne sort de l'UE.

Le fait est le même dans les deux cas : Cloudflare voit passer les adresses IP et
le trafic chiffré des visiteurs. Ce qui a changé, c'est qu'on l'a écrit quelque
part — et une affirmation RGPD contredite par une autre page du même site n'est
pas une imprécision, c'est une déclaration inexacte.

⚠️ **Le texte DÉCRIT le fait, il ne le QUALIFIE pas.** Savoir si ce relais
constitue un « transfert » au sens du chapitre V du RGPD est une question de
droit, et `standards/14` est explicite : *« sur un point qui engage, la réponse
est il faut vérifier, pas une improvisation »*. On écrit donc ce qui se passe —
un intermédiaire américain relaie les connexions, l'hébergement et le stockage
restent en France — et on laisse le lecteur, ou un juriste, en tirer les
conséquences. C'est vérifiable par n'importe qui (`curl -I`, un `dig`), là où
une qualification hâtive ne l'est pas.

### 2. Le responsable du traitement n'était personne

> « Le responsable du traitement est l'administrateur de cette instance
>   (syndic bénévole ou conseil syndical). »

Même défaut que les mentions légales, et le RGPD est plus exigeant encore : le
responsable du traitement est **l'interlocuteur** de toute demande de droits. Ne
pas le nommer, c'est rendre ces droits inexerçables tout en les décrivant.

### 3. Les droits ne s'exerçaient que depuis un compte

> « Contactez l'administrateur via la messagerie. »

Un droit RGPD doit pouvoir s'exercer **sans compte** — c'est même le cas
typique : quelqu'un dont le compte a été supprimé, ou un ancien résident. La
messagerie interne suppose une connexion, donc suppose exactement ce qu'on vient
peut-être d'effacer. Une adresse e-mail est ajoutée à côté ; la messagerie reste
proposée, elle est plus commode pour un résident actif.

## Ce qui n'est PAS touché

Les finalités, les bases légales, les durées et les cookies. Ils sont exacts, et
les modifier serait une décision juridique sans motif — pas un nettoyage.

Revision ID: 0171
Revises: 0170
Create Date: 2026-09-03
"""
from alembic import op
from sqlalchemy import text

revision = "0171"
down_revision = "0170"
branch_labels = None
depends_on = None


#: Chaque correction est un couple (avant, après) appliqué SI le fragment est
#: présent. Un remplacement ciblé, jamais une réécriture de la page entière :
#: tout ce qui a été rédigé à la main autour survit.
#:
#: 🔴 Et si AUCUN fragment ne correspond, la migration le DIT (voir `upgrade`).
#: Une migration de texte qui ne trouve pas sa cible passe au vert en n'ayant
#: rien fait — c'est le piège que `test_migration_0162` a attrapé, et il n'y a
#: aucune raison de le laisser rouvert ici.
CORRECTIONS = [
    (
        "<p>Le responsable du traitement est l'administrateur de cette instance 5Hostachy "
        "(syndic bénévole ou conseil syndical). Toute demande relative à vos données peut lui être adressée "
        "via la messagerie de l'application.</p>",
        "<p>Le responsable du traitement est <strong>Philippe Tressard</strong>, "
        "éditeur du site. Toute demande relative à vos données peut lui être "
        'adressée à <a href="mailto:contact@5hostachy.fr">contact@5hostachy.fr</a>, '
        "ou depuis la messagerie de l'application si vous disposez d'un compte.</p>",
    ),
    (
        "Elles ne sont pas transférées à des tiers ni commercialisées. Aucun transfert hors UE.</p>",
        "Elles ne sont ni cédées à des tiers, ni commercialisées, ni utilisées à des "
        "fins publicitaires.</p>"
        "<p><strong>Hébergement et acheminement.</strong> Les données sont stockées en "
        "France, sur une infrastructure privée ; aucun prestataire tiers ne les "
        "héberge. Les connexions transitent en revanche par "
        "<strong>Cloudflare, Inc.</strong> (États-Unis), qui assure la résolution DNS "
        "et le relais du trafic : à ce titre, cette société traite les adresses IP "
        "des visiteurs et achemine des flux chiffrés, sans accéder au contenu de la "
        "base ni aux documents. Cette information est donnée telle qu'elle est, pour "
        "que chacun sache par où passent ses connexions.</p>",
    ),
    (
        "opposition (art. 21) et retrait du consentement (art. 7-3). "
        "Contactez l'administrateur via la messagerie.",
        "opposition (art. 21) et retrait du consentement (art. 7-3). "
        "Pour les exercer, écrivez à "
        '<a href="mailto:contact@5hostachy.fr">contact@5hostachy.fr</a> — cette voie '
        "reste ouverte même sans compte, y compris après sa suppression. Les "
        "titulaires d'un compte peuvent aussi passer par la messagerie de "
        "l'application, ou exporter et effacer leurs données depuis leur profil.",
    ),
]


def upgrade():
    lien = op.get_bind()
    ligne = lien.execute(
        text("SELECT valeur FROM config_site WHERE cle = 'politique_confidentialite'")
    ).fetchone()
    if ligne is None:
        #  Rien en base : le seed sert de repli et porte déjà le texte du produit.
        #  Rien à corriger, et rien à inventer.
        return

    texte = ligne[0] or ""
    appliquees = 0
    for avant, apres in CORRECTIONS:
        if avant in texte:
            texte = texte.replace(avant, apres)
            appliquees += 1

    if appliquees == 0:
        #  Le texte a été réécrit à la main : on n'y touche pas. C'est le cas
        #  légitime, et il ne doit pas ressembler à un échec.
        return

    lien.execute(
        text("UPDATE config_site SET valeur = :v WHERE cle = 'politique_confidentialite'"),
        {"v": texte},
    )


def downgrade():
    #  Volontairement inerte : revenir en arrière remettrait en ligne une
    #  affirmation inexacte et un responsable du traitement anonyme.
    pass
