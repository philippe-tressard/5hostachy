"""Ce qu'est un « compte en attente de validation » — écrit une seule fois.

Trois endroits posaient la question, chacun avec sa propre requête : la liste de
l'écran Admin, sa variante enrichie, et le compteur du tableau de bord. Les trois
écrivaient `Utilisateur.actif == False`, donc les trois donnaient le même chiffre
— et c'est précisément ce qui rendait le défaut indétectable à la relecture : on
vérifie qu'ils sont d'accord, pas qu'ils ont raison (#399).

`actif` répond à « ce compte peut-il se connecter ? ». Il ne répond pas à « reste-t-il
quelque chose à faire dessus ? » : un compte refusé, un compte suspendu et un compte
qui vient de s'inscrire sont tous les trois inactifs, et un seul appelle une action.
C'est `decision_compte_le` qui les sépare — voir la migration 0148 pour ce que le
rétro-remplissage sait, et ce qu'il s'interdit d'inventer.

⚠️ Ne jamais réécrire la condition dans un router. Si un quatrième lecteur apparaît,
il appelle `condition_compte_en_attente()` — c'est le seul moyen pour que la
définition reste unique, et donc corrigible en un seul endroit.
"""
from datetime import datetime

from sqlalchemy import and_
from sqlmodel import Session, func, select

from app.models.core import Utilisateur


def condition_compte_en_attente():
    """Clause SQL « ce compte attend une décision de l'administration ».

    À composer dans un `select(...).where(...)` — c'est volontairement une
    condition et non une requête toute faite : les appelants n'ont pas tous
    besoin des mêmes colonnes (une liste, un décompte, une version enrichie).
    """
    return and_(
        Utilisateur.actif == False,  # noqa: E712  (colonne SQL, pas un booléen Python)
        Utilisateur.decision_compte_le.is_(None),
    )


def comptes_en_attente(session: Session) -> list[Utilisateur]:
    """Les comptes qui attendent une décision, du plus ancien au plus récent."""
    return list(
        session.exec(
            select(Utilisateur)
            .where(condition_compte_en_attente())
            .order_by(Utilisateur.cree_le)
        ).all()
    )


def nb_comptes_en_attente(session: Session) -> int:
    """Combien de comptes attendent une décision."""
    return session.exec(
        select(func.count(Utilisateur.id)).where(condition_compte_en_attente())
    ).one() or 0


def marquer_decide(user: Utilisateur, maintenant: datetime | None = None) -> None:
    """Acter qu'une décision vient d'être prise sur ce compte.

    À appeler pour les trois issues — validation, refus, désactivation — et pas
    seulement pour celles qui changent `actif`. Le refus n'en changeait aucun :
    c'est pour cela qu'un compte refusé revenait indéfiniment dans la file.

    Idempotent par construction : la date de la **première** décision est celle
    qui compte, la repousser n'apprendrait rien et effacerait un historique.
    """
    if user.decision_compte_le is None:
        user.decision_compte_le = maintenant or datetime.utcnow()
