"""Le chemin de réinitialisation d'un mot de passe — jeton, sessions, robustesse.

## Pourquoi ces tests (#771, audit du 05/09/2026)

`routers/auth_mot_de_passe.py` — demande de réinitialisation, réinitialisation,
changement — n'était nommé par **aucun** fichier de tests. C'est un chemin
d'**authentification** : jeton à usage unique, expiration, révocation des
sessions, robustesse du nouveau mot de passe.

🔴 Une régression y est **invisible à l'écran** : un jeton réutilisable ou une
session laissée ouverte après réinitialisation ne fait échouer aucune page. Le
défaut n'apparaît que le jour où quelqu'un s'en sert.

## Ce qui est vérifié ici, et ce qui ne l'est pas

Ces tests exercent les **fonctions du routeur** avec une session réelle, sans
monter de requête HTTP : c'est ce que fait déjà `test_tri_tickets_activite`, et
cela suffit pour les propriétés visées, qui sont toutes des propriétés de la
décision et non du transport.

La **limitation de débit** (`5/minute` sur ces routes) n'est pas éprouvée ici :
elle est portée par slowapi, au niveau du décorateur, et son contrôle vit avec
les autres garde-fous d'autorisation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, select
from starlette.requests import Request

from app.auth.jwt import hash_password, verify_password
from app.database import engine
from app.models.core import (
    PasswordResetToken,
    RefreshToken,
    RoleUtilisateur,
    Utilisateur,
)
from app.routers.auth_mot_de_passe import (
    ChangePasswordBody,
    PasswordResetConfirm,
    change_password,
    reset_password,
)
from app.utils.mots_de_passe import verifier_robustesse
from tests.conftest import requete_de_test
from tests.purge_test import purger_ligne

#: Une requête réelle, fabriquée par `tests/conftest.py` : la fabrique vivait
#: ici, et un second fichier de tests en a eu besoin le 19/09/2026 (#1027).
_Requete = requete_de_test


#: Un mot de passe qui satisfait les quatre critères de `verifier_robustesse`.
VALIDE = "Nouveau-Mdp1"


@pytest.fixture()
def utilisateur():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        u = Utilisateur(
            email=f"reinit-{uuid.uuid4().hex[:8]}@exemple.test",
            hashed_password=hash_password("Ancien-Mdp1"),
            prenom="Reine",
            nom="Ito",
            role=RoleUtilisateur.propriétaire,
            #  `actif` vaut False par défaut : un compte attend sa validation
            #  par le conseil syndical. Un compte de test doit donc l'activer
            #  explicitement, sinon il éprouve le refus, pas la règle.
            actif=True,
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        yield u
        for jeton in session.exec(
            select(PasswordResetToken).where(PasswordResetToken.user_id == u.id)
        ).all():
            session.delete(jeton)
        for rt in session.exec(
            select(RefreshToken).where(RefreshToken.user_id == u.id)
        ).all():
            session.delete(rt)
        session.commit()
        purger_ligne(session, Utilisateur, u.id)
        session.commit()


def _jeton(session: Session, user_id: int, **surcharges) -> PasswordResetToken:
    prt = PasswordResetToken(
        user_id=user_id,
        token=surcharges.pop("token", uuid.uuid4().hex),
        expires_at=surcharges.pop("expires_at", datetime.utcnow() + timedelta(hours=1)),
        **surcharges,
    )
    session.add(prt)
    session.commit()
    session.refresh(prt)
    return prt


# ── La robustesse, aux trois portes ──────────────────────────────────────────

def test_la_regle_de_robustesse_refuse_ce_qu_elle_doit_refuser():
    """Les quatre critères, un par un — sinon « le mot de passe est vérifié »
    reste une affirmation sans contenu."""
    for faible, manque in (
        ("Ab1@", "trop court"),
        ("minuscules1@", "sans majuscule"),
        ("SansChiffre@", "sans chiffre"),
        ("SansSpecial1", "sans caractère spécial"),
    ):
        with pytest.raises(HTTPException) as levee:
            verifier_robustesse(faible)
        assert levee.value.status_code == 400, f"« {faible} » ({manque}) accepté"

    verifier_robustesse(VALIDE)  # ne lève pas


def test_les_TROIS_portes_appellent_la_regle():
    """🔴 La portée fait partie du contrôle.

    Inscription, réinitialisation et changement doivent toutes trois passer par
    `verifier_robustesse`. Une règle centralisée qu'une seule porte emploie
    laisse les deux autres ouvertes — et donne l'illusion des trois
    (`standards/03` §1).
    """
    import ast
    import pathlib

    racine = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
    attendus = {
        "auth.py": ["register"],
        "auth_mot_de_passe.py": ["change_password", "reset_password"],
    }
    for fichier, fonctions in attendus.items():
        arbre = ast.parse((racine / fichier).read_text(encoding="utf-8"))
        #  Le module importe la règle sous un alias : on compare les CORPS, pas
        #  le nom importé — renommer l'alias ne doit pas désarmer le contrôle.
        corps = {
            n.name: ast.unparse(n)
            for n in ast.walk(arbre)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        alias = {
            a.asname or a.name
            for n in ast.walk(arbre)
            if isinstance(n, ast.ImportFrom) and n.module == "app.utils.mots_de_passe"
            for a in n.names
        }
        assert alias, f"{fichier} n'importe plus la règle de robustesse"
        for fonction in fonctions:
            assert fonction in corps, f"`{fonction}` a disparu de {fichier}"
            assert any(f"{nom}(" in corps[fonction] for nom in alias), (
                f"`{fonction}` ({fichier}) ne vérifie plus la robustesse du mot de "
                "passe : un mot de passe faible y passerait."
            )


# ── Le jeton ─────────────────────────────────────────────────────────────────

def test_un_jeton_ne_sert_QU_UNE_fois(utilisateur):
    """Le second usage doit être refusé, même quelques secondes après le premier.

    Sans cela, un lien de réinitialisation retrouvé dans une boîte aux lettres —
    ou dans l'historique d'un poste partagé — rouvre le compte indéfiniment.
    """
    with Session(engine) as session:
        prt = _jeton(session, utilisateur.id)
        reset_password(
            _Requete(), PasswordResetConfirm(token=prt.token, nouveau_mot_de_passe=VALIDE), session
        )
        with pytest.raises(HTTPException) as levee:
            reset_password(
                _Requete(),
                PasswordResetConfirm(token=prt.token, nouveau_mot_de_passe="Autre-Mdp2"),
                session,
            )
        assert levee.value.status_code == 400


def test_un_jeton_EXPIRE_est_refuse(utilisateur):
    """L'expiration est une promesse : « ce lien vaut une heure »."""
    with Session(engine) as session:
        prt = _jeton(session, utilisateur.id, expires_at=datetime.utcnow() - timedelta(minutes=1))
        with pytest.raises(HTTPException) as levee:
            reset_password(
                _Requete(),
                PasswordResetConfirm(token=prt.token, nouveau_mot_de_passe=VALIDE),
                session,
            )
        assert levee.value.status_code == 400


