"""Les modèles d'e-mail disent « affaire », comme le reste du site (#1101).

## Pourquoi une migration, et pas seulement le seed

`_poser_les_absents` ne pose que ce qui **manque** : ces dix modèles existent
déjà en base, la version du seed ne leur arriverait donc jamais. C'est le défaut
du modèle BOUCHON (09/09/2026, `project_modele_email_bouchon`), où
`ticket_externe` et `publication_externe` ont envoyé « Notification. » pendant
des mois parce que la migration 0105 n'avait pas repris les modèles déjà posés.

`REPLACE` sur fragment ciblé, comme 0136, 0184, 0185 et 0192 : une copropriété
qui aurait retouché son texte depuis Admin → Emails garde sa version **et**
reçoit la correction, pour peu qu'elle ait conservé la formule d'origine.

⚠️ Le fragment cherché disparaît une fois remplacé — rejouer `upgrade` ne
l'applique donc pas deux fois.

## 🔴 Ce qui NE bouge pas, et pourquoi

| Ce qui reste | La raison |
|---|---|
| les **codes** (`ticket_syndic`, `relance_syndic`) | ce sont les clés de `send_email` |
| la route `/tickets/{{ ticket.id }}` | elle est dans des courriels **déjà envoyés** |
| l'adresse à jeton `tickets+{{ … }}@` | l'acheminement des réponses en dépend |
| les identifiants **TK-xxxx** | `courriel_entrant.py` s'en sert pour rattacher |
| la variable `{{ ticket.* }}` | le contexte d'appel la fournit sous ce nom |

## ⚠️ L'accord, qui ne se remplace pas mécaniquement

« ticket » est masculin, « affaire » est féminin. « Un ticket a été transmis »
devient « Une affaire a été transmise » — deux mots changent, pas un. Le
renommage du manuel avait produit « un <strong>affaire » en remplaçant le seul
nom ; ici chaque formule est reprise entière.
"""
import sqlalchemy as sa
from alembic import op

revision = "0203"
down_revision = "0202"
branch_labels = None
depends_on = None

#: (code, ancien, nouveau) pour la colonne `libelle` — le nom du modèle tel que
#: l'administration l'affiche.
REMPLACEMENTS_LIBELLE: list[tuple[str, str, str]] = [
    ("ticket_bug_admin", "Ticket bug — notification admin site",
     "Affaire de type Bug — notification admin site"),
    ("ticket_syndic", "Ticket transmis au syndic", "Affaire transmise au syndic"),
    #  🔴 La base porte « Notification ticket au syndic » — un libellé que le
    #  seed n'a JAMAIS eu (constaté sur la production le 22/09/2026, capture à
    #  l'appui). Retouché depuis Admin → Emails, ou posé par une version
    #  antérieure du seed : dans les deux cas, un `REPLACE` qui ne cherche que
    #  le texte du dépôt ne l'aurait jamais trouvé.
    #
    #  ⚠️ C'est la limite de ce motif de migration, et elle mérite d'être dite :
    #  il corrige ce qu'il RECONNAÎT. Une copropriété qui a réécrit son libellé
    #  garde le sien — ce qui est voulu — mais garde alors aussi l'ancien mot.
    ("ticket_syndic", "Notification ticket au syndic", "Affaire transmise au syndic"),
    ("ticket_statut_change", "Statut ticket modifié", "Statut d’affaire modifié"),
    ("ticket_nouveau_cs", "Nouveau ticket — notification du conseil syndical",
     "Nouvelle affaire — notification du conseil syndical"),
    ("ticket_nouveau_message", "Nouveau message sur un ticket",
     "Nouveau message sur une affaire"),
    ("relance_syndic", "Relance tickets syndic non résolus",
     "Relance des affaires syndic non résolues"),
    ("ticket_externe", "Notification ticket (email externe)",
     "Notification d’affaire (email externe)"),
]

#: L'objet du message.
REMPLACEMENTS: list[tuple[str, str, str]] = [
    ("ticket_bug_admin", "Bug signalé via Tickets — ", "Bug signalé via les Affaires — "),
    ("ticket_syndic", "💬 Commentaire — Ticket #", "💬 Commentaire — Affaire #"),
    ("ticket_syndic", "{{ prefixe_copro }}Ticket #", "{{ prefixe_copro }}Affaire #"),
    ("ticket_statut_change", "Ticket #{{ ticket.numero }} mis à jour",
     "Affaire #{{ ticket.numero }} mise à jour"),
    ("ticket_nouveau_cs", "🎫 Ticket #", "🎫 Affaire #"),
    ("ticket_nouveau_message", "Nouveau message — Ticket #", "Nouveau message — Affaire #"),
    ("relance_syndic", "Relance ticket(s) sans avancée", "Relance d’affaire(s) sans avancée"),
    ("ticket_externe", "Relance Ticket #", "Relance — Affaire #"),
    ("ticket_externe", "{{ prefixe_copro }}Ticket #", "{{ prefixe_copro }}Affaire #"),
]

