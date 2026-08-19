---
name: infra-rpi
description: "Infrastructure HA 5Hostachy sur 2 Raspberry Pi : serveurs et rôle actif, protections SQLite, règle d'or anti-corruption DB et sa signature de diagnostic, distinction panne de chemin public / panne de nœud, crontabs, monitoring APScheduler, bridge WhatsApp, sync DB manuelle. Use when: intervenir sur un RPi, basculer, diagnostiquer un site HS ou une corruption de base, reconnecter WhatsApp, analyser un incident ou une coupure de courant."
argument-hint: "Décrire l'intervention ou le symptôme (ex. « site HS depuis 20 min », « reconnecter le bridge WhatsApp », « disk I/O error dans les logs »)"
---

# Infrastructure & Monitoring — 5Hostachy

Instanciation 5Hostachy de `standards/06-donnees-et-integrite.md` et
`standards/07-observabilite-et-alertes.md`. La **règle d'or anti-corruption DB**
ci-dessous est également résumée dans `CLAUDE.md` et dans
`.claude/5hostachy-preflight.md` : elle ne doit jamais dépendre de ce chargement.

> 📖 **Le générique n'est pas recopié ici** — l'ouvrir en parallèle :
> `standards/06-donnees-et-integrite.md` §1 (règle d'or généralisée à tout état
> multi-fichiers tenu ouvert — elle s'est reproduite sur l'authentification WhatsApp),
> §2 (copier une base), §6 (sauvegardes : restauration testée, et **où** elles vivent)
> · `standards/04-fiabilite-des-controles.md` §10 (deux sondes indépendantes avant
> toute décision destructive : panne de nœud ≠ panne de chemin) ·
> `standards/07-observabilite-et-alertes.md` §2 (un canal qui emprunte le lien en
> panne ne peut pas signaler cette panne), §5 (échec silencieux), §6–8 (rotation,
> maintenance sur tous les nœuds, hygiène).

## Serveurs
- **RPi 1** `192.168.1.222` (PhT-RB5) · **RPi 2** `192.168.1.223` (PhT-RB5i2)
- RPi actif : `cat /opt/5hostachy/.active` — ⚠️ ce fichier peut disparaître, le recréer si absent
- Conteneurs uniquement sur le RPi actif — vérifier les 2 en cas de doute (`docker ps`)
- En cas de split-brain (conteneurs sur les 2) : stopper le standby + recréer `.active`
- En cas de site HS : SSH sur le RPi actif → `cd /opt/5hostachy && docker compose up -d`

## Protections DB (v2.18.10)
- `stop_grace_period: 30s` sur le service API → Docker attend 30s avant SIGKILL
- `PRAGMA wal_checkpoint(TRUNCATE)` dans le lifespan shutdown → WAL vidé proprement à chaque arrêt
- `bascule.sh` phase 3 : WAL checkpoint avant rsync DB vers le peer
- `MaJ-Hostachy.sh` : bloque si lancé sur le RPi standby
- `synchronous=FULL` (v2.20.3) : chaque commit fsync'd intégralement (anti torn-write)
- `health_check` 06:00 + chaque backup : `PRAGMA quick_check` → alerte / backup annulé si corrompu
- `maintenance.sh` VACUUM : **API stoppée** (base au repos, 0 writer) puis `sqlite3` hôte

## ⚠️ Règle d'or anti-corruption DB (v2.20.3 · durcie 17/07/2026)
**Ne JAMAIS OUVRIR `app.db` depuis un process tiers tant que l'API tourne — même en lecture.**
- Checkpoint / intégrité à chaud → endpoints **in-process** : `POST /admin/db/checkpoint`,
  `GET /admin/db/integrite` (s'exécutent dans le process uvicorn = même connexion que l'app).
- VACUUM / copie / swap de fichier → **stopper l'API d'abord** (0 writer), comme bascule phase 3.
- ❌ `docker exec hostachy_api python3 … PRAGMA …` et `sqlite3` hôte sont **INTERDITS** tant
  que l'API tourne. **Sans exception de lecture seule.**

