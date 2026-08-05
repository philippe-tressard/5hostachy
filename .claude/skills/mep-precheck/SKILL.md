---
name: mep-precheck
description: "Pré-check et post-check obligatoires de mise en production 5Hostachy : étape 0 (poste de dev), étape 0 bis (autorisation, factorisation, documentation), pré-check 15 points sur les 2 RPi, post-check P1-P10, rollback, surveillance continue. Use when: déployer, préparer une MEP, merger vers main, diagnostiquer un déploiement qui n'a pas eu lieu, vérifier qu'un correctif est réellement servi, auditer les contrôles automatiques."
argument-hint: "Décrire le lot à déployer ou le point à vérifier (ex. « pré-check avant MEP v2.31.3 », « post-check après merge »)"
---

# Git & MEP — pré-check, post-check et surveillance continue

Instanciation 5Hostachy de `standards/09-livraison-et-mep.md` et
`standards/04-fiabilite-des-controles.md`. **Charger cette skill avant toute MEP** :
les trois règles ci-dessous priment sur la liste des contrôles.

> 📖 **Le générique n'est pas recopié ici** — l'ouvrir en parallèle :
> `standards/09-livraison-et-mep.md` §2 (les trois exigences de même rang que la
> sécurité), §3 (grille de pré-check générique), §4 (post-check et les trois pièges
> de vérification), §6 (rollback), §7 (rétrospective) ·
> `standards/04-fiabilite-des-controles.md` — dont trois seulement sont reprises
> ci-dessous · `standards/08-git-et-versioning.md` §2–3 (étape 0) ·
> skill globale **`avant-commit`** pour les six contrôles de deux minutes.

## ⚠️ Se resynchroniser AVANT de committer (obligatoire)

`origin/dev` et `origin/main` avancent **côté GitHub** : local `dev` → push → PR
vers `main` → merge sur GitHub → « Merge branch 'main' into dev », lui aussi sur
GitHub. Ces commits ne redescendent **jamais** tout seuls. Sans fetch explicite,
le clone local dérive d'exactement le nombre de PR fusionnées depuis le dernier
pull manuel — constaté le 26/07/2026 : `dev` à **16 commits** de retard, `main` à
**151**. Committer sur cette base expose aux conflits de version
(`front/package.json`) et à la divergence code ⇆ migrations Alembic (la panne que
le point 10 du pré-check existe pour attraper).

**Premier réflexe de toute session, avant le moindre commit :**
```bash
git fetch origin && git merge --ff-only origin/dev
```

