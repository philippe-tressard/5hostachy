"""
Règles de visibilité centralisées — source de vérité unique.

Toute logique de filtrage par rôle/périmètre/profil doit passer par ce module.
Ne jamais dupliquer ces règles dans les routers.

Règles métier appliquées :
  - CS et Admin voient toujours tout (pas de filtre).
  - Syndic : lecture seule sur tout (pas filtré ici — géré par les dépendances auth).
  - Mandataire : non géré ici (filtrage lot dans bailleur.py — périmètre trop spécifique).
  - Périmètre géographique : un nœud à portée globale (ou dont un ancêtre l'est) est
      visible par tous les résidents ; sinon, visible si le bâtiment du nœud — ou de
      son plus proche ancêtre qui en porte un — est celui de l'utilisateur.
      La liste des périmètres transverses n'est plus écrite ici : elle était en trois
      exemplaires (ici, `flux/evenements.py`, et le tableau de bord côté front) et
      c'est désormais le drapeau `portee_globale` de la table `perimetre`.
  - public_cible : résidents = tous ; copropriétaires = statut copropriétaire_* ;
      copropriétaires_occupants = copropriétaire_résident uniquement ; bailleurs =
      copropriétaire_bailleur uniquement ; locataires = statut locataire uniquement ;
      conseil_syndical = CS/admin uniquement.
      Si public_cible contient une valeur non reconnue ou non correspondante → non visible.
  - AG (événements) : visible uniquement par propriétaires, CS et admins.
  - Sondages : MÊME règle que les publications — perimetre_cible + public_cible.
      Ils ciblaient par `batiments_ids` + `profils_autorises`, seuls de tout le
      site : une deuxième règle d'accès à maintenir, et un écran qui ne savait
      cibler ni le parking, ni l'AFUL, ni un espace. Unifié le 16/08/2026.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from app.models.core import (
    Document,
    Evenement,
    ProfilAccesDocument,
    Publication,
    RoleUtilisateur,
    Sondage,
    Ticket,
    TypeEvenement,
    Utilisateur,
)
from app.utils.mes_batiments import batiments_de_l_utilisateur
from app.utils.perimetres import a_portee_globale, batiments_cibles, parse_perimetres

# ── Parseurs internes ─────────────────────────────────────────────────────────

def _parse_json_list(raw: Optional[str], default: list[str]) -> list[str]:
    """Parse un champ JSON stocké en base (ex: '["bat:1","bat:3"]')."""
    if not raw:
        return default
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
        return list(val) if isinstance(val, (list, tuple)) else default
    except Exception:
        return default


def _codes_json_pour_acces(raw: Optional[str]) -> Optional[list[str]]:
    """Codes de périmètre d'un champ JSON, pour une **décision d'accès**.

    Distingue trois états là où `utils/perimetres.parse_json_perimetres` n'en
    distingue que deux, et la nuance est une nuance de sécurité :

    - champ absent ou vide → `[]`, c'est-à-dire « aucune restriction ». C'était
      déjà le comportement, et il est conservé ;
    - JSON valide → les codes ;
    - JSON **illisible** → `None`, et l'appelant refuse.

    Ce dernier cas est un changement assumé. Jusqu'ici, un `perimetre_cible`
    corrompu retombait sur `["résidence"]` : une donnée abîmée **élargissait** la
    visibilité au lieu de la restreindre. Pour un badge à l'écran ce repli est
    bienvenu (cf. `parse_json_perimetres`) ; pour décider qui a le droit de lire,
    il est exactement à l'envers.
    """
    if not raw:
        return []
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None
    if not isinstance(val, (list, tuple)):
        return None
    return [str(v) for v in val]


# ── Règles géographiques ──────────────────────────────────────────────────────

def perimetre_visible(
    perimetres: list[str], user: Utilisateur, *, ouvert_a_la_copropriete: bool = False
) -> bool:
    """
    Retourne True si le périmètre de l'item est accessible à l'utilisateur.

    - CS / Admin : toujours True.
    - Nœud à portée globale, ou dont un ancêtre l'est : True pour tout résident.
    - `ouvert_a_la_copropriete` : les contenus dont le bâtiment ne restreint plus
      la lecture — actualités et tickets (#339). Voir ci-dessous.
    - Sinon : True si le bâtiment du nœud (ou du plus proche ancêtre qui en porte
      un) est celui de l'utilisateur.
    - Liste vide : aucune restriction → True.

    ## `ouvert_a_la_copropriete` — ce que ce paramètre ouvre, et ce qu'il n'ouvre pas

    Il vaut **False par défaut**, et c'est le point important : le comportement
    d'hier reste celui de tout ce qui ne demande pas explicitement l'ouverture.
    Documents, sondages et événements d'AG ne la demandent pas, et leur accès est
    donc rigoureusement inchangé.

    Ce paramètre élargit l'axe **bâtiment**, jamais l'axe **public**. Cette
    fonction est combinée en ET avec `public_cible` (résidents, copropriétaires,
    bailleurs, locataires, CS), avec `ProfilAccesDocument` et avec les règles
    mandataire de `routers/bailleur.py` : l'ouvrir ne peut donc rien débloquer
    pour quelqu'un que ces règles refusent. Contrainte posée par l'utilisateur le
    14/08/2026 — *une agence, un bailleur ou un mandataire qui n'avaient pas de
    visibilité n'en gagnent aucune* — et vérifiée couple par couple dans
    `tests/test_visibilite_ouverte.py`.

    - Code introuvable : n'accorde **rien**. Un nœud supprimé, un arbre vidé ou une
      table illisible ne peuvent pas justifier un accès — ils ne permettent pas de
      décider, et un contrôle qui ne peut pas s'exécuter ne renvoie jamais OK
      (`standards/04`). La première écriture de cette fonction court-circuitait à
      `True` quand l'arbre était vide : `tests/test_documents_acces.py` l'a
      attrapée, une pièce jointe ciblée sur un autre bâtiment devenant lisible dès
      que la table manquait.

    L'ordre des tests reproduit exactement celui de la règle précédente, qui
    comparait des chaînes : `api/tests/test_perimetres_arbre.py` rejoue l'ancienne
    implémentation contre celle-ci sur tous les couples (périmètre × utilisateur)
    et exige des verdicts identiques.
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    if not perimetres:
        return True
    if a_portee_globale(perimetres):
        return True

    if ouvert_a_la_copropriete:
        if not getattr(user, "restreindre_a_mes_batiments", False):
            return True
        #  L'utilisateur s'est restreint LUI-MÊME. On prend alors ses bâtiments au
        #  sens large — rattachement et lots —, parce qu'il s'agit de lui montrer
        #  les siens, pas de lui accorder quoi que ce soit : cette liste ne sert
        #  qu'ici, et seulement pour montrer MOINS.
        miens = batiments_de_l_utilisateur(user)
        if not miens:
            #  Cas zéro : rien de connu, donc rien à restreindre. Renvoyer False
            #  laisserait un fil vide à qui a simplement coché une case.
            return True
        return bool(miens & batiments_cibles(perimetres))

    if user.batiment_id is None:
        #  Pas de bâtiment assigné → accès résidence entière par défaut.
        #  ⚠️ Repli permissif **conservé volontairement** : le corriger changerait
        #  qui voit quoi aujourd'hui, ce qui n'est pas l'objet de ce lot. Il est
        #  épinglé par un test pour qu'il ne bouge pas par accident, et suivi à part.
        return True
    return user.batiment_id in batiments_cibles(perimetres)


# ── Règle « à qui ça s'adresse » ──────────────────────────────────────────────

#: Le vocabulaire du public cible, dans l'ordre où il est proposé à l'écran.
#:
#: `résidents` n'y figure pas : ce n'est pas un profil mais l'ABSENCE de
#: restriction, et le sélecteur le rend par une pastille à part.
#:
#: ⚠️ Cette liste ne fait pas foi à elle seule — c'est `public_cible_visible`
#: ci-dessous qui décide. Elle sert à ce qu'un contrôle puisse comparer les deux
#: côtés : `tests/test_destinataires_vocabulaire.py` vérifie que chaque code
#: d'ici est réellement honoré par la fonction (donc que la liste ne ment pas),
#: ET que `front/src/lib/destinataires.ts` propose exactement les mêmes. Sans
#: cela, un code ajouté d'un seul côté produit une pastille qui ne cible rien,
#: ou une règle que personne ne peut choisir.
CODES_PUBLIC_CIBLE: tuple[str, ...] = (
    "copropriétaires",
    "copropriétaires_occupants",
    "bailleurs",
    "locataires",
    "conseil_syndical",
)


def public_cible_visible(raw: Optional[str], user: Utilisateur) -> bool:
    """L'utilisateur fait-il partie du public visé par `raw` (JSON de codes) ?

    Écrite UNE fois : les publications et les sondages posent la même question,
    et le sondage y répondait avec son propre vocabulaire (des `StatutUtilisateur`
    bruts). Deux règles pour une notion, c'est deux règles qui divergent — celle
    du sondage ne connaissait ni « bailleurs », ni le conseil syndical.

    Vide ou absent = aucune restriction. Une valeur **non reconnue** ne donne
    jamais l'accès : c'est ce qui permet à la migration 0147 de laisser passer un
    résidu sans risque, puisqu'un résidu ne peut alors que restreindre.
    """
    public = _parse_json_list(raw, [])
    if not public:
        return True
    if "résidents" in public:
        return True
    statut = user.statut.value if user.statut is not None else ""
    if "copropriétaires" in public and statut.startswith("copropriétaire_"):
        return True
    if "locataires" in public and statut == "locataire":
        return True
    #  « Bailleurs » vise les copropriétaires qui LOUENT leur lot, et eux seuls ;
    #  « copropriétaires occupants » est son exact symétrique. `copropriétaires`
    #  ci-dessus couvre les deux statuts — mais rien ne permettait de s'adresser à
    #  l'un SANS l'autre, alors que des pans entiers du produit leur sont propres
    #  (baux et remise d'objets d'un côté, vie quotidienne de l'autre).
    if "bailleurs" in public and statut == "copropriétaire_bailleur":
        return True
    if "copropriétaires_occupants" in public and statut == "copropriétaire_résident":
        return True
    #  Le SEUL code du catalogue qui se décide sur le rôle et non sur le statut.
    #
    #  ⚠️ Cette branche manquait, et rien ne le montrait : les deux appelants
    #  (`publication_visible`, `sondage_accessible`) laissent sortir le CS et
    #  l'admin AVANT d'arriver ici, si bien qu'un contenu ciblé « conseil
    #  syndical » leur parvenait par ce chemin-là. Le comportement était donc
    #  juste — mais la fonction ne l'était pas, et un troisième appelant qui
    #  aurait oublié le court-circuit aurait caché au conseil syndical ce qui lui
    #  était explicitement adressé. Trouvé par `test_destinataires_vocabulaire.py`
    #  le 16/08/2026, qui interroge la règle SEULE.
    if "conseil_syndical" in public and user.has_role(
        RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical
    ):
        return True
    # Valeur non reconnue, ou public dont l'utilisateur ne fait pas partie
    return False


# ── Règles publication ────────────────────────────────────────────────────────

def publication_visible(pub: Publication, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir cette publication.

    Vérifie deux dimensions indépendantes :
      1. Périmètre géographique (perimetre_cible)
      2. Public cible (public_cible) : résidents | copropriétaires | locataires | conseil_syndical
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True

    # 1. Périmètre géographique
    perims = _codes_json_pour_acces(pub.perimetre_cible)
    if perims is None:
        #  Ciblage illisible : on refuse. Le CS et l'admin sont déjà sortis plus
        #  haut et gardent donc l'accès nécessaire pour corriger la publication.
        return False
    #  `ouvert_a_la_copropriete` : une actualité ciblée sur un autre bâtiment reste
    #  lisible (#339). La vie d'une copropriété se passe rarement dans un seul
    #  bâtiment — un chantier, une coupure, une réunion concernent souvent sans
    #  être « chez soi ». Le résident qui préfère l'ancien fonctionnement coche
    #  « n'afficher que mes bâtiments » dans son profil.
    #
    #  ⚠️ Ce n'est QUE l'axe bâtiment. Le public cible ci-dessous n'est pas touché,
    #  et c'est lui qui protège : une agence, un bailleur non résident ou un
    #  mandataire qui ne voyaient pas cette publication ne la voient pas davantage.
    #
    #  `confidentiel` (#347) ne fait que **refermer** cette ouverture-là, et rien
    #  d'autre : il n'existe pas de seconde règle d'accès pour les actualités
    #  confidentielles — c'est le paramètre à sa valeur par défaut, c'est-à-dire
    #  le comportement d'avant #339. Une règle à part aurait dû être maintenue en
    #  parallèle de celle-ci, et c'est ainsi que deux règles divergent.
    if not perimetre_visible(
        perims, user, ouvert_a_la_copropriete=not pub.confidentiel
    ):
        return False

    # 2. Public cible — règle partagée avec les sondages, voir plus haut.
    return public_cible_visible(pub.public_cible, user)


# ── Règles sondage ────────────────────────────────────────────────────────────

def sondage_clos(sondage: Sondage, maintenant: datetime) -> bool:
    """Ce sondage est-il terminé — de force, ou parce que l'échéance est passée ?

    Les DEUX voies comptent, et c'est tout l'intérêt d'une écriture unique : la
    même expression était recopiée quatre fois côté API (fiche du sondage, vote,
    modification, fil d'activité) et une cinquième côté front (`estCloture`).
    Le compteur du tableau de bord, lui, ne regardait que `cloture_forcee` — il
    annonçait donc « actifs » des sondages que tous les autres écrans donnaient
    pour clos, jusqu'à ce que quelqu'un pense à cliquer sur « clôturer ». Deux
    définitions coexistaient, et c'est la plus permissive qui alimentait la
    pastille (#399).

    `maintenant` est passé en paramètre, jamais lu ici : le fil calcule son
    instant une fois par requête (`ContexteFlux.now`) et douze rubriques qui
    appelleraient `utcnow()` chacune ne dateraient plus la même clôture.
    """
    return bool(
        sondage.cloture_forcee
        or (sondage.cloture_le is not None and sondage.cloture_le < maintenant)
    )


def resultats_sondage_visibles(resultats_publics: bool, cloture: bool) -> bool:
    """Les décomptes de ce sondage peuvent-ils quitter le serveur ?

    `resultats_publics` signifie « visibles **avant** la clôture » : une fois le
    sondage clos, ils le sont dans tous les cas.

    ⚠️ Cette règle décide de ce que l'API **envoie**, pas de ce que le front
    affiche. Jusqu'au 17/08/2026 elle n'existait pas : `GET /sondages/{id}`
    renvoyait `nb_votes` et les réponses en texte libre sans aucune condition, et
    seul le front tentait de les masquer. Décocher la case ne cachait donc rien —
    les résultats restaient lisibles dans la réponse réseau par tout destinataire
    avant son vote, alors que la case existe précisément pour qu'un vote en cours
    n'influence pas les suivants (#397).

    L'audience, elle, n'est PAS gérée ici : c'est celle du sondage, décidée par
    `sondage_accessible` (périmètre + public cible). Cette fonction ne répond
    qu'à la question du calendrier — avant ou après la clôture.

    Aucune exception pour l'auteur ni pour le conseil syndical : ils sont donc
    aveugles à la participation jusqu'à la clôture quand la case est décochée.
    C'est ce que l'option promet littéralement, et le défaut le plus sûr pour
    l'intégrité du vote — à rouvrir si l'usage montre que c'est trop strict.
    """
    return bool(resultats_publics or cloture)


def sondage_accessible(sondage: Sondage, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir/voter à ce sondage.

    - CS / Admin : toujours True.
    - `perimetre_cible` (JSON de codes) : vide = aucune restriction géographique.
    - `public_cible` (JSON de codes) : vide = tous les profils.

    C'est **exactement** la règle des publications, à une exception près et elle
    est délibérée : `ouvert_a_la_copropriete` reste à sa valeur par défaut, donc
    faux. Une actualité ciblée sur un bâtiment reste lisible de toute la
    copropriété (#339) parce qu'elle informe ; un sondage, lui, fait **voter** —
    l'ouvrir changerait qui pèse sur le résultat. L'accès d'un sondage ciblé sur
    un bâtiment est donc rigoureusement celui d'avant l'unification.
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    perims = _codes_json_pour_acces(sondage.perimetre_cible)
    if perims is None:
        #  Ciblage illisible : on refuse. Un contrôle qui ne peut pas s'exécuter
        #  ne renvoie jamais OK (`standards/04`), et le CS est déjà sorti plus
        #  haut — il garde donc de quoi corriger le sondage.
        return False
    if not perimetre_visible(perims, user):
        return False
    return public_cible_visible(sondage.public_cible, user)


# ── Règles événement ──────────────────────────────────────────────────────────

def evenement_visible(ev: Evenement, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir cet événement.

    - AG invisible pour les locataires, mandataires, syndics et aidants.
    - maintenance_recurrente invisible pour tous (usage interne uniquement).
    - Périmètre géographique (champ CSV ev.perimetre).
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        # CS/Admin voient tout sauf maintenance_recurrente (usage interne)
        if ev.type == TypeEvenement.maintenance_recurrente:
            return False
        return True

    if ev.type == TypeEvenement.maintenance_recurrente:
        return False

    if ev.type == TypeEvenement.ag:
        if not user.has_role(RoleUtilisateur.propriétaire):
            return False

    #  `parse_perimetres` porte le repli : un événement sans périmètre désigne le
    #  nœud racine à portée globale, désigné par les données et non par une chaîne
    #  « résidence » écrite ici — une autre copropriété peut l'avoir renommé.
    return perimetre_visible(parse_perimetres(ev.perimetre), user)


# ── Règle AG (helper rapide) ──────────────────────────────────────────────────

def can_see_ag(user: Utilisateur) -> bool:
    """True si l'utilisateur peut voir les événements AG."""
    return user.has_role(
        RoleUtilisateur.propriétaire,
        RoleUtilisateur.conseil_syndical,
        RoleUtilisateur.admin,
    )

# \u2500\u2500 R\u00e8gles ticket \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n
def ticket_visible(ticket: Ticket, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir ce ticket.

    - CS / Admin : toujours True.
    - Auteur du ticket (auteur_id == user.id).
    - R\u00e9sident inscrit pour le compte duquel le ticket a \u00e9t\u00e9 saisi
      (saisi_pour_user_id == user.id).
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    if ticket.auteur_id == user.id:
        return True
    if ticket.saisi_pour_user_id is not None and ticket.saisi_pour_user_id == user.id:
        return True
    return False

# ── Règles document ───────────────────────────────────────────────────────────

def document_visible(user: Utilisateur, doc: Document, session) -> bool:
    """Retourne True si l'utilisateur a le droit de lire ce document.

    Algorithme d'accès en 5 étapes (specs modele-donnees.md). Un document tire sa
    protection soit de l'objet qui le porte (contrat, actualité), soit de son profil
    d'accès de catégorie — jamais des deux, jamais d'aucun.

    Cette règle vivait dans `routers/documents.py`, et `flux.py` l'importait depuis
    ce router. Une règle de sécurité hors du module central, c'est une règle qu'un
    durcissement ultérieur peut manquer : c'est exactement ce qui est arrivé aux
    pièces jointes d'actualité, autorisées sans consulter l'actualité porteuse
    (cf. `tests/test_documents_acces.py`). Elle est ici, avec les autres.

    `session` n'est typé que par usage (`.get`) pour ne pas faire dépendre ce module
    de SQLModel : seuls `Publication` et `ProfilAccesDocument` sont chargés.
    """
    # Admin et CS voient tout
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True

    # Documents liés à un contrat (sans catégorie) : CS/admin uniquement
    if doc.contrat_id and not doc.categorie_id:
        return False

    # Pièce jointe d'actualité : elle suit EXACTEMENT la visibilité de son actualité.
    # Un document n'a pas de ciblage propre (ni `public_cible`, ni `perimetre_cible`) ;
    # sa seule protection légitime est celle de la publication qui le porte.
    if doc.publication_id and not doc.categorie_id:
        pub = session.get(Publication, doc.publication_id)
        # Publication introuvable → on refuse : aucune règle à appliquer.
        # Brouillon → rien n'est publié, la pièce jointe non plus (CS/admin sont
        # déjà sortis plus haut et gardent l'accès à leurs brouillons).
        if not pub or pub.brouillon:
            return False
        return publication_visible(pub, user)

    profil_id = doc.profil_acces_override_id or doc.categorie.profil_acces_id
    profil: ProfilAccesDocument = session.get(ProfilAccesDocument, profil_id)
    if not profil:
        return False

    # Vérifier le rôle (supporte valeurs de rôles ET de statuts pour compatibilité)
    roles_autorises = json.loads(profil.roles_autorises)
    user_idents = set(user.roles) | {user.statut.value}
    if not any(r in roles_autorises for r in user_idents):
        return False

    # Vérifier le périmètre
    if doc.perimetre == "bâtiment" and doc.batiment_id:
        user_batiments = {
            ul.lot.batiment_id for ul in user.user_lots if ul.actif and ul.lot
        }
        if doc.batiment_id not in user_batiments:
            return False

    if doc.perimetre == "lot" and doc.lot_id:
        user_lots = {ul.lot_id for ul in user.user_lots if ul.actif}
        if doc.lot_id not in user_lots:
            return False

    return True
