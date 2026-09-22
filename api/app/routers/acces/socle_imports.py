"""Le CYCLE d'un import d'accès, écrit UNE fois — télécommandes et Vigik (#847).

## Ce que ce module retire, et pourquoi ce n'était pas « deux jumeaux »

`imports_telecommandes.py` et `imports_vigik.py` portaient **trois corps
identiques** : l'appariement automatique, la mise à jour des liaisons, la
résolution. L'en-tête du paquet affirmait pourtant que les fondre « coûterait
plus cher que les deux fichiers », au nom de `standards/02` §4 — *deux morceaux
qui se ressemblent par hasard*.

🔴 **C'était faux, et la preuve est un défaut en production.** Deux morceaux qui
se ressemblent par hasard ne divergent pas sur la même ligne : ils n'ont pas la
même ligne. Ceux-ci en avaient une, et elle a divergé.

    #  imports_telecommandes — la possession physique est reportée sur l'objet
    tc = Telecommande(..., chez_locataire=imp.chez_locataire and bool(imp.user_locataire_id))

    #  imports_vigik — la même donnée, PERDUE
    vigik = Vigik(code=..., lot_id=..., user_id=..., statut=...)

`Vigik.chez_locataire` existe, et il **décide** : `routers/bailleur/acces.py` ne
propose au transfert que les accès `not chez_locataire`, et `_assert_transferable`
refuse ceux déjà remis au titre d'un autre bail. Un badge Vigik résolu au bénéfice
d'un locataire arrivait donc dans le système marqué « chez le propriétaire » — et
se proposait au transfert vers le locataire suivant alors qu'il était déjà, dans
la vraie vie, dans la poche du locataire en place. La télécommande du même lot,
elle, était protégée.

C'est `standards/02` §4 bis appliqué : entre deux implémentations, on retient **la
plus disante**, jamais un compromis.

## L'objet, et ce qu'il adapte

`utils/types_acces.TypeAcces` porte ce qui distingue réellement les deux
chaînes. Tout le reste est du cycle, et le cycle n'a qu'une écriture.

🔴 Ce module portait son PROPRE descripteur jusqu'au 18/09/2026 —
`TypeImportAcces`, qui redisait cinq des six champs de `TypeAcces` sous
d'autres noms et exportait des constantes du MÊME nom dans deux modules.
Deux objets pour une notion : `test_socle_imports_acces` refuse désormais
qu'un second se déclare.

⚠️ Ce qui reste **hors** de ce module est ce qui diffère vraiment : la lecture du
fichier Excel (`utils/import_telecommandes.py`, `utils/import_vigiks.py` — ni les
mêmes colonnes ni les mêmes règles) et l'étape d'appariement propre au Vigik
(bâtiment + appartement), passée en paramètre plutôt que codée ici.

## Ce que la mise en commun a changé de comportement, et c'est voulu

1. **`chez_locataire` est reporté sur l'objet Vigik** à la résolution — le défaut
   ci-dessus ;
2. **la correction d'un import déjà résolu** reporte désormais `chez_locataire`
   sur l'objet, des deux côtés. Elle ne le faisait nulle part : on pouvait
   corriger « la télécommande est chez le locataire » sur l'import sans que la
   télécommande l'apprenne. C'est le sens même du chemin de correction.

`api/tests/test_socle_imports_acces.py` verrouille les deux.
"""
from __future__ import annotations

from app.utils.recuperer import ou_404

from datetime import datetime
from typing import Callable, Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.models.core import StatutAcces, StatutImport, Utilisateur
from app.utils.acces_possession import chez_le_locataire, possesseur
from app.utils.types_acces import TypeAcces
from app.utils.auto_match_service import (
    _matches_user,
    _user_keys,
    rattacher_lot_unique,
)