**Pourquoi la lecture seule n'est PAS sûre** — leçon du 17/07/2026 : cette ligne affirmait
l'inverse (« = OK (ne mute rien) »), ce qui a fait écrire `check-reliability.sh` C8 ainsi et
a coûté ~12 h d'écritures. Les connexions du pool SQLAlchemy sont *ouvertes mais SANS VERROU*
quand elles sont idle. Un process tiers qui ouvre la base puis la referme se croit donc
**dernière connexion** → checkpoint + **`unlink` de `app.db-wal` et `app.db-shm`**. L'API
continue alors d'écrire dans des **inodes orphelins** :
1. writes **invisibles** aux autres connexions (générations de WAL divergentes) ;
2. `disk I/O error` (SQLITE_IOERR) en rafales → **503** sur toute requête authentifiée ;
3. **PERTE DES DONNÉES** au prochain arrêt : le checkpoint de shutdown échoue
   (`WAL checkpoint échoué au shutdown (non bloquant)`) → le WAL orphelin est abandonné.

**Signature de diagnostic (30 s, décisive) :**
```bash
DB_DIR=$(docker volume inspect 5hostachy_app_data --format '{{.Mountpoint}}')
sudo stat -c '%n mtime=%y' $DB_DIR/app.db          # figé depuis des heures = ALERTE ROUGE
sudo ls $DB_DIR/ | grep -E 'app.db-(wal|shm)'      # absents du disque…
sudo lsof -p $(docker inspect hostachy_api --format '{{.State.Pid}}') | grep app.db
#   … mais tenus ouverts par uvicorn, a fortiori sur PLUSIEURS inodes = fichiers supprimés
```
- `app.db` dont le `mtime` ne bouge pas alors que le site écrit ⇒ **aucun checkpoint n'aboutit
  ⇒ toutes les écritures depuis ce `mtime` sont en sursis.** Traiter comme une urgence.
- 🚫 **Ne PAS redémarrer l'API dans cet état** : cela libère les inodes orphelins et rend la
  perte **définitive**. Extraire d'abord les WAL orphelins (`/proc/<pid>/fd/<n>`).
- Zéro erreur `dmesg`/ext4/mmc ⇒ ce n'est **pas** le matériel, c'est un process tiers.
- ⚠️ Un `integrity_check` vert **n'innocente rien** (nouveau process = vue saine).
- ⚠️ Les rafales **se résorbent spontanément** puis récidivent (recyclage du pool) : une
  accalmie sans explication n'est **pas** une résolution.

Cause racine des corruptions `telemetry_event` des 05 et 17/06/2026 **et** de l'incident du
17/07/2026 (login 503 + 2 publications perdues) — coupable : `check-reliability.sh` C8, qui
faisait exactement cela toutes les 15 min (contrôle supprimé, cf. commentaire dans le script).
Cf. [[project_db_corruption_telemetry]] et le commentaire de `admin.py` → `/db/checkpoint`.

## ⚠️ Panne de CHEMIN public ≠ panne de NŒUD (incident du 30/07/2026)

Entre 00:52 et 01:46, une panne DNS/WAN a coupé le tunnel des **deux** nœuds
(`lookup _v2-origintunneld._tcp.argotunnel.com on 1.0.0.1:53: server misbehaving`,
`Email KO: [Errno 101] Network is unreachable`). Aucun RPi n'avait redémarré ni gelé.

`health-watch.sh` ne sondait que l'**URL publique**. Chaque nœud a donc conclu que
l'autre était mort : **12 failovers croisés en 55 min**, stack arrêtée et redémarrée
alternativement sur les deux, rôle actif déplacé 12 fois **sans synchronisation de
base** (un failover ne sync pas la DB — [[project_freezes_recurrents_rpi2]]), et à
trois reprises `systemctl start cloudflared` a échoué sur le nouvel actif *avant*
que l'ancien soit démoté → **cloudflared inactif sur aucun nœud**. Aucune de ces
bascules n'a rétabli quoi que ce soit : le nœud actif servait parfaitement en LAN.

