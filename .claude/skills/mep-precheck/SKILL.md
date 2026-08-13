---
name: mep-precheck
description: "MEP 5Hostachy : lancer `bash rejouer-ci.sh` puis `bash precheck-mep.sh` (tous les points s'exécutent), lire ses verdicts, dérouler le post-check P1-P11 (dont la clôture des tickets, après vérification en production), rollback. Use when: AVANT tout `git push` sur dev ou main, avant de remettre une PR, après un merge vers main, pour diagnostiquer un déploiement qui n'a pas eu lieu ou vérifier qu'un correctif est réellement servi. L'histoire des incidents qui ont fait naître chaque contrôle est dans HISTORIQUE.md, à ouvrir seulement pour diagnostiquer."
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
>
> 📜 **`HISTORIQUE.md`, à côté de ce fichier** : pourquoi chaque contrôle existe,
> quel incident l'a fait naître, quels faux verts il a déjà produits. À ouvrir
> **pour diagnostiquer**, jamais pour agir — c'est ce qui permet à cette
> procédure-ci de tenir en une page.

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

## Pré-check obligatoire avant MEP — il s'exécute

```bash
bash precheck-mep.sh          # à la racine du dépôt
```

**Ne pas dérouler la grille à la main.** Elle l'a été trop souvent de mémoire, en
sous-ensemble : trois lots sont partis sans aucun pré-check les 07 et 08/08/2026,
et deux contrôles improvisés ont rendu des faux verts. Le script mesure, écrit sa
trace dans `.git/precheck-mep.ok`, et `.githooks/pre-push` refuse le push sans
elle.

**Fusionner la PR EST la mise en production** : `auto-deploy.sh` déploie
`origin/main` toutes les 5 minutes. Le pré-check se passe donc **avant le push sur
`dev`**, pas après la fusion.

### Ce que le script couvre

| # | Contrôle | Verdict possible |
|---|---|---|
| 0a | Clone à jour sur `origin/dev` | OK · FAIL |
| 0b | Modularité — ce que la CI vérifiera | OK · FAIL |
| 0c | **CI de la branche**, hors échecs que ce lot corrige | OK · FAIL · INCONNU |
| 0d | **Un seul bump de version dans le lot** | OK · ÉCART · FAIL |
| 0f | **Titre et descriptif de PR préparés** (`.git/pr-brief.md`) | OK · FAIL · INCONNU |
| 15 | Aucun endpoint orphelin | OK · FAIL |
| 16 | **CI rejouée en local sur ce commit** (`rejouer-ci.sh`) | OK · FAIL · INCONNU |
| 1 | Site public répond | OK · FAIL · INCONNU |
| 2 | Rôle actif cohérent **et conforme au réel** | OK · FAIL |
| 3 | Standby sans conteneur (pas de split-brain) | OK · FAIL |
| 4 | Base saine — WAL présent, 0 `disk I/O error`, **sans ouvrir `app.db`** | OK · FAIL |
| 5 | Bridge WhatsApp connecté | OK · FAIL |
| 6 | Aucune ERROR/CRITICAL (1 h) | OK · FAIL |
| 7 | Scripts cron exécutables | OK · FAIL |
| 8 | Battement d'auto-deploy sur le standby | OK · FAIL |
| 9 | **E-mails en échec** | **INCONNU — voir ci-dessous** |
| 10 | Parité de code entre les 2 nœuds | OK · ÉCART |
| 11 | Auto-deploy de l'actif vivant | OK · FAIL |
| 12 | Image postérieure au commit déployé | OK · FAIL |
| 13 | Canal d'alerte non muet | OK · FAIL |
| 14 | Hygiène disque sur les **2** nœuds | OK · FAIL |

### Lire le verdict

- **FAIL** → MEP non autorisée. Diagnostiquer, corriger, **relancer le script**.
- **ÉCART** (points 10 et 0d) → toléré, mais à lire. Point 10 : le standby se
  resynchronise à la bascule de 02:00 (`bascule.sh` phase 0). Point 0d : un lot
  **sans** bump se déploie quand même — c'est P3 qui devient incapable de prouver
  que le déploiement a eu lieu, la version servie étant identique avant et après.
