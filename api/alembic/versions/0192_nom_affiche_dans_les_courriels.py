"""Les courriels rendent « Prénom NOM », comme partout ailleurs (#959).

## Le défaut

La règle d'affichage d'un nom — *« Prénom NOM, le nom en capitales »* — a été
arbitrée à l'écran le **31/08/2026**, sur une carte du fil qui rendait
« Jean-Sébastien **CourT** ». Elle vit dans `app/utils/noms.nom_affiche`, avec
son pendant côté front, et `npm run lint:noms` vérifie que les deux concordent.

🔴 **Elle ne s'appliquait pas aux courriels** — c'est-à-dire précisément là où le
nom sort de l'application et arrive chez quelqu'un. Dix-sept points d'envoi
passaient le nom brut, et le gabarit le composait lui-même :

    "auteur": {"prenom": user.prenom, "nom": user.nom}   →   {{ auteur.prenom }} {{ auteur.nom }}

Le destinataire lisait donc le nom **tel qu'il a été tapé à l'inscription**, sur
la surface la plus visible du produit.

Le correctif tient en deux gestes : `contexte_personne()` (`utils/noms.py`) pose
désormais une clé `affiche` **déjà rendue**, et les gabarits l'emploient au lieu
de recomposer. `test_email_templates.py` refuse maintenant qu'un gabarit du dépôt
recompose un nom.

## Pourquoi une migration — et pas seulement le seed

`_poser_les_absents` ne pose que ce qui **manque** : ces quatorze modèles
existent déjà en base, la version du seed ne leur arriverait donc jamais. C'est
exactement le défaut du modèle BOUCHON (09/09/2026, mémoire
`project_modele_email_bouchon`), où `ticket_externe` et `publication_externe` ont
envoyé « Notification. » **pendant des mois** parce que la migration 0105 n'avait
pas repris les modèles déjà posés.

`REPLACE` sur fragment ciblé, comme 0136, 0184 et 0185 : une installation qui
aurait retouché son texte depuis Admin → Emails garde sa version **et** reçoit la
correction, pour peu qu'elle ait conservé la composition d'origine.

⚠️ Le fragment cherché disparaît une fois le remplacement fait — rejouer
`upgrade` ne l'applique donc pas deux fois, et `test_email_templates` le vérifie
(`ancien not in nouveau`).

## Ce que la migration ne touche pas

`{{ destinataire.prenom }}` — « Bonjour Jean, » — reste intact : on ne
l'identifie pas, on **lui parle**. C'est la distinction que pose l'en-tête de
`utils/noms.py` entre `nom_affiche` (identifier, « DUPONT ») et
`_nom_presentable` (s'adresser, « Dupont »), et la confondre donnerait des
courriels qui hurlent.

Revision ID: 0192
Revises: 0191
Create Date: 2026-09-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0192"
down_revision = "0191"
branch_labels = None
depends_on = None


def _compose(variable: str) -> tuple[str, str]:
    """Le couple (recomposé, rendu) pour une variable de gabarit.

    Composé plutôt qu'écrit quatorze fois : les deux formes se déduisent l'une de
    l'autre, et les recopier laisserait la prochaine variable arriver avec une
    faute de frappe qu'aucun test ne verrait — le `REPLACE` ne trouverait alors
    simplement rien, en silence.
    """
    return ("{{ %s.prenom }} {{ %s.nom }}" % (variable, variable),
            "{{ %s.affiche }}" % variable)


_AUTEUR = _compose("auteur")
_AUTEUR_ACTION = _compose("auteur_action")
_DEMANDEUR = _compose("demandeur")
_UTILISATEUR = _compose("utilisateur")

#: L'objet du message — deux modèles seulement y nomment une personne.
REMPLACEMENTS: list[tuple[str, str, str]] = [
    ("acces_apparies_auto", *_UTILISATEUR),
    ("etage_divergent", *_UTILISATEUR),
]

#: Le corps du message.
REMPLACEMENTS_CORPS: list[tuple[str, str, str]] = [
    ("compte_en_attente", *_UTILISATEUR),
    ("vigik_commande_recue", *_DEMANDEUR),
    ("acces_apparies_auto", *_UTILISATEUR),
    ("etage_divergent", *_UTILISATEUR),
    ("ticket_bug_admin", *_AUTEUR),
    ("ticket_syndic", *_AUTEUR),
    ("ticket_nouveau_cs", *_AUTEUR),
    ("ticket_nouveau_message", *_AUTEUR_ACTION),
    ("ticket_externe", *_AUTEUR),
    ("publication_syndic", *_AUTEUR),
    ("publication_externe", *_AUTEUR),
    ("annonce_hall", *_AUTEUR),
]


def _remplacer(conn, colonne: str, code: str, ancien: str, nouveau: str) -> None:
    """Un seul balayage pour les deux colonnes — deux jumelles auraient divergé.

    ⚠️ Jamais de f-string sur les VALEURS (`standards/06` §3) : elles voyagent en
    `bindparams`. Le nom de la colonne, lui, ne vient pas d'une entrée — il est
    choisi ici parmi deux littéraux.
    """
    assert colonne in ("sujet", "corps_html"), colonne
    conn.execute(
        sa.text(
            f"UPDATE modele_email SET {colonne} = REPLACE({colonne}, :ancien, :nouveau) "  # noqa: S608
            f"WHERE code = :code AND instr({colonne}, :ancien) > 0"
        ).bindparams(code=code, ancien=ancien, nouveau=nouveau)
    )


def upgrade():
    conn = op.get_bind()
    for code, ancien, nouveau in REMPLACEMENTS:
        _remplacer(conn, "sujet", code, ancien, nouveau)
    for code, ancien, nouveau in REMPLACEMENTS_CORPS:
        _remplacer(conn, "corps_html", code, ancien, nouveau)


def downgrade():
    conn = op.get_bind()
    for code, ancien, nouveau in reversed(REMPLACEMENTS_CORPS):
        _remplacer(conn, "corps_html", code, nouveau, ancien)
    for code, ancien, nouveau in reversed(REMPLACEMENTS):
        _remplacer(conn, "sujet", code, nouveau, ancien)
