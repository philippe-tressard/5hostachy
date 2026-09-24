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

import pathlib
import uuid

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.copropriete import Lot
from app.models.core import (
    StatutImport,
    Telecommande,
    TelecommandeImport,
    Utilisateur,
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
#: (La table de liaison M2M qui venait en quatrième a disparu le 23/09/2026,
#: #1194 : les porteurs se déduisent du lot.)
CHAINES = [
    pytest.param(TELECOMMANDE, TelecommandeImport, Telecommande, id="telecommande"),
    pytest.param(VIGIK, VigikImport, Vigik, id="vigik"),
]


@pytest.fixture()
def deux_comptes():
    """Un propriétaire et un locataire, réels — les clés étrangères sont actives."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        jeton = uuid.uuid4().hex[:8]
        proprio = Utilisateur(
            email=f"proprio-{jeton}@exemple.test",
            mot_de_passe_hash="x",
            prenom="P",
            nom="PROPRIO",
            actif=True,
        )
        locataire = Utilisateur(
            email=f"loc-{jeton}@exemple.test",
            mot_de_passe_hash="x",
            prenom="L",
            nom="LOCATAIRE",
            actif=True,
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
    #  Le lot est ce qui rend une ligne rattachable depuis #1194 : un compte
    #  propriétaire n'y suffit plus.
    lot = Lot(numero=f"L-{uuid.uuid4().hex[:6]}", type=type_import.types_lot[0])
    session.add(lot)
    session.commit()
    imp = modele_import(
        lot_id=lot.id,
        nom_proprietaire="PROPRIO P",
        nom_locataire="LOCATAIRE L",
        user_proprietaire_id=proprio.id,
        user_locataire_id=locataire.id if locataire else None,
        chez_locataire=chez_locataire,
        statut=StatutImport.proprietaire_lie,
    )
    setattr(imp, type_import.colonne_code_import, f"REF-{uuid.uuid4().hex[:6]}")
    session.add(imp)
    session.commit()
    session.refresh(imp)
    return imp


def _purger(session, type_import, modele_import, modele_objet, import_id):
    """Defait TOUTE la chaine creee : lien, liaisons M2M, objet, import.

    ATTENTION a l'ORDRE, et il n'est pas negociable : les cles etrangeres sont
    actives (#546) et AUCUNE relation SQLAlchemy n'est declaree entre ces tables,
    donc rien n'ordonne les DELETE a notre place. L'import pointe vers l'objet
    (`champ_lien`), et les liaisons M2M aussi : supprimer l'objet d'abord echoue,
    et l'echec survient en teardown, la ou il est le plus penible a lire.
    """
    imp = session.get(modele_import, import_id)
    objet_id = getattr(imp, type_import.colonne_import) if imp else None
    lot_id = imp.lot_id if imp else None

    if imp and objet_id:
        setattr(imp, type_import.colonne_import, None)
        session.add(imp)
        session.flush()

    if objet_id:
        objet = session.get(modele_objet, objet_id)
        if objet:
            session.delete(objet)
            session.flush()

    if imp:
        session.delete(imp)
        session.flush()
    if lot_id:
        session.delete(session.get(Lot, lot_id))
    session.commit()


@pytest.mark.parametrize("type_import,modele_import,modele_objet", CHAINES)
def test_la_POSSESSION_est_reportee_sur_l_objet(
    type_import, modele_import, modele_objet, deux_comptes
):
    """🔴 Le défaut lui-même — il n'existait que côté Vigik."""
    session, proprio, locataire = deux_comptes
    imp = _creer_import(
        type_import, modele_import, proprio, locataire, session, chez_locataire=True
    )
    try:
        socle_imports.resoudre(type_import, imp.id, session)
        objet = session.get(
            modele_objet, getattr(session.get(modele_import, imp.id), type_import.colonne_import)
        )
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
        _purger(session, type_import, modele_import, modele_objet, imp.id)


@pytest.mark.parametrize("type_import,modele_import,modele_objet", CHAINES)
def test_la_CORRECTION_d_un_import_resolu_redescend_sur_l_objet(
    type_import, modele_import, modele_objet, deux_comptes
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
        socle_imports.patch(type_import, imp.id, PatchImportBody(chez_locataire=True), session)

        recharge = session.get(modele_import, imp.id)
        objet = session.get(modele_objet, getattr(recharge, type_import.colonne_import))
        assert objet.chez_locataire is True, (
            f"{type_import.libelle} : la correction n'a pas atteint l'objet."
        )
        assert objet.user_id == locataire.id
    finally:
        _purger(session, type_import, modele_import, modele_objet, imp.id)


@pytest.mark.parametrize("type_import,modele_import,modele_objet", CHAINES)
def test_chez_le_locataire_SANS_compte_reste_chez_le_locataire(
    type_import, modele_import, modele_objet, deux_comptes
):
    """🔴 Inversé le 23/09/2026 (#1194) : le fait physique prime sur le compte.

    Ce test exigeait l'inverse — un badge remis à un locataire sans compte était
    déclaré « chez le propriétaire », et nommait le propriétaire comme détenteur.
    Le badge appartient désormais au lot : remis au locataire, il est porté par
    le locataire DU LOT (`utils/porteurs_acces`), inscrit ou non, et il ne se
    propose plus au transfert — ce qui est exact, il n'est plus disponible.
    """
    session, proprio, _ = deux_comptes
    imp = _creer_import(type_import, modele_import, proprio, None, session, chez_locataire=True)
    try:
        socle_imports.resoudre(type_import, imp.id, session)
        recharge = session.get(modele_import, imp.id)
        objet = session.get(modele_objet, getattr(recharge, type_import.colonne_import))
        assert objet.chez_locataire is True
        assert objet.user_id is None, "le propriétaire est nommé détenteur d'un badge qu'il n'a pas"
    finally:
        _purger(session, type_import, modele_import, modele_objet, imp.id)


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
    assert TELECOMMANDE.modele is not VIGIK.modele
    assert TELECOMMANDE.colonne_code_import != VIGIK.colonne_code_import
    assert TELECOMMANDE.colonne_import != VIGIK.colonne_import
    assert len(CHAINES) == 2


def test_UN_SEUL_objet_decrit_les_deux_types_d_acces():
    """🔴 Le garde-fou du 18/09/2026 : pas de second descripteur.

    `routers/acces/socle_imports.py` en portait un — `TypeImportAcces` — qui
    redisait cinq des six champs de `TypeAcces` sous d'autres noms
    (`modele_objet`, `champ_reference`, `champ_lien`…), et qui exportait des
    constantes du MÊME nom, `VIGIK` et `TELECOMMANDE`, dans deux modules
    différents. Deux objets pour une notion : la divergence n'était pas un
    risque théorique, c'est l'histoire de ce paquet.

    Le contrôle est simple et vérifiable : la déclaration de ces deux constantes
    n'existe qu'à UN endroit dans `app/`.
    """
    import re

    racine = pathlib.Path(__file__).resolve().parents[1] / "app"
    declarations: dict[str, list[str]] = {"VIGIK": [], "TELECOMMANDE": []}
    fichiers = [p for p in racine.rglob("*.py") if "__pycache__" not in str(p)]
    assert fichiers, "aucun module lu — le contrôle ne peut pas conclure"

    for chemin in fichiers:
        source = chemin.read_text(encoding="utf-8")
        for nom in declarations:
            if re.search(rf"^{nom} = ", source, re.MULTILINE):
                declarations[nom].append(str(chemin.relative_to(racine)).replace("\\", "/"))

    for nom, lieux in declarations.items():
        assert lieux == ["utils/types_acces.py"], (
            f"`{nom}` est déclaré dans {lieux} — il doit l'être dans "
            "`utils/types_acces.py` et nulle part ailleurs. Un second "
            "descripteur du même type d'accès divergera du premier."
        )