**Correctif (v2.27.2)** — avant de basculer, le standby doit établir que la panne
vient bien du nœud actif, via deux sondes indépendantes de l'URL publique :

| API de l'actif en LAN | Edge Cloudflare depuis le standby | Décision |
|---|---|---|
| KO | — | **Failover** (nœud réellement mort — chemin critique inchangé) |
| OK | KO | **Abstention** + alerte : panne de chemin, basculer ne rétablirait rien |
| OK | OK | **Failover** : le nœud actif vit mais son tunnel est cassé |

La sonde LAN est `http://<actif>/api/health` (via Caddy — le port 8000 n'est **pas**
publié, et un GET `/health` reste in-process : aucune ouverture de `app.db`). La
sonde d'edge (`cdn-cgi/trace`) exerce DNS + TLS, c'est-à-dire exactement la chaîne
dont le tunnel dépend : « pourrais-je seulement servir ? ». Logique isolée en
fonction pure `decide_failover()` + `./health-watch.sh --selftest`, vérifiée en CI.

**Réflexe de diagnostic** au prochain « site public KO » : avant de suspecter un
nœud, `curl http://<actif>/api/health` depuis l'autre RPi. S'il répond 200, le
problème est sur le chemin (box, DNS, Cloudflare) — ne pas basculer, ne pas
redémarrer la stack.

## Risques connus
- **Build OOM** : `npm run build` peut saturer la RAM du RPi → préférer `--nocache` en cas de build lourd
- **health-watch failover** → peut créer un split-brain ; toujours vérifier `docker ps` sur les 2 RPi
- **Sauvegardes** : le volume `backups` n'est **pas** répliqué par `bascule.sh` (qui ne
  synchronise que `uploads`, `whatsapp_auth` et `app_data`). Le rôle alternant chaque
  nuit, chaque nœud n'accumule qu'un jour sur deux, et `_rotate_backups()` ne voit que
  ses fichiers locaux → 7 versions ≈ 14 jours **à trous**, aucun nœud n'ayant celle de
  la veille. Copie hors site : `scripts/poste/export-hors-site.cmd` (voir ci-dessous)
- **`.active` peut disparaître** → le recréer manuellement sur les 2 RPi si absent

## Copie hors site des sauvegardes (v2.37.0 — 04/08/2026)

Avant cette date, **100 % des archives vivaient sur les deux RPi**, au même domicile,
sur la même box et la même alimentation. Les deux nœuds protègent de la panne d'**un**
nœud — jamais d'un `docker volume rm`, d'un rançongiciel ou d'un sinistre, qui
emportent base + uploads + toutes les sauvegardes d'un coup
(`standards/06-donnees-et-integrite.md` §6).

- **Lancement : MANUEL depuis le poste** — double-clic sur `scripts/poste/export-hors-site.cmd`, ou
  `bash /c/Dev/5hostachy/scripts/poste/export-hors-site.sh`. Destination par défaut : `C:\Backup`
  (`EXPORT_DEST`), 14 versions (`EXPORT_KEEP`).
- Le script choisit sa source par **comportement** (qui répond sur `/api/health` en
  LAN), pas en lisant `.active` — et **s'abstient** en cas de split-brain : deux nœuds
  qui servent = deux bases divergentes, en copier une au hasard puis faire tourner la
  rotation détruirait la bonne.
- Il **n'ouvre jamais `app.db`** sur un RPi : il ne lit que des `.tar.gz` clos.
  L'`integrity_check` porte sur la copie extraite **sur le poste**.
- Vérifications avant de déclarer la copie bonne : empreinte SHA-256 identique à la
  source, `app.db` présent dans l'archive, `PRAGMA integrity_check`. Une copie non
  validée est renommée `.invalide` — elle ne doit pas se présenter comme une
  sauvegarde disponible. **Intégrité non vérifiable = échec, pas succès.**