Garde-fou mécanique : `.githooks/pre-commit` refuse un commit si la branche est
en retard sur son upstream. Il est versionné mais `core.hooksPath` doit être armé
**une fois par clone** :
```bash
git config core.hooksPath .githooks && git config pull.ff only
```
(`pull.ff only` évite qu'un `git pull` fabrique un merge commit parasite au lieu
d'un fast-forward.) Contournement d'urgence : `ALLOW_STALE=1 git commit …`.

- `main` = production protégé — toutes les modifications via PR vers `dev`
- Prefixes commits : `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `perf:`
- MEP : `MaJ-Hostachy.sh` sur le **RPi actif uniquement** — bloque automatiquement sur le standby
- `.env` non versionné · `SECRET_KEY` min 32 chars · `ENABLE_API_DOCS=false` en prod
- Bascule manuelle (test) : `sudo bash /opt/5hostachy/bascule.sh` depuis le RPi actif

## Trois règles qui priment sur la liste des contrôles

Issues de l'incident du 26/07/2026 (cf. « Rétrospective » en fin de section). Un
contrôle mal conçu est plus dangereux qu'un contrôle absent, parce qu'il produit
de la confiance.

1. **Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.**
   `sudo` en SSH non interactif échoue en demandant un mot de passe ; `… | grep -c`
   sur cette sortie vide affiche `0`, c'est-à-dire « aucun problème ». Le 26/07 j'ai
   annoncé « 0 inode fantôme » sur cette base : c'était un faux vert. Toute commande
   du pré-check doit soit fonctionner sans `sudo`, soit signaler explicitement son
   échec. **Ne jamais déduire un vert d'une sortie vide.**
2. **Ce qui est critique en continu ne doit pas être vérifié seulement en MEP.**
   Le pré-check est ponctuel ; les invariants de redondance sont permanents. Le
   26/07, `.active` était incohérent depuis 02:00 et personne ne l'a su avant un
   pré-check à 09:00 — entre-temps le site est resté HS ~50 min sans failover. Voir
   « À automatiser » ci-dessous.
3. **Vérifier le fait, pas le symptôme attendu.** Avant de déclarer une anomalie,
   confirmer qu'elle en est une (le 26/07 l'image API paraissait périmée : le commit
   ne touchait que `front/`). Et avant de déclarer un vert, confirmer que le
   contrôle mesure bien ce qu'on croit.

## Étape 0 — poste de développement (avant d'écrire une ligne)

| # | Vérification | Commande | Attendu |
|---|---|---|---|
| 0a | Clone à jour | `git fetch origin && git merge --ff-only origin/dev` | Fast-forward propre (cf. section ci-dessus) |
| 0b | Modes des fichiers exécutables versionnés | **Automatisé** : job CI `test-scripts` (étape « Bits d'exécution versionnés ») | `100755` sur tout ce qui doit s'exécuter, `100644` sur les modules sourcés `lib-*.sh` |

**0b — pourquoi :** `core.filemode=false` sur un clone Windows fait avaler `chmod +x`
en silence ; le fichier part en `100644` et Linux refuse alors de l'exécuter, sans
message. Constaté le 26/07 sur `.githooks/pre-commit` — garde-fou inerte, découvert
seulement sur demande de relecture. Même classe que le point 7, côté dépôt.
Remédiation : `git update-index --chmod=+x <fichier>`.

## Étape 0 bis — exigences sans exception (avant le pré-check)

Deux exigences de même rang que la sécurité, à contrôler **avant** de dérouler le
pré-check technique. Elles ne portent pas sur l'état des machines mais sur celui du
code et de la documentation livrée : un pré-check vert sur une base qui viole ces
règles reste un mauvais déploiement.

| # | Exigence | Vérification | Automatisé par |
|---|---|---|---|
| 0c | **Autorisation centralisée, aucun passe-droit** | Toute règle de sécurité dans `app/auth/deps.py` · tout endpoint porte une dépendance · exceptions publiques énumérées et justifiées · `has_role(RoleUtilisateur.…)` jamais `user.role` ni chaîne · exposition publique en **liste blanche** | `api/tests/test_autorisation.py` (5 tests, CI) |
| 0d | **Factorisation** | Aucun code spécifique ne réimplémente une bibliothèque partagée (dates, montants, alertes, thème PDF, destinataires) | `test_dates_fr.py` · `front/scripts/check-dates.mjs` — le reste par relecture |
| 0e | **Documentation à jour** | README (et ses badges) · manuel utilisateur · `specs/` reflètent l'état livré | `api/tests/test_documentation.py` pour la partie mécanique ; le fond reste à relire |

**0c — pourquoi cette exigence a besoin d'un test et non d'une consigne.** L'audit du
26/07/2026 a trouvé l'exigence globalement respectée — 276 endpoints, aucun contrôle
sur `user.role`, tout par `has_role()` — et pourtant **trois dérives installées sans
que rien ne les signale** :
1. `GET /config` filtrait par liste **noire** : 31 clés exposées sans authentification,
   dont toute la configuration SMTP, l'URL interne du bridge WhatsApp, l'identifiant
   du groupe privé et un **lien d'invitation fonctionnel** au groupe WhatsApp des
   résidents. Le motif était correct à cinq clés de configuration ; il est devenu une
   fuite à mesure qu'elles s'accumulaient, sans que personne ne rouvre le fichier.
2. `_require_bailleur` dans `routers/bailleur.py`, doublon exact de
   `require_proprietaire`, hors du module central — 17 endpoints dessus. Un
   durcissement de la règle centrale ne les aurait pas atteints. **Aggravant :
   `specs/architecture/api.md` le documentait comme une dépendance officielle** — la
   spec légitimait la dérive au lieu de la signaler.
3. Deux contrôles par chaîne littérale (`has_role("admin")`) au lieu de l'enum.

Le point commun : **aucune n'était visible sans rouvrir le fichier concerné**. Une
exigence, même « critique et prioritaire », ne se maintient pas par la consigne — la
consigne était là. Elle se maintient par un contrôle qui échoue.

**0e — pourquoi.** La synchronisation du manuel entre `docs/` et `front/static/`
n'était qu'une case à cocher : elle a tenu, mais une case ne résiste pas à une
session pressée, et les résidents auraient lu une version périmée. Les badges du
README avaient connu la dérive inverse, réelle : Python annoncé « 3.10+ » pour une
image en 3.12. Ce qui est mécanique est désormais testé (synchronisation des manuels,
badges Python/Node/CI alignés sur `Dockerfile` et `ci.yml`) ; le fond — le manuel
décrit-il encore l'application, les specs l'état livré — reste une relecture, à faire
ici et pas après.

## Pré-check obligatoire avant MEP

Avant toute MEP, Claude vérifie les points suivants. Si une anomalie est détectée → diagnostic + plan proposé → correction si validée par l'utilisateur → reprise de la MEP.

| # | Vérification | Commande | Attendu |
|---|---|---|---|
| 1 | Site public | `curl https://5hostachy.fr/api/health` | HTTP 200 |
| 2 | **Rôle actif cohérent sur les 2 nœuds ET conforme au réel** | `cat /opt/5hostachy/.active` sur les 2 + qui porte les conteneurs | **Même valeur** sur les 2 **et** égale au nœud qui fait tourner les conteneurs |
| 3 | Pas de split-brain | `docker ps -q --filter name=hostachy \| wc -l` sur les 2 RPi | 0 sur le standby (exclut l'appli co-hébergée List-dons) |
| 4 | DB saine | ⚠️ **PAS de `docker exec`, PAS de `sudo` !** Voir « Point 4 » ci-dessous | `app.db-wal` et `app.db-shm` **présents sur le disque** · 0 `disk I/O error` |
| 5 | WhatsApp | Logs du bridge, voir « Point 5 » (pas de token requis) | Dernier `WhatsApp connected ✓` **postérieur** au dernier `Connection closed` |
| 6 | Erreurs API | `docker logs --since 1h` | Aucune ERROR/CRITICAL |
| 7 | Droits scripts cron | `ls -la /opt/5hostachy/*.sh` sur les 2 RPi | Bit `x` (`-rwxr*`) sur tous les `.sh` **lancés par cron** — les modules *sourcés* (`lib-alert.sh`) restent en 644, un `x` y serait trompeur |
| 8 | Logs cron : ni erreur, ni **battement manquant** | `tail` + comptage des lignes attendues, voir « Point 8 » | Aucune erreur **et** les lignes périodiques attendues sont présentes |
| 9 | Emails sans échec récent | ⚠️ **PAS de `docker exec` !** Admin → Emails → Historique (filtre `erreur`, 7 j) — repli : voir « Point 9 » | 0 ligne |
| 10 | Parité de code RPi actif ⇆ standby | `git -C /opt/5hostachy rev-parse HEAD` sur les 2 RPi | HEAD **identique** sur les 2 |
| 11 | Auto-deploy de l'actif vivant | Sur l'**actif** : `stat -c %U /var/log/hostachy-deploy.log` + HEAD actif vs `origin/main` | Log **`ptressard`** (pas `root`) · HEAD actif **==** `origin/main` |
| 12 | Image en cours = code déployé, **pour les services concernés** | `git diff --name-only <image>..HEAD` pour savoir quels services sont touchés, puis `docker inspect <svc>` — voir « Point 12 » | Image du service **touché** reconstruite après le commit ; un service non touché n'est pas une anomalie |
| 13 | Le canal d'alerte fonctionne | Dernière alerte reçue / `grep 'Email KO' /var/log/hostachy-health-watch.log` | Aucun `Email KO` récent — sinon les contrôles automatiques sont muets |
| 14 | **Hygiène disque sur les 2 RPi** | `docker system df` + `ls -la /var/log/hostachy-*.log` sur les **2** nœuds | Cache de build **< 20 Go** · aucun log **> 5 Mo** · dernière maintenance < 8 j **sur chaque nœud** (voir « Point 14 ») |
| 15 | **Aucun endpoint orphelin introduit par le lot** | `cd api && pytest tests/test_endpoints_orphelins.py -q` (poste de dev, avant le push) | 3 tests verts — voir « Point 15 » |

**Point 2 — pourquoi (26/07/2026) :** « fichier présent, cohérent » était trop vague
et ne disait pas *cohérent avec quoi*.

Déroulé réel, après **coupure d'électricité** (confirmé : rpi2 a redémarré à 07:37,
`uptime` 2 h ; rpi1 n'a **pas** redémarré, `uptime` 4 jours — probablement onduleur
côté rpi1, mais perte de la connectivité externe, d'où `github` injoignable et
`Email KO`) :
1. 02:00 — bascule rpi2 → rpi1 réussie ; les 2 flags disent `rpi1`.
2. Coupure ; rpi1 cesse de servir (dernier checkpoint de sa base à 04:53).
3. 06:53 — rpi2, encore debout, voit le site HS, tente un failover, **échoue**
   (réseau) mais a déjà écrit `.active=rpi2`. Les 2 nœuds se croient actifs.
4. 06:57→07:42 — `health-watch.sh` ne bascule que s'il se croit **standby** (« je
   suis l'actif → pas d'intervention, le standby me surveille »). Les deux
   s'abstiennent : site HS ~50 min **sans aucun failover**.
5. 07:37 — rpi2 redémarre ; 07:38:49 `boot-role-guard.sh` reprend la main et le site
   revient vers 07:45. Mais le flag de rpi1 reste faux jusqu'à correction manuelle
   (09:28).

