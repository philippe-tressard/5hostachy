"""Rattacher une ligne d'import à son badge — écrit une fois (#1194).

## Ce qui a changé le 23/09/2026

Résoudre une ligne **exigeait un compte** propriétaire (422 sinon), puis
attribuait le badge à des personnes, une par une, dans `user_vigik` /
`user_telecommande`. Deux conséquences mesurées : la majorité des lignes ne
pouvaient pas se résoudre, et un conjoint inscrit plus tard ne voyait rien.

La ligne se résout désormais **par son lot** : c'est lui qui est obligatoire,
et les porteurs s'en déduisent à la lecture (`utils/porteurs_acces`). Aucune
attribution n'est plus écrite.

## 🔴 Ce que ce module remplace

La création de l'objet était écrite **deux fois** : `socle_imports.resoudre`
(l'écran) et `_auto_match_acces` (l'inscription d'un résident). Une troisième
aurait suivi avec le rattachement en masse.

## Un code, un objet

Le code d'un badge est unique (migration 0213). Les fichiers du syndic, eux,
répètent des codes — 16 fois pour les télécommandes. Une seconde ligne qui porte
un code déjà connu se rattache donc à l'objet existant au lieu d'en créer un.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.core import StatutAcces, StatutImport
from app.utils.acces_possession import chez_le_locataire, possesseur


def exiger_code_libre(session: Session, type_acces, code: str, sauf_id: int | None = None) -> None:
    """Refuse un code déjà porté par un AUTRE badge — 400, et non l'erreur d'intégrité.

    Trois gestes créent ou renomment un badge à la main : le parc du conseil
    syndical (création, correction) et la déclaration par un résident. Le code
    était vérifié « pour cette personne », jamais pour tout le parc : deux objets
    pouvaient porter le même numéro gravé.
    """
    modele = type_acces.modele
    autre = session.exec(select(modele).where(modele.code == code)).first()
    if autre is not None and autre.id != sauf_id:
        raise HTTPException(400, f"{type_acces.libelle} {code} déjà enregistré")


def en_stock(imp) -> bool:
    """Une ligne « STOCK » : un badge de réserve, pas encore affecté (23/09/2026).

    Le fichier du syndic écrit « STOCK » à la place du propriétaire. Le badge
    existe, dans un tiroir : il entre au parc SANS lot, et le conseil syndical
    l'affecte le jour où il le remet.
    """
    from app.utils.auto_match_service import _cle_de_nom

    return _cle_de_nom(imp.nom_proprietaire) == "stock"


def peut_se_rattacher(type_acces, imp) -> bool:
    """Une ligne se rattache si elle a un code et un lot — ou si elle est en stock."""
    return (
        imp.statut in (StatutImport.en_attente, StatutImport.proprietaire_lie)
        and (bool(imp.lot_id) or en_stock(imp))
        and bool(getattr(imp, type_acces.colonne_code_import))
    )


def rattacher(type_acces, imp, session: Session):
    """Pose le badge de cette ligne sur son lot, et rend l'objet. Sans `commit`."""
    if imp.statut == StatutImport.resolu:
        raise HTTPException(400, "Import déjà résolu")
    if imp.statut == StatutImport.ignore:
        raise HTTPException(400, "Cet import est ignoré")
    code = getattr(imp, type_acces.colonne_code_import)
    if not code:
        raise HTTPException(422, f"Cet import n'a pas de référence ({type_acces.libelle})")
    if not imp.lot_id and not en_stock(imp):
        raise HTTPException(422, "Choisissez le lot avant de rattacher")

    modele = type_acces.modele
    objet = session.exec(select(modele).where(modele.code == code)).first()
    if objet is None:
        objet = modele(code=code, statut=StatutAcces.actif)
    objet.lot_id = imp.lot_id
    objet.user_id = possesseur(imp) or objet.user_id
    objet.chez_locataire = chez_le_locataire(imp)
    #  🔴 Ce que le badge OUVRE, déduit de son lot comme partout ailleurs : le
    #  rattachement ne le posait pas, et la colonne « Accès » restait vide sur
    #  tout le parc importé (signalé le 23/09/2026). Une valeur déjà posée ne
    #  se touche pas.
    if objet.perimetre_cible is None:
        from app.utils.acces_gestes import _acces_json

        objet.perimetre_cible = _acces_json(session, type_acces, None, objet.lot_id, objet.user_id)
    session.add(objet)
    session.flush()

    imp.statut = StatutImport.resolu
    setattr(imp, type_acces.colonne_import, objet.id)
    imp.resolu_le = datetime.utcnow()
    session.add(imp)
    return objet


def synchroniser_import(session: Session, type_acces, objet) -> None:
    """Le PARC corrige, l'IMPORT suit — demandé le 23/09/2026.

    « Est-ce que cette vue enrichie peut compléter les imports, notamment quand
    une modification manuelle est faite ? » Le sens inverse existait déjà : une
    ligne corrigée à l'import redescend sur son badge (`socle_imports.patch`).
    Celui-ci manquait — un badge saisi ou corrigé au parc laissait sa ligne du
    fichier « en attente », et « Rattacher » l'aurait proposée une seconde fois.

    - la ligne qui porte le CODE du badge s'y rattache, sur son lot ;
    - une ligne rattachée à ce badge sous un AUTRE code (le code a été corrigé
      au parc) est libérée : elle ne désigne plus cet objet.

    Une ligne ignorée le reste : c'est une décision prise. Sans `commit`.
    """
    modele = type_acces.modele_import
    lien = getattr(modele, type_acces.colonne_import)
    for ligne in session.exec(select(modele).where(lien == objet.id)).all():
        if getattr(ligne, type_acces.colonne_code_import) != objet.code:
            setattr(ligne, type_acces.colonne_import, None)
            ligne.statut = (StatutImport.proprietaire_lie if ligne.user_proprietaire_id
                            else StatutImport.en_attente)
            ligne.resolu_le = None
            session.add(ligne)
    for ligne in session.exec(select(modele).where(
        type_acces.champ_code_import == objet.code, modele.statut != StatutImport.ignore,
    )).all():
        setattr(ligne, type_acces.colonne_import, objet.id)
        ligne.lot_id = objet.lot_id
        ligne.chez_locataire = objet.chez_locataire
        if ligne.statut != StatutImport.resolu:
            ligne.statut = StatutImport.resolu
            ligne.resolu_le = datetime.utcnow()
        session.add(ligne)


def rattacher_les_reconnues(type_acces, session: Session) -> dict:
    """Le rattachement en masse : toutes les lignes dont le lot est connu."""
    modele = type_acces.modele_import
    lignes = session.exec(
        select(modele).where(
            modele.statut.in_([StatutImport.en_attente, StatutImport.proprietaire_lie])
        )
    ).all()
    rattachees = 0
    for imp in lignes:
        if peut_se_rattacher(type_acces, imp):
            rattacher(type_acces, imp, session)
            rattachees += 1
    session.commit()
    return {"rattachees": rattachees, "restantes": len(lignes) - rattachees}


__all__ = [
    "en_stock", "exiger_code_libre", "peut_se_rattacher", "rattacher",
    "rattacher_les_reconnues", "synchroniser_import",
]
