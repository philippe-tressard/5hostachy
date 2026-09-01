"""Résolution des destinataires — source unique.

Factorise la logique « membres du CS concernés par un périmètre » utilisée par
la démarche nouvel arrivant (`admin.py`) et par les annonces de hall
(`annonces_hall.py`). Ne pas dupliquer ces règles dans les routers.

Règles :
  - Seuls les membres du CS **liés à un compte utilisateur actif avec e-mail**
    sont notifiables (`MembreCS.user_id` renseigné).
  - Le **gestionnaire du site** est toujours ajouté, quel que soit le périmètre.
  - Périmètre à portée globale (ou dont un ancêtre l'est) → tout le CS.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from app.models.core import ConfigSite, GenreCivilite, MembreCS, MembreSyndic, Utilisateur
from app.utils.perimetres import a_portee_globale, batiments_cibles


def site_manager_user_id(session: Session) -> Optional[int]:
    """Id utilisateur du gestionnaire du site (ConfigSite), ou None."""
    cfg = session.get(ConfigSite, "site_manager_user_id")
    if not cfg:
        return None
    valeur = (cfg.valeur or "").strip()
    return int(valeur) if valeur.isdigit() else None


def batiments_du_perimetre(perimetres: list[str]) -> Optional[set[int]]:
    """`['bat:1','bat:3']` → `{1, 3}` ; None si le périmètre concerne tout le monde.

    Un nœud à portée globale — ou dont un ancêtre l'est — concerne l'ensemble des
    résidents, et l'on renvoie alors None (« tout le conseil syndical »). Sinon on
    remonte l'arbre pour chaque code afin de trouver le bâtiment visé : c'est ce qui
    permet de cibler « Bât. 2 › Hall d'entrée » sans redire que le hall est dans le
    bâtiment 2.

    La liste des périmètres transverses n'est plus écrite ici. Elle vivait en trois
    exemplaires et c'est maintenant `perimetre.portee_globale`.
    """
    if not perimetres:
        return None
    if a_portee_globale(perimetres):
        return None
    return batiments_cibles(perimetres) or None


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


# ── Syndic + conseil syndical : QUI reçoit un e-mail interne ──────────────────
#
# 🔴 Cette règle existait en QUATRE exemplaires, tous identiques à la variable
# près : tickets, calendrier, publications, sondages. Et celui des tickets
# portait, en toutes lettres, *« elle est le seul endroit où cette règle
# s'écrit »* — une affirmation d'unicité au milieu de quatre copies.
#
# ⚠️ C'est la forme la plus coûteuse de la duplication : les trois autres
# n'avaient AUCUN commentaire, donc rien ne signalait qu'elles existaient, et le
# seul fichier qui parlait du sujet disait que le problème n'existait pas.
# Corriger la règle chez l'un — ajouter un destinataire, changer la
# déduplication — laissait les trois autres en arrière sans qu'un contrôle,
# ni une relecture, ne puisse le voir.
#
# 🔒 `api/tests/test_destinataires_source_unique.py` refuse une cinquième.

def syndic_principal(session: Session) -> Optional[MembreSyndic]:
    """Le gestionnaire syndic principal, ou None s'il n'est pas configuré."""
    return session.exec(
        select(MembreSyndic).where(MembreSyndic.est_principal == True)  # noqa: E712
    ).first()


def membres_cs_avec_email(session: Session) -> list[tuple[int, str]]:
    """(id, e-mail) des membres du CS joignables par courriel.

    ⚠️ Le critère est le **rôle** `conseil_syndical`, sans notion de périmètre —
    à distinguer de `membres_cs_notifiables()` ci-dessus, qui part de la table
    `MembreCS` et filtre par bâtiment. Les deux coexistent volontairement, et
    `CLAUDE.md` dit laquelle sert à quoi : celle-ci vise le rôle (publications,
    sondages, calendrier, tickets), l'autre vise le périmètre (nouvel arrivant,
    annonces de hall).
    """
    return [
        (uid, email)
        for uid, email in session.exec(
            select(Utilisateur.id, Utilisateur.email).where(
                Utilisateur.actif == True,  # noqa: E712
                Utilisateur.email.isnot(None),
                Utilisateur.roles_json.contains("conseil_syndical"),
            )
        ).all()
        if email
    ]


def destinataires_syndic_cs(
    session: Session,
    *,
    syndic: bool,
    cs: bool,
    deja_vus: Optional[set[str]] = None,
) -> list[tuple[int | None, str]]:
    """(user_id, e-mail) du syndic principal puis des membres du CS, dédoublonnés.

    Le syndic passe en premier et **gagne le doublon** : c'est lui le destinataire
    principal, un membre du CS qui serait aussi le syndic ne doit pas recevoir le
    message deux fois.

    `deja_vus` permet à une relance d'exclure du CC les adresses déjà placées en
    destinataire principal, sans réécrire la déduplication.
    """
    return syndic_puis(
        session,
        syndic=syndic,
        membres=membres_cs_avec_email(session) if cs else [],
        deja_vus=deja_vus,
    )


def syndic_puis(
    session: Session,
    *,
    syndic: bool,
    membres: list[tuple[int | None, str]],
    deja_vus: Optional[set[str]] = None,
) -> list[tuple[int | None, str]]:
    """Le syndic principal, puis une liste de membres DÉJÀ choisie, dédoublonnés.

    🔴 Ce site choisit le conseil syndical de **deux** façons, et les confondre
    envoie le bon message aux mauvaises personnes :

    - par le **rôle** — `membres_cs_avec_email` : publications, sondages,
      calendrier, tickets ;
    - par le **périmètre** — `membres_cs_notifiables` : nouvel arrivant, annonces
      de hall, où seul le CS du bâtiment concerné est visé.

    La règle de **déduplication**, elle, est la même dans les deux cas — le
    syndic passe en premier et gagne le doublon. Elle vit donc ici, et le choix
    du CS reste à l'appelant : c'est ce qui a permis à l'annonce de hall de
    recevoir le canal « syndic » (#480) sans écrire une cinquième copie du bloc.

    ⚠️ Le bloc a déjà existé en **quatre exemplaires identiques** jusqu'au
    31/08/2026 — et celui des tickets affirmait, en toutes lettres, être « le
    seul endroit où cette règle s'écrit ».
    """
    destinataires: list[tuple[int | None, str]] = []
    vus: set[str] = set(deja_vus or ())

    if syndic:
        principal = syndic_principal(session)
        if principal and principal.email:
            destinataires.append((principal.user_id, principal.email))
            vus.add(principal.email.lower())

    for uid, email in membres:
        if email and email.lower() not in vus:
            destinataires.append((uid, email))
            vus.add(email.lower())

    return destinataires