> **🐛 Cause racine — `boot-role-guard.sh` ne corrige pas le flag du peer.**
> Son log du 26/07 est explicite : `Peer rpi1 joignable — conteneurs=0
> cloudflared=inactive .active=rpi1` → `Décision : active` → `.active → rpi2`.
> Il **constate** que le peer, *joignable*, se croit encore actif, décide
> correctement d'assumer le rôle… et laisse le flag du peer inchangé. C'est ce
> qui fabrique l'incohérence, et donc la neutralisation du failover.
> **À corriger** : quand `boot-role-guard` prend le rôle actif et que le peer est
> joignable, il doit aussi écrire `.active` chez le peer (ou alerter s'il n'y
> parvient pas). Idem pour le failover de `health-watch.sh`, qui a laissé la même
> incohérence à 06:53. Tant que ce n'est pas fait, **toute coupure ou reboot d'un
> nœud peut laisser les deux flags en désaccord** — donc vérifier le point 2 après
> chaque événement électrique ou redémarrage.
En parallèle, `auto-deploy.sh` sur rpi1 franchissait son garde-fou anti-split-brain
à chaque tick de 5 min (`ACTIVE == SELF`) et n'échouait qu'ensuite, au `git fetch`,
faute de réseau — un merge sur `main` avec le WAN rétabli aurait donc démarré les
conteneurs sur les deux nœuds, soit **deux bases divergentes**. Le contrôle doit
comparer les deux fichiers entre eux **et** au réel (qui porte les conteneurs).

**Point 13 — pourquoi (26/07/2026) :** pendant cette même panne,
`health-watch.sh` a loggué `Email KO: [Errno 101] Network is unreachable`. L'alerting
est **mono-canal (SMTP)** et tombe précisément quand le réseau tombe, c'est-à-dire
quand on en a besoin. Tant qu'il n'y a pas de second canal, vérifier au moins que le
premier n'est pas muet.

**Coupure de courant — réflexe.** Les deux RPi partagent le même local, donc la même
alimentation : la redondance ne protège **pas** contre une coupure électrique, elle
protège contre la panne d'un nœud. Après tout événement électrique, contrôler dans
l'ordre : point 2 (les 2 flags), point 3 (split-brain), `uptime` sur les 2 pour
savoir qui a redémarré, puis point 4 (la base a-t-elle été fermée proprement —
`app.db-wal` présent, `quick_check` via `GET /admin/db/integrite`).

> ### 🚨 Points 4 et 9 — ce pré-check contenait lui-même l'opération interdite
> Jusqu'au 17/07/2026, le point 4 disait `PRAGMA integrity_check` et le point 9 fournissait une
> commande `docker exec -w /app hostachy_api python3 -c "from app.database import engine …"`.
> **Exécuter ces commandes pendant que l'API tourne casse la base** (unlink du WAL sous le pool
> → `disk I/O error` → pertes de données). C'est exactement ce qui s'est produit le 17/07.
> Le pré-check ne doit **jamais** ouvrir `app.db`. Cf. « Règle d'or anti-corruption DB ».

**Point 4 — méthode sans `sudo` (26/07/2026).** Les commandes ci-dessous utilisaient
`sudo`, qui échoue en SSH non interactif (« a terminal is required to read the
password ») ; le `grep -c` qui suit renvoie alors `0` et on croit le contrôle vert.
Passer par un conteneur jetable, qui lit le volume **sans `sudo` et sans ouvrir la
base** (`ls`/`stat` n'ouvrent pas un fichier SQLite) :
```bash
docker run --rm -v 5hostachy_app_data:/data:ro python:3.12-slim \
  ls -la /data/app.db /data/app.db-wal /data/app.db-shm
docker logs hostachy_api --since 1h 2>&1 | grep -c 'disk I/O error'   # 0
```
Le signal **décisif** est la **présence** de `app.db-wal` et `app.db-shm` sur le
disque : dans le scénario de corruption, ils sont *unlinkés* tout en restant ouverts
par uvicorn. Un `mtime` de `app.db` figé n'est **pas** à lui seul une alerte — sans
trafic il n'y a rien à checkpointer ; croiser avec le `mtime` du WAL (s'il ne bouge
pas non plus, il n'y a simplement pas d'écriture). Intégrité réelle : contrôlée
in-process par `backup.py` (03:00) et `health_monitor.py` (06:00), ou à la demande
via `GET /admin/db/integrite`.

**Point 5 — méthode sans token (26/07/2026) :** `GET /status` du bridge répond
`{"error":"Unauthorized"}` sans clé d'API — le pré-check ne doit pas exiger un
secret. Lire l'état dans les logs, qui sont horodatés en epoch ms :
```bash
docker logs hostachy_whatsapp --since 14h 2>&1 \
  | grep -oE '"time":[0-9]+[^}]*"msg":"[^"]+"' | tail -20
```
Vert si le dernier `WhatsApp connected ✓` est **postérieur** au dernier
`Connection closed`. Des fermetures suivies de « Reconnexion programmée » puis d'une
reconnexion sont le **fonctionnement normal** du backoff v2.20.x, pas une panne — ne
pas confondre avec la boucle morte du 24/07 (fermetures sans jamais de reconnexion).

**Point 4 — comment vérifier sans ouvrir la base** (sur le RPi actif) :
```bash
DB_DIR=$(docker volume inspect 5hostachy_app_data --format '{{.Mountpoint}}')
sudo stat -c '%n mtime=%y' $DB_DIR/app.db     # doit AVOIR BOUGÉ depuis le dernier checkpoint
                                              # (backup 03:00 / redémarrage) — figé = ALERTE
sudo lsof -p $(docker inspect hostachy_api --format '{{.State.Pid}}') | grep -c deleted   # 0
docker logs hostachy_api --since 1h 2>&1 | grep -c 'disk I/O error'                       # 0
```
L'intégrité elle-même est déjà contrôlée **in-process** et alerte par email en cas de problème :
`backup.py` (03:00, backup annulé si KO) et `health_monitor.py` (06:00). Vérification à la demande :
`GET /admin/db/integrite` (in-process, session admin). **Jamais `docker exec` ni `sqlite3` hôte.**

**Point 9 — comment vérifier sans ouvrir la base** : interface **Admin → Emails → Historique**,
filtrer `statut = erreur` sur 7 jours (l'endpoint `GET /admin/emails/historique` s'exécute
in-process). Si l'API est arrêtée et la base au repos (0 writer), `sqlite3` hôte redevient sûr :
```bash
sudo sqlite3 "$DB_DIR/app.db" "SELECT code, COUNT(*), MAX(cree_le) FROM historique_email \
  WHERE statut='erreur' AND cree_le >= datetime('now','-7 days') GROUP BY code;"
```

**Point 7 — pourquoi :** un script peut perdre son bit d'exécution sans prévenir (ex. `auto-deploy.sh` le 21/04 → `Permission denied` silencieux dans le cron pendant des semaines, empêchant le déploiement automatique de v2.18.11). Vérifier en particulier `auto-deploy.sh`, `bascule.sh`, `health-watch.sh`, `maintenance.sh`, `MaJ-Hostachy.sh`, `check-stack.sh`. Si un bit `x` manque : `chmod +x <script>` sur le(s) RPi concerné(s).

