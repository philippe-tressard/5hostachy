"""« Cet objet est-il le mien ? » — les règles, au même endroit.

## Pourquoi ce module (#1028, point 2)

L'audit du 19/09/2026 relevait que les règles d'appartenance vivaient **chez les
routeurs**, hors du module central, et que `test_autorisation.py` ne pouvait pas
les voir : ce ne sont pas des `Depends`, mais des fonctions ordinaires appelées
au début d'un geste.

Le ticket demandait « un module d'appartenance complet ». La première question
était donc : **peut-on les fondre ?** La réponse est non, et c'est mesuré :

| | bail d'un bailleur | accès d'un porteur |
|---|---|---|
| champ de propriété | `bailleur_id` | `user_id` |
| le conseil syndical y a-t-il accès ? | **oui** | **non** |
| refus | **403** | **404** |

Trois axes de divergence pour deux fonctions. Les réunir demanderait quatre
paramètres de variation, c'est-à-dire une abstraction si pauvre qu'elle serait
contournée au troisième appelant (`standards/02` §4 quater). Et les deux
décisions sont **justes** : un bail refusé peut dire « interdit », parce que son
existence n'apprend rien ; un badge qui n'est pas le vôtre doit dire
« introuvable », parce que « interdit » confirmerait qu'il existe.

## Ce que ce module apporte, puisque ce n'est pas une fonction commune

**Un lieu.** Les deux règles sont côte à côte, avec leur décision écrite, et on
les compare d'un coup d'œil — ce qui était impossible quand l'une vivait dans
`routers/bailleur/commun.py` et l'autre dans `routers/acces/resident.py`.

C'est ce que `standards/03` §1 demande : une règle d'autorisation ne vit pas chez
un routeur. Le lieu ne supprime pas la divergence — il la rend **visible**, et
c'est la seule chose qui empêche la troisième règle d'être écrite au hasard.

🔒 `api/tests/test_appartenance_source_unique.py` refuse qu'une comparaison entre
un champ d'objet et `user.id` gouverne une levée HTTP hors de `auth/`.

## Deux questions, deux fonctions — ne pas les remélanger

« Existe-t-il ? » est répondu par `utils/recuperer.ou_404`, et **uniquement** par
lui. Les fonctions ci-dessous l'appellent, puis ajoutent leur question propre :
« est-ce le vôtre ? ». Les helpers qu'elles remplacent mêlaient les deux, et
`recuperer.py` explique déjà pourquoi c'est un défaut : un 404 posé « pour ne pas
révéler l'existence » est une décision de sécurité, pas une réponse à
« existe-t-il ? ».
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException
from sqlmodel import Session

from app.auth.deps import est_moderateur
from app.models.core import LocationBail, Utilisateur
from app.utils.recuperer import ou_404


def exiger_bail_du_bailleur(session: Session, bail_id: int, user: Utilisateur) -> LocationBail:
    """Le bail, s'il est celui de ce bailleur — **403** sinon.

    Le conseil syndical et l'administration y ont accès : ils arbitrent les
    litiges de gestion locative, et c'est pour cela que ce cas existe.

    ⚠️ **403 et non 404**, contrairement à l'accès d'un porteur : l'existence d'un
    bail sur un lot n'apprend rien à qui n'y a pas droit — le lot, lui, est
    public dans la copropriété. Dire « interdit » est donc honnête, et plus
    utile qu'un « introuvable » qui enverrait chercher une erreur de saisie.
    """
    bail = ou_404(session, LocationBail, bail_id, "Bail")
    if bail.bailleur_id != user.id and not est_moderateur(user):
        raise HTTPException(status_code=403, detail="Accès interdit")
    return bail


def exiger_aidant_de_la_delegation(delegation, user: Utilisateur) -> None:
    """Seul l'aidant désigné accepte une délégation — **403** sinon.

    Troisième décision, troisième combinaison, et c'est tout l'intérêt de les
    avoir côte à côte : ici le conseil syndical n'est **pas** admis — accepter
    une délégation engage l'aidant personnellement, personne ne peut le faire à
    sa place — mais le refus dit « interdit », parce que la délégation existe
    bel et bien et que le demandeur le sait : il en est le mandant.

    ⚠️ La **révocation**, elle, admet le mandant, l'aidant ET le conseil : on
    peut avoir besoin de défaire ce qu'on n'a pas le droit de faire. Elle reste
    chez son routeur — elle ne compare pas une propriété, elle vérifie une
    appartenance à un ensemble de trois, ce qui est une autre question.
    """
    if delegation.aidant_id != user.id:
        raise HTTPException(403, "Seul l'aidant désigné peut accepter")


def exiger_acces_du_porteur(session: Session, type_acces, objet_id: int, user: Utilisateur):
    """Le badge ou la télécommande, s'il appartient à qui le demande — **404** sinon.

    🔴 **404 et non 403**, et le conseil syndical n'est **pas** admis ici. Les
    deux décisions se tiennent : répondre « interdit » confirmerait l'existence
    d'un badge qui n'est pas le vôtre, et permettrait de deviner le parc d'un
    voisin en essayant des identifiants.

    Cette règle était écrite **quatre fois** à l'identique avant d'être ramenée
    dans `routers/acces/resident.py` ; elle est ici depuis #1028, avec les autres.
    """
    from app.utils.porteurs_acces import porteurs

    #  Porteur = ce que dit le LOT (#1194) : le conjoint signale la perte du
    #  badge du ménage, lui aussi. `user_id` seul n'en laissait qu'un.
    objet = session.get(type_acces.modele, objet_id)
    if not objet or user.id not in porteurs(session, objet):
        raise HTTPException(404, f"{type_acces.libelle} introuvable")
    return objet


def exiger_cible_visible(
    session: Session,
    modele: type,
    cible_id: int,
    libelle: str,
    user: Utilisateur,
    visible_de: Callable[[Any, Utilisateur], bool],
) -> Any:
    """La cible existe ET l'utilisateur a le droit de la voir — **404** sinon.

    Quatrième décision, quatrième combinaison — et la seule qui prenne le
    prédicat de visibilité **en paramètre** : ce qui rend une annonce visible
    n'est pas ce qui rend une idée visible, et cette variation-là est légitime
    parce qu'elle ne porte que sur UNE question, pas sur trois.

    🔒 **404 et non 403**, délibérément : répondre « interdit » confirmerait
    l'existence de l'objet à qui n'a pas le droit de le voir. Sur une petite
    annonce ciblée, cela révélerait qu'un voisin vend quelque chose sans dire
    quoi — une fuite plus discrète, mais réelle.

    Les trois routes de réponses posaient la même question à moitié (« existe-t-il ? »)
    et chacune à sa façon. Une seule écriture, appelée trois fois.
    """
    cible = session.get(modele, cible_id)
    if not cible or not visible_de(cible, user):
        raise HTTPException(404, f"{libelle} introuvable")
    return cible