- Il poste son rapport sur le canal cron existant (`POST /admin/maintenance/rapport`,
  `tache=export_hors_site`) → visible dans **Admin → Maintenance**, et le contrôle de
  06:00 alerte au-delà de **7 jours** (seuil hebdomadaire assumé : le poste n'est pas
  allumé en permanence, et une alerte quotidienne ignorée est un contrôle mort).
- Le contrôle distingue **deux** questions : « l'export a-t-il tourné ? » et « la copie
  est-elle fraîche ? ». Un export fidèle qui recopie chaque jour la même archive
  périmée est un faux vert — verrouillé par `api/tests/test_sauvegarde_hors_site.py`.

⚠️ **Portée** : le poste est au même domicile que les RPi. Cette copie couvre la perte
d'un nœud, le `docker volume rm` et le rançongiciel visant les RPi — **pas l'incendie
ni le vol**. Une destination réellement distante (S3 UE chiffré, disque tournant) reste
à ajouter ; `EXPORT_DEST` et la boucle de vérification sont écrits pour l'accueillir.

## Qui reçoit les verdicts de `check-reliability.sh` (#449 — 19/08/2026)

**Deux canaux, deux rythmes**, et la fréquence se règle par le **cooldown**, jamais
en coupant le canal :

| Verdict | Canal | Cooldown |
|---|---|---|
| au moins un **FAIL** | alerte e-mail « ❌ contrôle(s) en échec » | 1 h |
| aucun FAIL, au moins un **WARN** | digest e-mail « ⚠️ point(s) de vigilance » | 24 h |
| tout vert | rien | — |

La décision est **pure** (`verdict_notification`, `lib-verdicts.sh`, couverte par
`--selftest`) ; l’envoi vit dans `lib-notification.sh`.

🔴 **Pourquoi le digest existe.** L’alerte ne partait que sur `FAILS > 0`. Or **cinq**
contrôles rendent WARN par choix assumé — C16 (cache de build), C17 (maintenance en
retard), C19 (journal ⇆ base), C20 (sudo), C22 (points d’entrée) — au motif qu’un FAIL
à `*/15` enverrait un mail par heure. Le raisonnement était juste sur la **fréquence**
et faux sur la **conclusion** : on en a déduit « pas de mail » là où il fallait « pas
ce mail-là ». Ces cinq contrôles n’avaient donc **aucun destinataire**.

Ce que ça a coûté : le **16/08/2026 à 03:02**, le rapport de la maintenance a été
refusé (HTTP 422). **C19 l’a vu** et a rendu WARN. Personne n’a été prévenu ; le défaut
a été trouvé le **18** à l’œil, sur l’écran d’administration, **par l’utilisateur**.
L’écran affichait « À jour » sur un rapport vieux de cinq jours.

⚠️ **Un WARN sans destinataire est un contrôle mort** — `standards/04` §7. Poser un
nouveau contrôle en WARN est légitime ; le laisser sans canal ne l’est pas.

## Sync DB manuelle (sans basculer)
⚠️ Copier `app.db` pendant que l'API écrit = copie potentiellement déchirée. On stoppe
l'API le temps de la copie (≈ qq s) → fichier cohérent garanti (cf. règle d'or ci-dessus).
```bash
# Depuis le RPi actif — base au repos pour une copie cohérente
DB_DIR=$(docker volume inspect 5hostachy_app_data --format '{{.Mountpoint}}')
docker stop hostachy_api
sqlite3 "$DB_DIR/app.db" "PRAGMA wal_checkpoint(TRUNCATE);"   # vide le WAL
cp "$DB_DIR/app.db" /tmp/app_sync.db
cd /opt/5hostachy && docker compose up -d api                  # API repart immédiatement
scp /tmp/app_sync.db ptressard@<PEER_IP>:/tmp/app_sync.db
# Sur le standby :
docker run --rm -v 5hostachy_app_data:/data -v /tmp/app_sync.db:/tmp/app_sync.db alpine sh -c 'cp /tmp/app_sync.db /data/app.db && rm -f /data/app.db-wal /data/app.db-shm'
```

## Crontabs et unité systemd — **source versionnée : `infra/points-entree/`**