**Point 8 — pourquoi :** le point 7 ne couvre que **la cause** déjà rencontrée (perte du bit `x`). Le point 8 détecte **le symptôme** quelle qu'en soit la cause (droits, chemin déplacé, faute de syntaxe, dépendance manquante…) en inspectant directement les logs produits par les crons — c'est ce qui aurait permis de détecter le problème `auto-deploy.sh` dès sa première occurrence le 21/04, au lieu d'attendre 7 semaines. Si une erreur récurrente apparaît → diagnostiquer la cause (pas seulement les droits) avant de poursuivre la MEP. ⚠ **Angle mort** : ce point ne détecte **rien** si le log est figé/absent/non-inscriptible (aucune ligne à lire = faux « OK ») — précisément le cas du bug auto-deploy du 15/07 (cf. **point 11**). Un `tail` vide ou un log root-owned n'est PAS un feu vert.
⚠ **Second angle mort, découvert le 26/07/2026 — le battement manquant.** La liste de
motifs (`Permission denied`…) ne couvre que des erreurs *attendues*. Ce jour-là,
`auto-deploy.sh` sur rpi1 écrivait une ligne « n'est pas l'actif — ignoré » toutes les
5 min jusqu'à 01:58, puis **plus rien de daté pendant 7 h 30** : il franchissait
désormais le garde-fou et mourait au `git fetch`, ne laissant que des blocs d'erreur
git **non horodatés** (`ssh: connect to host github.com port 22: Network is
unreachable`) — invisibles à un `grep` de motifs et à un tri par date. Donc vérifier
aussi la **présence** des lignes périodiques attendues, pas seulement l'absence
d'erreurs :
```bash
# rpi standby : ~12 lignes/heure attendues ; un trou = le script ne va plus au bout
grep -c "$(date '+%Y-%m-%d %H')" /var/log/hostachy-deploy.log
grep -E '^\[[0-9]{4}-' /var/log/hostachy-deploy.log | tail -5   # dernières décisions datées
```
Et élargir les motifs d'erreur au réseau et à git : `Network is unreachable`,
`Could not read from remote repository`, `fatal:`, `Connection timed out`.

⚠ **Troisième angle mort — tous les logs ne battent pas (05/08/2026).**
`hostachy-health-watch.log` était figé depuis **44 h** sur les deux nœuds, ce qui
ressemble exactement au battement manquant du point précédent — sauf que
`health-watch.sh` sort en `exit 0` **sans écrire** quand le site répond 200
(ligne « Site OK »). Son silence est le fonctionnement nominal : il n'écrit que
sur panne. Crier au loup ici ferait perdre du temps avant chaque MEP, et pire,
apprendrait à ignorer ce log.

Avant de conclure au battement manquant, **savoir si le script écrit à chaque
passage** :

| Log | Bat à chaque passage ? | Silence = |
|---|---|---|
| `hostachy-deploy.log` (standby) | oui, ~12 lignes/h | anomalie |
| `hostachy-reliability.log` | oui, toutes les 15 min | anomalie |
| `hostachy-check.log` (actif) | oui, toutes les 10 min | anomalie |
| `hostachy-health-watch.log` | **non — seulement si le site est HS** | normal |
| `hostachy-bascule.log` | non — une fois par nuit à 02:00 | normal |
| `hostachy-maintenance.log` | non — le dimanche à 03:00 | normal |
| `hostachy-role-guard.log` | non — au démarrage du nœud | normal |

⚠ **Et ne pas écrire `$(grep -c … || echo 0)`** — le piège documenté en
« Surveillance continue » §4 se retend à chaque pré-check improvisé : `grep -c`
affiche déjà `0` **et** sort en code 1, donc le `||` ajoute une seconde valeur et
le test qui suit devient inexploitable. Reproduit le 05/08/2026 dans un contrôle
écrit à la volée, avec la documentation du piège sous les yeux : sept fichiers
sont apparus « illisibles » alors qu'ils étaient simplement sans erreur.

**Point 9 — pourquoi :** les emails partent en `BackgroundTask` et échouent **silencieusement** — l'erreur n'apparaît que dans la table `historique_email`, jamais dans les logs API ni à l'écran. La même cause racine (un template Jinja2 référence une variable absente du contexte du point d'appel → `UndefinedError`) s'est produite deux fois en 12 jours : `reinitialisation_mdp` le 03/06 (`destinataire.prenom` manquant) puis `ticket_statut_change` le 15/06 (même variable). Dans les deux cas, découvert seulement après un signalement utilisateur « je ne reçois pas mes mails ». Comme le point 8, ce point lit **le symptôme** quelle qu'en soit la cause (contexte template, SMTP HS, adresse invalide, domaine `.local` filtré…). Si une ligne `erreur` apparaît → ouvrir le template et le contexte du point d'appel (`send_email(code=...)`), vérifier que toute variable `{{ x.y }}` du template est fournie ; aligner sur un template voisin qui fonctionne (ex. `verification_email`).
**Repli quand l'UI n'est pas accessible (26/07/2026)** — si le **standby** n'a aucun
conteneur, sa base est au repos : `sqlite3`/Python y sont sûrs (règle d'or). On lit
l'historique sur une **copie**, sans jamais ouvrir l'original, ce qui donne l'état
jusqu'à la dernière bascule (angle mort : les écritures postérieures sur l'actif) :
```bash
ssh <standby> "cat > /tmp/m.py" <<'PY'
import sqlite3, shutil
shutil.copy("/data/app.db", "/tmp/m.db")
c = sqlite3.connect("/tmp/m.db")
print(c.execute("SELECT code, COUNT(*), MAX(cree_le) FROM historique_email "
                "WHERE statut='erreur' GROUP BY code").fetchall())
PY
ssh <standby> "docker run --rm -v 5hostachy_app_data:/data:ro -v /tmp/m.py:/m.py:ro \
  python:3.12-slim python /m.py; rm -f /tmp/m.py"
```
Référence au 26/07 : 7 erreurs sur tout l'historique, toutes antérieures au 15/06 et
correspondant aux deux incidents déjà corrigés. Toute nouvelle ligne est donc un
signal fort.

