"""La durée ANNONCÉE au résident est celle du jeton qu'il reçoit.

POURQUOI CE TEST (16/09/2026) :

`auth.py` émettait le lien de vérification d'adresse à DEUX endroits —
l'inscription et le renvoi — et la durée y était écrite **quatre** fois :

    timedelta(hours=24)     la validité réelle du jeton      ×2
    "expire_heures": 24     ce que le courriel annonce       ×2

Rien ne les liait. Changer la validité réelle sans toucher aux deux littéraux
aurait fait **mentir le message** : « ce lien est valable 24 heures » sur un lien
mort depuis douze. Et l'écart n'aurait été visible que pour le résident dont le
lien expire plus tôt qu'annoncé — c'est-à-dire pour personne qui puisse le
signaler utilement.

Les deux viennent maintenant de `VALIDITE_VERIFICATION_EMAIL`, et ce test vérifie
le **fait** plutôt que la forme : il émet un vrai courriel de vérification et
compare l'heure d'expiration du jeton réellement posé à la durée annoncée dans le
contexte. Une réécriture qui redéclarerait un littéral échouerait ici, quelle que
soit la façon dont elle s'y prend.
"""
import uuid
from datetime import datetime

from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import EmailVerificationToken, Utilisateur
from app.routers.auth import VALIDITE_VERIFICATION_EMAIL, emettre_verification_email


class _TachesDeFond:
    """Une doublure de `BackgroundTasks` qui retient ce qu'on lui confie."""

    def __init__(self):
        self.taches = []

    def add_task(self, fonction, *args, **kwargs):
        self.taches.append((fonction, args, kwargs))


def _emettre(session):
    """Un compte neuf, puis l'émission réelle du lien de vérification."""
    user = Utilisateur(
        email=f"verif-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x",
        prenom="Test",
        nom="Durée",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    taches = _TachesDeFond()
    avant = datetime.utcnow()
    emettre_verification_email(session, user, taches)
    return user, taches, avant


def _jeton(session, user_id):
    return session.exec(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
    ).one()


def test_la_duree_annoncee_est_celle_du_jeton_pose():
    """Le cœur : ce que le courriel promet est ce que la base applique."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user, taches, avant = _emettre(session)
        jeton = _jeton(session, user.id)

    assert len(taches.taches) == 1, f"un seul envoi attendu, reçu {len(taches.taches)}"
    contexte = taches.taches[0][2]["context"]

    heures_annoncees = contexte["expire_heures"]
    heures_reelles = (jeton.expires_at - avant).total_seconds() / 3600

    #  Une seconde de tolérance : les deux horodatages ne sont pas pris au même
    #  instant. Ce qu'on refuse, c'est un ÉCART DE DURÉE, pas une microseconde.
    assert abs(heures_reelles - heures_annoncees) < 0.01, (
        f"le courriel annonce {heures_annoncees} h, le jeton expire dans "
        f"{heures_reelles:.2f} h — le message ment au résident"
    )


def test_la_duree_vient_de_la_constante_partagee():
    """Le cas zéro : sans lui, le test ci-dessus passerait sur deux littéraux égaux.

    Deux `24` écrits séparément donnent le même résultat — c'est précisément ce
    qui rendait le défaut invisible. On vérifie donc que la valeur annoncée est
    bien DÉDUITE de `VALIDITE_VERIFICATION_EMAIL`, en la comparant à elle.
    """
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _user, taches, _avant = _emettre(session)
    contexte = taches.taches[0][2]["context"]

    attendu = int(VALIDITE_VERIFICATION_EMAIL.total_seconds() // 3600)
    assert contexte["expire_heures"] == attendu, (
        f"le contexte annonce {contexte['expire_heures']} h là où la constante "
        f"vaut {attendu} h — un littéral a été réintroduit"
    )


def test_le_lien_porte_le_jeton_reellement_pose():
    """Un lien qui ne porte pas LE jeton créé mène à une page d'erreur.

    Les deux étaient composés côte à côte dans les blocs recopiés ; les séparer
    dans une fonction rendait l'erreur possible, ce contrôle la rend visible.
    """
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user, taches, _avant = _emettre(session)
        jeton = _jeton(session, user.id)
    contexte = taches.taches[0][2]["context"]

    assert contexte["token"] == jeton.token
    assert f"token={jeton.token}" in contexte["lien"], (
        f"le lien ne porte pas le jeton posé : {contexte['lien']}"
    )
