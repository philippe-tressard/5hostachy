"""La section **Quand** — les dates d'un objet, et ce qu'elles dispensent.

## Pourquoi ce module (#1092, chantier v2.0.0)

Le chantier réduit trois objets à deux : **Actualité** et **Affaire**. Le
Calendrier cesse d'être un objet pour devenir une vue — « tout ce qui porte une
date » —, comme le carnet d'entretien est déjà une vue sur trois tables.

Pour cela, une publication et un ticket doivent pouvoir porter une date. Ce
module tient les **deux notions de date**, qu'il ne faut surtout pas confondre :

| | `debut` / `fin` | `echeance` |
|---|---|---|
| Sens | *ça se passe le X* | *ça doit être fait avant le X* |
| Exemple | AG le 14 novembre · coupure d'eau jeudi 9h-12h | devis attendu sous 15 jours |
| Alimente | le **calendrier** | le **suivi** (relance, retard) |
| Portée | actualité et affaire | **affaire seulement** |

Les mêler afficherait « devis attendu » dans l'agenda de la résidence, et
n'alerterait jamais sur un retard.

## La règle de description, et pourquoi elle vit ICI

> **La description est obligatoire. Sans exception.**

🔴 Elle a porté une condition pendant deux jours — *« sauf si une date
d'événement est renseignée »* —, au motif que « Coupure d'eau — jeudi 9h-12h »
se suffit. Retirée le 22/09/2026, arbitré à l'écran :

> « Un évènement avec une date doit aussi remplir une description
>   (obligatoire sans exception). »

⚠️ Elle reste dans CE module bien qu'elle ne dépende plus d'une date, et c'est
délibéré : c'est ici que les deux créations l'appellent déjà, et que son test
la surveille. La déplacer pour la beauté du rangement rouvrirait la question
de *où* elle se décide — précisément l'oubli qui l'a rendue nécessaire.

Deux défauts opposés l'ont rendue nécessaire, et ce sont les deux faces du même
oubli — personne n'avait écrit *où* la question se décide :

- côté **actualités et tickets**, l'astérisque de « Description * » ne vivait
  qu'à l'écran. `PublicationCreate.contenu` et `TicketCreate.description` sont
  typés `str`, ce qui accepte `""` : un appel direct créait un objet vide, et le
  champ requis mentait (mesuré le 20/09/2026) ;
- côté **calendrier**, la description n'était pas exigée du tout, ce qui a fait
  déclarer une dérogation (#1089).

Écrite **sans condition ni dérogation d'objet**, la règle est vraie partout,
quel que soit l'écran où l'on saisit. C'est ce qui referme #1089 — et, depuis le
22/09/2026, sans même une condition à comprendre.

🔒 `api/tests/test_description_conditionnelle.py` — unicité, appel effectif par
les deux créations, et le **cas zéro** (une fonction qui ne lève jamais rendrait
les deux premiers contrôles verts).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException


def exiger_description(texte: Optional[str], *, debut: Optional[datetime] = None) -> None:
    """Refuser une description vide. Sans exception.

    Ne rend rien : elle lève, ou elle laisse passer. C'est volontaire — un
    appelant qui reçoit un booléen finit par l'ignorer, et la règle redevient
    décorative (`standards/04` §7).

    ⚠️ `422` et non `400` : c'est une entrée qui ne satisfait pas une règle de
    validation, au même titre que les refus de Pydantic sur le même corps. Deux
    codes pour le même geste rendraient le message du front dépendant de qui a
    refusé.
    """
    if texte and texte.strip():
        return
    #  ⚠️ `debut` est ACCEPTÉ et ignoré, volontairement. Il dispensait de
    #  description jusqu'au 22/09/2026 ; le retirer de la signature obligerait à
    #  toucher les deux appelants dans le même lot, pour un paramètre que le
    #  prochain lot pourrait vouloir relire. Le garder inerte et le DIRE coûte
    #  une ligne ; le retirer en silence ferait croire qu'il n'a jamais existé.
    del debut
    raise HTTPException(422, "Une description est attendue.")