- **0c** → il ne compte que les échecs de CI que ce lot **ne corrige pas**. Un
  échec est dépassé s'il est suivi d'un succès plus récent, **ou** si HEAD
  descend du commit fautif. Sans cette nuance, le push qui corrige une CI rouge
  était refusé par le contrôle même qui constatait le rouge — et la seule issue
  était `SKIP_PRECHECK=1`, donc désarmer les vingt points pour en contourner un
  (#318, corrigé le 12/08/2026). Les **deux** conditions sont nécessaires : les
  PR étant fusionnées en squash puis `dev` réaligné, l'ascendance seule disparaît
  au premier réalignement.

  ⚠️ **Deux contrôles différents portent le nom « 0c »** : celui-ci, exécuté par
  le script, et l'exigence d'**autorisation centralisée** de l'étape 0 bis
  ci-dessus, qui est vérifiée par `test_autorisation.py`. La collision est
  historique ; à renommer un jour, en attendant lire le contexte.
- **0f** → le lot doit porter son titre et son descriptif de PR **avant** le push,
  dans `.git/pr-brief.md` : première ligne `commit: <sha court de HEAD>`, deuxième
  ligne le titre en `# …`, puis le corps (5 lignes minimum). Un brief rédigé pour
  un autre commit **échoue** — sinon il décrirait le lot précédent. Ajouté le
  11/08/2026 après deux oublis dans la même journée, le second juste après
  s'être fait reprendre sur le premier : la consigne de la skill `avant-commit`
  ne tenait pas seule.
- **0d en FAIL** → le lot porte **deux bumps ou plus**. N'en garder qu'un, posé
  en dernier : `git reset --soft <avant le 1er bump>` puis recommit et
  `push --force-with-lease` — `dev` n'est pas protégée et le force-push y est
  déjà le geste normal après chaque squash. Ne **jamais** empiler un second bump
  quand le lot repart : la version intermédiaire n'atteindra jamais la
  production et l'historique annoncera un déploiement qui n'a pas eu lieu
  (PR #297, 11/08/2026 — v2.49.1 jamais servie).
- **16** → il ne mesure rien lui-même : il **lit la trace** que `rejouer-ci.sh`
  écrit dans `.git/rejeu-ci.ok`, et qui porte le commit couvert. Une trace d'un
  autre commit rend INCONNU — sinon un lot hériterait du vert du lot précédent.

  ```bash
  bash rejouer-ci.sh
  ```

  Le script **extrait** les commandes de `.github/workflows/ci.yml` ; il n'en
  tient aucune liste, parce qu'une seconde liste divergerait au premier job
  ajouté — et c'est le job ajouté qu'on oublie de rejouer. Environ une minute.
  Il rend compte de trois genres d'étapes : les **contrôles** (exécutés), les
  **installations** (affichées, jamais exécutées — elles écraseraient
  l'environnement du poste), et les **non rejouables** (INCONNU). Une étape dont
  l'outil manque sur le poste est requalifiée en INCONNU, jamais en échec.

  Pourquoi ce point existe : le 12/08/2026, pytest, svelte-check, le build, les
  six lints du front et les self-tests avaient tous été rejoués à la main — le
  seul job non lancé, Ruff, est le seul qui a échoué (#319). La consigne de tout
  rejouer existait déjà, avec sa commande d'extraction ; rien ne forçait à
  l'exécuter, rien ne constatait qu'on l'avait fait.

  Un seul job : `bash rejouer-ci.sh build-frontend` — utile en cours de
  correction, mais **aucune trace n'est écrite** et le point 16 reste INCONNU.
- **INCONNU** → le contrôle n'a **pas pu** mesurer. Ce n'est jamais un vert. Le
  script sort en 2 au-delà d'un seul INCONNU.
- **Point 9 est INCONNU par construction** : l'historique des e-mails s'interroge
  in-process (`GET /admin/emails/historique`) et exige une session admin. Le
  vérifier à la main dans **Admin → E-mails → Historique**, filtre `erreur`,
  7 jours. Repli quand le standby est au repos : voir `HISTORIQUE.md`.

### Avant même le script — les deux exigences hors machines

| # | Exigence | Automatisé par |
|---|---|---|
| 0c | **Autorisation centralisée**, aucun passe-droit | `api/tests/test_autorisation.py` |
| 0d | **Factorisation** — aucun code spécifique ne réimplémente une bibliothèque partagée | `test_dates_fr.py`, `npm run lint:dates`, `lint:notifications` |
| 0e | **Documentation à jour** — manuel, README, `specs/` | `api/tests/test_documentation.py` (partie mécanique) |

**Protocole si anomalie** : diagnostiquer → proposer un plan → corriger après
validation → relancer le script → livrer seulement si tout est vert.

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
| P11 | **Clore les tickets du lot** — après P7, jamais avant | `gh issue close <n> --comment "…"` avec la preuve observée | Chaque ticket du lot est clos **ou** dit ce qu'il attend encore |

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

**P11 — clore les tickets, et surtout pas par mot-clé GitHub (11/08/2026).**
Écrire `Closes #299` dans le corps d'une PR fait fermer le ticket **au merge**.
C'est la mauvaise date : ce soir-là, #299 aurait été clos pendant qu'une
régression était en vol — quatre colonnes disparues de l'écran, trouvées par
l'utilisateur *après* la fusion. Et le matin même, un merge avait livré un
`check-reliability.sh` incapable de démarrer. **Fusionner n'est pas déployer,
déployer n'est pas vérifier.**

Un ticket se ferme quand le comportement qu'il décrit est **observé corrigé en
production** — donc après P7, et avec la preuve dans le commentaire :

```bash
gh issue close 299 --comment "Vérifié en production après la MEP v2.52.2 : <ce qui a été observé, et comment>."
```

Un ticket dont la vérification est **différée** (elle dépend d'un événement à
venir : un passage hebdomadaire, une bascule) **reste ouvert**, et reçoit un
commentaire disant ce qu'il attend et à quelle date. Le fermer « parce que le
code est livré » revient à confondre le correctif et sa preuve.

Le corps de la PR continue de **nommer** les tickets en français (« Ferme #299 »)
— c'est de la lisibilité pour le relecteur, pas un mécanisme. À ne pas confondre :
le français n'est pas reconnu par GitHub, donc cette mention ne ferme rien, et
c'est très bien ainsi. Les tickets **ouverts** par le lot se listent aussi, pour
qu'un relecteur voie ce qui a été découvert sans être traité.

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


