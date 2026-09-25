"""Ce que l'application fait **toute seule** — la liste, et son contrôle.

## Pourquoi cette table (#1047, audit du 19/09/2026)

Sept tâches tournent en permanence dans le process de l'API, enregistrées à
**trois** endroits (`main.py`, `utils/backup.py`, et des tâches de rattrapage
dans `utils/rattrapage.py`). **Aucun test ne citait un seul identifiant** :
`test_taches_planifiees.py`, `test_sante_taches_forme.py` et `test_taches_sante.py`
vérifiaient des formes, jamais la liste.

Conséquence, et c'est la règle de `standards/07` §5 : **une tâche planifiée qui
disparaît ne prévient personne.** Un `add_job` supprimé par mégarde — dans un
refactor, une fusion, un `if` mal placé — laisse l'application démarrer
normalement. La sauvegarde ne se fait plus, la relève des courriels s'arrête, et
on l'apprend le jour où l'on en a besoin.

C'est déjà arrivé au voisinage : la skill `infra-rpi` en listait **quatre sur
six**, parce que personne ne pouvait comparer sa table à la réalité.

## Ce que cette table sert — deux fois, et c'est le point

1. **Au démarrage** (`main.py`), les identifiants réellement enregistrés lui sont
   comparés, et tout écart part en `WARNING` : c'est le seul contrôle qui parle
   de ce qui tourne **vraiment**, dans le process, avec sa configuration.
2. **En CI** (`test_taches_planifiees_declarees.py`), chaque identifiant déclaré
   doit correspondre à un `add_job` du code, et réciproquement — ce qui attrape
   la disparition **avant** le déploiement.

Un seul des deux ne suffirait pas : le test statique ne voit pas un `add_job`
qu'une condition saute à l'exécution, et le contrôle au démarrage ne se lit que
si quelqu'un regarde les journaux.

⚠️ Les tâches de **rattrapage** (`utils/rattrapage.py`) n'y figurent pas : elles
sont de type `date`, créées à la volée pour rejouer un passage manqué, et leur
nombre dépend de l'état du système. Les exiger ici rendrait le contrôle rouge sur
une installation saine.
"""

#: Les tâches permanentes, par identifiant — et ce que leur disparition coûte.
#:
#: Le second membre n'est pas une description : c'est **ce qu'on perd** si elle
#: cesse de tourner. C'est ce qui permet de trancher, en cas d'écart, s'il faut
#: intervenir tout de suite ou au prochain lot.
TACHES_PERMANENTES: dict[str, str] = {
    "backup": "la sauvegarde quotidienne de la base — sans elle, plus aucune copie "
    "n'est produite, et on l'apprend le jour d'une restauration",
    "health_check": "le contrôle de santé de 06:00, seul job qui envoie une alerte "
    "de lui-même (WhatsApp déconnecté, sauvegarde > 25 h, disque < 15 %)",
    "whatsapp_scheduled": "la fenêtre d'envoi WhatsApp de 18 h à 21 h 45 — les "
    "messages programmés ne partent plus",
    "telemetry_aggregation": "l'agrégation de la télémétrie à 02:00 ; sans elle, "
    "la table brute gonfle et les écrans de mesure se vident",
    "manuel_pdf_prechauffage": "le rendu du manuel 20 s après le démarrage — sans "
    "lui, le premier lecteur d'après un manuel modifié attend 21 s",
    "manuel_pdf_quotidien": "le même rendu à 00:05, parce que la clé du cache porte "
    "la date : sans lui, le premier lecteur du jour repaie l'attente",
    "courriel_reponses": "la relève IMAP toutes les 10 minutes — les réponses du "
    "syndic par courriel n'entrent plus dans les tickets",
}


def verifier_taches_enregistrees(scheduler, logger) -> list[str]:
    """Comparer ce qui tourne à ce qui est déclaré, et journaliser l'écart.

    Rend la liste des identifiants **manquants** (vide si tout va bien). Ne lève
    jamais : un écart de tâches ne doit pas empêcher l'application de démarrer —
    ce serait échanger une panne silencieuse contre une panne totale.

    ⚠️ En `WARNING`, comme le journal de sécurité et pour la même raison : le
    point 6 du pré-check et `check-reliability.sh` comptent les `ERROR`, et un
    `ERROR` ici ferait sonner le canal d'alerte à chaque démarrage d'une
    installation qui n'a pas encore sa configuration.
    """
    enregistrees = {job.id for job in scheduler.get_jobs()}
    manquantes = sorted(set(TACHES_PERMANENTES) - enregistrees)
    for identifiant in manquantes:
        logger.warning(
            "tache planifiee ABSENTE : %s — %s",
            identifiant,
            TACHES_PERMANENTES[identifiant],
        )
    #  L'inverse compte aussi : une tâche qui tourne sans être déclarée n'a pas
    #  de coût écrit, donc personne ne saura quoi faire le jour où elle tombe.
    for identifiant in sorted(enregistrees - set(TACHES_PERMANENTES)):
        #  Les rattrapages sont attendus et non déclarés (voir l'en-tête).
        if identifiant.startswith("rattrapage"):
            continue
        logger.warning("tache planifiee NON DECLAREE : %s", identifiant)
    return manquantes
