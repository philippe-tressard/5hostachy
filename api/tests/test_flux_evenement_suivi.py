"""Le fil d'activité suit l'Historique d'un événement (18/08/2026).

## Pourquoi ce garde-fou

Signalé à l'écran : *« le fil d'actualité suite à un historique n'est pas mis à
jour, seule la notification principale est notifiée avec sa date, mais elle
devrait être réajustée comme ticket »*.

`flux/evenements.py` ne lisait QUE la table `Evenement`. La table
`EvenementEvolution` est née la veille (migration 0150) et **personne n'est venu
l'y brancher** : une affaire passée chez le prestataire ce matin restait datée de
son annonce, donc noyée parmi les vieilles lignes — alors que c'est précisément
l'avancée qu'on vient chercher dans un fil.

⚠️ Ce défaut-là est structurel, pas accidentel : le fil est **une douzaine de
rubriques indépendantes**, et rien n'oblige une table neuve à s'y déclarer. Le
test décrit donc ce qu'on attend d'une rubrique — *le fil date ses lignes du
dernier fait, pas du premier* — et non la ligne de code qui l'implémente.

Il vérifie **le fait** : les cartes réellement produites par `collecter`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import Evenement, RoleUtilisateur, TypeEvenement, Utilisateur
from app.models.evenement import EvenementEvolution
from app.routers.flux.commun import ContexteFlux
from app.routers.flux.evenements import collecter

COMMENTAIRE = "Le prestataire est passé, la vanne est remplacée."


@pytest.fixture()
def contexte():
    """Un événement annoncé il y a dix jours, et son auteur."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = Utilisateur(
            email=f"cs-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x",
            prenom="Camille",
            nom="Sorel",
            role=RoleUtilisateur.conseil_syndical,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        annonce = datetime.utcnow() - timedelta(days=10)
        ev = Evenement(
            titre=f"Remplacement de vanne {uuid.uuid4().hex[:6]}",
            description="<p>Coupure d'eau programmée.</p>",
            type=TypeEvenement.travaux,
            debut=datetime.utcnow() + timedelta(days=2),
            perimetre='["résidence"]',
            statut_kanban="syndic",
            #  `affichable` vaut False par DÉFAUT : un événement qui ne l'a pas
            #  n'entre pas dans le fil. Le premier montage l'oubliait — et le test
            #  de base a échoué AVANT d'avoir rien prouvé, ce qui est exactement ce
            #  qu'on lui demande (`standards/04` §2 : un contrôle qui ne peut pas
            #  mesurer échoue, il ne conclut pas au vert).
            affichable=True,
            auteur_id=user.id,
            cree_le=annonce,
        )
        session.add(ev)
        session.commit()
        session.refresh(ev)

        now = datetime.utcnow()
        ctx = ContexteFlux(
            session=session, user=user, now=now, since=now - timedelta(days=30)
        )
        yield session, ctx, ev, user

        for e in session.exec(
            __import__("sqlmodel").select(EvenementEvolution).where(
                EvenementEvolution.evenement_id == ev.id
            )
        ).all():
            session.delete(e)
        session.delete(session.get(Evenement, ev.id))
        session.delete(session.get(Utilisateur, user.id))
        session.commit()


def _carte(ctx, ev_id: int):
    for c in collecter(ctx):
        if c.meta.get("ev_id") == ev_id:
            return c
    return None


def test_sans_historique_la_carte_reste_datee_de_l_annonce(contexte):
    """Le cas de base — il doit continuer de marcher, sinon on a déplacé le défaut."""
    _session, ctx, ev, _user = contexte
    carte = _carte(ctx, ev.id)
    assert carte is not None, "l'événement a disparu du fil"
    assert carte.date == ev.cree_le
    assert carte.meta.get("evol_contenu") is None


