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

import itertools
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
from app.routers.auth_mot_de_passe import PasswordResetConfirm, reset_password
from app.utils.mots_de_passe import verifier_robustesse
from tests.purge_test import purger_ligne

#: Chaque requête de test vient d'une adresse distincte (voir `_Requete`).
_compteur_ip = itertools.count()

#: Un mot de passe qui satisfait les quatre critères de `verifier_robustesse`.
VALIDE = "Nouveau-Mdp1"


def _Requete() -> Request:
    """Une vraie requête Starlette, minimale.

    ⚠️ Un objet imitateur ne suffit pas : la limitation de débit (slowapi) est
    posée en décorateur sur ces routes et exige une `starlette.requests.Request`
    — elle lit l'adresse du client pour compter. Le contourner en retirant le
    décorateur reviendrait à tester une fonction que la production n'exécute pas.
    """
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/reinitialiser-mot-de-passe",
            "headers": [],
            "query_string": b"",
            "scheme": "https",
            "server": ("test", 443),
            #  🔴 UNE ADRESSE DIFFÉRENTE À CHAQUE APPEL. La limitation est de
            #  5/minute PAR CLIENT : sans cela, le sixième test de ce fichier
            #  recevrait un 429 et échouerait pour une raison qui n'a rien à
            #  voir avec ce qu'il vérifie. On ne désarme pas le décorateur — on
            #  cesse d'être le même visiteur.
            "client": (f"10.0.0.{next(_compteur_ip) % 250 + 1}", 51234),
        }
    )


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
