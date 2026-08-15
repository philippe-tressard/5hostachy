# Points d'entrée de l'exploitation — l'état attendu, versionné

Ce répertoire porte **ce que les deux Raspberry Pi doivent avoir installé** pour que
l'exploitation tourne : les tâches cron et l'unité systemd qui lancent les scripts.

## Pourquoi ils sont ici

Ils ne l'étaient pas. Rien, dans le dépôt, ne disait quels scripts sont réellement
lancés ni à quelle cadence — il fallait ouvrir un terminal sur chaque nœud pour le
savoir. Trois conséquences :

- **Renommer ou déplacer un script était une opération à l'aveugle** : les chemins
  sont absolus, un déplacement les fait pointer dans le vide sur les deux nœuds
  dans les cinq minutes suivant la fusion — et sans aucune alerte, puisque
  `check-reliability.sh` fait partie de ce qui ne démarre plus.
- **`C18` compare les deux nœuds ENTRE EUX**, pas au dépôt. Deux crontabs
  identiquement périmés lui paraissent parfaits.
- **L'unité systemd ne s'exécute qu'au démarrage** : un chemin cassé n'y produit
  rien pendant des semaines, puis se révèle à la première coupure de courant —
  exactement quand le garde-fou anti-split-brain devrait servir.

Capturés le **15/08/2026 à l'identique** de ce qui tournait, sans rien changer.
Cette première étape n'a pas modifié le comportement : elle l'a rendu **lisible**.

## Ce que ces fichiers sont, et ne sont pas

Ils décrivent l'**état attendu**. Ils ne sont **pas** posés automatiquement : rien
ici n'écrit sur un nœud. Les installer reste un geste explicite, fait un nœud à la
fois. Un fichier versionné qui s'installerait tout seul serait un déploiement
d'infrastructure déguisé.

## ⚠️ Phase de transition (depuis le 15/08/2026)

Les scripts d'exploitation vivent désormais dans `scripts/exploitation/`, mais les
crontabs et l'unité systemd **désignent encore la racine**. Des relais d'une ligne
y pourvoient : `bascule.sh` à la racine fait un `exec` vers le vrai script.

Les fichiers de ce répertoire décrivent donc **les anciens chemins**, et c'est
volontaire : ils décrivent ce qui est *installé*, pas ce qui serait souhaitable.
Le contrôle doit rester **vert** pendant toute la transition.

Quand les points d'entrée seront basculés vers `scripts/exploitation/`, il faudra
mettre à jour **ensemble** : les crontabs des deux nœuds, l'unité systemd, les
fichiers de ce répertoire, et `docs/restauration-complete.md`. Les relais ne
partent qu'après, et seulement une fois la bascule de 02:00 constatée sur les deux
nœuds.

## Vérifier qu'un nœud est conforme

    bash scripts/poste/verifier-points-entree.sh ptressard@192.168.1.222

Le contrôle **normalise** avant de comparer (commentaires, lignes vides, espaces),
et **ignore les lignes qui ne concernent pas 5Hostachy** : rpi2 héberge aussi
List-dons, dont une tâche cron est parfaitement légitime. Sans ces deux règles, le
contrôle alerterait tous les jours — et une alerte quotidienne ignorée est un
contrôle mort.

## Deux limites, à connaître

- `sudo -n` est **refusé sur rpi2** (cf. #302) : la lecture du crontab root peut y
  être impossible. Le contrôle rend alors **INCONNU**, jamais OK.
- La conformité de l'unité systemd ne prouve pas qu'elle **fonctionne** : cela ne
  s'observe qu'au démarrage. Redémarrer le **standby** — qui ne sert rien — est le
  seul moyen de le vérifier sans risque.