def test_un_jeton_INCONNU_est_refuse(utilisateur):
    """Le cas zéro du contrôle : un jeton fabriqué ne doit rien ouvrir."""
    with Session(engine) as session:
        with pytest.raises(HTTPException):
            reset_password(
                _Requete(),
                PasswordResetConfirm(token="jeton-inexistant", nouveau_mot_de_passe=VALIDE),
                session,
            )


def test_un_compte_DESACTIVE_ne_se_reinitialise_pas(utilisateur):
    """Un compte fermé ne se rouvre pas par la porte du mot de passe oublié."""
    with Session(engine) as session:
        u = session.get(Utilisateur, utilisateur.id)
        u.actif = False
        session.add(u)
        prt = _jeton(session, utilisateur.id)
        session.commit()
        try:
            with pytest.raises(HTTPException):
                reset_password(
                    _Requete(),
                    PasswordResetConfirm(token=prt.token, nouveau_mot_de_passe=VALIDE),
                    session,
                )
        finally:
            u.actif = True
            session.add(u)
            session.commit()


# ── Ce que la réinitialisation doit VRAIMENT faire ───────────────────────────

def test_le_mot_de_passe_change_et_l_ancien_ne_vaut_plus(utilisateur):
    with Session(engine) as session:
        prt = _jeton(session, utilisateur.id)
        reset_password(
            _Requete(), PasswordResetConfirm(token=prt.token, nouveau_mot_de_passe=VALIDE), session
        )
        u = session.get(Utilisateur, utilisateur.id)
        session.refresh(u)
        assert verify_password(VALIDE, u.hashed_password), "le nouveau mot de passe ne vaut pas"
        assert not verify_password("Ancien-Mdp1", u.hashed_password), (
            "l'ancien mot de passe fonctionne encore"
        )


