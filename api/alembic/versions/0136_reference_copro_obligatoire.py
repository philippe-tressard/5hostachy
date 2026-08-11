"""La référence de copropriété : dans TOUT message au syndic, sous UNE forme.

C'est l'identifiant du dossier chez lui : un message qui ne la porte pas sort de
son tri par affaire. L'état de départ montre pourquoi une règle « sans
exception » ne tient pas quand elle est recopiée dans chaque modèle — quatre
manières différentes de ne pas la respecter coexistaient :

- `ticket_syndic`, `publication_syndic` — présente à la **création**, absente du
  **commentaire**. C'est-à-dire absente de l'échange qui suit une transmission,
  donc précisément là où le rattachement au dossier compte ;
- `ticket_externe`, `publication_externe` — absente des deux branches, et pas
  même fournie par leur point d'appel. Ces canaux s'adressent « au syndic ou à
  un tiers » (cf. l'en-tête de `seed/emails/tickets.py`) : l'adresse est saisie
  à la main et le code ne peut pas savoir laquelle des deux ;
- `relance_syndic` — présente, mais sous une forme à elle : « [🏢 00213] – »
  quand les autres écrivaient « 🏢 00213 — » ;
- `nouvel_arrivant_bal` — conforme, seul de son espèce.

Les six objets pointent désormais vers `{{ prefixe_copro }}`, composé par
`email._prefixe_copro` et injecté **après** le contexte de l'appelant, donc ni
omissible ni surchargeable. Le `{% if reference_copro %}` disparaît des modèles :
il y était recopié sept fois, et un modèle se réécrit depuis Admin → Emails — une
règle qu'un formulaire peut retirer n'est pas une règle.

Ce déplacement en crée un autre, assumé : la clé vide ne produit plus rien de
visible. C'est pourquoi `health_monitor._check_reference_copro` alerte désormais
le gestionnaire du site quand elle n'est pas renseignée — sans lui, la règle
serait vérifiée sur les modèles et fausse à chaque envoi.

`REPLACE()` sur fragment ciblé, comme 0131 et 0135 : les personnalisations faites
depuis Admin → Emails survivent, et aucun fragment de remplacement ne contient
celui qu'il remplace — c'est ce qui rend la migration rejouable sans appliquer
l'ajout deux fois. `test_email_templates` le vérifie sur toutes les migrations.

Revision ID: 0136
Revises: 0135
Create Date: 2026-08-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0136"
down_revision = "0135"
branch_labels = None
depends_on = None

#  Le préambule tel qu'il était recopié dans les objets. Il n'est plus écrit
#  nulle part après cette migration : sa forme vit dans `email._prefixe_copro`.
_ANCIEN = "{% if reference_copro %}\U0001f3e2 {{ reference_copro }} — {% endif %}"
_NOUVEAU = "{{ prefixe_copro }}"

# (code du modèle, fragment actuel, fragment voulu)
REMPLACEMENTS: list[tuple[str, str, str]] = [
    #  Les deux modèles « syndic » : la branche de création portait le préambule,
    #  celle du commentaire ne portait rien. D'où deux opérations de nature
    #  différente sur le même objet — remplacer d'un côté, ajouter de l'autre.
    ("ticket_syndic",
     "{% else %}" + _ANCIEN + "Ticket #",
     "{% else %}" + _NOUVEAU + "Ticket #"),
    ("ticket_syndic",
     "{% if is_commentaire %}\U0001f4ac Commentaire",
     "{% if is_commentaire %}" + _NOUVEAU + "\U0001f4ac Commentaire"),
    ("publication_syndic",
     "{% else %}" + _ANCIEN + "Nouvelle publication",
     "{% else %}" + _NOUVEAU + "Nouvelle publication"),
    ("publication_syndic",
     "{% if is_commentaire %}\U0001f4ac Commentaire sur",
     "{% if is_commentaire %}" + _NOUVEAU + "\U0001f4ac Commentaire sur"),
    #  Les canaux externes : rien dans aucune des deux branches.
    ("ticket_externe",
     "{% if is_commentaire %}Relance Ticket #",
     "{% if is_commentaire %}" + _NOUVEAU + "Relance Ticket #"),
    ("ticket_externe",
     "{% else %}Ticket #",
     "{% else %}" + _NOUVEAU + "Ticket #"),
    ("publication_externe",
     "{% if is_commentaire %}Relance {{ publication.titre }}",
     "{% if is_commentaire %}" + _NOUVEAU + "Relance {{ publication.titre }}"),
    ("publication_externe",
     "{% else %}{{ publication.titre }} — {{ residence.nom }}",
     "{% else %}" + _NOUVEAU + "{{ publication.titre }} — {{ residence.nom }}"),
    #  Forme divergente : crochets et tiret demi-cadratin.
    ("relance_syndic",
     "[\U0001f3e2 {{ reference_copro }}] – Relance ticket(s)",
     _NOUVEAU + "Relance ticket(s)"),
    #  Déjà conforme au fond, mais il portait sa propre copie du préambule.
    ("nouvel_arrivant_bal",
     _ANCIEN + "Nouvel arrivant",
     _NOUVEAU + "Nouvel arrivant"),
]


def _remplacer(conn, code: str, ancien: str, nouveau: str) -> None:
    conn.execute(
        sa.text(
            "UPDATE modele_email SET sujet = REPLACE(sujet, :ancien, :nouveau) "
            "WHERE code = :code AND instr(sujet, :ancien) > 0"
        ).bindparams(code=code, ancien=ancien, nouveau=nouveau)
    )


def upgrade():
    conn = op.get_bind()
    for code, ancien, nouveau in REMPLACEMENTS:
        _remplacer(conn, code, ancien, nouveau)


def downgrade():
    conn = op.get_bind()
    #  Ordre inverse : plusieurs remplacements portent sur le même objet, et
    #  défaire le premier avant le second retirerait un fragment que le second
    #  attend encore.
    for code, ancien, nouveau in reversed(REMPLACEMENTS):
        _remplacer(conn, code, nouveau, ancien)