Depuis le 15/08/2026, les six points d'entrée (4 crons root, 1 cron utilisateur,
et l'unité `hostachy-role-guard.service`) sont décrits dans le dépôt. Vérifier
qu'un nœud y est conforme :

    bash scripts/poste/verifier-points-entree.sh

C'est le **point 17** du pré-check. À la différence de C18 — qui compare les deux
nœuds *entre eux* et laisse donc passer la dérive commune — il compare au **dépôt**.
Rien n'est posé automatiquement : installer reste un geste explicite, un nœud à la
fois.

## Crontabs (sudo root — identiques sur les 2 RPi)
```
0 2 * * *   bascule.sh        # bascule active/standby
0 3 * * 0   maintenance.sh    # purge, VACUUM, rotation logs (dimanche)
*/5 * * * * health-watch.sh   # failover automatique si site HS
```

## Le standby s'aligne tout seul (#448 — 19/08/2026)

`auto-deploy.sh` (cron **utilisateur** `ptressard`, `*/5`) tourne sur les **deux**
nœuds. Il sortait jusqu'ici avant le `git fetch` sur le standby : son code et ses
images restaient figés au jour où il a cessé d'être actif.

Le 19/08/2026, rpi2 était ainsi resté à **v2.90.0** pendant que la production
servait **v2.102.2** — 13 commits, et la migration **0154 absente de son code**,
alors que sa base est synchronisée à chaque bascule. Un failover cette nuit-là
aurait servi du code v2.90.0 sur une base migrée en 0154.

**Ce que fait le standby désormais** : `git reset --hard origin/main` puis
`docker compose build`. Et rien d'autre — **aucun conteneur démarré** (ce serait
le split-brain), **aucune migration appliquée** (sa base est une copie que la
bascule écrase ; migrer ici divergerait en silence).

⚠️ **La bascule de 02:00 n'a jamais aligné que le nœud ENTRANT.** La tolérance du
point 10 du pré-check disait « le standby se resynchronise à la bascule » : c'était
faux dans les deux sens — quand la bascule échoue, mais aussi quand elle réussit,
puisque le sortant repart avec le retard. C'est pour cela que le retard revenait
après chaque déploiement.

🔒 **Verrou `flock`** posé au passage (`.auto-deploy.lock`) : un build de front sur
RPi dépasse volontiers cinq minutes, donc le cron suivant tombait dans le
précédent — le remède était noté depuis l'incident du 17/07/2026 sans avoir été
posé. Le chemin « déjà en cours » écrit sa ligne datée : le CONTRAT DE BATTEMENT
lu par C14 exige qu'aucun chemin ne soit muet.

Si le build du standby échoue, une alerte part (cooldown 6 h) : c'est l'état le
plus trompeur, la parité **git** devenant verte alors que les **images** sont
restées vieilles — distinction que le point 10 ne sait pas faire.

## Monitoring APScheduler (tourne dans le conteneur API)
| Heure | Job | Alerte email si… |
|-------|-----|-----------------|
| 03:00 | backup | — |
| 06:00 | **health_check** | WhatsApp déconnecté · backup > 25h · disque < 15% |
| 18:00-21:45 (`*/15`) | whatsapp_scheduled | Fenêtre de rattrapage épuisée sans envoi réussi |
| 02:00 | telemetry_aggregation | — |

## WhatsApp bridge
- Reconnexion QR : Admin → WhatsApp → **bouton Statut** (affiche le QR si déconnecté)
- Session corrompue (`creds.json` vide) : vider le volume + redémarrer le bridge
  ```bash
  docker run --rm -v 5hostachy_whatsapp_auth:/data alpine sh -c 'rm -rf /data/*'
  cd /opt/5hostachy && docker compose up -d whatsapp-bridge
  ```
- `bascule.sh` ne propage jamais un `creds.json` vide vers le peer

#### Lire l’historique des envois — trois verdicts, pas deux (19/08/2026)

