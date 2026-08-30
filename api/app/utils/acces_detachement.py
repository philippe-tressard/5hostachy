"""Retirer un badge ou une télécommande : ce qui part, et ce qui se délie.

## Pourquoi ce module (#546, 30/08/2026)

Vigik et télécommande sont deux objets **jumeaux** : même cycle de vie, mêmes
tables satellites, mêmes gestes. Leurs deux suppressions vivaient pourtant côte à
côte dans `acces.py`, écrites séparément — et elles avaient divergé :

| | attributions (`user_*`) | ligne d'import (`*_import`) |
|---|---|---|
| télécommande | **oubliées** | déliée ✔ |
| vigik | **oubliées** | **oubliée** |

La télécommande déliait son import, le badge non. Personne ne l'avait décidé :
c'est la seconde copie qui l'a produit. Les remettre en état séparément aurait
recréé la même paire, avec la même dérive à venir.

## La règle, et elle n'est pas la même pour les deux satellites

🔴 **L'attribution PART, la ligne d'import RESTE.**

  • `user_vigik` / `user_telecommande` — « ce badge est attribué à cette
    personne » n'a plus d'objet quand le badge disparaît. La colonne est
    d'ailleurs **NOT NULL** : on ne pourrait même pas la délier.

  • `vigik_import` / `telecommande_import` — elle décrit ce que le fichier du
    syndic contenait. L'effacer perdrait la trace de l'import, et le
    rapprochement automatique (`auto_match_service`) ne saurait plus qu'une ligne
    a existé. Elle repasse donc à l'état d'avant l'appariement.

## L'ordre, qui ne va pas de soi

Aucune de ces tables ne porte de `Relationship` vers son objet — seulement une
clé étrangère. SQLAlchemy n'a donc rien pour ordonner les DELETE et supprime le
parent d'abord : voir `suppression_liee.py`, où le fait est établi en traçant le
SQL réellement émis.
"""

from sqlmodel import Session, select

from app.models.core import StatutImport
from app.utils.suppression_liee import flush_si_necessaire


def detacher_acces(
    session: Session,
    objet_id: int,
    modele_attribution,
    colonne_attribution: str,
    modele_import,
    colonne_import: str,
) -> None:
    """Détacher les satellites d'un vigik ou d'une télécommande, avant sa suppression.

    N'exécute **ni `flush` final ni `commit`** au-delà de ce qu'exige l'ordre des
    DELETE : l'appelant supprime l'objet lui-même et décide de sa transaction.
    """
    champ_attr = getattr(modele_attribution, colonne_attribution)
    attributions = session.exec(select(modele_attribution).where(champ_attr == objet_id)).all()
    for attribution in attributions:
        session.delete(attribution)

    champ_imp = getattr(modele_import, colonne_import)
    ligne_import = session.exec(select(modele_import).where(champ_imp == objet_id)).first()
    if ligne_import:
        setattr(ligne_import, colonne_import, None)
        #  Retour à l'état d'AVANT l'appariement : si le propriétaire avait été
        #  reconnu, la ligne reste « propriétaire lié » ; sinon elle repart en
        #  attente. C'est ce que faisait déjà la télécommande, et c'est ce que le
        #  vigik ne faisait pas.
        ligne_import.statut = (
            StatutImport.proprietaire_lie
            if ligne_import.user_proprietaire_id
            else StatutImport.en_attente
        )
        session.add(ligne_import)

    flush_si_necessaire(session, len(attributions))
