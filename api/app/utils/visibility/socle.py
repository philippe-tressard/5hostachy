"""Primitives de visibilité — géographie et public visé.

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

import json
from typing import Optional

from app.models.core import (
    RoleUtilisateur,
    Utilisateur,
)
from app.utils.mes_batiments import batiments_de_l_utilisateur
from app.utils.perimetres import a_portee_globale, batiments_cibles

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

    #  🔴 LE REPLI PERMISSIF EST FERMÉ (02/09/2026), sur arbitrage :
    #  *« un utilisateur sans bâtiment ne doit rien voir car il n'est pas
    #  résident »*.
    #
    #  Il rendait `True` dès que `user.batiment_id` était `None` — « accès
    #  résidence entière par défaut ». Deux tests l'épinglaient en disant, l'un et
    #  l'autre, « le jour où ce repli sera repris » : c'est ce jour-là.
    #
    #  Ce que ça referme, au-delà des périmètres : la CONFIDENTIALITÉ passe par ce
    #  même chemin (`ouvert_a_la_copropriete=False`). Un compte sans bâtiment
    #  voyait donc les actualités confidentielles de TOUS les bâtiments.
    #
    #  ⚠️ POURQUOI LES LOTS, ET POURQUOI SEULEMENT ICI. Un copropriétaire
    #  BAILLEUR n'a par construction aucun `batiment_id` : c'est son locataire qui
    #  habite. Fermer sur le seul rattachement l'aurait coupé de sa propre
    #  copropriété, en croyant n'écarter que des comptes techniques.
    #
    #  Mais la consultation des lots reste CONFINÉE à cette branche, et c'est la
    #  contrainte posée le 14/08/2026, écrite dans `utils/mes_batiments` : *une
    #  agence, un bailleur ou un mandataire qui n'avaient pas de visibilité n'en
    #  gagnent aucune*. Décider sur `batiments_de_l_utilisateur()` en toutes
    #  circonstances — ce qu'a fait la première écriture de ce correctif —
    #  ÉLARGIT : un bailleur rattaché au bâtiment A et détenteur d'un lot en B
    #  gagnait l'accès à B. Un élargissement obtenu en croyant ne faire que
    #  restreindre, et qu'aucun test existant n'attrapait, tous portant sur le
    #  rattachement seul.
    #
    #  Confinée ici, la règle ne peut que retirer : celui qui a un rattachement
    #  garde exactement ce qu'il avait, celui qui n'en a pas passe de « toute la
    #  résidence » aux bâtiments de ses lots — et à rien du tout s'il n'en a
    #  aucun. Verrouillé par `test_visibilite_ouverte.py`.
    if user.batiment_id is None:
        #  Sans rattachement, ce sont les lots qui disent de quoi ce compte est.
        #  Vide = ni rattachement ni lot : pas résident de la copropriété. Ce qui
        #  lui est destiné passe par les périmètres à portée globale, traités plus
        #  haut, et par les objets dont il est l'auteur ou le destinataire.
        return bool(batiments_de_l_utilisateur(user) & batiments_cibles(perimetres))
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
