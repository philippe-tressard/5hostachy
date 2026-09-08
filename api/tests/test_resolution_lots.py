"""Les DEUX voies d'auto-résolution rendent le même résultat (#829, 08/09/2026).

## Le défaut

Transformer un `LotImport` rapproché en `Lot` + `UserLot` était écrit **deux
fois**, et les deux chemins sont atteignables depuis l'interface :

- Administration → **Auto-résoudre** (`POST /lots/admin/imports/auto-resoudre`) ;
- **validation d'un compte** (`auto_match_pour_utilisateur`).

Le bloc « trouver ou créer le lot » y était identique au caractère près. **Trois
règles, non** — dont le garde-fou anti-pollution, que seule la seconde portait.
Le résultat dépendait donc du bouton employé, et rien ne le disait.

## Ce que ce fichier verrouille

Le premier test est **le** garde-fou : il compare les deux voies sur le même
import. C'est le seul qui aurait vu la divergence — aucun test unitaire de l'une
ou de l'autre ne peut la détecter, puisque chacune est cohérente avec elle-même.

Les suivants fixent les deux décisions prises en fusionnant :

- 🔴 un import dont un occupant est **locataire** est TRAITÉ (arbitrage du
  08/09/2026), en n'excluant que le LIEN locataire ;
- 🔴 le **garde-fou anti-pollution** s'applique aux deux voies : un
  `utilisateurs_json` devenu faux ne produit pas de `UserLot`, et un lien
  existant qui ne correspond plus est **supprimé**.

⚠️ Ce second point n'est pas du confort. Un `UserLot` donne accès au lot, à ses
badges et à ses documents : c'est une décision d'autorisation.
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Batiment,
    Copropriete,
    Lot,
    LotImport,
    StatutLotImport,
    UserLot,
    Utilisateur,
)
from app.utils.resolution_lots import (
    rapprocher_imports,
    resoudre_imports,
    resoudre_pour_utilisateur,
)


@pytest.fixture()
def scene():
    """Une copropriété, un bâtiment, deux comptes — et la table nettoyée après.

    ⚠️ Rien n'est laissé derrière : `test_copropriete_fiche` supprime toutes les
    copropriétés dans sa propre fixture, et un bâtiment orphelin y ferait tomber
    six tests par un `copropriete_id` NULL sur une colonne NOT NULL. Le piège est
    documenté dans `conftest.py` ; il ne se voit qu'en ajoutant un fichier qui
    trie AVANT lui.
    """
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        marque = uuid.uuid4().hex[:6]
        copro = Copropriete(nom=f"T-{marque}", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        bat = Batiment(copropriete_id=copro.id, numero="1")
        session.add(bat)
        session.flush()
        proprio = Utilisateur(
            email=f"p-{marque}@exemple.test", mot_de_passe_hash="x",
            prenom="Alix", nom="RIVANT", roles_json="propriétaire", actif=True,
        )
        locataire = Utilisateur(
            email=f"l-{marque}@exemple.test", mot_de_passe_hash="x",
            prenom="Camille", nom="BERNAERT", roles_json="résident", actif=True,
        )
        session.add(proprio)
        session.add(locataire)
        session.commit()
        for objet in (copro, bat, proprio, locataire):
            session.refresh(objet)

        yield session, bat, proprio, locataire

        for lien in session.exec(
            select(UserLot).where(UserLot.user_id.in_([proprio.id, locataire.id]))  # type: ignore
        ).all():
            session.delete(lien)
        for imp in session.exec(select(LotImport)).all():
            session.delete(imp)
        for lot in session.exec(select(Lot).where(Lot.batiment_id == bat.id)).all():
            session.delete(lot)
        session.delete(proprio)
        session.delete(locataire)
        session.delete(bat)
        session.delete(copro)
        session.commit()


def _import(bat, numero: str, occupants: list[dict], nom="RIVANT") -> LotImport:
    return LotImport(
        batiment_id=bat.id,
        numero=numero,
        type_raw="AP",
        etage_raw="2EME",
        nom_coproprietaire=nom,
        statut=StatutLotImport.utilisateur_lie,
        utilisateurs_json=json.dumps(occupants, ensure_ascii=False),
    )


def _liens(session, lot_numero: str, bat) -> list[UserLot]:
    lot = session.exec(
        select(Lot).where(Lot.batiment_id == bat.id, Lot.numero == lot_numero)
    ).first()
    if not lot:
        return []
    return list(session.exec(select(UserLot).where(UserLot.lot_id == lot.id)).all())


def test_les_DEUX_voies_rendent_le_meme_resultat(scene):
    """🔴 LE garde-fou de #829, et le seul qui pouvait voir la divergence.

    Aucun test unitaire de l'une ou de l'autre voie ne l'aurait détectée :
    chacune était cohérente avec elle-même. Ce n'est qu'en les CONFRONTANT sur le
    même import que la différence apparaît.
    """
    session, bat, proprio, locataire = scene
    #  ⚠️ L'import porte un LOCATAIRE à dessein. Sur un import banal — un seul
    #  copropriétaire, nom concordant — les deux voies s'accordaient déjà : ce
    #  test serait passé au vert AVANT le correctif, et n'aurait rien prouvé.
    #  C'est précisément sur ce cas-là qu'elles divergeaient (l'une sautait tout
    #  l'import, l'autre n'excluait que le lien).
    occupants = [
        {"user_id": proprio.id, "type_lien": "propriétaire"},
        {"user_id": locataire.id, "type_lien": "locataire"},
    ]

    session.add(_import(bat, "A101", occupants))
    session.commit()
    resoudre_imports(session)
    session.commit()
    par_admin = sorted((lien.user_id, lien.type_lien.value) for lien in _liens(session, "A101", bat))

    session.add(_import(bat, "A102", occupants))
    session.commit()
    resoudre_pour_utilisateur(proprio, session)
    session.commit()
    par_compte = sorted((lien.user_id, lien.type_lien.value) for lien in _liens(session, "A102", bat))

    assert par_admin == par_compte, (
        "les deux voies d'auto-résolution ne produisent pas les mêmes liens : "
        f"admin={par_admin} · validation de compte={par_compte}. Le résultat "
        "dépend du bouton employé, et rien à l'écran ne le dit."
    )
    assert par_admin, "cas zéro : aucune des deux voies n'a rien produit"


def test_un_import_avec_un_LOCATAIRE_est_traite_et_seul_le_lien_est_exclu(scene):
    """🔴 L'arbitrage du 08/09/2026.

    L'une des deux voies sautait **tout l'import** dès qu'un occupant était
    locataire : le lot n'était pas créé, et le copropriétaire restait sans accès
    à son propre lot. La décision retenue est de traiter l'import et de n'exclure
    que le LIEN locataire — son rattachement relève du workflow de bail.
    """
    session, bat, proprio, locataire = scene
    session.add(_import(bat, "A201", [
        {"user_id": proprio.id, "type_lien": "propriétaire"},
        {"user_id": locataire.id, "type_lien": "locataire"},
    ]))
    session.commit()

    stats = resoudre_imports(session)
    session.commit()

    assert stats["resolus"] == 1, (
        "l'import a été sauté parce qu'un occupant est locataire : le "
        "copropriétaire reste sans accès à son propre lot."
    )
    lies = {lien.user_id for lien in _liens(session, "A201", bat)}
    assert proprio.id in lies, "le copropriétaire n'a pas été rattaché"
    assert locataire.id not in lies, (
        "le locataire a été rattaché automatiquement : son rattachement relève "
        "du workflow de bail, pas de l'import."
    )


@pytest.mark.parametrize("voie", ["admin", "compte"], ids=["admin", "compte"])
def test_le_garde_fou_ANTI_POLLUTION_vaut_pour_les_deux_voies(scene, voie):
    """🔴 Une entrée devenue fausse ne doit pas donner accès au lot d'un autre.

    `utilisateurs_json` est écrit par le rapprochement automatique ; une entrée
    périmée — nom corrigé dans le classeur, homonyme écarté — y reste. Sans
    revalidation, elle produit un `UserLot`, donc l'accès d'une personne au lot
    d'une autre, à ses badges et à ses documents.

    ⚠️ La voie « admin » ne portait PAS ce garde-fou. C'est ce que l'onglet
    « Audit des lots » existe pour nettoyer après coup.
    """
    session, bat, proprio, locataire = scene
    #  Le classeur dit RIVANT ; `utilisateurs_json` désigne BERNAERT.
    session.add(_import(
        bat, "A301",
        [{"user_id": locataire.id, "type_lien": "propriétaire"}],
        nom="RIVANT",
    ))
    session.commit()

    if voie == "admin":
        resoudre_imports(session)
    else:
        resoudre_pour_utilisateur(locataire, session)
    session.commit()

    lies = {lien.user_id for lien in _liens(session, "A301", bat)}
    assert locataire.id not in lies, (
        f"[{voie}] un compte dont le nom ne correspond PAS à la ligne du "
        "classeur a été rattaché au lot. Il en voit les badges et les documents."
    )


def test_un_lien_devenu_faux_est_SUPPRIME_pas_seulement_ignore(scene):
    """Ignorer ne suffit pas : le lien déjà posé continuerait de donner accès."""
    session, bat, proprio, locataire = scene
    lot = Lot(batiment_id=bat.id, numero="A401", type="appartement")
    session.add(lot)
    session.flush()
    session.add(UserLot(user_id=locataire.id, lot_id=lot.id, type_lien="propriétaire", actif=True))
    session.add(_import(
        bat, "A401",
        [{"user_id": locataire.id, "type_lien": "propriétaire"}],
        nom="RIVANT",
    ))
    session.commit()

    resoudre_imports(session)
    session.commit()

    assert locataire.id not in {lien.user_id for lien in _liens(session, "A401", bat)}, (
        "le lien erroné préexistant a survécu : la revalidation doit le "
        "SUPPRIMER, pas seulement s'abstenir d'en créer un second."
    )


def test_cas_zero_un_import_SANS_occupant_n_est_pas_resolu(scene):
    """Sans occupant, il n'y a rien à rattacher — et le compte le dit."""
    session, bat, _, _ = scene
    session.add(_import(bat, "A501", []))
    session.commit()

    stats = resoudre_imports(session)
    session.commit()

    assert stats["resolus"] == 0
    assert stats["sans_occupant"] == 1, (
        "un import sans occupant doit être COMPTÉ, pas passé sous silence : "
        "c'est ce chiffre qui dit à l'admin qu'il reste du travail."
    )