**Point 10 — pourquoi :** `auto-deploy.sh` ne tourne que sur le RPi **actif** (il fait `docker compose up -d` → l'exécuter sur le standby créerait un split-brain). Le code du standby ne suit donc jamais `main` : il dérive derrière la DB. Le 16/06/2026, l'actif (rpi2) avait appliqué la migration `0111` ; la bascule nocturne a poussé cette DB vers rpi1 dont le code était resté à `0110` → `alembic upgrade head` au démarrage = `Can't locate revision identified by '0111'` → `start.sh` (`set -e`) → API en crash-loop → timeout phase 5 → bascule annulée. Correctif pérenne : `bascule.sh` phase 0 resynchronise le code du peer sur le commit de l'actif (`git reset --hard` + rebuild) **avant** toute opération destructive, et avorte proprement (prod intacte) si la resync échoue. Ce point 10 est le garde-fou amont : si les 2 HEAD diffèrent avant une MEP → resynchroniser le standby (`ssh <standby> 'cd /opt/5hostachy && git fetch origin main && git reset --hard origin/main && docker compose build'`, **sans** `up -d`).

**Point 11 — pourquoi :** `auto-deploy.sh` est le **seul cron utilisateur** (`ptressard`) ; tous les autres crons tournent en root. Or `/var/log` est `root:root` : si `hostachy-deploy.log` devient root-owned, la redirection `>> /var/log/hostachy-deploy.log` du cron user échoue en `Permission denied` et **cron n'exécute même pas le script** → l'actif cesse de se déployer **silencieusement**. Découvert le 15/07/2026 : rpi1 bloqué à v2.20.7 malgré 3 merges, chaque MEP exigeant un `bash auto-deploy.sh` manuel — invisible au point 8 (aucun log produit = angle mort). Cause structurelle : `maintenance.sh` (root, dimanche) faisait `mv .tmp log` → repassait le log root-owned **chaque semaine**, cassant le cron user de façon permanente après la 1ʳᵉ rotation. Corrigé (v2.20.10) : `chown 1000:1000` du log après rotation dans `maintenance.sh` (self-healing sur les 2 RPi) + contrôle automatisé **C13** dans `check-reliability.sh` (cron */15). Au pré-check : si le log est root-owned → `sudo chown ptressard:ptressard /var/log/hostachy-deploy.log` ; si HEAD actif ≠ `origin/main` alors que `dev` est mergé → auto-deploy ne tourne pas, diagnostiquer (ownership du log en premier) **avant** MEP.

**Point 12 — pourquoi :** le point 10 vérifie que le **git** du RPi est à jour, mais **la parité de HEAD ne garantit PAS que l'image Docker en cours a été construite depuis ce commit**. Le 18/07/2026, après la bascule nocturne rpi1 → rpi2, rpi2 était à jour côté git (`1211767`) mais son **image API datait du 16/07** (rebuild sauté par `bascule.sh` phase 0, qui ne rebuildait que si les HEAD différaient) → le conteneur servait l'ancien `flux.py` sans le filtre `_is_archived` (fix v2.20.16) → le bug de la publication épinglée résolue **réapparaissait** au tableau de bord. Diagnostic (lecture seule, **ne touche pas `app.db`**) : `docker inspect hostachy_api --format '{{.Created}}'` antérieur au dernier commit servi = image périmée ; confirmer avec `docker exec hostachy_api grep -c <marqueur> /app/...` vs le même `grep` sur `/opt/5hostachy/...` (disque). Remédiation (réversible, cycle standard, **pas** une violation de la règle d'or) : `cd /opt/5hostachy && docker compose build <svc> && docker compose up -d <svc>`. Correctif pérenne (v2.20.19) : `bascule.sh` phase 0 rebuild **toujours** l'image du peer, même à git égal (cache Docker → quasi instantané si rien n'a changé). Cf. [[project_bascule_image_stale]].
⚠ **Faux positif à écarter d'abord (26/07/2026) :** une image antérieure au commit HEAD
n'est une anomalie que si ce commit **touche ce service**. Ce jour-là l'image API
précédait le HEAD de 10 min, mais le commit ne modifiait que `front/` — rien
d'anormal. Établir le périmètre avant de conclure :
```bash
git diff --name-only <dernier-commit-couvert-par-l-image>..HEAD | cut -d/ -f1 | sort -u
# api/ touché -> vérifier hostachy_api ; front/ touché -> vérifier hostachy_front
```

**Protocole si anomalie :**
1. Diagnostiquer la cause
2. Proposer un plan de correction à l'utilisateur
3. Corriger après validation
4. Relancer le pré-check complet
5. MEP uniquement si tous les points sont verts

Un point **INCONNU** (contrôle impossible à exécuter) se traite comme une anomalie :
soit on trouve un moyen de le mesurer, soit on décide explicitement de passer outre
en le disant. Jamais de vert par défaut.

**Point 14 — pourquoi (31/07/2026) :** trois oublis d'hygiène, tous silencieux, tous
sur le **standby** que le pré-check n'inspectait pas :
- `maintenance.sh` ne tournait **que sur l'actif**, alors que rotation, `chown` et
  prune ne touchent ni l'appli ni la base. Un nœud n'étant actif qu'**un dimanche
  sur deux** (bascule alternée), le standby dérivait : 80 218 lignes dans
  `hostachy-check.log` sur rpi2. Corrigé — `hygiene_locale()` tourne sur les 2 nœuds.
- La rotation listait les logs **nominativement** : `hostachy-reliability.log`
  (1,7 Mo, ~2 100 lignes/jour) et `hostachy-role-guard.log` n'y figuraient pas et
  n'ont **jamais** été rotés. Corrigé — la boucle itère sur le glob
  `/var/log/hostachy-*.log`, donc sur tout log ajouté ensuite. **Un log hors de ce
  motif ne sera jamais roté** : le job CI `test-scripts` refuse désormais tout
  chemin `/var/log/…` qui n'y correspond pas (c'est ainsi qu'a été trouvé
  `5hostachy-backup.log` dans `setup-rpi5.sh`).
- Le **cache de build BuildKit** n'était purgé par rien (`docker image prune` ne le
  touche pas) : 64 Go sur rpi1 (disque à 66 %) et 59 Go sur rpi2, à raison d'un
  rebuild du peer par nuit depuis la v2.20.19. Purgé à 10 Go
  (`docker builder prune -f --max-used-space 10G`) → rpi1 71 → 22 Go, rpi2 66 → 21 Go,
  sans toucher images, volumes ni sauvegardes. Plafonné chaque dimanche, surveillé
  par **C16** (WARN ≥ 20 Go). Ne pas descendre sous 10 Go : la bascule compte sur ce
  cache pour ne pas rejouer `npm run build` (OOM). Cf. [[project_retention_logs_maintenance]].

**Point 15 — pourquoi (03/08/2026) :** en basculant les pièces jointes vers
`POST /uploads/fichier`, deux endpoints (`/uploads/ticket/{id}`,
`/uploads/evenement/{id}`) se sont retrouvés **sans le moindre appelant**, et
personne ne l'a vu — ni la CI, ni le pré-check, ni `svelte-check`, qui ne signale
que le code mort *à l'intérieur* d'un fichier, jamais une route serveur devenue
inutile. Un endpoint orphelin n'est pas un simple déchet : c'est une **surface
d'attaque authentifiée que plus aucun test ne parcourt**, et il fige un contrat
(ici : alimenter `photos_urls` après création) que le reste du code ne respecte
plus — donc il diverge en silence jusqu'au jour où quelqu'un s'y fie.

Le contrôle est **automatisé**, `api/tests/test_endpoints_orphelins.py` : il lit les
décorateurs `@router.<méthode>` par analyse statique (aucun import de l'app, donc
aucune base) et cherche un consommateur dans `front/src` **et** dans les `*.sh` —
`maintenance.sh` et `check-reliability.sh` sont des clients aussi légitimes qu'une
page Svelte, c'est ce qui distingue `/admin/db/integrite` d'une route morte.

Deux détails qui font la différence entre un garde-fou et un décor :
- la liste d'exceptions `SANS_CONSOMMATEUR_FRONT` est vérifiée **dans les deux sens** —
  une entrée qui a retrouvé un appelant fait échouer le test, sinon la liste
  grossit à chaque exception et finit par tout couvrir ;
- le détecteur s'auto-contrôle (`> 200 routes`, sources consommatrices non vides) :
  un parseur cassé rendrait tout « consommé », donc vert à vide.

Ce point se déroule **sur le poste de développement, avant le push** : il ne
nécessite aucun accès aux RPi. Une route orpheline n'est pas bloquante en soi —
c'est la **décision** qui l'est : supprimer l'endpoint *et* son client TypeScript,
ou l'inscrire dans la liste d'exceptions avec sa raison en une ligne.

⚠ **Daemon Docker partagé sur rpi2** (co-hébergement de List-dons) : le prune d'images
est **filtré sur `label=com.docker.compose.project=5hostachy`** — un prune nu
supprimerait aussi les couches orphelines de l'autre application, et arbitrer sur ses
ressources n'est pas notre rôle. `docker system prune` est **interdit** (il détruirait
ses volumes et réseaux). Les deux règles sont vérifiées en CI. Seul le **cache
BuildKit** reste commun — aucun filtre par projet n'existe : il est purgé **par âge**
(> 7 j) d'abord, le plafond de 10 Go ne servant que de garde-fou.

