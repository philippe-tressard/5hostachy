"""Visibilité par entité — publication, sondage, événement, ticket.

⚠️ Fragment de `app/utils/visibility/` — **la règle reste unique**, elle a seulement
cessé de tenir dans un seul fichier (#547, 20/08/2026). Le paquet expose la même
surface qu'avant : `from app.utils.visibility import …` ne change pas d'une ligne
pour ses seize importateurs.

Le découpage suit une couture réelle, pas la ligne où le compteur a dépassé :
`socle` porte les deux primitives que tout le reste compose (géographie et public
visé), `objets` les règles par entité, `documents` l'algorithme d'accès en cinq
étapes — le seul qui interroge la base, et le seul adossé à un modèle de profil
d'accès.
"""
from __future__ import annotations

from datetime import datetime

from app.models.core import (
    Evenement,
    Idee,
    PetiteAnnonce,
    Publication,
    RoleUtilisateur,
    Sondage,
    StatutUtilisateur,
    Ticket,
    TypeEvenement,
    Utilisateur,
)
from app.utils.perimetres import parse_perimetres

#  ⚠️ `_codes_json_pour_acces` est privé au paquet, pas au fichier : c'est le
#  parseur commun des listes de codes (« qui est visé »), et deux fragments le
#  composent. Le découpage a coupé cette dépendance au premier essai — 56 tests
#  sont tombés d'un coup sur un `NameError`, ce qui est la bonne façon d'échouer.
from .socle import (
    _codes_json_pour_acces,
    cible_visible,
    perimetre_visible,
)
#  ⚠️ `public_cible_visible` n'est plus importé ici depuis le 06/09/2026 : aucune
#  règle de ce fichier ne l'appelle en direct — elles passent toutes par
#  `cible_visible`, qui pose les deux axes. Une factorisation se termine par la
#  suppression de ce qu'elle a remplacé, et c'est Ruff (F401) qui l'a rappelé.

# ── Règles publication ────────────────────────────────────────────────────────

def publication_visible(pub: Publication, user: Utilisateur) -> bool:
    """L'utilisateur peut-il voir cette publication ?

    Périmètre puis public cible : c'est `cible_visible` qui les pose, et elle est
    la SEULE écriture de cette règle depuis le 06/09/2026 (#782). Ce corps
    portait les mêmes onze lignes que `sondage_accessible`, au paramètre
    d'ouverture près.

    #  `ouvert_a_la_copropriete` : une actualité ciblée sur un autre bâtiment
    #  reste lisible (#339). La vie d'une copropriété se passe rarement dans un
    #  seul bâtiment — un chantier, une coupure, une réunion concernent souvent
    #  sans être « chez soi ». Le résident qui préfère l'ancien fonctionnement
    #  coche « n'afficher que mes bâtiments » dans son profil.
    #
    #  ⚠️ Ce n'est QUE l'axe bâtiment. Le public cible n'est pas touché, et c'est
    #  lui qui protège : une agence, un bailleur non résident ou un mandataire
    #  qui ne voyaient pas cette publication ne la voient pas davantage.
    #
    #  `confidentiel` (#347) ne fait que **refermer** cette ouverture-là, et rien
    #  d'autre : il n'existe pas de seconde règle d'accès pour les actualités
    #  confidentielles — c'est le paramètre à sa valeur par défaut, c'est-à-dire
    #  le comportement d'avant #339. Une règle à part aurait dû être maintenue en
    #  parallèle de celle-ci, et c'est ainsi que deux règles divergent.
    """
    return cible_visible(
        pub.perimetre_cible,
        pub.public_cible,
        user,
        ouvert_a_la_copropriete=not pub.confidentiel,
    )


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
    """L'utilisateur peut-il voir ce sondage et y voter ?

    - CS / Admin : toujours True.
    - `perimetre_cible` (JSON de codes) : vide = aucune restriction géographique.
    - `public_cible` (JSON de codes) : vide = tous les profils.

    C'est **exactement** la règle des publications, à une exception près et elle
    est délibérée : `ouvert_a_la_copropriete` reste à sa valeur par défaut, donc
    faux. Une actualité ciblée sur un bâtiment reste lisible de toute la
    copropriété (#339) parce qu'elle informe ; un sondage, lui, fait **voter** —
    l'ouvrir changerait qui pèse sur le résultat.

    Depuis le 06/09/2026 (#782), « exactement la même règle » n'est plus une
    phrase de docstring : c'est le même appel.
    """
    return cible_visible(sondage.perimetre_cible, sondage.public_cible, user)


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

