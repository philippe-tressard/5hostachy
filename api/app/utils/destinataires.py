"""Résolution des destinataires — source unique.

Factorise la logique « membres du CS concernés par un périmètre » utilisée par
la démarche nouvel arrivant (`admin.py`) et par les annonces de hall
(`annonces_hall.py`). Ne pas dupliquer ces règles dans les routers.

Règles :
  - Seuls les membres du CS **liés à un compte utilisateur actif avec e-mail**
    sont notifiables (`MembreCS.user_id` renseigné).
  - Le **gestionnaire du site** est toujours ajouté, quel que soit le périmètre.
  - Périmètre transverse (résidence / parking / cave / AFUL) → tout le CS.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from app.models.core import ConfigSite, GenreCivilite, MembreCS, MembreSyndic, Utilisateur
from app.utils.visibility import SCOPES_RESIDENCE


def site_manager_user_id(session: Session) -> Optional[int]:
    """Id utilisateur du gestionnaire du site (ConfigSite), ou None."""
    cfg = session.get(ConfigSite, "site_manager_user_id")
    if not cfg:
        return None
    valeur = (cfg.valeur or "").strip()
    return int(valeur) if valeur.isdigit() else None


def batiments_du_perimetre(perimetres: list[str]) -> Optional[set[int]]:
    """`['bat:1','bat:3']` → `{1, 3}` ; None si le périmètre couvre la résidence.

    Les périmètres transverses (parking, cave, AFUL) concernent l'ensemble des
    résidents : ils sont traités comme « résidence entière ».
    """
    if not perimetres:
        return None
    ids: set[int] = set()
    for p in perimetres:
        p = p.lower()
        if p in SCOPES_RESIDENCE:
            return None
        if p.startswith("bat:"):
            ident = p.split(":", 1)[1]
            if ident.isdigit():
                ids.add(int(ident))
    return ids or None


def membres_cs_notifiables(
    session: Session, batiment_ids: Optional[set[int]] = None
) -> list[tuple[int, str]]:
    """Destinataires CS `[(user_id, email)]`, dédoublonnés.

    `batiment_ids` à None → tous les membres du CS. Sinon, membres rattachés à
    l'un des bâtiments, plus le gestionnaire du site.
    """
    manager_id = site_manager_user_id(session)

    stmt = select(MembreCS).where(MembreCS.user_id != None)  # noqa: E711
    if batiment_ids:
        filtres = MembreCS.batiment_id.in_(batiment_ids)  # type: ignore[union-attr]
        if manager_id is not None:
            filtres = filtres | (MembreCS.user_id == manager_id)
        stmt = stmt.where(filtres)
    membres = session.exec(stmt).all()

    destinataires: list[tuple[int, str]] = []
    vus: set[str] = set()
    for membre in membres:
        user = session.get(Utilisateur, membre.user_id)
        if not user or not user.actif or not user.email:
            continue
        email = user.email.strip()
        if not email or email.lower() in vus:
            continue
        vus.add(email.lower())
        destinataires.append((user.id, email))
    return destinataires


# ── Interlocuteurs chez le syndic ────────────────────────────────────────────

#: Fonctions auxquelles un e-mail de la copropriété s'adresse, en minuscules et
#: sans accents. Le cabinet fonctionne en binôme — l'assistante de gestion supplée
#: la gestionnaire en son absence — donc **les deux** figurent dans la formule
#: d'appel, et l'ordre de l'annuaire les classe.
#:
#: La comptable en est volontairement exclue : elle traite les appels de fonds,
#: pas les signalements techniques. Écrire les noms en dur serait le vrai défaut :
#: le cabinet change de personnel, l'annuaire est la seule source qui suit.
FONCTIONS_INTERLOCUTRICES = ("gestionnaire", "assistant")


def _sans_accent_minuscule(texte: str) -> str:
    """Comparaison tolérante d'un intitulé saisi à la main.

    Les intitulés sont saisis au clavier : « Gestionnaire de Copropriétés »,
    « Assistante de gestion », « Comptable de copropriété » — majuscules, accents
    et genre y varient d'une ligne à l'autre. Comparer sur la forme
    brute reviendrait à ne reconnaître que l'orthographe du jour de la saisie.
    """
    from app.utils.import_xlsx import normaliser

    #  `normaliser` est la fonction de comparaison de noms déjà partagée par les
    #  trois imports et l'appariement des accès. En réécrire une seconde ici,
    #  c'est exactement la duplication que le socle interdit — son emplacement
    #  dans `import_xlsx` est discutable, sa réutilisation ne l'est pas.
    return normaliser(texte).lower()


def interlocuteurs_syndic(session: Session) -> list[MembreSyndic]:
    """Les personnes du syndic à qui l'on s'adresse, dans l'ordre de l'annuaire.

    Sélection par **fonction**, jamais par nom. Repli sur le membre marqué
    `est_principal` si aucune fonction ne correspond — sans quoi un intitulé
    inattendu produirait une formule d'appel vide, et un e-mail qui commence par
    une virgule ne se remarque qu'une fois parti.
    """
    membres = session.exec(
        select(MembreSyndic).order_by(MembreSyndic.ordre, MembreSyndic.id)
    ).all()
    retenus = [
        m for m in membres
        if any(f in _sans_accent_minuscule(m.fonction or "") for f in FONCTIONS_INTERLOCUTRICES)
    ]
    if retenus:
        return retenus
    return [m for m in membres if m.est_principal]


def _nom_presentable(nom: str) -> str:
    """« DUPONT » → « Dupont », « durand » → « Durand », « de La Tour » inchangé.

    Une casse uniforme trahit une saisie machinale, pas une orthographe voulue :
    on la corrige. Une casse mixte, elle, porte peut-être une particule ou un nom
    composé — on n'y touche pas.
    """
    nom = (nom or "").strip()
    return nom.title() if (nom.isupper() or nom.islower()) else nom


def formule_appel(membres: list[MembreSyndic]) -> str:
    """« Madame Dupont, Madame Durand » — civilité et NOM, sans prénom.

    Le prénom est volontairement absent : c'est une correspondance entre un
    conseil syndical et un cabinet de gestion, pas un échange personnel.
    """
    civilites = {GenreCivilite.mr: "Monsieur"}
    return ", ".join(
        f"{civilites.get(m.genre, 'Madame')} {_nom_presentable(m.nom)}"
        for m in membres
        if (m.nom or "").strip()
    )