## Post-check obligatoire après MEP

La MEP se termine par ces contrôles, pas par le merge. Un merge déclenche
`auto-deploy.sh` dans les 5 min ; **il n'y a aucune notification de fin de
déploiement**, donc rien ne garantit spontanément que le code est réellement servi.
Attendre le tick, puis :

| # | Vérification | Commande | Attendu |
|---|---|---|---|
| P1 | Le déploiement a eu lieu **et est terminé** | `grep 'Déployé' /var/log/hostachy-deploy.log \| tail -2` sur l'actif | Ligne `Déployé: <hash>` avec le hash attendu |
| P2 | Site debout | `curl -s -o /dev/null -w '%{http_code}' https://5hostachy.fr/api/health` | 200 |
| P3 | Version servie = version bumpée | Voir « P3 » ci-dessous — l'ancienne commande ne pouvait **pas** fonctionner | La version de `front/package.json`, ou `INCONNU` (jamais vide) |
| P4 | Image du service touché reconstruite | Point 12, restreint aux services modifiés par le lot | Image postérieure au commit |
| P5 | Migrations appliquées | `docker logs hostachy_api --since 10m \| grep -iE 'alembic\|revision'` | Pas d'erreur ; head atteint |
| P6 | Aucune régression visible en logs | `docker logs hostachy_api --since 10m \| grep -cE 'ERROR\|CRITICAL'` | 0 |
| P7 | **Le correctif est effectivement observable** | Vérifier le comportement corrigé sur le site réel | Le bug ne se reproduit plus |
| P8 | Redondance intacte après MEP | Point 2 (rôle cohérent sur les 2 nœuds) | Inchangé et cohérent |
| P9 | Parité du standby | Point 10 | HEAD identiques, **ou** noter que la resynchro aura lieu à la bascule de 02:00 (`bascule.sh` phase 0) |
| P10 | **Bilan mémoire du lot** — 🟡 priorité 3 | Relire les activités de la PR : qu'a-t-on appris qui n'est écrit nulle part ? Voir « P10 » | Chaque leçon est **écrite** (socle ou banque projet), ou explicitement écartée |

> **⏱ Attendre la BONNE condition (constaté le 26/07/2026, en utilisant ce
> post-check pour la première fois).** Ne pas attendre que `HEAD` change : dans
> `auto-deploy.sh`, `git reset --hard` a lieu **au début**, avant `docker compose
> build`. Un post-check déclenché sur le changement de HEAD s'exécute donc pendant
> le build et voit des images encore anciennes et pas de ligne `Déployé` — j'ai
> conclu à tort à un déploiement partiel. La condition de fin est la ligne
> **`Déployé: <hash>`** :
> ```bash
> until ssh <actif> "grep -q 'Déployé: <hash>' /var/log/hostachy-deploy.log"; do sleep 20; done
> ```

**P3 — l'ancienne commande renvoyait toujours du vide (corrigé le 03/08/2026).**
`curl -s https://5hostachy.fr/ | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'` ne pouvait pas
marcher : la racine **redirige vers `/auth/connexion`**, et le pied de page versionné
vit dans le layout `(app)`, donc derrière l'authentification. Le `grep` ne trouvait
rien et rendait la main sans un mot — un `$(…)` vide qu'on lit comme « rien à
signaler ». C'est la règle 1 (« une sortie vide n'est pas un vert ») dans le
post-check lui-même.

La version **est** publique : Vite intègre `front/package.json` dans le chunk du
layout `(app)`. On l'y lit sans authentification et sans rien exposer de nouveau —
c'est aussi le seul point de mesure qui reflète ce qu'un **navigateur reçoit
vraiment**, là où lire `package.json` dans le conteneur ne décrirait que l'image.

```bash
#!/usr/bin/env bash
# Version réellement servie, ou INCONNU. Code 0 = mesurée, 2 = non mesurable.
set -uo pipefail
SITE="${1:-https://5hostachy.fr}"
entry=$(curl -sL --max-time 15 "$SITE/" \
        | grep -oE '/_app/immutable/entry/app\.[A-Za-z0-9_-]+\.js' | head -1)
[ -n "$entry" ] || { echo "INCONNU: point d'entrée introuvable"; exit 2; }
for n in $(curl -s --max-time 15 "$SITE$entry" \
           | grep -oE 'nodes/[0-9]+\.[A-Za-z0-9_-]+\.js' | sort -u); do
  v=$(curl -s --max-time 12 "$SITE/_app/immutable/$n" \
      | grep -oE '"hostachy-front",[A-Za-z_$]+="[0-9]+\.[0-9]+\.[0-9]+"' \
      | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  [ -n "$v" ] && { echo "$v"; exit 0; }
done
echo "INCONNU: version absente du bundle servi"; exit 2
```

L'ancrage est `"hostachy-front"`, le **nom** du paquet : il précède immédiatement la
version et survit à la minification, contrairement aux noms de variables (`_n=` au
03/08) et au numéro du chunk. Ne pas se contenter d'un `grep '2\.[0-9]'` sur le
chunk : `package.json` y est intégré **en entier**, dépendances comprises — on
récupérerait la version de Tiptap ou de SvelteKit.

Les deux chemins d'échec ont été éprouvés (site sans bundle, hôte injoignable) :
`INCONNU` et code 2. Un contrôle qui ne sait pas dire qu'il n'a pas pu mesurer est
un contrôle qui ment.

⚠️ **P3 mesure le serveur, pas le client.** Un onglet PWA resté ouvert peut servir
l'ancienne version depuis son cache — c'est ce qui s'est produit le 26/07/2026, le
pied de page bloqué en v2.22.8 après la MEP v2.23.0, alors que P3 était vert. Le
bandeau de mise à jour (v2.24.0) couvre ce cas, et `api/tests/test_pwa_maj.py` le
verrouille.

> 🔒 **Pourquoi ne pas exposer la version dans `/api/health`** (question posée le
> 03/08/2026). L'endpoint est public et porte déjà un champ `version`, mais figé à
> `"0.2.0"` — un littéral codé en dur **deux fois** (`main.py` L166 et L261), sans
> aucun rapport avec l'application. Le rendre exact donnerait un P3 en une ligne, au
> prix d'une **divulgation publique de la version déployée** que rien n'impose
> aujourd'hui. Décision : on ne l'a pas fait. Lire le bundle coûte trois requêtes et
> n'expose rien de plus qu'aujourd'hui. Le littéral dupliqué reste un défaut de
> factorisation à traiter séparément, sans changer ce qui est publié.

