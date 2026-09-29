"""L'affaire dit si son intervenant agit sous contrat — et lequel (#1445).

Une affaire désignait un prestataire, jamais le contrat : `utils/prochaine_visite`
le DEVINAIT (libellé du contrat dans le titre, à défaut le seul contrat actif),
et un dépannage hors contrat avançait la visite d'entretien.

Colonne simple, **sans clé étrangère** : SQLite refuse d'en ajouter une à une
table existante, et la migration crasherait après avoir posé la colonne (0117,
0165). La règle vit dans `utils/intervenant.contrat_valide`.

## La reprise — deux sources, dans cet ordre

1. **L'événement d'origine** : la 0212 a fait des événements du calendrier des
   affaires, en recopiant prestataire et fréquence mais PAS `evenement.contrat_id`
   (0165). Il est repris, si le contrat est celui du même prestataire.
2. **La règle d'avant**, appliquée une dernière fois aux affaires Entretien
   récurrentes restantes : le contrat en cours du prestataire dont le libellé
   figure dans le titre, à défaut son seul contrat en cours.

Sous contrat, le rythme est celui du contrat : celui de l'affaire est effacé.
Une reprise vers un contrat SANS fréquence n'est pas faite — l'affaire
perdrait son rythme ; elle reste hors contrat, comme avant.

Idempotente : une affaire rattachée n'est plus candidate. `downgrade` retire la
colonne ; les fréquences effacées ne reviennent pas (le contrat les porte).
"""

import sqlalchemy as sa
from alembic import op

revision = "0235"
down_revision = "0234"
branch_labels = None
depends_on = None

TABLE = "ticket"
#  Identifiant de colonne : constante de ce fichier, jamais une saisie.
COLONNE = "contrat_id"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def _contrats_en_cours(conn) -> list[dict]:
    lignes = conn.execute(
        sa.text(
            "SELECT id, prestataire_id, libelle, frequence_type FROM contrat_entretien "
            "WHERE actif = 1 AND type_equipement NOT IN ('assurance', 'syndic')"
        )
    ).mappings()
    return [dict(ligne) for ligne in lignes]


def retenir(contrats: list[dict], prestataire_id: int, titre: str) -> dict | None:
    """La règle d'AVANT (`apres_cloture` jusqu'au 28/09/2026), appliquée une fois."""
    siens = [c for c in contrats if c["prestataire_id"] == prestataire_id]
    par_titre = next(
        (c for c in siens if c["libelle"] and c["libelle"].lower() in (titre or "").lower()),
        None,
    )
    return par_titre or (siens[0] if len(siens) == 1 else None)


def _rattacher(conn, ticket_id: int, contrat_id: int) -> None:
    conn.execute(
        sa.text(
            "UPDATE ticket SET contrat_id = :contrat, frequence_type = NULL, "
            "frequence_valeur = NULL WHERE id = :ticket"
        ).bindparams(contrat=contrat_id, ticket=ticket_id)
    )


def upgrade():
    conn = op.get_bind()
    if COLONNE not in _colonnes(conn):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer(), nullable=True))

    contrats = _contrats_en_cours(conn)
    par_id = {c["id"]: c for c in contrats}

    #  1. Le contrat de l'événement d'origine.
    if "evenement" in sa.inspect(conn).get_table_names():
        origines = conn.execute(
            sa.text(
                "SELECT t.id, t.prestataire_id, e.contrat_id FROM ticket t "
                "JOIN evenement e ON e.id = t.promu_depuis_evenement_id "
                "WHERE t.contrat_id IS NULL AND t.prestataire_id IS NOT NULL "
                "AND e.contrat_id IS NOT NULL AND t.categorie = :entretien"
            ).bindparams(entretien="entretien")
        ).all()
        for ticket_id, prestataire_id, contrat_id in origines:
            c = par_id.get(contrat_id)
            if c and c["prestataire_id"] == prestataire_id and c["frequence_type"]:
                _rattacher(conn, ticket_id, contrat_id)

    #  2. La règle d'avant, sur les Entretien récurrents restants.
    restants = conn.execute(
        sa.text(
            "SELECT id, prestataire_id, titre FROM ticket "
            "WHERE contrat_id IS NULL AND prestataire_id IS NOT NULL "
            "AND frequence_type IS NOT NULL AND categorie = :entretien"
        ).bindparams(entretien="entretien")
    ).all()
    for ticket_id, prestataire_id, titre in restants:
        c = retenir(contrats, prestataire_id, titre)
        if c and c["frequence_type"]:
            _rattacher(conn, ticket_id, c["id"])


def downgrade():
    if COLONNE in _colonnes(op.get_bind()):
        with op.batch_alter_table(TABLE) as lot:
            lot.drop_column(COLONNE)