class PatchImportBody(BaseModel):
    """Les liaisons modifiables d'un import — **les mêmes pour les deux types**.

    Les deux fichiers en portaient une copie chacun, champ pour champ. Un champ
    ajouté d'un seul côté aurait produit un formulaire acceptant une donnée que
    l'autre écran ignore, sans que rien ne le signale.
    """

    user_proprietaire_id: int | None = None
    user_locataire_id: int | None = None
    lot_id: int | None = None
    chez_locataire: bool | None = None
    refuse_par_locataire: bool | None = None
    notes_admin: str | None = None

    #  🔴 Les NOMS venus du fichier du syndic, corrigeables (#1152, 22/09/2026).
    #
    #  Demandé à l'écran : *« quand il y a une faute d'orthographe le
    #  rapprochement vigik et TC est impossible »*. `auto_match` compare ces
    #  chaînes aux comptes inscrits ; une lettre de travers, et la ligne reste
    #  « en attente » sans que rien ne dise pourquoi.
    #
    #  ⚠️ On corrige le TEXTE IMPORTÉ, pas la fiche du copropriétaire — arbitré
    #  le même jour. Une faute dans le fichier du syndic ne doit pas obliger à
    #  retoucher un compte, qui sert à l'annuaire, aux courriels et aux affiches.
    nom_proprietaire: str | None = None
    nom_locataire: str | None = None


def auto_match(
    type_import: TypeAcces,
    session: Session,
    etape_supplementaire: Optional[Callable[[object, Session], bool]] = None,
) -> dict:
    """Apparie les imports en attente aux comptes inscrits.

    `etape_supplementaire` est le crochet des différences réelles : le Vigik y
    résout son lot par `batiment_raw` + `appartement_raw`, ce que la télécommande
    ne peut pas faire — son fichier ne porte pas ces colonnes.
    """
    modele = type_import.modele_import
    imports = session.exec(
        select(modele).where(
            modele.statut.in_([StatutImport.en_attente, StatutImport.proprietaire_lie])
        )
    ).all()
    utilisateurs = session.exec(select(Utilisateur)).all()

    #  Pré-calcul des clés d'appariement : sans lui, `_user_keys` serait rappelée
    #  pour chaque utilisateur à chaque ligne d'import.
    cles_par_utilisateur: dict[int, set[str]] = {
        u.id: _user_keys(u.nom, u.prenom) for u in utilisateurs
    }

    apparies = 0
    for imp in imports:
        change = False

        for champ_nom, champ_lien in (
            ("nom_proprietaire", "user_proprietaire_id"),
            ("nom_locataire", "user_locataire_id"),
        ):
            if getattr(imp, champ_lien) or not getattr(imp, champ_nom):
                continue
            candidats = [
                u
                for u in utilisateurs
                if _matches_user(getattr(imp, champ_nom), cles_par_utilisateur[u.id])
            ]
            if candidats:
                #  Un nom d'Excel désignant un couple rend plusieurs candidats : le
                #  premier est retenu, les autres sont rattachés à la résolution par
                #  `creer_liaisons`.
                setattr(imp, champ_lien, candidats[0].id)
                change = True

        if etape_supplementaire and etape_supplementaire(imp, session):
            change = True

        #  La règle du lot unique vit dans `rattacher_lot_unique` — elle était
        #  écrite quatre fois, avec deux comportements différents.
        if rattacher_lot_unique(imp, session):
            change = True

        if change:
            if imp.user_proprietaire_id:
                imp.statut = StatutImport.proprietaire_lie
            session.add(imp)
            apparies += 1

    session.commit()
    return {"matches": apparies, "total": len(imports)}


def _charger(type_import: TypeAcces, import_id: int, session: Session):
    imp = ou_404(session, type_import.modele_import, import_id, "Import")
    return imp