**P7 — pourquoi :** c'est le seul contrôle qui teste ce que la MEP était censée
apporter. Le 26/07, le bug du mois en anglais n'a été trouvé par **aucun** contrôle
automatique ou manuel : il a été vu à l'œil sur un document. Les points P1–P6
confirment qu'on a déployé *quelque chose*, jamais qu'on a déployé *ce qu'il
fallait*. Pour un correctif de rendu, ouvrir le document concerné (fiche arrivant,
annonce de hall) et regarder.

> **🌐 Le comportement se vérifie dans un navigateur, sur une route imbriquée
> (constaté le 26/07/2026, v2.24.0 → v2.24.1).** La v2.24.0 ajoutait un bandeau
> « nouvelle version disponible » à la PWA. P1–P6 étaient **tous verts** — image
> reconstruite, version 2.24.0 dans le conteneur, hash du commit et code du bandeau
> présents dans le bundle servi — et la fonctionnalité était morte : elle avait de
> surcroît **cassé l'existant**, plus aucun service worker n'était enregistré, donc
> plus de cache hors ligne. Cause : `vite-plugin-pwa` hérite du `base` de Vite, vide
> sous SvelteKit, et génère `new Workbox('./sw.js', { scope: './' })` ; ce chemin
> **relatif** est résolu depuis la page courante, donc `/auth/sw.js` → 404 sur toute
> route autre que la racine. Trois règles en sortent :
> - **Tester ailleurs qu'à la racine.** Un chemin relatif, un cookie de portée, une
>   règle Caddy fonctionnent souvent sur `/` et nulle part ailleurs.
> - **Les artefacts ne prouvent rien sur le comportement.** Bundle, `sw.js`, image
>   Docker, version du conteneur : tout était correct pendant que la fonctionnalité
>   ne s'exécutait pas. Ouvrir la page et regarder l'état réel
>   (`navigator.serviceWorker.getRegistrations()`, console, requêtes réseau).
> - **Un composant qui reprend un mécanisme fourni par un plugin hérite de ses
>   valeurs par défaut.** Ici `injectRegister` masquait le défaut depuis toujours ;
>   le reprendre à la main l'a exposé. Quand on remplace un mécanisme automatique,
>   vérifier ce qu'il faisait *en plus* de ce qu'on voulait.
>
> Et brancher les callbacks d'erreur (`onRegisterError` ici) : l'échec n'a produit
> **aucun log**, ni côté serveur ni côté navigateur. Ce qui échoue en silence ne se
> découvre qu'à P7, ou jamais.

> **🧪 Une vérification locale ne vaut que pour le chemin d'erreur qu'elle emprunte
> (26/07/2026, v2.26.0 → v2.26.1).** La conservation du lien d'origine à travers
> l'authentification a été vérifiée dans un navigateur, sur le build de production
> servi en local : elle marchait. En production, elle ne marchait pas. En local il
> n'y a **pas de backend** : `auth.me()` échoue en **erreur réseau** et c'est la
> garde du layout qui redirige ; en production l'API répond **401**, et c'est
> `$lib/api.ts` qui redirige en premier — un troisième chemin, non corrigé. Avant de
> conclure d'un test local, se demander **quel chemin de code il a réellement
> exercé**, et si la production en emprunte un autre (API absente vs 401/403,
> cookies, HTTPS, service worker, reverse proxy). Quand un même effet a plusieurs
> points de déclenchement, les chercher tous — ici, un test qui interdit toute
> redirection en dur vers `/auth/connexion` dans `front/src` aurait trouvé le
> troisième du premier coup, là où la relecture en avait vu deux.

**Rollback si P1–P6 échoue :** `cd /opt/5hostachy && git reset --hard <commit-précédent>
&& docker compose build && docker compose up -d`. Réversible et dans le cycle normal
— ce n'est pas une violation de la règle d'or (aucune ouverture de `app.db`).

**P10 — bilan mémoire du lot (🟡 priorité 3, ajouté le 03/08/2026).** Une MEP réussie
n'est pas une MEP close : ce qui a été appris pendant le lot disparaît si personne ne
l'écrit. Ce point est le **dernier** du post-check, et le seul qui ne regarde pas la
production — il regarde le lot.

Ce point **ne bloque pas** la MEP (priorité 3, après la sécurité et la fiabilité des
contrôles) : il la **termine**. Une leçon écartée doit l'être explicitement, pas par
omission.

Relire les activités de la PR — pas le diff, les **surprises** — et se poser les
quatre questions dans cet ordre :

1. **Un défaut a-t-il été trouvé par l'utilisateur plutôt que par un contrôle ?**
   C'est le signal le plus fort : le contrôle manquant est la vraie leçon, pas le
   défaut. → charger la skill globale `retrospective-incident`.
2. **Cela pouvait-il arriver sur un autre projet ?** Si oui, ça monte dans le socle
   `~/.claude/standards/`, et **nulle part ailleurs** (règle de placement,
   `~/.claude/CLAUDE.md` §1). Une pratique générique recopiée dans un projet est déjà
   une divergence.
3. **Sinon, est-ce propre à 5Hostachy ?** → banque `~/.claude/projects/C--Dev-5hostachy/memory/`,
   un fichier = un fait, plus une ligne dans `MEMORY.md`.
4. **Une mémoire existante est-elle devenue fausse ?** Une mémoire périmée est pire
   qu'une mémoire absente : elle est citée avec assurance. La corriger ou la
   supprimer — ne jamais empiler une exception par-dessus.

Vérifier aussi que la documentation *visible* a suivi : manuel utilisateur mis à jour
**et** sa version/date bumpées aux deux emplacements
(cf. [[feedback_manuel_version_date]]), `specs/` si un contrat d'API a changé.

**Pourquoi ce point existe :** sur le lot des pièces jointes (03/08/2026), quatre
constats n'auraient été écrits nulle part sans un rappel explicite — la version du
manuel jamais bumpée, les fins de ligne cassées par `sed -i` puis « réparées » d'une
façon qui ne restaure pas un fichier mixte, les endpoints devenus orphelins, et le
drapeau `fichiers` des e-mails calculé sur l'intention plutôt que sur la pièce jointe
réelle. Trois d'entre eux ont été soulevés **par l'utilisateur**, pas par le
processus : c'est exactement la question 1.

## Rétrospective du 26/07/2026 — ce que le processus n'a pas vu

Inventaire honnête, à garder comme étalon de ce que les contrôles doivent attraper.
Colonne clé : **qui** a détecté.

