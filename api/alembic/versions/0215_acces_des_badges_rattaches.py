"""Ce qu'ouvre un badge rattaché à son lot — rattrapé (#1194, 23/09/2026).

Signalé à l'écran : « plein de Vigik sans porteur ni bâtiment ». Le
rattachement de la v2.24.0 posait le lot et pas l'ACCÈS (`perimetre_cible`),
que tous les autres chemins déduisent — le bâtiment du lot pour un Vigik, les
portails pour une télécommande. Le rattachement le déduit désormais
(`utils/resolution_acces`) ; cette migration le fait pour ceux déjà rattachés.

La règle n'est pas recopiée : c'est celle de l'écran (`utils/acces_gestes`).
Un accès déjà posé — y compris une liste vide, qui veut dire « on ne sait
pas » — ne se touche pas : seuls les `NULL` sont complétés.

Le retour arrière ne défait rien : rien ne distingue après coup un accès
déduit ici d'un accès déduit à l'écran.
"""
from alembic import op
from sqlmodel import Session, select

revision = "0215"
down_revision = "0214"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.utils.acces_gestes import _acces_json
    from app.utils.types_acces import TYPES_ACCES

    with Session(bind=op.get_bind()) as session:
        for t in TYPES_ACCES.values():
            for o in session.exec(select(t.modele).where(
                t.modele.lot_id != None, t.modele.perimetre_cible == None,  # noqa: E711
            )).all():
                o.perimetre_cible = _acces_json(session, t, None, o.lot_id, o.user_id)
                session.add(o)
        session.flush()


def downgrade() -> None:
    pass