def patch(
    type_import: TypeAcces,
    import_id: int,
    body: PatchImportBody,
    session: Session,
):
    """Met à jour les liaisons d'un import, résolu ou non."""
    imp = _charger(type_import, import_id, session)

    for champ in ("user_proprietaire_id", "user_locataire_id", "lot_id"):
        valeur = getattr(body, champ)
        if valeur is not None:
            #  `or None` : le formulaire envoie 0 pour « aucun », et un 0 stocké
            #  serait une clé étrangère vers un identifiant qui n'existe pas.
            setattr(imp, champ, valeur or None)

    if body.chez_locataire is not None:
        imp.chez_locataire = body.chez_locataire
    if body.refuse_par_locataire is not None:
        imp.refuse_par_locataire = body.refuse_par_locataire
        if body.refuse_par_locataire:
            imp.chez_locataire = False  # refus → retour chez le propriétaire
    if body.notes_admin is not None:
        imp.notes_admin = body.notes_admin

    #  🔴 Les noms importés (#1152). `strip()` d'abord : un nom collé à un
    #  espace insécable n'appariera pas davantage que la faute qu'on corrige.
    if body.nom_proprietaire is not None:
        #  ⚠️ Un nom VIDE est refusé en silence plutôt qu'accepté : la colonne
        #  est obligatoire au modèle, et une ligne d'import sans nom n'est plus
        #  rattachable à personne — elle disparaîtrait des recherches sans que
        #  rien ne le dise. Le formulaire n'offre pas de vider ce champ ; ceci
        #  garde la porte fermée côté serveur.
        propre = body.nom_proprietaire.strip()
        if propre:
            imp.nom_proprietaire = propre
    if body.nom_locataire is not None:
        #  Celui-ci PEUT se vider : une ligne sans locataire est un cas normal
        #  (le propriétaire occupe son lot), et `None` le dit mieux que « ».
        imp.nom_locataire = body.nom_locataire.strip() or None

    objet_id = getattr(imp, type_import.colonne_import)
    if imp.statut == StatutImport.resolu and objet_id:
        objet = session.get(type_import.modele, objet_id)
        if objet:
            detenteur = possesseur(imp)
            if detenteur:
                objet.user_id = detenteur
                objet.lot_id = imp.lot_id or objet.lot_id
                #  🔴 Reporté depuis le 08/09/2026 : sans cette ligne, corriger
                #  « chez le locataire » sur l'import laissait l'objet en dire le
                #  contraire, et c'est l'objet que lit le transfert de bail.
                objet.chez_locataire = chez_le_locataire(imp)
                session.add(objet)
    else:
        imp.statut = (
            StatutImport.proprietaire_lie
            if imp.user_proprietaire_id
            else StatutImport.en_attente
        )

    session.add(imp)
    session.commit()
    session.refresh(imp)
    return imp


def resoudre(type_import: TypeAcces, import_id: int, session: Session) -> dict:
    """Crée l'accès réel depuis un import apparié, et lie les copropriétaires."""
    imp = _charger(type_import, import_id, session)
    if imp.statut == StatutImport.resolu:
        raise HTTPException(400, "Import déjà résolu")
    if imp.statut == StatutImport.ignore:
        raise HTTPException(400, "Cet import est ignoré")
    if not imp.user_proprietaire_id:
        raise HTTPException(422, "Le propriétaire doit être lié avant de résoudre")

    reference = getattr(imp, type_import.colonne_code_import)
    if not reference:
        raise HTTPException(
            422, f"Cet import n'a pas de référence ({type_import.libelle})"
        )

    objet = type_import.modele(
        code=reference,
        lot_id=imp.lot_id or None,
        user_id=possesseur(imp),
        chez_locataire=chez_le_locataire(imp),
        statut=StatutAcces.actif,
    )
    session.add(objet)
    session.flush()

    type_import.attribuer_aux_coproprietaires(objet, session)

    imp.statut = StatutImport.resolu
    setattr(imp, type_import.colonne_import, objet.id)
    imp.resolu_le = datetime.utcnow()
    session.add(imp)
    session.commit()
    session.refresh(objet)
    #  La clé de sortie garde le nom de l'objet : le front lit `telecommande` ou
    #  `vigik`, et un renommage « uniformisant » casserait deux écrans.
    return {type_import.modele.__tablename__: objet, "import_id": imp.id}


__all__ = [
    "PatchImportBody",
    "auto_match",
    "patch",
    "possesseur",
    "resoudre",
]
