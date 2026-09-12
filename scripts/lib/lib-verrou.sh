#!/usr/bin/env bash
#  Le VERROU de bascule — `.bascule-lock`, posé et relâché sur les deux nœuds.
#
#  Extrait de `bascule.sh` le 12/09/2026 : le geste y était écrit CINQ fois, et le
#  plafond de modularité a refusé la correction qui le rendait symétrique. La
#  coupe suit la nature de l'objet — un verrou partagé entre deux machines, que
#  tout script d'exploitation touchant au rôle doit savoir poser.
#
#  ## Ce que le verrou protège
#
#  `auto-deploy.sh` tourne toutes les cinq minutes sur les DEUX nœuds et décide
#  d'après `.active`. Pendant une bascule, ce fichier est en train de changer :
#  `action_auto_deploy` rend « attendre » dès qu'elle voit le verrou, **quel que
#  soit le rôle lu**. C'est la seule coordination entre les deux crons.
#
#  L'appelant fournit `$REPO`, `$PEER_IP`, `$SSH_CMD`, `run` et `log`.

#  ── Le verrou de bascule, posé et relâché des DEUX côtés ────────────────────
#
#  🔴 Il ne l'était que sur le PEER jusqu'au 12/09/2026 — split-brain en
#  production (#915, et `project_split_brain_verrou_bascule`). Le nœud exposé est
#  celui qui BASCULE : son rôle change, donc son propre `auto-deploy` peut lire un
#  `.active` périmé et démarrer les conteneurs.
#
#  En fonctions parce que le geste apparaissait CINQ fois, et que ses deux moitiés
#  doivent rester accordées sur chacun des cinq chemins, rollback compris —
#  `test_verrou_bascule.py` en vérifie la symétrie.
#  ⚠️ Sans `run` ni `set -e` : appelée depuis les chemins d'ABANDON, où elle doit
#  aboutir même si le peer est injoignable. Un verrou local jamais relâché
#  laisserait ce nœud sans aucun déploiement, en silence.
verrou_liberer() {
  $SSH_CMD ptressard@"$PEER_IP" "rm -f /opt/5hostachy/.bascule-lock" 2>/dev/null || true
  rm -f "$REPO/.bascule-lock" 2>/dev/null || true
}

#  🔴 Le `trap` est armé PAR la pose, et c'est la règle la plus déployée :
#  `health-watch.sh` et `MaJ-Hostachy.sh` le font tous deux depuis toujours
#  (`touch` puis `trap 'rm -f …' EXIT`). `bascule.sh` était le seul à libérer son
#  verrou à la main, sur cinq chemins — et c'est exactement ce qui permet d'en
#  oublier un. Une sortie imprévue (`set -e`, `kill`) le relâche désormais aussi.
#
#  ⚠️ Le `trap` remplace les libérations dispersées, il ne s'y ajoute pas :
#  `verrou_liberer` reste appelable pour dire « la bascule est finie » au journal,
#  et elle est idempotente (`rm -f`).
verrou_poser() {
  run "$SSH_CMD ptressard@$PEER_IP 'touch /opt/5hostachy/.bascule-lock'"
  run "touch $REPO/.bascule-lock"
  trap verrou_liberer EXIT
  log "  → Lock bascule posé sur les DEUX nœuds (libération garantie à la sortie)."
}