def test_le_rapprochement_ne_regresse_JAMAIS_un_import_deja_lie(scene):
    """L'affectation du statut à trois branches, et pourquoi elle est retenue.

    Les deux copies d'origine ne l'écrivaient pas pareil : l'une choisissait
    entre `lot_lie` et `utilisateur_lie`, l'autre gardait un repli `en_attente`.
    Le repli est aujourd'hui inatteignable — on n'arrive là qu'après avoir posé
    un lot ou des occupants — mais la version courte cesserait d'être équivalente
    au premier ajout d'une façon de marquer un changement.
    """
    session, bat, proprio, _ = scene
    lot = Lot(batiment_id=bat.id, numero="A601", type="appartement")
    session.add(lot)
    session.add(LotImport(
        batiment_id=bat.id, numero="A601", type_raw="AP",
        nom_coproprietaire="RIVANT", statut=StatutLotImport.en_attente,
        utilisateurs_json="[]",
    ))
    session.commit()

    rapprocher_imports(session)
    session.commit()

    imp = session.exec(select(LotImport).where(LotImport.numero == "A601")).first()
    assert imp.lot_id == lot.id, "le lot existant n'a pas été retrouvé"
    assert imp.statut == StatutLotImport.lot_lie, (
        f"statut inattendu après rapprochement : {imp.statut}"
    )
