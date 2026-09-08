"""Garde-fou — **les deux chaînes d'import d'accès résolvent PAREIL** (#847).

## Le défaut qui a motivé ces tests

`imports_telecommandes` reportait la possession physique sur l'objet créé :

    tc = Telecommande(..., chez_locataire=imp.chez_locataire and bool(imp.user_locataire_id))

`imports_vigik`, ligne pour ligne son jumeau, **ne le faisait pas**. Un badge
Vigik résolu au bénéfice d'un locataire arrivait donc marqué « chez le
propriétaire ».

Et ce drapeau **décide** : `routers/bailleur/acces.py` ne propose au transfert
que les accès `not chez_locataire`, et `_assert_transferable` refuse ceux déjà
remis au titre d'un autre bail. Le badge se serait donc proposé au transfert vers
le locataire suivant alors qu'il était déjà dans la poche du locataire en place —
et le bailleur l'aurait « transféré » sans l'avoir en main.

⚠️ Ce test ne vérifie pas que le code appelle le socle : **il éprouve le
résultat**. Un jour, quelqu'un réécrira une des deux résolutions en ligne pour
« faire simple », et c'est le comportement qui doit le refuser, pas la forme.

## Ce qui est verrouillé, et dans quel sens

1. la **possession** est reportée sur l'objet, pour les DEUX types ;
2. la **correction** d'un import déjà résolu redescend sur l'objet — elle ne le
   faisait nulle part avant le 08/09/2026 ;
3. le **détenteur** est le locataire quand il l'a en main, le propriétaire sinon,
   et un import coché « chez le locataire » SANS locataire lié n'invente personne ;
4. le **cas zéro** : sans le report, l'objet dit le contraire de l'import.
"""
from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    StatutImport,
    Telecommande,
    TelecommandeImport,
    Utilisateur,
    UserTelecommande,
    UserVigik,
    Vigik,
    VigikImport,
)
from app.routers.acces import socle_imports
from app.routers.acces.imports_telecommandes import TELECOMMANDE
from app.routers.acces.imports_vigik import VIGIK
from app.routers.acces.socle_imports import PatchImportBody

#: Les deux chaînes, avec de quoi fabriquer un import de staging pour chacune.
#: ⚠️ Le paramétrage porte le CHAMP de référence, pas une valeur codée en dur :
#: c'est justement ce champ qui diffère, et l'écrire ici le rendrait faux le jour
#: où il change.
#: Le quatrième élément est la table de liaison M2M, nécessaire au NETTOYAGE :
#: `conftest` active `foreign_keys=ON` (#546), donc supprimer un utilisateur
#: encore référencé échoue — et l'échec survient en teardown, où il est le plus
#: pénible à lire.
CHAINES = [
    pytest.param(
        TELECOMMANDE, TelecommandeImport, Telecommande, UserTelecommande,
        id="telecommande",
    ),
    pytest.param(VIGIK, VigikImport, Vigik, UserVigik, id="vigik"),
]


