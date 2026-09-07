"""Le vocabulaire d'un ticket — états du workflow, catégories, priorités.

Extrait de `core.py` le 17/08/2026, au fil de l'eau : le fichier faisait déjà
1 245 lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé
qu'il grossisse pour recevoir la correction de #415. La règle est « on découpe
le fichier QUAND on y touche ».

## Ce que ce module porte, et ce qu'il ne porte pas

Il porte le **vocabulaire** : les valeurs qu'un ticket peut prendre, et les
réponses aux deux questions qu'on lui pose partout — « demande-t-il encore du
suivi ? », « est-il clos ? ». C'est précisément ce que #415 a trouvé recopié
dans neuf endroits, divergent dans les deux sens.

Il ne porte **pas** les tables (`Ticket`, `MessageTicket`, `TicketEvolution`),
qui restent dans `core.py` : leurs `Relationship` croisent `Utilisateur` et
`Lot`, et les déplacer imposerait un cycle d'import entre les deux modules —
avec, à la clé, un ordre de chargement qui décide si l'application démarre. Ce
découpage-là se fera quand on touchera aux tables elles-mêmes, et il demandera
sa propre vérification.

Les noms restent **ré-exportés par `core.py`** : aucun des dix-huit modules
appelants n'a une ligne à changer, comme pour `copropriete.py` (13/08),
`communaute.py` (16/08) et `validations.py` (17/08).
"""
from enum import Enum


class StatutTicket(str, Enum):
    """Les quatre états du workflow d'un ticket — et il n'y en a pas d'autre.

    `fermé` a vécu ici jusqu'au 17/08/2026 sous la mention « conservé pour
    compatibilité données existantes ». Il ne se distinguait de `résolu` par
    rien : même clôture, même sortie de la liste active, même exclusion des
    relances. C'était un reliquat du modèle d'origine (`2792b76`), pas une étape
    de vie — et il était pourtant le seul état que le formulaire d'évolution de
    la fiche proposait en plus des trois évidents, pendant que `annulé` y était
    refusé (#415). La migration 0149 a basculé les tickets concernés en `résolu`.

    C'est cette énumération qui fait foi, partout : les deux endpoints qui
    changent l'état d'un ticket valident par elle (`TicketUpdate.statut`,
    `TicketEvolutionCreate.nouveau_statut`), et `$lib/tickets.ts` lui répond
    côté écran. `api/tests/test_statuts_tickets.py` échoue si l'un des deux
    dérive.
    """

    ouvert = "ouvert"
    en_cours = "en_cours"
    résolu = "résolu"
    annulé = "annulé"


#: Un ticket dans l'un de ces états ne demande plus de suivi : il quitte la liste
#: active, sort des relances syndic et des compteurs « à traiter ». **Source
#: unique** — quatre modules réécrivaient cette liste chacun de leur côté, et
#: elles avaient divergé (`annulé` manquait à deux d'entre elles).
STATUTS_TICKET_CLOS: tuple[str, ...] = (StatutTicket.résolu.value, StatutTicket.annulé.value)

#: Le complément : un ticket qui demande encore du suivi. Écrit `("ouvert",
#: "en_cours")` à la main dans deux modules de `flux/`, où il aurait fallu penser
#: à l'ajouter le jour où un cinquième état serait apparu.
STATUTS_TICKET_ACTIFS: tuple[str, ...] = tuple(
    s.value for s in StatutTicket if s.value not in STATUTS_TICKET_CLOS
)

#: Valeurs qu'aucun ticket ne porte plus, mais que l'historique du fil
#: (`ticket_evolution.ancien_statut` / `nouveau_statut`) conserve : elles doivent
#: rester **affichables** — jamais proposables.
STATUTS_TICKET_HISTORIQUES: tuple[str, ...] = ("fermé",)


class CategorieTicket(str, Enum):
    """Ce que le ticket EST — jamais son degré d'urgence.

    🔴 « urgence » a été retirée le 07/09/2026, et c'est une correction de
    conception, pas un retrait de fonctionnalité. Elle mélangeait deux axes :
    une panne peut être urgente, une nuisance aussi. Un résident dont
    l'ascenseur est bloqué avec quelqu'un dedans devait choisir entre « Panne »
    et « Urgence », et perdait l'autre moitié de l'information quel que soit son
    choix.

    Le remplacement existait DÉJÀ et servait déjà : `PrioriteTicket.haute`, que
    la case « Urgent » du formulaire écrit depuis #766. Le commentaire de
    `front/src/lib/tickets.ts` le disait en toutes lettres — « `urgente` →
    `priorite === 'haute'`, ce que la catégorie Urgence pose déjà ». Les deux
    axes se recoupaient, et le code le savait.

    ⚠️ Les quatre catégories ajoutées le même jour ne le sont pas pour enrichir
    la liste : chacune change ce qu'on FAIT du ticket — le destinataire, le
    délai ou le geste attendu. Une catégorie qui ne change rien au traitement
    est un filtre décoratif, et elle rend le choix plus difficile pour rien.

    ## Ce que la consolidation a corrigé dans la première estimation

    Le relevé initial proposait « Dégât des eaux ». La documentation des
    assureurs et des syndics montre que **le dégât des eaux n'est qu'un cas** :
    incendie, vandalisme, bris de glace et catastrophe naturelle suivent la
    MÊME procédure — constat, photos, devis, et déclaration à l'assurance
    multirisque sous **cinq jours ouvrés**. C'est la procédure qui fait la
    catégorie, pas la cause. « Sinistre » les couvre toutes ; « Dégât des eaux »
    en laissait trois sans catégorie, donc en « Panne », où rien ne dit qu'un
    délai légal court.

    « Espaces verts » vient du même recoupement : elle figure dans toutes les
    applications de signalement (municipales comme résidentielles), et le
    prestataire n'est ni celui du nettoyage ni celui de la technique.

    Deux candidates ÉCARTÉES bien qu'omniprésentes ailleurs : « Éclairage »
    (c'est une panne d'équipement) et « Stationnement » (déjà nommé dans la
    description de « Nuisance »). Les ajouter aurait dispersé le choix sans rien
    changer au traitement.
    """

    panne = "panne"
    nuisance = "nuisance"
    proprete = "proprete"            # autre prestataire : le nettoyage, pas le technique
    espaces_verts = "espaces_verts"  # autre prestataire encore, et une saisonnalité
    sinistre = "sinistre"            # constat + déclaration à l'assurance sous 5 jours ouvrés
    etude_travaux = "etude_travaux"  # le dossier long que le conseil syndical suit
    question = "question"
    bug = "bug"


class PrioriteTicket(str, Enum):
    basse = "basse"
    normale = "normale"
    haute = "haute"
