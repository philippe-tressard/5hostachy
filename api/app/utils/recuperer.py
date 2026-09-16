"""**Récupérer une entité, ou dire qu'elle n'existe pas.**

## 🔴 Pourquoi ce module (15/09/2026)

Un relevé mécanique a compté **90 occurrences** de ces trois lignes, dans
**37 fichiers** :

    objet = session.get(Modele, objet_id)
    if not objet:
        raise HTTPException(404, "Chose introuvable")

C'est la duplication la plus répandue du dépôt. Aucune de ces écritures n'est
fausse ; c'est leur nombre qui pose problème — le jour où l'on veut y ajouter
quelque chose (une trace, une distinction entre « supprimé » et « jamais
existé », un identifiant dans le message), il faut le faire quatre-vingt-dix
fois, et on en manquera.

⚠️ Et elles avaient déjà commencé à diverger sur le LIBELLÉ : neuf
« Utilisateur introuvable », mais aussi « Compte introuvable » ailleurs pour la
même table. Le suffixe est désormais composé ici, donc identique partout.

## Ce que cette fonction NE fait pas

**Elle ne décide d'aucun droit.** Rendre 404 sur un objet qu'on n'a pas le droit
de voir est une décision d'autorisation — elle vit dans `auth/deps` et dans les
fonctions de visibilité, jamais ici. Cette fonction répond à « existe-t-il ? »,
pas à « puis-je le voir ? ».

⚠️ Les deux questions se ressemblent et se confondent vite : un contrôle qui
rendrait 404 « pour ne pas révéler l'existence » relève de la sécurité, et doit
être écrit là où les autres règles d'accès le sont — sinon il y a deux endroits
où lire les droits (`standards/03` §1).
"""
from __future__ import annotations

from typing import Optional, Type, TypeVar

from fastapi import HTTPException
from sqlmodel import Session, select

T = TypeVar("T")


def ou_404(session: Session, modele: Type[T], identifiant, libelle: str) -> T:
    """L'objet, ou un **404** qui le nomme.

    :param libelle: le nom de l'entité *au singulier*, sans le mot
        « introuvable » — il est composé ici. C'est ce qui garantit que les
        quatre-vingt-dix messages du produit disent la même chose de la même
        façon.

    ⚠️ `identifiant` peut valoir `None` — un chemin d'API le donne parfois ainsi.
    `session.get(Modele, None)` rend `None` sans lever : le 404 est alors la
    bonne réponse, et c'est ce qui se passe.
    """
    objet: Optional[T] = session.get(modele, identifiant)
    if not objet:
        raise HTTPException(404, f"{libelle} introuvable")
    return objet

#: La FENÊTRE d'un historique d'exploitation : on ne lit que les derniers
#: rapports. Au-delà, ils n'apprennent plus rien — la santé d'une tâche se lit
#: sur ses dernières exécutions, pas sur un an d'archives.
DERNIERS_RAPPORTS = 10


def derniers_rapports(session: Session, modele: Type[T], combien: int = DERNIERS_RAPPORTS):
    """Les N derniers rapports d'un historique, du plus récent au plus ancien.

    🔴 Écrit **trois fois** avant le 16/09/2026 — courriels, télémétrie,
    sauvegardes —, avec le `10` recopié à chaque fois. Trois écrans lisent la
    même fenêtre ; le jour où l'un l'élargit, les deux autres restent en
    arrière sans que rien ne le dise, et l'administrateur compare des
    profondeurs différentes en croyant comparer des tables.

    ⚠️ Comme `ou_404`, cette fonction **ne décide d'aucun droit** : les trois
    routes qui l'emploient portent `require_admin`, et c'est là que la
    décision se prend.
    """
    return session.exec(
        select(modele).order_by(modele.cree_le.desc()).limit(combien)
    ).all()