| Problème | Détecté par | Pourquoi le processus l'a manqué |
|---|---|---|
| Mois en anglais sur la fiche arrivant (`%B` en locale C, 5 sites) | **L'utilisateur, à l'œil** | Aucun contrôle du rendu des documents → **P7** créé, + `tests/test_dates_fr.py` qui interdit `%B` dans `app/` |
| La fiche arrivant n'est jamais transmise au nouvel arrivant | Demande d'examen de l'utilisateur | Aucun test du parcours d'accueil de bout en bout ; **non corrigé à ce jour** |
| Clone local à 16 commits de retard (`main` à 151) | Précaution avant commit | Le pré-check ne regardait que les RPi, jamais le poste de dev → **étape 0a** + `.githooks/pre-commit` |
| Hook committé en `100644` = garde-fou inerte | Demande de relecture de l'utilisateur | Le point 7 ne couvrait que les scripts en prod, pas les modes dans git → **étape 0b** |
| `.active` incohérent → failover neutralisé, site HS ~50 min | Pré-check (manuel, 7 h après le début) | Contrôle ponctuel pour un invariant permanent, et libellé trop vague → **point 2** réécrit, + à automatiser |
| `auto-deploy` de rpi1 franchissant l'anti-split-brain 7 h 30 | Lecture de log a posteriori | Aucune détection de battement manquant → **point 8** étendu |
| Aucune alerte pendant la panne (`Email KO`) | Lecture de log | Alerting mono-canal, qui tombe avec le réseau → **point 13** |
| Faux vert « 0 inode fantôme » (sudo muet en SSH) | Demande de vérification | **Le pré-check lui-même** était en cause → **règle 1** + point 4 sans `sudo` |
| Faux positif « image API périmée » | Vérification avant d'alarmer | Point 12 ne bornait pas le périmètre → **règle 3** + point 12 corrigé |
| Version périmée servie à un onglet resté ouvert (footer bloqué en v2.22.8 après la MEP v2.23.0) | **L'utilisateur, en lisant le footer** | Le cache d'une PWA n'était surveillé par rien, et P3 lit « la version servie » sur le serveur, pas chez le client → bandeau de mise à jour (v2.24.0) + `test_pwa_maj.py` |
| Service worker plus enregistré du tout (URL relative → 404 hors racine), cache hors ligne cassé en production | **P7**, dans un navigateur réel | P1–P6 ne regardent que des artefacts : image, version du conteneur, code présent dans le bundle — tous corrects pendant que rien ne s'exécutait → encadré P7 « tester sur une route imbriquée » + `npm run lint:sw` sur le bundle construit |

## Surveillance continue — état après le 26/07/2026

> **La détection existait déjà et fonctionnait. C'est la notification qui manquait.**
> `check-reliability.sh` porte un contrôle **C4** (« `.active` cohérent entre les 2 et
> conforme à la réalité terrain ») depuis bien avant l'incident, et il a émis
> `[FAIL] .active divergent — rpi2='rpi2' vs rpi1='rpi1'` **neuf fois** entre 06:53 et
> 09:28, pendant que le failover était neutralisé. Personne ne l'a su : le cron
> redirige toute la sortie vers `/var/log/hostachy-reliability.log`, donc `MAILTO` ne
> reçoit rien, et le script n'avait aucun canal d'alerte propre.
> **Leçon : avant d'ajouter un contrôle, vérifier qu'il n'existe pas — et qu'il a un
> destinataire.** Un contrôle sans destinataire est un contrôle absent.

Corrigé (v2.22.3) :

1. **Alerte sur échec critique** — `check-reliability.sh` envoie désormais un e-mail
   quand `FAILS > 0`, via le module partagé `lib-alert.sh` (cooldown 1 h : à `*/15`,
   un FAIL persistant produirait 96 e-mails par jour). Le mécanisme SMTP, jusqu'ici
   écrit en dur dans `health-watch.sh`, est factorisé dans ce module.
2. **Battement d'`auto-deploy` (C14)** — alerte si les lignes périodiques du standby
   disparaissent. Ne s'applique **qu'au standby** : sur l'actif, `auto-deploy`
   n'écrit rien tant qu'il n'y a pas de changement, le silence y est normal.
3. **Propagation du flag au peer** — `boot-role-guard.sh` (`become_active`) et
   `health-watch.sh` (démotion de l'ancien actif) écrivent maintenant `.active` chez
   le peer joignable, ce qui supprime la cause racine de l'incohérence.

Complété le 30/07/2026 (v2.27.2) — **trois contrôles qui mentaient**, tous corrigés :

4. **Le contrôle du battement (C14) était vert quand le battement était nul.**
   `HB=$(grep -c … || echo 0)` : `grep -c` affiche déjà `0` et sort en 1 quand rien
   ne correspond, donc le `|| echo 0` **ajoutait** une seconde valeur → `"0\n0"` →
   `[ "0\n0" -lt 6 ]` échoue en `integer expression expected`, l'expression passe à
   faux et le contrôle affiche `[ OK ]` — exactement dans le cas qu'il existe pour
   attraper (log vide, illisible ou renommé). Reproduit avant correction. C14 mesure
   désormais l'**âge du dernier battement horodaté** (≤ 20 min), ce qui supprime aussi
   la traîne des tranches horaires : le 30/07 le mail est parti à 02:06 sur les
   compteurs de 01:00-01:59, alors que tout était vert depuis 01:46.
5. **L'alerte décrivait le log, pas son exécution.** Le corps du mail reprenait
   `grep '^\[FAIL\]' /var/log/hostachy-reliability.log | tail -10`, donc l'historique
   de toutes les exécutions passées : un sujet « 1 contrôle en échec » accompagné de
   **six** lignes, dont cinq d'une panne déjà résorbée. Le corps liste maintenant les
   FAIL de l'exécution courante, horodatés.
6. **`curl … || echo 000`** produisait `HTTP 000000` dans les logs et les alertes
   (`-w '%{http_code}'` écrit déjà `000` en cas d'échec). Une seule fonction `http_code()`
   par script, une seule valeur rendue.

> **Leçon, dans le prolongement de la règle 1 (« un contrôle qui ne peut pas
> s'exécuter renvoie INCONNU, jamais OK ») : un contrôle qui compte doit être testé
> sur le cas ZÉRO.** Les trois défauts ci-dessus ont vécu des semaines en produisant
> des lignes vertes plausibles. Aucun n'était visible sans rouvrir le fichier — d'où
> le job CI `test-scripts`.

Reste ouvert :

* **Second canal d'alerte.** Le canal est unique (SMTP) et tombe avec le réseau,
  donc précisément quand on en a besoin — le 26/07, `Email KO: [Errno 101] Network
  is unreachable`. Une alerte WhatsApp via le bridge (le conteneur tourne en local,
  mais son `/status` exige un token, donc il faudrait sortir la clé de `.env`) ou un
  heartbeat sortant vers un service tiers couvriraient le cas. Décision de conception
  à prendre. La panne du 30/07 l'a confirmé une seconde fois : sept alertes perdues
  entre 01:06 et 01:44, la première n'est partie qu'à 02:06, le réseau revenu.
  *(Cette limite est structurelle : un canal qui emprunte le lien en panne ne peut
  pas signaler la panne de ce lien. Le cooldown n'est volontairement pas marqué en
  cas d'échec d'envoi, donc l'alerte est bien retentée — elle arrive en retard, pas
  jamais.)*

*Fait :* la migration de `health-watch.sh` vers `lib-alert.sh` est **terminée** (le
script source le module, avec un repli qui journalise si le fichier manque — le
failover reste opérationnel sans lui, contrainte du chemin critique).
