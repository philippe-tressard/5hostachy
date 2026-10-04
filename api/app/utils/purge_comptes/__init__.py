"""La purge des comptes inactifs (#1580) — la durée de conservation, appliquée.

## Pourquoi

La politique de confidentialité annonçait « données de compte actif : durée de
la relation + 2 ans », et aucun code ne l'appliquait : une durée écrite sans
purge automatisée est une durée **fictive** (`standards/14` §1). Arbitrage de
Philippe, 04/10/2026 : un compte **sans connexion depuis 2 ans** reçoit un
**avertissement par courriel**, puis il est **supprimé 30 jours plus tard** s'il
ne s'est pas reconnecté entre-temps.

## Deux modules, et pourquoi

| Module | Ce qu'il porte |
|---|---|
| `regles` | les seuils et les questions (qui est inactif, qui est exclu, quel volume est anormal) — sans base, sans courriel, sans planificateur |
| `tache` | la tâche quotidienne : avertir, supprimer par `utils/suppression_compte`, journaliser |

`regles` est lu par le gabarit de la politique (`seed/contenus_legaux`), qui
compose la phrase à partir de ses constantes : la durée annoncée ne peut pas
diverger de celle qui est appliquée. C'est aussi pour cela que ce paquet
n'importe RIEN à son chargement — `tache` tire le moteur de courriel, qui tire
le seed : l'importer ici fermerait un cycle.
"""
