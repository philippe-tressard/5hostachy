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
mêmes colonnes ni les mêmes règles) et la façon de retrouver le LOT d'une ligne
(`utils/lot_des_imports` : bâtiment + appartement pour le Vigik, nom du
copropriétaire dans le fichier des lots pour la télécommande).

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

from pydantic import BaseModel
from sqlmodel import Session, select

from app.models.core import StatutImport, Utilisateur
from app.utils.acces_possession import chez_le_locataire, possesseur
from app.utils.lot_des_imports import trouveur_de_lot
from app.utils.resolution_acces import rattacher
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


def auto_match(type_import: TypeAcces, session: Session) -> dict:
    """Apparie les imports en attente : leur LOT d'abord, les comptes ensuite.

    Le lot se retrouve sans aucun compte (`utils/lot_des_imports`) — c'est lui
    qui rend une ligne rattachable depuis #1194. Les comptes ne servent plus
    qu'à dire qui a le badge en main.
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

    etape_lot = trouveur_de_lot(type_import, session)
    apparies = 0
    for imp in imports:
        change = etape_lot(imp)

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
                #  premier est retenu comme détenteur. L'autre n'a rien à recevoir —
                #  il porte le badge par le lot, comme conjoint (#1194).
                setattr(imp, champ_lien, candidats[0].id)
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
        #  🔴 `null` DÉLIE (#1194) : le serveur l'ignorait, et une liaison posée
        #  par erreur ne se défaisait plus. Un champ ABSENT du corps, lui, ne
        #  change rien — c'est ce que distingue `model_fields_set`.
        if champ in body.model_fields_set:
            #  `or None` : le formulaire envoie 0 pour « aucun », et un 0 stocké
            #  serait une clé étrangère vers un identifiant qui n'existe pas.
            setattr(imp, champ, getattr(body, champ) or None)

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
            #  Le lot de l'import EST celui du badge (#1194) : le délier ici
            #  délie le badge, et le détenteur est celui que la ligne nomme.
            objet.lot_id = imp.lot_id
            objet.user_id = possesseur(imp)
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
    """Rattache le badge d'une ligne à son lot — la règle : `utils/resolution_acces`."""
    imp = _charger(type_import, import_id, session)
    objet = rattacher(type_import, imp, session)
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
