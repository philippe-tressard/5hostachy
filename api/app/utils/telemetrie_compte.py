"""Ce que la mesure d'audience garde d'UN compte — et son effacement, écrit une fois (#1629).

Trois tables portent le compte : les évènements (30 jours), la présence
mensuelle et le jour de la dernière visite (12 mois). Deux gestes les
effacent — le compte lui-même depuis son profil (`DELETE /auth/me/telemetrie`,
RGPD art. 17) et l'administrateur qui supprime le compte. Le second n'effaçait
que les évènements : la présence mensuelle d'un compte supprimé restait en
base, sans clé étrangère pour la retenir (`purge_referentielle` ne voit que les
clés déclarées), et un nouveau compte qui aurait repris son identifiant en
aurait hérité. La liste vit ICI, et les deux gestes l'appellent.
"""

from sqlmodel import Session, select

from app.models.telemetrie import DerniereVisite, PresenceMensuelle, TelemetryEvent


def oublier_derniere_visite(session: Session, user_id: int) -> None:
    """Efface le jour de la dernière visite — sans `commit`.

    Aussi au REFUS de la mesure : il ne sert qu'à dire qui ne vient plus, et qui
    a refusé en sort ; le garder ne servirait à rien, donc il ne se garde pas.
    """
    visite = session.get(DerniereVisite, user_id)
    if visite is not None:
        session.delete(visite)


def effacer_telemetrie(session: Session, user_id: int) -> None:
    """Efface tout ce que la mesure d'audience tient de ce compte — sans `commit`."""
    for modele in (TelemetryEvent, PresenceMensuelle):
        for ligne in session.exec(select(modele).where(modele.user_id == user_id)).all():
            session.delete(ligne)
    oublier_derniere_visite(session, user_id)
