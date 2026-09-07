"""La clôture d'un sondage : UNE définition, et elle vit côté serveur (#468).

Le serveur savait déjà répondre — `sondage_clos()` — mais n'exposait sa réponse
que sur la **fiche** (`GET /sondages/{id}`). La **liste** ne renvoyait que
`cloture_le` et `cloture_forcee` : la page n'avait donc pas le choix, elle
recalculait la règle en JavaScript.

Deux implémentations d'une même question, dont une seule fait autorité. Elles
étaient d'accord — et deux listes d'accord entre elles ne prouvent rien : elles
divergent à la première règle ajoutée. Les candidats n'étaient même pas
hypothétiques :

  • **le fuseau** — le front comparait `cloture_le` à `new Date()`, l'heure locale
    du navigateur, quand le serveur date en UTC. Un sondage clôturant à minuit
    était clos ou non selon d'où on le lisait ;
  • **une règle métier future** — « clôture quand tout le monde a voté »,
    « prolongation si quorum non atteint » — s'écrira côté serveur, et la liste
    aurait continué d'appliquer l'ancienne.

Ce que ce fichier vérifie, et que rien ne vérifiait :

  1. `GET /sondages` **transporte** la réponse (`cloture`), sur les deux voies de
     clôture — l'échéance passée et la clôture forcée ;
  2. la **liste** et la **fiche** ne se contredisent jamais, sondage par sondage ;
  3. la liste ne se contredit pas **elle-même** : un seul instant sert à dater
     toute la page, jamais un `utcnow()` par sondage.

⚠️ Ce test ne réécrit **pas** la règle de clôture. La comparer à une copie
reviendrait à comparer une fonction à elle-même — c'est la leçon de #415, déjà
écrite en tête de `test_compteurs_tableau_de_bord.py`. Il compare deux **chemins**
qui doivent dire la même chose.
"""
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import Batiment, Copropriete, Lot, Sondage, Utilisateur
from app.routers.sondages.crud import get_sondage, list_sondages
from app.seed.patrimoine import poser_arborescence
from app.utils import perimetres as P
from tests.conftest import vider_patrimoine

MODELES_ECRITS = (Sondage, Lot, Utilisateur)


@pytest.fixture()
def base():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session, MODELES_ECRITS)
        copro = Copropriete(nom="Test clôture", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        session.add(Batiment(copropriete_id=copro.id, numero="1"))
        session.commit()
        poser_arborescence(session)
        session.commit()
        P.invalider_cache()
        yield session
        vider_patrimoine(session, MODELES_ECRITS)
    P.invalider_cache()


def _cs(session: Session) -> Utilisateur:
    u = Utilisateur(
        nom="N", prenom="cs", email="cs@test.fr", roles_json="conseil_syndical",
        actif=True, decision_compte_le=datetime.utcnow(),
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _sondage(session: Session, auteur_id: int, question: str, **kw) -> Sondage:
    s = Sondage(question=question, auteur_id=auteur_id, **kw)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def test_la_liste_transporte_la_cloture_sur_les_deux_voies(base):
    """Échéance passée ET clôture forcée : la liste le DIT, elle ne le suggère pas."""
    cs = _cs(base)
    _sondage(base, cs.id, "ouvert")
    _sondage(base, cs.id, "echeance-passee", cloture_le=datetime.utcnow() - timedelta(days=1))
    _sondage(base, cs.id, "echeance-future", cloture_le=datetime.utcnow() + timedelta(days=7))
    _sondage(base, cs.id, "force", cloture_forcee=True)

    par_question = {s.question: s for s in list_sondages(session=base, user=cs)}
    assert len(par_question) == 4, "la fixture n'a pas produit les quatre cas"

    assert par_question["ouvert"].cloture is False
    assert par_question["echeance-future"].cloture is False
    assert par_question["echeance-passee"].cloture is True, (
        "une échéance passée ne se voit QUE si le serveur la transporte — c'est "
        "exactement ce que la page devait recalculer avant #468"
    )
    assert par_question["force"].cloture is True


def test_la_liste_et_la_fiche_ne_se_contredisent_jamais(base):
    """Le défaut du 17/07/2026, en germe : visible dans une vue, absent de l'autre."""
    cs = _cs(base)
    _sondage(base, cs.id, "ouvert")
    _sondage(base, cs.id, "echeance-passee", cloture_le=datetime.utcnow() - timedelta(days=1))
    _sondage(base, cs.id, "force", cloture_forcee=True)

    for lu in list_sondages(session=base, user=cs):
        fiche = get_sondage(sondage_id=lu.id, session=base, user=cs)
        assert lu.cloture == fiche["cloture"], (
            f"« {lu.question} » : la liste dit {lu.cloture}, la fiche dit "
            f"{fiche['cloture']} — deux écrans du même objet ne peuvent pas trancher "
            "différemment (`ux-patterns` §16)"
        )


def test_un_seul_instant_date_toute_la_liste(base):
    """Douze sondages, douze `utcnow()` : la page se contredirait elle-même.

    Le cas est étroit mais réel — une échéance qui tombe PENDANT la construction
    de la réponse serait close pour les sondages évalués après, ouverte pour ceux
    évalués avant, dans une seule et même page. C'est pourquoi `sondage_clos()`
    reçoit `maintenant` en paramètre au lieu de le lire lui-même, et c'est ce que
    ce test verrouille : la liste ne doit appeler l'horloge qu'une fois.
    """
    import app.routers.sondages.crud as crud

    cs = _cs(base)
    for i in range(5):
        _sondage(base, cs.id, f"s{i}", cloture_le=datetime.utcnow() + timedelta(days=1))

    appels = {"n": 0}
    vrai_datetime = crud.datetime

    class _HorlogeComptee:
        @staticmethod
        def utcnow():
            appels["n"] += 1
            return vrai_datetime.utcnow()

        def __getattr__(self, nom):  # tout le reste passe au vrai module
            return getattr(vrai_datetime, nom)

    crud.datetime = _HorlogeComptee()
    try:
        list_sondages(session=base, user=cs)
    finally:
        crud.datetime = vrai_datetime

    assert appels["n"] == 1, (
        f"{appels['n']} appels à utcnow() pour une seule liste — un par sondage "
        "signifie que la page ne date pas ses clôtures au même instant"
    )