#: Le corps du message. L'ordre compte : les formules longues d'abord, pour que
#: le fragment court ne les ampute pas.
REMPLACEMENTS_CORPS: list[tuple[str, str, str]] = [
    ("ticket_bug_admin", "Un ticket de type ", "Une affaire de type "),
    ("ticket_syndic", "📋 Ticket transmis par le conseil syndical",
     "📋 Affaire transmise par le conseil syndical"),
    ("ticket_syndic", "Un ticket a été transmis à votre attention",
     "Une affaire a été transmise à votre attention"),
    ("ticket_syndic", "ajouté sur le ticket <strong>#", "ajouté sur l’affaire <strong>#"),
    ("ticket_statut_change", "Mise à jour de votre ticket", "Mise à jour de votre affaire"),
    ("ticket_statut_change", "Le statut de votre ticket a été mis à jour",
     "Le statut de votre affaire a été mis à jour"),
    ("ticket_nouveau_cs", "🎫 Nouveau ticket", "🎫 Nouvelle affaire"),
    ("ticket_nouveau_cs", "Un ticket vient d", "Une affaire vient d"),
    ("ticket_nouveau_message", "💬 Nouveau message sur votre ticket",
     "💬 Nouveau message sur votre affaire"),
    ("ticket_nouveau_message", "ajouté sur le ticket <strong>#",
     "ajouté sur l’affaire <strong>#"),
    ("ticket_nouveau_message", "Voir le ticket", "Voir l’affaire"),
    ("relance_syndic", "🔔 Relance ticket(s) sans avancée",
     "🔔 Relance d’affaire(s) sans avancée"),
    ("relance_syndic", "concernant les tickets ci-dessous, transmis au syndic",
     "concernant les affaires ci-dessous, transmises au syndic"),
    ("ticket_externe", "🔧 Ticket{% endif %}", "🔧 Affaire{% endif %}"),
    ("nouvel_arrivant_bal", "ou ouvrez un ticket depuis", "ou ouvrez une affaire depuis"),
]

#: Le bouton « Consulter le ticket » est partagé par cinq modèles : il se
#: remplace dans TOUS, d'où le code vide.
PARTOUT: list[tuple[str, str]] = [
    ("Consulter le ticket", "Consulter l’affaire"),
    (">Ticket #{{ ticket.numero }}", ">Affaire #{{ ticket.numero }}"),
]

#: Les deux seules colonnes de texte servi. Choisies ici parmi des littéraux —
#: un identifiant ne peut pas se lier en SQLite (`CLAUDE.md`, conventions).
COLONNES = ("libelle", "sujet", "corps_html")


def _remplacer(conn, colonne: str, code: str, ancien: str, nouveau: str) -> None:
    """Un seul balayage pour toutes les colonnes — deux jumelles auraient divergé.

    ⚠️ Jamais de f-string sur les VALEURS (`standards/06` §3) : elles voyagent en
    `bindparams`. Le nom de la colonne, lui, ne vient pas d'une entrée.
    """
    assert colonne in COLONNES, colonne
    ou = "WHERE instr({c}, :ancien) > 0" if not code else "WHERE code = :code AND instr({c}, :ancien) > 0"
    params = {"ancien": ancien, "nouveau": nouveau}
    if code:
        params["code"] = code
    conn.execute(
        sa.text(
            f"UPDATE modele_email SET {colonne} = REPLACE({colonne}, :ancien, :nouveau) "  # noqa: S608
            + ou.format(c=colonne)
        ).bindparams(**params)
    )


def upgrade() -> None:
    conn = op.get_bind()
    for code, ancien, nouveau in REMPLACEMENTS_LIBELLE:
        _remplacer(conn, "libelle", code, ancien, nouveau)
    for code, ancien, nouveau in REMPLACEMENTS:
        _remplacer(conn, "sujet", code, ancien, nouveau)
    for code, ancien, nouveau in REMPLACEMENTS_CORPS:
        _remplacer(conn, "corps_html", code, ancien, nouveau)
    for ancien, nouveau in PARTOUT:
        _remplacer(conn, "corps_html", "", ancien, nouveau)


def downgrade() -> None:
    conn = op.get_bind()
    for ancien, nouveau in reversed(PARTOUT):
        _remplacer(conn, "corps_html", "", nouveau, ancien)
    for code, ancien, nouveau in reversed(REMPLACEMENTS_CORPS):
        _remplacer(conn, "corps_html", code, nouveau, ancien)
    for code, ancien, nouveau in reversed(REMPLACEMENTS):
        _remplacer(conn, "sujet", code, nouveau, ancien)
    for code, ancien, nouveau in reversed(REMPLACEMENTS_LIBELLE):
        _remplacer(conn, "libelle", code, nouveau, ancien)
