"""L'objet des e-mails de tickets et de publications nomme ce dont il parle.

« 🏢 00213 — Ticket #TK-427648 — 5Hostachy » n'apprenait rien à qui reçoit dix
messages par jour : il fallait ouvrir pour savoir de quel sujet il s'agissait, et
deux tickets de la même copropriété avaient des objets interchangeables. Le titre
est désormais dans l'objet.

Il est placé **avant** le nom de la résidence, et non à la fin : un client de
messagerie n'affiche qu'une soixantaine de caractères, et sur les trois
informations de cet objet, celle que le destinataire ne connaît pas encore est le
titre. La résidence est ce qu'on accepte de perdre à la troncature.

`REPLACE()` sur un fragment ciblé, comme 0131 : la personnalisation faite depuis
Admin → Emails sur le reste de l'objet survit. Aucun fragment de remplacement ne
contient celui qu'il remplace — c'est ce qui rend la migration rejouable sans
faire apparaître le titre deux fois, et `test_email_templates` le vérifie.

⚠️ La borne de longueur et l'assainissement de l'objet ne sont **pas** ici :
un modèle est réécrivable depuis l'administration, donc une règle de sûreté qui y
serait écrite pourrait être retirée par un formulaire. Elle vit dans
`app/utils/email.py` (`_sujet_sur_une_ligne`), qui s'applique à l'objet rendu.

Revision ID: 0135
Revises: 0134
Create Date: 2026-08-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0135"
down_revision = "0134"
branch_labels = None
depends_on = None

#  Deux modèles se terminent exactement pareil : écrit une fois, sinon les deux
#  fragments divergeraient au premier ajustement.
_NUMERO_PUIS_RESIDENCE = (
    "Ticket #{{ ticket.numero }} — {{ residence.nom }}",
    "Ticket #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}",
)

# (code du modèle, fragment actuel, fragment voulu)
REMPLACEMENTS: list[tuple[str, str, str]] = [
    #  `ticket_syndic` porte ce fragment deux fois — à la création et sur la
    #  branche « commentaire ». `REPLACE()` traite les deux occurrences.
    ("ticket_syndic", *_NUMERO_PUIS_RESIDENCE),
    ("ticket_nouveau_message", *_NUMERO_PUIS_RESIDENCE),
    (
        "ticket_statut_change",
        "mis à jour — {{ residence.nom }}",
        "mis à jour — {{ ticket.titre }} — {{ residence.nom }}",
    ),
    (
        "ticket_bug_admin",
        "via Tickets — {{ residence.nom }}",
        "via Tickets — {{ ticket.titre }} — {{ residence.nom }}",
    ),
    #  Seule la branche « nouvelle publication » est aveugle : celle du
    #  commentaire nomme déjà la publication.
    (
        "publication_syndic",
        "Nouvelle publication{% endif %}",
        "Nouvelle publication — {{ publication.titre }}{% endif %}",
    ),
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
    for code, ancien, nouveau in REMPLACEMENTS:
        _remplacer(conn, code, nouveau, ancien)
