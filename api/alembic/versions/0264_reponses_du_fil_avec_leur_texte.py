"""Les réponses déjà inscrites au fil reprennent le texte de leur message.

Signalé le 05/10/2026 : sur la carte d'une affaire, la réponse d'un résident
apparaissait comme un en-tête sans corps (« 20:30 · Nom ») alors que le courriel
envoyé au conseil citait le message. `add_message` journalisait l'entrée
`reponse` sans texte : la fiche montre les messages dans son fil de bulles, la
carte de liste ne rend que l'Historique.

Le code écrit désormais le texte et les pièces à la naissance de l'entrée ; cette
migration rattrape celles d'avant.

## Comment on retrouve le message

L'entrée et le message n'ont aucun lien en base : ils sont écrits dans la même
requête, par le même auteur, à quelques millisecondes d'écart. Pour chaque entrée
`reponse` encore vide, on prend le message PUBLIC du même ticket et du même
auteur le plus proche dans le temps, à moins de `ECART_MAX` — et chaque message
ne sert qu'une fois. Une entrée sans message plausible reste vide : on ne devine
pas, on ne comble pas au hasard.

Un message interne n'est jamais copié (son entrée porte « Message interne »).

Idempotente : ne touche que les entrées au contenu vide.

⚠️ Les noms de table sont des CONSTANTES du fichier ; les valeurs sont liées.

Revision ID: 0264
Revises: 0263
"""

from datetime import datetime, timedelta

import sqlalchemy as sa

from alembic import op

revision = "0264"
down_revision = "0263"
branch_labels = None
depends_on = None

EVOLUTIONS = "ticket_evolution"  # identifiants : constantes du fichier
MESSAGES = "message_ticket"

#: Les deux lignes naissent dans la même requête : quelques millisecondes. Cinq
#: secondes laissent de la marge à une base lente sans confondre deux messages.
ECART_MAX = timedelta(seconds=5)


def _date(valeur) -> datetime:
    return valeur if isinstance(valeur, datetime) else datetime.fromisoformat(str(valeur))


def rattraper(conn) -> int:
    """Remplit les entrées `reponse` vides ; rend le nombre d'entrées remplies."""
    tables = set(sa.inspect(conn).get_table_names())
    if not {EVOLUTIONS, MESSAGES} <= tables:
        return 0

    vides = conn.execute(
        sa.text(
            "SELECT id, ticket_id, auteur_id, cree_le, fichiers_urls FROM ticket_evolution "
            "WHERE type = 'reponse' AND (contenu IS NULL OR contenu = '')"
        )
    ).all()
    messages = conn.execute(
        sa.text(
            "SELECT id, ticket_id, auteur_id, cree_le, contenu, fichiers_urls "
            "FROM message_ticket WHERE interne = 0"
        )
    ).all()

    par_auteur: dict[tuple[int, int], list] = {}
    for m in messages:
        par_auteur.setdefault((m.ticket_id, m.auteur_id), []).append(m)

    pris: set[int] = set()
    remplies = 0
    for e in vides:
        quand = _date(e.cree_le)
        candidats = [
            m
            for m in par_auteur.get((e.ticket_id, e.auteur_id), [])
            if m.id not in pris and abs(_date(m.cree_le) - quand) <= ECART_MAX
        ]
        if not candidats:
            continue
        m = min(candidats, key=lambda c: abs(_date(c.cree_le) - quand))
        pris.add(m.id)
        pieces = e.fichiers_urls if e.fichiers_urls not in (None, "", "[]") else m.fichiers_urls
        conn.execute(
            sa.text(
                "UPDATE ticket_evolution SET contenu = :contenu, fichiers_urls = :pieces "
                "WHERE id = :id"
            ).bindparams(contenu=m.contenu, pieces=pieces or "[]", id=e.id)
        )
        remplies += 1
    return remplies


def upgrade() -> None:
    rattraper(op.get_bind())


def downgrade() -> None:
    # Le texte copié est une donnée vraie, pas un schéma : on ne le retire pas.
    pass
