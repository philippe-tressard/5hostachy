"""Le drapeau `archivee` atteint-il vraiment l'écran ? — bout en bout, par objet.

## 🔴 Pourquoi ce fichier (02/09/2026, question posée à l'écran)

Cinq objets ont été branchés sur la règle d'archivage du site dans la journée.
Sur deux d'entre eux — la Boîte à idées et les Sondages — l'utilisateur n'a vu
**aucune section Archives** apparaître.

Deux explications possibles, et on ne peut pas les départager en regardant :

  1. il n'y a rien à archiver dans les données (aucune idée décidée ni aucun
     sondage clos depuis plus de 30 jours) — auquel cas tout va bien ;
  2. le drapeau ne sort pas de l'API, et **aucun objet ne s'archivera jamais**.

⚠️ La seconde a failli arriver le jour même, sur les tickets : `archivee` était
passé à `TicketRead(...)` sans avoir été ajouté au schéma, et **Pydantic l'ignore
en silence**. Les 970 tests, `svelte-check` et Ruff sont tous restés verts.
`test_schemas_champs.py` couvre ce cas-là ; celui-ci couvre le reste du chemin.

## Ce que ce fichier vérifie, et ce que les autres ne vérifient pas

| Fichier | Ce qu'il éprouve |
|---|---|
| `test_archivage.py` | la **décision** — 52 cas sur les sept règles |
| `test_archivage_branche.py` | qu'une règle déclarée est **appelée** quelque part |
| `test_schemas_champs.py` | qu'un champ passé à un schéma y est **déclaré** |
| **celui-ci** | que le drapeau **sort du point d'entrée**, avec la bonne valeur |

Autrement dit : les trois premiers vérifient chacun un maillon, celui-ci tire sur
la chaîne. C'est `standards/04` §14 — observer la chose, pas son enregistrement.

⚠️ Les fonctions de routeur sont appelées DIRECTEMENT, comme
`test_calendrier_lot.py` : ce qu'on vérifie est ce que l'objet rendu contient,
pas un code HTTP.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.communaute import Idee, Sondage
from app.models.core import RoleUtilisateur, Utilisateur
from app.routers.idees import list_idees
from app.routers.sondages.crud import list_sondages
from tests.purge_test import purger_ligne

#: Bien au-delà du délai du site (30 jours), pour que le test ne dépende pas du
#: réglage courant : s'il passait à 60, ce cas resterait juste.
VIEUX = timedelta(days=400)


@pytest.fixture()
def auteur():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        u = Utilisateur(
            email=f"arch-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x", prenom="Alix", nom="Renard",
            role=RoleUtilisateur.conseil_syndical,
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        yield u
        purger_ligne(session, Utilisateur, u.id)
        session.commit()


def _sans_bruit(rendus, ids):
    """Ne garder que ce que CE test a créé — la base porte d'autres objets."""
    return [o for o in rendus if (o["id"] if isinstance(o, dict) else o.id) in ids]


def test_une_idee_decidee_il_y_a_longtemps_ressort_archivee(auteur):
    """🔴 Le cas que l'écran ne pouvait pas départager d'une absence de données."""
    with Session(engine) as session:
        vieille = Idee(
            titre="Composteur collectif", description="…", auteur_id=auteur.id,
            statut="retenue", statut_change_le=datetime.utcnow() - VIEUX,
        )
        recente = Idee(
            titre="Local à vélos", description="…", auteur_id=auteur.id,
            statut="retenue", statut_change_le=datetime.utcnow(),
        )
        #  Une idée OUVERTE ne s'archive pas, quelle que soit son ancienneté : elle
        #  n'a pas de décision à dater. C'est ce qui distingue « rien à archiver »
        #  de « le drapeau ne sort pas ».
        ouverte = Idee(
            titre="Repas de quartier", description="…", auteur_id=auteur.id,
            statut="ouverte", cree_le=datetime.utcnow() - VIEUX,
        )
        session.add_all([vieille, recente, ouverte])
        session.commit()
        for o in (vieille, recente, ouverte):
            session.refresh(o)
        ids = {vieille.id, recente.id, ouverte.id}
        try:
            rendus = {
                i["id"]: i for i in _sans_bruit(list_idees(session=session, user=auteur), ids)
            }
            assert set(rendus) == ids, "les trois idées doivent être rendues"
            assert rendus[vieille.id]["archivee"] is True, (
                "une idée retenue il y a plus d'un an doit ressortir ARCHIVÉE — "
                "si elle ne l'est pas, aucune section Archives n'apparaîtra jamais"
            )
            assert rendus[recente.id]["archivee"] is False
            assert rendus[ouverte.id]["archivee"] is False, (
                "une idée sans décision n'a rien à dater : elle reste active"
            )
        finally:
            for o in (vieille, recente, ouverte):
                purger_ligne(session, Idee, o.id)
            session.commit()


def test_un_sondage_clos_il_y_a_longtemps_ressort_archive(auteur):
    """Même chaîne, sur l'autre objet dont l'écran ne montrait rien."""
    with Session(engine) as session:
        vieux = Sondage(
            question="Couleur du hall ?", auteur_id=auteur.id,
            cloture_le=datetime.utcnow() - VIEUX,
        )
        recent = Sondage(
            question="Horaires du local ?", auteur_id=auteur.id,
            cloture_le=datetime.utcnow(),
        )
        #  Sans date de clôture, on ne sait pas dater : on n'archive pas.
        sans_date = Sondage(question="Idées pour la fête ?", auteur_id=auteur.id)
        session.add_all([vieux, recent, sans_date])
        session.commit()
        for o in (vieux, recent, sans_date):
            session.refresh(o)
        ids = {vieux.id, recent.id, sans_date.id}
        try:
            rendus = {s.id: s for s in _sans_bruit(list_sondages(session=session, user=auteur), ids)}
            assert set(rendus) == ids, "les trois sondages doivent être rendus"
            assert rendus[vieux.id].archivee is True, (
                "un sondage clos il y a plus d'un an doit ressortir ARCHIVÉ"
            )
            assert rendus[recent.id].archivee is False
            assert rendus[sans_date.id].archivee is False, (
                "sans date de clôture, rien à dater : on n'archive pas (cas zéro)"
            )
        finally:
            for o in (vieux, recent, sans_date):
                purger_ligne(session, Sondage, o.id)
            session.commit()
