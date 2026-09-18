"""Qui a lancé une tâche planifiée — un vocabulaire, et un geste.

## 🔴 Ce que le relevé a trouvé (18/09/2026)

Les quatre tâches planifiées — sauvegarde, maintenance, agrégation de la
télémétrie, contrôle de santé — écrivent toutes dans un champ `declenchee_par`
que l'écran **affiche tel quel**, colonne « Déclenchée par » de
`TachesPlanifiees`. Trois vocabulaires y coexistaient pour deux idées :

| Ce qui écrivait | Valeur posée | Ce que l'utilisateur lisait |
|---|---|---|
| l'écran d'administration (×3) | `manuelle` | « manuelle » |
| le repli de la sauvegarde | `automatique` | « automatique » |
| le planificateur de la télémétrie | `cron` | « cron » |
| les rapports des scripts d'infra | `cron` (défaut du corps) | « cron » |

⚠️ **Et une valeur était FAUSSE.** Le repli de `run_maintenance` — le chemin
emprunté quand la tâche est lancée sans entrée préexistante, c'est-à-dire par le
planificateur — posait `manuelle`, et **sans nœud**. Une maintenance automatique
s'affichait donc comme déclenchée à la main, sur un nœud inconnu : exactement le
défaut que le commentaire de l'endpoint disait avoir corrigé en v2.32.0, resté
entier dans l'autre chemin.

## Ce que ce module pose

Deux valeurs, et elles suffisent : une tâche est lancée **par quelqu'un** ou
**par le planificateur**. « cron » disait la même chose qu'« automatique » avec
le mot de l'implémentation plutôt que celui du lecteur.

`normaliser()` accepte les anciens mots — un script d'infra déployé continue
d'envoyer `cron` — et les traduit à l'écriture. La compatibilité se paie à la
frontière, pas dans la colonne que l'utilisateur lit.

`tracer_lancement_manuel()` écrit l'entrée d'historique **avant** de planifier la
tâche : c'est cette entrée qui porte le nœud, parce qu'une tâche déclenchée
depuis l'interface s'exécute dans CE processus, donc sur ce nœud-ci.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from sqlmodel import Session

from app.utils.noeud import noeud_courant

#: Lancée par une personne, depuis l'écran d'administration.
MANUELLE = "manuelle"
#: Lancée par le planificateur — cron, APScheduler, script d'infra.
AUTOMATIQUE = "automatique"

#: Les mots d'hier, et ce qu'ils voulaient dire. Écrire « cron » n'était pas une
#: erreur : c'était le mot de celui qui posait la ligne, pas de celui qui la lit.
_ANCIENS = {
    "cron": AUTOMATIQUE,
    "auto": AUTOMATIQUE,
    "automatic": AUTOMATIQUE,
    "planifiee": AUTOMATIQUE,
    "planifiée": AUTOMATIQUE,
    "manuel": MANUELLE,
    "manual": MANUELLE,
}


def normaliser(valeur: Optional[str]) -> str:
    """Un mot quelconque → l'un des deux du vocabulaire.

    ⚠️ L'inconnu devient AUTOMATIQUE et non `manuelle` : une tâche dont on ignore
    l'origine n'a pas été déclenchée par quelqu'un qu'on pourrait nommer.
    """
    if not valeur:
        return AUTOMATIQUE
    mot = valeur.strip().lower()
    if mot in (MANUELLE, AUTOMATIQUE):
        return mot
    return _ANCIENS.get(mot, AUTOMATIQUE)


def tracer_lancement_manuel(
    session: Session,
    background_tasks,
    *,
    modele: type,
    tache: Callable[[int], Any],
    libelle: str,
    par=None,
) -> dict:
    """Trace un lancement manuel, planifie la tâche, rend le message et l'id.

    🔴 Ces six lignes étaient écrites TROIS fois — sauvegarde, maintenance,
    télémétrie — et la répétition avait déjà coûté : l'une d'elles a été ajoutée
    en doublon d'une autre sur le même chemin, si bien qu'un gestionnaire entier
    n'a jamais répondu (retiré en v1.44.10).

    L'ordre compte et c'est tout l'objet de la fonction : l'entrée d'historique
    est créée, committée et rafraîchie AVANT que la tâche ne soit planifiée,
    parce que la tâche reçoit son identifiant et écrira dedans.

    :param modele: la table d'historique de cette tâche.
    :param tache: la fonction de fond, qui prend l'identifiant de l'entrée.
    :param libelle: ce que l'utilisateur lit — « Sauvegarde », « Maintenance ».
    :param par: l'utilisateur, quand le modèle sait le retenir. Seule la
        sauvegarde porte cette colonne : elle produit une archive, et savoir qui
        l'a demandée fait partie de la trace.
    """
    champs: dict[str, Any] = {"declenchee_par": MANUELLE, "noeud": noeud_courant()}
    if par is not None and "declenchee_par_user_id" in getattr(modele, "model_fields", {}):
        champs["declenchee_par_user_id"] = par.id

    entree = modele(**champs)
    session.add(entree)
    session.commit()
    session.refresh(entree)
    background_tasks.add_task(tache, entree.id)
    return {"message": f"{libelle} lancée en arrière-plan", "id": entree.id}
