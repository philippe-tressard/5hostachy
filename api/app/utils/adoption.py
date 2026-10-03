"""Quelle part de la résidence se sert du site — le taux d'adoption (#1628).

## Pourquoi (03/10/2026)

Le tableau de bord donnait des volumes : 40 utilisateurs actifs, c'est beaucoup
sur 50 comptes et peu sur 200. Le taux rapporte les comptes VENUS sur la
période aux comptes qui POUVAIENT venir.

## La règle

- **dénominateur** : les comptes ouverts (`actif`), MOINS ceux qui ont refusé la
  mesure d'audience — leurs visites ne sont pas enregistrées, les compter
  ferait baisser le taux par construction. Leur nombre est rendu à côté, pour
  que l'écran le dise ;
- **numérateur** : ceux de ces comptes qui ont au moins un événement de
  télémétrie sur les `JOURS` derniers jours — la durée de conservation des
  événements détaillés, au-delà de laquelle on ne sait plus qui est venu ;
- ventilé par **profil** — les rôles, CUMULÉS : un copropriétaire membre du
  conseil compte sous « Propriétaire » et sous « Conseil syndical », donc les
  lignes ne s'additionnent pas —, par **type de résident** (le statut :
  copropriétaire résident, bailleur, locataire…) et par **bâtiment**
  (`libelle_batiment`). Libellés de `roles_libelles`, jamais réécrits ici.
  Présentation arbitrée sur maquette le 03/10/2026 (« Qui vient »).

Chaque ligne porte ses deux nombres avec le taux : sur un bâtiment de trois
comptes, « 33 % » ne veut rien dire seul.
"""

from datetime import timedelta

from sqlmodel import Session, select

from app.models.copropriete import Batiment
from app.models.core import TelemetryEvent, Utilisateur
from app.utils import horloge
from app.utils.batiments import libelle_batiment_ou
from app.utils.roles_libelles import libelle_role, libelle_statut

JOURS = 30

#: Le libellé d'un compte sans bâtiment — syndic, compte technique, arrivant
#: pas encore rattaché.
SANS_BATIMENT = "Sans bâtiment"


def _ligne(libelle: str, comptes: list[Utilisateur], actifs: set[int]) -> dict:
    venus = sum(1 for c in comptes if c.id in actifs)
    return {
        "libelle": libelle,
        "actifs": venus,
        "comptes": len(comptes),
        "taux": round(100 * venus / len(comptes)) if comptes else None,
    }


def _par(comptes: list[Utilisateur], libelles, actifs: set[int]) -> list[dict]:
    """Une ligne par libellé ; `libelles(compte)` en rend un ou plusieurs."""
    groupes: dict[str, list[Utilisateur]] = {}
    for c in comptes:
        for libelle in libelles(c):
            groupes.setdefault(libelle, []).append(c)
    lignes = [_ligne(libelle, groupe, actifs) for libelle, groupe in groupes.items()]
    return sorted(lignes, key=lambda ligne: (-ligne["comptes"], ligne["libelle"]))


def adoption(session: Session) -> dict:
    """Le taux d'adoption sur les `JOURS` derniers jours, et sa ventilation."""
    ouverts = session.exec(select(Utilisateur).where(Utilisateur.actif == True)).all()  # noqa: E712
    mesures = [c for c in ouverts if not c.opt_out_telemetrie]
    depuis = horloge.maintenant() - timedelta(days=JOURS)
    actifs = set(
        session.exec(
            select(TelemetryEvent.user_id)
            .where(TelemetryEvent.cree_le >= depuis, TelemetryEvent.user_id.isnot(None))
            .distinct()
        ).all()
    )
    batiments = {b.id: b for b in session.exec(select(Batiment)).all()}
    return {
        "jours": JOURS,
        "global": _ligne("Tous les comptes", mesures, actifs),
        "refus": len(ouverts) - len(mesures),
        "par_profil": _par(mesures, lambda c: [libelle_role(r) for r in c.roles], actifs),
        "par_type": _par(mesures, lambda c: [libelle_statut(c.statut)], actifs),
        "par_batiment": _par(
            mesures,
            lambda c: [libelle_batiment_ou(batiments.get(c.batiment_id), SANS_BATIMENT)],
            actifs,
        ),
    }