`Admin → WhatsApp → Historique des envois` ne dit **pas** « parti / pas parti » :
il en distingue **trois**, et la nuance est ce qui protège du doublon.

| Verdict | Ce qu’on sait | Rejouable ? |
|---|---|---|
| **envoyé** | le serveur WhatsApp a acquitté | — |
| **incertain** | le message a **pu** être remis | 🔴 **jamais** |
| **échec** | on sait que rien n’est sorti (connexion refusée, 4xx) | oui, sans risque |

🔴 **« incertain » n’est pas un échec.** Rejouer un envoi dont on ignore le sort
fabrique un doublon dans le groupe des copropriétaires — et un doublon ne se
retire pas. C’est le triple envoi du 14/08/2026.

⚠️ **Deux causes très différentes produisent « incertain », et il faut les lire :**

- **« message émis, accusé de réception non observé »** — `sendMessage()` a rendu
  la main, donc **le message est parti** ; seul l’accusé du serveur WhatsApp a
  tardé (15 s). Il a très probablement été remis : **vérifier dans WhatsApp avant
  toute action**, c’est le cas le plus fréquent ;
- **« réponse 500 du bridge »** — le bridge a échoué en cours de route sans dire
  de quel côté de l’envoi. Là, on ne sait vraiment pas.

**Why** : jusqu’au 19/08/2026 le bridge répondait `500` dans les DEUX cas — son
`catch` était commun. L’utilisateur a comparé son fil WhatsApp et l’écran : deux
messages **remis** (double coche) y figuraient en « incertain — réponse 500 du
bridge ». Le bridge rend désormais **`202 Accepted`** avec `envoye: true` quand
le message est parti sans accusé, et l’API le traduit en clair. Verrouillé par
`api/tests/test_whatsapp_verdict_envoi.py`, qui éprouve les trois verdicts côte
à côté — un test qui ne vérifierait qu’un seul ne prouverait pas qu’il distingue.

#### Incident du 24/07/2026 — bridge bloqué 2h23, message mensuel manqué
Le message WhatsApp planifié du 4ᵉ samedi (18h00) a échoué : le bridge était en
boucle `stream:error conflict:replaced` ininterrompue depuis 14h28, sans jamais
revenir à `state: open`. Deux causes cumulées, corrigées :

1. **`bascule.sh` synchronisait `5hostachy_whatsapp_auth` « à chaud » (Phase 1,
   conteneur source encore actif et en train d'écrire `creds.json` + fichiers de
   clés)** → snapshot multi-fichiers potentiellement déchiré propagé au peer à
   chaque bascule nocturne. **Corrigé** : le sync se fait désormais en Phase 2,
   après `docker compose stop` (0 writer, comme la DB), avec vérification que
   `creds.json` est un JSON valide avant de l'installer sur le peer. Même classe
   de bug que la « Règle d'or anti-corruption DB » ci-dessus, appliquée à l'état
   d'authentification WhatsApp plutôt qu'à `app.db`.
2. **`whatsapp-bridge/index.js` ne supervisait pas sa propre reconnexion** :
   `setTimeout(startBaileys, 5_000)` appelait une fonction `async` sans
   `.catch()` → une reconnexion qui rejette (ex. timeout réseau) tue la chaîne
   silencieusement, sans aucun log. C'est ce qui a laissé le bridge mort de
   16h18 à 18h41 sans la moindre tentative. **Corrigé** : verrou anti-concurrence
   (`starting`), `.catch()` systématique sur chaque relance, backoff exponentiel
   (5s → 60s max), et un watchdog (`setInterval` 60s) qui force une reconnexion
   si l'état reste hors `open`/`connecting`/`waiting_qr` sans reconnexion en cours.
3. Le job `whatsapp_scheduled` ne tentait l'envoi **qu'une fois, à 18h00 pile**
   — un échec ponctuel du bridge à cette seconde précise perdait le message du
   mois. **Corrigé** : fenêtre de rattrapage 18h00→21h45 toutes les 15 min (la
   déduplication existante empêche tout doublon), alerte email si la fenêtre se
   ferme sans envoi réussi.