def test_une_entree_d_historique_redate_la_carte(contexte):
    """Le défaut signalé : la carte restait figée à la date de l'annonce."""
    session, ctx, ev, user = contexte
    quand = datetime.utcnow() - timedelta(hours=2)
    session.add(EvenementEvolution(
        evenement_id=ev.id, type="commentaire", contenu=COMMENTAIRE,
        auteur_id=user.id, cree_le=quand,
    ))
    session.commit()

    carte = _carte(ctx, ev.id)
    assert carte is not None
    assert carte.date == quand, (
        f"carte datée du {carte.date} au lieu du {quand} — le fil ignore "
        "l'Historique et l'avancée reste noyée dans les vieilles lignes."
    )
    assert COMMENTAIRE in (carte.meta.get("evol_contenu") or ""), (
        "le texte du suivi n'est pas transporté : la carte remonterait sans dire "
        "ce qui a changé."
    )
    assert carte.meta.get("evol_auteur"), "l'auteur du suivi manque"
    #  L'événement reste l'événement : sa description doit rester lisible sous le
    #  suivi, comme sur un ticket mis à jour.
    assert "Coupure d'eau" in (carte.meta.get("full_html") or "")


def test_un_changement_de_colonne_annonce_l_etat_atteint(contexte):
    """Un `etat` porte sa colonne ; un `commentaire` n'en a pas."""
    session, ctx, ev, user = contexte
    session.add(EvenementEvolution(
        evenement_id=ev.id, type="etat", contenu="", auteur_id=user.id,
        ancien_statut="syndic", nouveau_statut="fournisseur",
        cree_le=datetime.utcnow() - timedelta(hours=1),
    ))
    session.commit()

    carte = _carte(ctx, ev.id)
    assert carte is not None
    assert carte.detail == "Suivi : Prestataire", (
        f"detail = {carte.detail!r} — le libellé doit venir de `KANBAN_LABELS`, "
        "jamais d'une seconde table recopiée dans le fil."
    )


def test_une_seule_ligne_par_evenement_la_plus_recente(contexte):
    """Le fil résume ; l'Historique complet vit sur la fiche."""
    session, ctx, ev, user = contexte
    #  Les deux horodatages sont calculés à partir d'un SEUL `utcnow()` : deux
    #  appels séparés diffèrent de quelques microsecondes, et l'égalité stricte
    #  ci-dessous échouait sur cet écart — un test qui mesure l'heure de sa propre
    #  exécution plutôt que le comportement.
    maintenant = datetime.utcnow()
    recent = maintenant - timedelta(minutes=5)
    for quand, texte in ((maintenant - timedelta(days=3), "ancien"), (recent, "récent")):
        session.add(EvenementEvolution(
            evenement_id=ev.id, type="commentaire", contenu=texte,
            auteur_id=user.id, cree_le=quand,
        ))
    session.commit()

    cartes = [c for c in collecter(ctx) if c.meta.get("ev_id") == ev.id]
    assert len(cartes) == 1, f"{len(cartes)} lignes pour un seul événement"
    assert cartes[0].date == recent
    assert "récent" in (cartes[0].meta.get("evol_contenu") or "")


def test_le_type_reste_evenement(contexte):
    """🔴 Le front teste `type === 'evenement'` à six endroits — dont le filtre
    qui masque les AG à qui n'y a pas droit. Un type propre aux mises à jour
    passerait à côté des six, et une AG commentée deviendrait visible de tous."""
    session, ctx, ev, user = contexte
    session.add(EvenementEvolution(
        evenement_id=ev.id, type="commentaire", contenu=COMMENTAIRE,
        auteur_id=user.id, cree_le=datetime.utcnow(),
    ))
    session.commit()

    carte = _carte(ctx, ev.id)
    assert carte is not None
    assert carte.type == "evenement", (
        f"type = {carte.type!r} : le front ne saurait ni le colorer, ni le lier, "
        "ni surtout appliquer la règle de visibilité des AG."
    )
