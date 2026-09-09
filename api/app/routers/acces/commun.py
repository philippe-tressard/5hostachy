"""Ce que les trois modules du contrôle d'accès partagent.

🔴 **Le découpage a montré que les deux imports partagent CINQ fonctions**, pas
une. `_stats_socle`, `_lister_imports`, `_remettre_en_attente_import` et
`_ignorer_import` vivaient dans le module des télécommandes, et celui des vigiks
les appelait — un couplage invisible tant que tout tenait dans un seul fichier.
C'est Ruff qui l'a dit, en refusant quatre noms indéfinis.

⚠️ L'en-tête du paquet affirmait d'abord que « ce qu'ils partagent vraiment est
la normalisation des noms ». C'était faux, et le compilateur l'a établi avant
qu'on le croie. Un découpage ne crée pas les dépendances : il les RÉVÈLE.

🔴 **`_normaliser` a vécu ici sans que PERSONNE ne l'appelle** — retirée le
09/09/2026. L'en-tête affirmait qu'elle « est ici parce que les DEUX chaînes
d'import l'emploient » ; les deux importaient en réalité la `normaliser` de
`utils/import_xlsx`, dont ce corps était la copie exacte. Et cette fonction-là
porte, depuis le 08/08/2026, la mention « Écrite trois fois à l'identique » : la
consolidation d'alors en avait donc laissé une **quatrième**, ici, protégée par
un commentaire qui expliquait pourquoi il ne fallait pas la dupliquer.

⚠️ C'est la forme la plus tenace de la duplication : le seul fichier qui parle du
sujet affirme que le problème n'existe pas. Un nom d'import qui aurait dérivé
d'un accent aurait rapproché les personnes d'un côté et pas de l'autre — sauf
qu'ici la copie ne servait à rien du tout, ce qui est pire : elle donnait à lire
une règle qui ne s'appliquait nulle part.
"""
from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.core import (
    StatutImport,
    Utilisateur, Batiment, Lot,
)


def _stats_socle(modele, session: Session) -> tuple[list, dict]:
    lignes = session.exec(select(modele)).all()
    socle = {"total": len(lignes)}
    for statut in StatutImport:
        socle[statut.value] = sum(1 for i in lignes if i.statut == statut)
    socle["avec_locataire"] = sum(1 for i in lignes if i.nom_locataire)
    return lignes, socle


def _lister_imports(modele, statut, session: Session):
    q = select(modele)
    if statut:
        q = q.where(modele.statut == statut)
    q = q.order_by(modele.nom_proprietaire)
    items = session.exec(q).all()
    result = []
    for item in items:
        d = item.model_dump()
        if item.user_proprietaire_id:
            u = session.get(Utilisateur, item.user_proprietaire_id)
            d["proprietaire"] = {"id": u.id, "nom": u.nom, "prenom": u.prenom} if u else None
        else:
            d["proprietaire"] = None
        if item.user_locataire_id:
            u = session.get(Utilisateur, item.user_locataire_id)
            d["locataire"] = {"id": u.id, "nom": u.nom, "prenom": u.prenom} if u else None
        else:
            d["locataire"] = None
        if item.lot_id:
            lot = session.get(Lot, item.lot_id)
            if lot:
                bat = session.get(Batiment, lot.batiment_id)
                d["lot_label"] = f"Bât.{bat.numero} — {lot.numero}" if bat else lot.numero
            else:
                d["lot_label"] = None
        else:
            d["lot_label"] = None
        result.append(d)
    return result


#  Le SOCLE des statistiques : total et statuts, communs aux deux types. Chaque
#  endpoint l'ENRICHIT de ses compteurs propres (référence, code, lot).


def _remettre_en_attente_import(modele, import_id: int, session: Session):
    """Rattrape un import ignoré par erreur.

    ⚠️ Seul un import IGNORÉ peut revenir : un import RÉSOLU a créé un objet, et
    le remettre en attente le laisserait sans import pour le porter (#576).
    """
    imp = session.get(modele, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    if imp.statut != StatutImport.ignore:
        raise HTTPException(400, "Seuls les imports ignorés peuvent être remis en attente")
    imp.statut = StatutImport.en_attente
    session.add(imp)
    session.commit()
    return {"statut": imp.statut}


def _ignorer_import(modele, import_id: int, session: Session):
    """Écarte un import du traitement — accès non résidentiel, doublon…"""
    imp = session.get(modele, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    if imp.statut == StatutImport.resolu:
        raise HTTPException(400, "Import déjà résolu — ne peut être ignoré")
    imp.statut = StatutImport.ignore
    session.add(imp)
    session.commit()
    return {"statut": imp.statut}