@pytest.fixture()
def deux_comptes():
    """Un propriétaire et un locataire, réels — les clés étrangères sont actives."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        jeton = uuid.uuid4().hex[:8]
        proprio = Utilisateur(
            email=f"proprio-{jeton}@exemple.test", mot_de_passe_hash="x",
            prenom="P", nom="PROPRIO", actif=True,
        )
        locataire = Utilisateur(
            email=f"loc-{jeton}@exemple.test", mot_de_passe_hash="x",
            prenom="L", nom="LOCATAIRE", actif=True,
        )
        session.add(proprio)
        session.add(locataire)
        session.commit()
        session.refresh(proprio)
        session.refresh(locataire)
        yield session, proprio, locataire
        session.delete(proprio)
        session.delete(locataire)
        session.commit()


def _creer_import(type_import, modele_import, proprio, locataire, session, *, chez_locataire):
    imp = modele_import(
        nom_proprietaire="PROPRIO P",
        nom_locataire="LOCATAIRE L",
        user_proprietaire_id=proprio.id,
        user_locataire_id=locataire.id if locataire else None,
        chez_locataire=chez_locataire,
        statut=StatutImport.proprietaire_lie,
    )
    setattr(imp, type_import.champ_reference, f"REF-{uuid.uuid4().hex[:6]}")
    session.add(imp)
    session.commit()
    session.refresh(imp)
    return imp


def _purger(session, type_import, modele_import, modele_objet, modele_liaison, import_id):
    """Defait TOUTE la chaine creee : lien, liaisons M2M, objet, import.

    ATTENTION a l'ORDRE, et il n'est pas negociable : les cles etrangeres sont
    actives (#546) et AUCUNE relation SQLAlchemy n'est declaree entre ces tables,
    donc rien n'ordonne les DELETE a notre place. L'import pointe vers l'objet
    (`champ_lien`), et les liaisons M2M aussi : supprimer l'objet d'abord echoue,
    et l'echec survient en teardown, la ou il est le plus penible a lire.
    """
    imp = session.get(modele_import, import_id)
    objet_id = getattr(imp, type_import.champ_lien) if imp else None

    if imp and objet_id:
        setattr(imp, type_import.champ_lien, None)
        session.add(imp)
        session.flush()

    if objet_id:
        for liaison in session.exec(
            select(modele_liaison).where(
                getattr(modele_liaison, type_import.champ_lien) == objet_id
            )
        ).all():
            session.delete(liaison)
        session.flush()
        objet = session.get(modele_objet, objet_id)
        if objet:
            session.delete(objet)
            session.flush()

    if imp:
        session.delete(imp)
    session.commit()


@pytest.mark.parametrize("type_import,modele_import,modele_objet,modele_liaison", CHAINES)
def test_la_POSSESSION_est_reportee_sur_l_objet(
    type_import, modele_import, modele_objet, modele_liaison, deux_comptes
):
    """🔴 Le défaut lui-même — il n'existait que côté Vigik."""
    session, proprio, locataire = deux_comptes
    imp = _creer_import(
        type_import, modele_import, proprio, locataire, session, chez_locataire=True
    )
    try:
        socle_imports.resoudre(type_import, imp.id, session)
        objet = session.get(modele_objet, getattr(session.get(modele_import, imp.id),
                                                  type_import.champ_lien))
        assert objet is not None, "la résolution n'a créé aucun objet"
        assert objet.user_id == locataire.id, (
            "l'accès a été affecté au propriétaire alors qu'il est chez le locataire"
        )
        assert objet.chez_locataire is True, (
            f"{type_import.libelle} : la possession physique n'a pas été reportée. "
            "L'accès se proposera au transfert vers le locataire SUIVANT alors "
            "qu'il est déjà remis (routers/bailleur/acces.py)."
        )
    finally:
        _purger(session, type_import, modele_import, modele_objet, modele_liaison, imp.id)


@pytest.mark.parametrize("type_import,modele_import,modele_objet,modele_liaison", CHAINES)
def test_la_CORRECTION_d_un_import_resolu_redescend_sur_l_objet(
    type_import, modele_import, modele_objet, modele_liaison, deux_comptes
):
    """L'import et l'objet ne peuvent pas dire deux choses différentes.

    Avant le 08/09/2026, aucune des deux chaînes ne reportait `chez_locataire`
    lors d'une correction : on cochait « chez le locataire » sur l'import, et
    l'objet — le seul que lit le transfert de bail — continuait d'affirmer le
    contraire.
    """
    session, proprio, locataire = deux_comptes
    imp = _creer_import(
        type_import, modele_import, proprio, locataire, session, chez_locataire=False
    )
    try:
        socle_imports.resoudre(type_import, imp.id, session)
        socle_imports.patch(
            type_import, imp.id, PatchImportBody(chez_locataire=True), session
        )

        recharge = session.get(modele_import, imp.id)
        objet = session.get(modele_objet, getattr(recharge, type_import.champ_lien))
        assert objet.chez_locataire is True, (
            f"{type_import.libelle} : la correction n'a pas atteint l'objet."
        )
        assert objet.user_id == locataire.id
    finally:
        _purger(session, type_import, modele_import, modele_objet, modele_liaison, imp.id)


@pytest.mark.parametrize("type_import,modele_import,modele_objet,modele_liaison", CHAINES)
def test_chez_le_locataire_SANS_locataire_lie_n_invente_personne(
    type_import, modele_import, modele_objet, modele_liaison, deux_comptes
):
    """Le cas tordu que la case seule ne suffit pas à décrire.

    Un import coché « chez le locataire » dont le locataire n'est pas encore
    inscrit ne doit pas produire un objet remis à quelqu'un d'introuvable : il
    reste chez le propriétaire jusqu'à ce que le compte existe.
    """
    session, proprio, _ = deux_comptes
    imp = _creer_import(
        type_import, modele_import, proprio, None, session, chez_locataire=True
    )
    try:
        socle_imports.resoudre(type_import, imp.id, session)
        recharge = session.get(modele_import, imp.id)
        objet = session.get(modele_objet, getattr(recharge, type_import.champ_lien))
        assert objet.user_id == proprio.id
        assert objet.chez_locataire is False, (
            "l'objet se dit chez un locataire qui n'est lié à personne — "
            "`bailleur/acces.py` refuserait ensuite de le transférer sans "
            "pouvoir dire à qui il est."
        )
    finally:
        _purger(session, type_import, modele_import, modele_objet, modele_liaison, imp.id)


def test_cas_zero_SANS_report_l_objet_dit_le_CONTRAIRE_de_l_import(deux_comptes):
    """🔴 La preuve que les tests ci-dessus mesurent quelque chose.

    On reproduit ici, à la main, l'ancienne création du Vigik — celle qui ne
    passait pas `chez_locataire`. Si cette assertion tombait, c'est que le
    modèle aurait pris un défaut à `True`, et les trois tests précédents
    passeraient au vert **sans rien prouver**.
    """
    session, proprio, locataire = deux_comptes
    ancien = Vigik(
        code=f"ZERO-{uuid.uuid4().hex[:6]}",
        lot_id=None,
        user_id=locataire.id,
        # `chez_locataire` volontairement OMIS — c'était le code du 07/09/2026.
    )
    session.add(ancien)
    session.commit()
    session.refresh(ancien)
    try:
        assert ancien.chez_locataire is False, (
            "`Vigik.chez_locataire` vaut désormais True par défaut : le défaut "
            "de #847 serait masqué, et ce garde-fou ne verrait plus rien."
        )
    finally:
        session.delete(ancien)
        session.commit()


def test_les_DEUX_chaines_sont_bien_deux(deux_comptes):
    """Cas zéro de la PORTÉE — deux paramètres identiques ne prouveraient rien.

    `standards/04` §40 : la portée d'un contrôle fait partie du contrôle. Si un
    copier-coller faisait pointer `VIGIK` et `TELECOMMANDE` sur le même modèle,
    tout ce fichier passerait en n'éprouvant qu'une seule chaîne.
    """
    assert TELECOMMANDE.modele_import is not VIGIK.modele_import
    assert TELECOMMANDE.modele_objet is not VIGIK.modele_objet
    assert TELECOMMANDE.champ_reference != VIGIK.champ_reference
    assert TELECOMMANDE.champ_lien != VIGIK.champ_lien
    assert TELECOMMANDE.creer_liaisons is not VIGIK.creer_liaisons
    assert len(CHAINES) == 2