def test_TOUTES_les_sessions_actives_sont_REVOQUEES(utilisateur):
    """🔴 La moitié qu'on oublie, et celle qui compte le plus.

    On réinitialise son mot de passe **parce qu'on craint** que quelqu'un l'ait.
    Laisser ses sessions ouvertes reviendrait à changer la serrure en laissant
    les clés déjà distribuées : le geste rassurerait sans rien fermer.

    Une session déjà révoquée le reste — le test en pose une pour vérifier que la
    révocation ne « dé-révoque » rien au passage.
    """
    with Session(engine) as session:
        vivante = RefreshToken(
            user_id=utilisateur.id,
            token=uuid.uuid4().hex,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        deja_revoquee = RefreshToken(
            user_id=utilisateur.id,
            token=uuid.uuid4().hex,
            expires_at=datetime.utcnow() + timedelta(days=7),
            revoked=True,
        )
        session.add(vivante)
        session.add(deja_revoquee)
        prt = _jeton(session, utilisateur.id)
        session.commit()

        reset_password(
            _Requete(), PasswordResetConfirm(token=prt.token, nouveau_mot_de_passe=VALIDE), session
        )

        restantes = session.exec(
            select(RefreshToken).where(
                RefreshToken.user_id == utilisateur.id,
                RefreshToken.revoked == False,  # noqa: E712
            )
        ).all()
        assert not restantes, (
            "une session reste ouverte après réinitialisation : changer le mot de "
            "passe n'a pas fermé l'accès de celui qui l'avait."
        )


def test_un_mot_de_passe_FAIBLE_est_refuse_AVANT_de_consommer_le_jeton(utilisateur):
    """L'ordre compte : un refus qui aurait brûlé le jeton obligerait à
    redemander un lien pour avoir mal tapé son mot de passe."""
    with Session(engine) as session:
        prt = _jeton(session, utilisateur.id)
        with pytest.raises(HTTPException):
            reset_password(
                _Requete(),
                PasswordResetConfirm(token=prt.token, nouveau_mot_de_passe="faible"),
                session,
            )
        session.refresh(prt)
        assert not prt.used, "le jeton a été consommé par une tentative refusée"


# ── Changer son mot de passe : la porte jumelle ──────────────────────────────
#
#  🔴 Ces quatre tests manquaient, et le défaut avec eux (#1027). `reset_password`
#  révoquait les sessions actives ; `change_password` ne révoquait rien. Un
#  attaquant qui détenait une session ouverte la conservait SEPT JOURS après que
#  la victime avait changé son mot de passe — et la victime croyait avoir
#  refermé la porte.
#
#  Les deux routes posaient un mot de passe chacune à sa façon. Elles passent
#  désormais par `poser_mot_de_passe`, et c'est l'écriture la plus STRICTE qui a
#  gagné, non la plus répandue : en sécurité, la minorité prudente prime
#  (`standards/02` §4 bis).

def _session_ouverte(session: Session, user_id: int, jeton: str | None = None) -> RefreshToken:
    rt = RefreshToken(
        user_id=user_id,
        token=jeton or uuid.uuid4().hex,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    session.add(rt)
    session.commit()
    session.refresh(rt)
    return rt


def _corps(actuel: str = "Ancien-Mdp1", nouveau: str = VALIDE) -> ChangePasswordBody:
    return ChangePasswordBody(mot_de_passe_actuel=actuel, nouveau_mot_de_passe=nouveau)


def test_changer_son_mot_de_passe_REVOQUE_les_AUTRES_sessions(utilisateur):
    """Le défaut exact du 19/09/2026."""
    with Session(engine) as session:
        u = session.get(Utilisateur, utilisateur.id)
        ailleurs = _session_ouverte(session, u.id)

        change_password(_Requete(), _corps(), session, u, refresh_token=None)

        session.refresh(ailleurs)
        assert ailleurs.revoked, (
            "une session ouverte ailleurs survit au changement de mot de passe : "
            "celui qui détenait l'ancien mot de passe garde l'accès."
        )


def test_la_session_COURANTE_survit_au_changement(utilisateur):
    """La décision prise, et son revers : déconnecter l'auteur du geste serait
    sûr mais hostile, et l'inciterait à ne plus changer son mot de passe.

    La session qui présente le jeton est celle de la victime — la requête vient
    d'elle. Les autres tombent.
    """
    with Session(engine) as session:
        u = session.get(Utilisateur, utilisateur.id)
        courante = _session_ouverte(session, u.id)
        ailleurs = _session_ouverte(session, u.id)

        change_password(_Requete(), _corps(), session, u, refresh_token=courante.token)

        session.refresh(courante)
        session.refresh(ailleurs)
        assert not courante.revoked, "la session qui a fait le geste a été fermée"
        assert ailleurs.revoked, "une autre session a survécu"


def test_un_mot_de_passe_ACTUEL_faux_ne_change_ni_ne_revoque_rien(utilisateur):
    """Le cas zéro de la route : sans cette vérification, une session volée
    suffirait à s'approprier le compte."""
    with Session(engine) as session:
        u = session.get(Utilisateur, utilisateur.id)
        ailleurs = _session_ouverte(session, u.id)

        with pytest.raises(HTTPException) as levee:
            change_password(
                _Requete(), _corps(actuel="Pas-Le-Bon1"), session, u, refresh_token=None
            )
        assert levee.value.status_code == 400

        session.refresh(u)
        session.refresh(ailleurs)
        assert verify_password("Ancien-Mdp1", u.hashed_password), "le mot de passe a changé"
        assert not ailleurs.revoked, "des sessions ont été fermées par un refus"


def test_les_DEUX_portes_passent_par_la_MEME_pose_de_mot_de_passe():
    """🔴 La portée, encore : c'est de l'avoir écrite deux fois que vient le défaut.

    Un contrôle qui vérifierait seulement le comportement d'aujourd'hui laisserait
    réapparaître une troisième écriture — la prochaine route qui pose un mot de
    passe. Celui-ci refuse qu'une route en pose un sans passer par la fonction
    commune.
    """
    import ast
    import pathlib

    fichier = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "auth_mot_de_passe.py"
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    corps = {
        n.name: ast.unparse(n)
        for n in ast.walk(arbre)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for porte in ("change_password", "reset_password"):
        assert porte in corps, f"`{porte}` a disparu du routeur"
        assert "poser_mot_de_passe(" in corps[porte], (
            f"`{porte}` pose un mot de passe sans passer par `poser_mot_de_passe` : "
            "la révocation des sessions redevient l'affaire de chaque route."
        )
        assert "hash_password(" not in corps[porte], (
            f"`{porte}` hache un mot de passe lui-même : c'est ainsi que les deux "
            "portes avaient divergé."
        )