# ── Règles ticket ─────────────────────────────────────────────────────────────
def ticket_visible(ticket: Ticket, user: Utilisateur) -> bool:
    """Qui peut LIRE ce ticket — jamais qui peut y écrire.

    ## L'ouverture du 02/09/2026 (#710)

    > « Les copropriétaires et locataires peuvent désormais voir les tickets de
    >   leur périmètre. »

    Un résident voit les tickets dont le périmètre recoupe **ses bâtiments**, et
    ceux à portée globale. La règle n'est pas réécrite ici : `perimetre_visible`
    la porte, `mes_batiments` porte « quels bâtiments sont les siens ». Ce corps
    ne fait que les **composer** — aucune liste de périmètres, aucun
    `batiment_id`, aucun rôle en dur.

    🔴 ET CE N'EST PAS LA RÈGLE DES ACTUALITÉS, malgré l'apparence. La première
    écriture de cette fonction passait `ouvert_a_la_copropriete=not confidentiel`,
    par analogie avec `publication_visible` — deux tests l'ont refusée dans la
    minute, et ils avaient raison deux fois :

    - ce paramètre ne restreint pas au périmètre, il **l'ignore** : un résident
      sans préférence de restriction voyait alors TOUS les tickets, y compris
      ceux d'un bâtiment où il n'a rien. L'ouverture demandée était « son
      périmètre », pas « tout » ;
    - et il rendait le drapeau `confidentiel` **inopérant** sur le cas le plus
      courant, un ticket à portée « résidence » : la portée globale est décidée
      avant lui, donc il ne refermait rien du tout.

    Une actualité s'adresse à la copropriété et son ciblage n'est qu'un accent
    (#339) ; un ticket est une **affaire**, et son périmètre dit qui elle
    regarde. Le même mot, deux règles — les composer pareil était l'erreur.

    ## Ce que cette fonction n'ouvre PAS

    Elle décide de la **lecture**. Commenter, faire avancer le suivi, corriger la
    demande passent par `peut_commenter` / `peut_editer` (`auth/deps.py`), qui ne
    l'appellent pas : élargir la lecture ne donne donc aucun droit d'écriture.
    C'est ce qui rend le « lecture seule » du ticket structurel plutôt que promis.

    ## `confidentiel` — le filet

    Un litige de voisinage, un impayé, un dégât des eaux qui nomme quelqu'un :
    ces tickets existent, et l'ouverture les rendrait lisibles de tout un
    bâtiment. Le drapeau les ramène à ce qu'ils étaient hier — **l'auteur, la
    personne pour qui le ticket a été saisi, le CS**, et personne d'autre. Ces
    trois cas sont traités AVANT, et le drapeau ne les touche pas.

    ⚠️ Il refuse donc SANS consulter le périmètre, et c'est délibéré : un ticket
    confidentiel à portée « résidence » doit se refermer comme les autres. Écrit
    dans l'autre ordre, le drapeau n'aurait mordu que sur les tickets déjà les
    plus restreints — ceux dont on n'a pas besoin de lui.
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    if ticket.auteur_id == user.id:
        return True
    if ticket.saisi_pour_user_id is not None and ticket.saisi_pour_user_id == user.id:
        return True

    #  🔴 UN LOCATAIRE NE VOIT QUE LES SIENS (05/09/2026), demandé à l'écran :
    #  *« les locataires ne voient pas les tickets »*.
    #
    #  C'est un retrait partiel de l'ouverture du 02/09 (#710), qui visait « les
    #  copropriétaires et locataires ». Ce qu'un locataire a déposé — ou ce qu'on
    #  a saisi pour lui — lui reste visible : ces deux cas sont traités AVANT, et
    #  cette règle ne les touche pas. Il peut donc toujours signaler, et suivre sa
    #  propre demande ; il ne lit simplement plus les affaires de l'immeuble.
    #
    #  ⚠️ La règle est ICI, avec les autres, et nulle part ailleurs : ni dans un
    #  écran, ni dans un `where` de liste. *« pour la sécurité tout doit être
    #  centralisé, pas de règles perdues dans une page »* — et c'est aussi ce qui
    #  fait que la liste et la fiche ne peuvent pas diverger, puisque les deux
    #  passent par cette fonction.
    if user.statut == StatutUtilisateur.locataire:
        return False

    if ticket.confidentiel:
        return False

    perims = _codes_json_pour_acces(ticket.perimetre_cible)
    if perims is None:
        #  Ciblage illisible : on refuse. Le CS, l'admin et l'auteur sont déjà
        #  sortis plus haut — personne ne perd l'accès nécessaire pour corriger.
        return False
    return perimetre_visible(perims, user)

# ── Règles Communauté : petite annonce et idée ────────────────────────────────
#
#  🔴 CES DEUX FONCTIONS N'ONT PAS DE CORPS, ET C'EST LE SUJET.
#
#  Le public cible leur a été ouvert le 06/09/2026 (#782, migration 0176), avec
#  la même sémantique que le sondage : il filtre la VISIBILITÉ, pas seulement les
#  notifications. Écrire ici « if user.has_role(admin, cs): return True » suivi
#  des deux axes aurait donné une TROISIÈME et une QUATRIÈME copie de la même
#  règle — et une règle d'accès en quatre exemplaires se durcit une fois sur
#  quatre. Ce dépôt a déjà payé ce prix (`utils/destinataires.py`, quatre copies
#  jusqu'au 31/08 ; `_require_bailleur`, doublon de `require_proprietaire` avec
#  dix-sept endpoints dessus, que la spec documentait comme officiel).
#
#  Elles existent quand même, plutôt qu'un appel direct à `cible_visible` chez
#  l'appelant, pour deux raisons : elles NOMMENT la décision (« cette annonce
#  est-elle visible ? » se lit mieux que trois arguments), et elles sont l'endroit
#  où s'écrira une divergence FUTURE, si le produit en décide une — avec son
#  motif, à un seul endroit.

def annonce_visible(annonce: PetiteAnnonce, user: Utilisateur) -> bool:
    """Cette petite annonce est-elle visible de cet utilisateur ?

    `ouvert_a_la_copropriete` reste faux : une annonce s'adresse à qui son auteur
    a choisi. L'ouverture qui vaut pour une actualité — elle informe, donc elle
    déborde son bâtiment (#339) — n'aurait ici aucun sens : on ne propose pas un
    lave-linge à des voisins qu'on a explicitement écartés.
    """
    return cible_visible(annonce.perimetre_cible, annonce.public_cible, user)


def idee_visible(idee: Idee, user: Utilisateur) -> bool:
    """Cette idée est-elle visible de cet utilisateur ?

    ⚠️ Une idée ciblée est privée des voix qui la porteraient — c'est exactement
    l'objection que la déclaration d'écran opposait à cette section, et elle
    reste vraie. Elle a été tranchée : le ciblage est un choix de l'auteur, pas
    un défaut du produit. Ne pas le contourner ici en ouvrant discrètement
    l'audience ; ce serait décider à sa place, sans que rien ne le dise.
    """
    return cible_visible(idee.perimetre_cible, idee.public_cible, user)
