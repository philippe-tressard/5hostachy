# CLAUDE.md — 5Hostachy

Règles de développement à appliquer dans toutes les sessions sur ce projet.

## Principe fondamental

Avant toute implémentation : **grep le pattern existant**. Si le pattern existe ≥ 2 fois → l'appliquer à l'identique. Si une demande contredit un pattern établi → signaler le conflit et demander confirmation.

Les références canoniques sont dans `.github/skills/`.

---

## Stack

- **Backend** : FastAPI + SQLModel + SQLite WAL + Alembic (`api/`)
- **Documents imprimables** : HTML/CSS → PDF via WeasyPrint (libs système dans `api/Dockerfile`)
- **Frontend** : SvelteKit v2 + TypeScript strict + Vite + PWA (`front/`)
- **Infra** : Docker Compose + Caddy + Raspberry Pi 5
- **Langue** : français exclusif (interface + nommage des champs)

---

## Patterns UX établis

### Carte expansible
- **Une seule** carte ouverte à la fois : `expandedItems = new Set([id])`
- Méta (lieu, périmètre, auteur) : toujours visible en état collapsé ET expandé
- Prévisualisation : `.clamp-5` (5 lignes max, `-webkit-line-clamp: 5`)
- `role="button"` + `tabindex="0"` + `on:keydown` (Enter/Space) obligatoires
- `on:click|stopPropagation` sur les actions secondaires dans le corps
- Border-left : `var(--color-border)` → `var(--color-primary)` au hover/expand
- Urgence : `border-left-color: var(--color-danger)` — **jamais de badge texte 🚨**

### Vignette & galerie de photos
- Vignette carrée : `$lib/components/Vignette.svelte` (`src`, `alt`, `placeholder`, `count`, `size`, slot d'actions)
- Galerie éditable : `$lib/components/PhotosUpload.svelte` (`urls`, `max`, `readonly`, `upload`, `remove`)
  — le téléversement est délégué par callback, chaque rubrique garde son endpoint
- Utilisés par la Communauté (petites annonces) et les Annonces Hall
- **Ne pas recréer** de `.xxx-thumb` ni de rangée de photos ad hoc

### Icônes de contexte
- 📍 = lieu physique (adresse, salle) — texte inline, pas de badge
- 🔹 = périmètre logique (Parking, Bât.) — badge `.badge-gray` ou `.badge-blue`
- **Ne jamais mélanger** les deux

### Périmètre
- Ne pas afficher si valeur = `'résidence'`
- Séparateur multi-périmètre : ` · ` (espace · espace)
- Labels : `'résidence'→'Copropriété entière'`, `'bat:1'→'Bât. 1'`, `parking→'Parking'`, `cave→'Cave'`

### Ligne de publication
Ordre : `[📌 coin absolu] [Brouillon?] Titre [Statut] [🔹 Périmètre]`
Badges **toujours après** le titre, jamais avant.

### Onglets (Tabs)
- `role="tablist"` sur le conteneur, `role="tab"` sur chaque bouton
- CSS : `.tabs` + `.tabs button.active`
- **Ne jamais** utiliser le pattern `view-toggle` / `view-btn` (supprimé)

### Pill buttons
- `≤ 8 options`, libellés courts, `type="button"` obligatoire
- Classes : `.perimetre-pills`, `.pill`, `.pill-active`

### Visibilité Kanban (calendrier + widget dashboard)

Filtre colonnes : `if (col.id === 'ag' || col.id === 'cs') return canSeeAG;`

| Colonne     | Locataire        | Copropriétaire   | CS / Admin  |
| ----------- | ---------------- | ---------------- | ----------- |
| AG          | ✗                | ✓                | ✓           |
| CS          | ✗                | ✓                | ✓           |
| Syndic      | ✓                | ✓                | ✓           |
| Prestataire | ✓                | ✓                | ✓           |
| Terminé     | ✓ (affichables)  | ✓ (affichables)  | ✓ (tout)    |
| Annulé      | masqué dashboard | masqué dashboard | masqué      |

Items non-affichables : masqués aux non-CS/admin (sauf `maintenance_recurrente`).

### Archiver vs Supprimer
- Archiver (📦) : CS + admin → `PATCH { archivee: true }` — vue principale
- Supprimer (🗑️) : admin seul → `DELETE` — vue Archives uniquement
- Jamais de bouton Supprimer sur la vue principale

### Champs de formulaire
- Requis : label suivi de ` *` (`Titre *`)
- Pas de mention "(optionnel)" — l'absence de `*` suffit
- Actions : bouton secondaire/Annuler **à gauche**, action primaire **à droite**

---

## Conventions Svelte / TypeScript

### Imports standard d'une page
```svelte
<script lang="ts">
    import Icon from '$lib/components/Icon.svelte';
    import { onMount } from 'svelte';
    import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
    import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
    import { safeHtml } from '$lib/sanitize';
    import { toast } from '$lib/components/Toast.svelte';
</script>
```

### Sécurité XSS — OBLIGATOIRE
```svelte
<!-- INTERDIT -->
{@html contenu}

<!-- CORRECT -->
{@html safeHtml(contenu)}
```
Seule exception : `Icon.svelte` (SVG hardcodé côté serveur).

### Accessibilité
- `role="button"` + `tabindex="0"` + `on:keydown` sur éléments cliquables non-`<button>`
- `role="tablist"` / `role="tab"` sur les onglets
- `aria-modal="true"` + `role="dialog"` sur les modales
- `aria-label` + `title` sur tous les boutons icône-seule

### Variables CSS disponibles
```css
var(--color-primary)        /* Bleu Seine #1E3A5F */
var(--color-primary-light)  /* Bleu clair fond */
var(--color-danger)         /* Rouge urgence/erreur */
var(--color-success)        /* Vert */
var(--color-warning)        /* Orange */
var(--color-border)
var(--color-text)
var(--color-text-muted)
var(--color-bg)
var(--color-surface)
var(--radius)
var(--shadow)
```

### Helpers de formatage (à réutiliser)
```typescript
fmtDate(d: string)          // DD Mon YYYY
fmtDateHeure(d: string)     // DD Mon YYYY HH:mm
perimetreLabel(items)       // 'bat:1,parking' → 'Bât. 1 · Parking'
renderDesc(c: string)       // texte ou HTML → HTML sanitisé
```

### Emojis non-BMP (U+10000+)
```typescript
// JS/TS : encoder \u{HEX}
const icon = '\u{1F6E0}'; // 🔧

// HTML/Svelte template : encoder &#xHEX;
// &#x1F539; pour 🔹
```

---

## Conventions Backend (Python / FastAPI)

### Modèle SQLModel
- `__tablename__` = snake_case français
- Champs en français snake_case : `statut_validation`, `date_debut`
- Timestamps : suffixe `_le` → `cree_le`, `mis_a_jour_le`
- FK : `{modele}_id = Field(default=None, foreign_key="table.id")`
- Soft delete : `actif: bool = Field(default=True)` (pas de suppression physique sauf admin)
- Enums : `class MonEnum(str, Enum)` → slugs français lowercase

### Schémas Pydantic (3 par entité)
- `EntiteCreate` : champs d'entrée, pas d'id ni timestamps
- `EntiteRead` : sortie complète avec id + timestamps, `class Config: from_attributes = True`
- `EntiteUpdate` : tous les champs `Optional` pour PATCH partiel

### Migrations Alembic
- ID séquentiel 4 chiffres : `0087`, `0088`…
- **Jamais** modifier une migration existante — créer une nouvelle
- **Jamais** de f-string dans `op.execute()` → `text(...).bindparams(...)`
- SQLite : pas de `ALTER TYPE`, pas de `CREATE TYPE`
- `start.sh` a `set -e` : une migration qui crash = conteneur bloqué

### Dépendances d'auth
| Dependency | Usage |
|-----------|-------|
| `get_current_user` | Tout utilisateur connecté |
| `require_cs_or_admin` | Création/modification de contenu |
| `require_admin` | Suppression définitive, config système |
| `require_proprietaire` | Fonctions propriétaires |
| `get_acting_user` | Délégation (header `X-Acting-As`) |

### Documents imprimables (PDF)
- Thème commun : `app/utils/pdf_theme.py` — logo, palette de la charte, data-URI (image/QR), `html_to_pdf()`.
  **Ne jamais** redéfinir une palette, un logo ou un moteur PDF ailleurs.
- Le HTML doit être **autonome** : CSS dans `<style>`, images en data-URI (rendu hors requête HTTP).
- Format de page via `@page { size: A4|A5 }`. Pas d'emoji dans les affiches — logo SVG et aplats de couleur.
- Documents existants : fiche arrivant (`fiche_arrivant.py`), annonce de hall (`annonce_hall.py`).

### Destinataires CS
- `app/utils/destinataires.py` est la source unique : `membres_cs_notifiables(session, batiment_ids)`
  (membres du CS liés à un compte actif + gestionnaire du site, dédoublonnés) et
  `batiments_du_perimetre()` (résidence/parking/cave/AFUL = tout le CS).
- À distinguer de `envoyer_cs` (publications/sondages/calendrier) qui vise **le rôle**
  `conseil_syndical`, sans notion de périmètre.

### Sécurité
- JWT HS256 en cookies `httponly=True`, `secure=settings.cookie_secure`, `samesite="strict"`
- CORS : allowlist explicite, jamais `["*"]` avec `credentials=True`
- Rate limiting slowapi sur `/auth/*`
- Uploads : UUID-prefix + `os.path.basename()` + `re.sub(r"[^\w.\-]", "_", ...)`

---

## Checklist avant commit

### Frontend
- [ ] Pattern existant réutilisé (pas de variante ad hoc)
- [ ] Méta toujours visible en mode collapsé
- [ ] `.clamp-5` sur les aperçus
- [ ] `safeHtml()` sur tout `{@html}`
- [ ] Accessibilité : `role`, `tabindex`, `aria-label`, `on:keydown`
- [ ] Périmètre : pas affiché si `'résidence'`
- [ ] Archiver (pas supprimer) sur la vue principale
- [ ] Champs requis : label + ` *`

### Backend (nouveau endpoint)
- [ ] Modèle dans `models/core.py`
- [ ] Schémas Create/Read/Update dans `schemas.py`
- [ ] Migration créée avec bon numéro séquentiel
- [ ] Router créé + enregistré dans `main.py`
- [ ] Client TypeScript ajouté dans `front/src/lib/api.ts`

### Manuel utilisateur
- [ ] `docs/manuel-utilisateur.html` mis à jour dans le même commit
- [ ] Synchronisé : `Copy-Item docs/manuel-utilisateur.html front/static/manuel-utilisateur.html`

### Tests préventifs (CI : `api/tests/`, lancés à chaque PR)
Garde-fous contre les classes d'erreurs récurrentes de l'historique GitHub :
- **`test_email_templates.py`** — verrouille les variables Jinja2 de chaque template
  (`EXPECTED_VARS`). Complète le **point 9** (réactif) côté template.
  ⚠️ Si tu modifies les variables d'un template (`seed.EMAIL_TEMPLATES`), **mets à jour
  `EXPECTED_VARS`** ET vérifie que le `send_email(code=...)` correspondant fournit ces
  variables — sinon échec silencieux à l'envoi (cf. bug `'destinataire' is undefined`).
- **`test_migrations.py`** — chaîne Alembic : head unique, base unique, révisions uniques
  (attrape un `down_revision` erroné qui bloquerait `alembic upgrade head` au démarrage).
- Lancer en local (deps requises) : `cd api && pytest tests/ -q`.

---

## Infrastructure & Monitoring

### Serveurs
- **RPi 1** `192.168.1.222` (PhT-RB5) · **RPi 2** `192.168.1.223` (PhT-RB5i2)
- RPi actif : `cat /opt/5hostachy/.active` — ⚠️ ce fichier peut disparaître, le recréer si absent
- Conteneurs uniquement sur le RPi actif — vérifier les 2 en cas de doute (`docker ps`)
- En cas de split-brain (conteneurs sur les 2) : stopper le standby + recréer `.active`
- En cas de site HS : SSH sur le RPi actif → `cd /opt/5hostachy && docker compose up -d`

### Protections DB (v2.18.10)
- `stop_grace_period: 30s` sur le service API → Docker attend 30s avant SIGKILL
- `PRAGMA wal_checkpoint(TRUNCATE)` dans le lifespan shutdown → WAL vidé proprement à chaque arrêt
- `bascule.sh` phase 3 : WAL checkpoint avant rsync DB vers le peer
- `MaJ-Hostachy.sh` : bloque si lancé sur le RPi standby
- `synchronous=FULL` (v2.20.3) : chaque commit fsync'd intégralement (anti torn-write)
- `health_check` 06:00 + chaque backup : `PRAGMA quick_check` → alerte / backup annulé si corrompu
- `maintenance.sh` VACUUM : **API stoppée** (base au repos, 0 writer) puis `sqlite3` hôte

### ⚠️ Règle d'or anti-corruption DB (v2.20.3 · durcie 17/07/2026)
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

### Risques connus
- **Build OOM** : `npm run build` peut saturer la RAM du RPi → préférer `--nocache` en cas de build lourd
- **health-watch failover** → peut créer un split-brain ; toujours vérifier `docker ps` sur les 2 RPi
- **Sauvegardes** stockées uniquement sur le RPi actif (volume Docker non répliqué)
- **`.active` peut disparaître** → le recréer manuellement sur les 2 RPi si absent

### Sync DB manuelle (sans basculer)
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

### Crontabs (sudo root — identiques sur les 2 RPi)
```
0 2 * * *   bascule.sh        # bascule active/standby
0 3 * * 0   maintenance.sh    # purge, VACUUM, rotation logs (dimanche)
*/5 * * * * health-watch.sh   # failover automatique si site HS
```

### Monitoring APScheduler (tourne dans le conteneur API)
| Heure | Job | Alerte email si… |
|-------|-----|-----------------|
| 03:00 | backup | — |
| 06:00 | **health_check** | WhatsApp déconnecté · backup > 25h · disque < 15% |
| 18:00-21:45 (`*/15`) | whatsapp_scheduled | Fenêtre de rattrapage épuisée sans envoi réussi |
| 02:00 | telemetry_aggregation | — |

### WhatsApp bridge
- Reconnexion QR : Admin → WhatsApp → **bouton Statut** (affiche le QR si déconnecté)
- Session corrompue (`creds.json` vide) : vider le volume + redémarrer le bridge
  ```bash
  docker run --rm -v 5hostachy_whatsapp_auth:/data alpine sh -c 'rm -rf /data/*'
  cd /opt/5hostachy && docker compose up -d whatsapp-bridge
  ```
- `bascule.sh` ne propage jamais un `creds.json` vide vers le peer

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

---

## Git & MEP

### ⚠️ Se resynchroniser AVANT de committer (obligatoire)

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

### Pré-check obligatoire avant MEP

Avant toute MEP, Claude vérifie les points suivants. Si une anomalie est détectée → diagnostic + plan proposé → correction si validée par l'utilisateur → reprise de la MEP.

| # | Vérification | Commande | Attendu |
|---|---|---|---|
| 1 | Site public | `curl https://5hostachy.fr/api/health` | HTTP 200 |
| 2 | RPi actif identifié | `cat /opt/5hostachy/.active` sur les 2 | Fichier présent, cohérent |
| 3 | Pas de split-brain | `docker ps -q --filter name=hostachy \| wc -l` sur les 2 RPi | 0 sur le standby (exclut l'appli co-hébergée List-dons) |
| 4 | DB saine | ⚠️ **PAS de `docker exec` !** Voir « Point 4 » ci-dessous | `mtime` récent · 0 inode fantôme · 0 `disk I/O error` |
| 5 | WhatsApp | `GET /status` bridge | `state: open` |
| 6 | Erreurs API | `docker logs --since 1h` | Aucune ERROR/CRITICAL |
| 7 | Droits scripts cron | `ls -la /opt/5hostachy/*.sh` sur les 2 RPi | Bit `x` (`-rwxr*`) sur tous les `.sh` lancés par cron |
| 8 | Logs cron sans échec récent | `tail -20 /var/log/hostachy-{deploy,bascule,health-watch,maintenance,check}.log` sur les 2 RPi | Aucune ligne `Permission denied` / `No such file` / `command not found` / erreur répétée |
| 9 | Emails sans échec récent | ⚠️ **PAS de `docker exec` !** Admin → Emails → Historique (filtre `erreur`, 7 j) | 0 ligne |
| 10 | Parité de code RPi actif ⇆ standby | `git -C /opt/5hostachy rev-parse HEAD` sur les 2 RPi | HEAD **identique** sur les 2 |
| 11 | Auto-deploy de l'actif vivant | Sur l'**actif** : `stat -c %U /var/log/hostachy-deploy.log` + HEAD actif vs `origin/main` | Log **`ptressard`** (pas `root`) · HEAD actif **==** `origin/main` |
| 12 | Image en cours = code déployé (pas seulement git à jour) | Sur l'actif : `docker inspect hostachy_api --format '{{.Created}}'` ≥ date du commit HEAD ; en cas de doute `docker exec hostachy_api grep -c <marqueur-du-dernier-fix> /app/...` | Image reconstruite **après** le dernier commit servi (pas d'image périmée) |

> ### 🚨 Points 4 et 9 — ce pré-check contenait lui-même l'opération interdite
> Jusqu'au 17/07/2026, le point 4 disait `PRAGMA integrity_check` et le point 9 fournissait une
> commande `docker exec -w /app hostachy_api python3 -c "from app.database import engine …"`.
> **Exécuter ces commandes pendant que l'API tourne casse la base** (unlink du WAL sous le pool
> → `disk I/O error` → pertes de données). C'est exactement ce qui s'est produit le 17/07.
> Le pré-check ne doit **jamais** ouvrir `app.db`. Cf. « Règle d'or anti-corruption DB ».

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

**Point 9 — pourquoi :** les emails partent en `BackgroundTask` et échouent **silencieusement** — l'erreur n'apparaît que dans la table `historique_email`, jamais dans les logs API ni à l'écran. La même cause racine (un template Jinja2 référence une variable absente du contexte du point d'appel → `UndefinedError`) s'est produite deux fois en 12 jours : `reinitialisation_mdp` le 03/06 (`destinataire.prenom` manquant) puis `ticket_statut_change` le 15/06 (même variable). Dans les deux cas, découvert seulement après un signalement utilisateur « je ne reçois pas mes mails ». Comme le point 8, ce point lit **le symptôme** quelle qu'en soit la cause (contexte template, SMTP HS, adresse invalide, domaine `.local` filtré…). Si une ligne `erreur` apparaît → ouvrir le template et le contexte du point d'appel (`send_email(code=...)`), vérifier que toute variable `{{ x.y }}` du template est fournie ; aligner sur un template voisin qui fonctionne (ex. `verification_email`).

**Point 10 — pourquoi :** `auto-deploy.sh` ne tourne que sur le RPi **actif** (il fait `docker compose up -d` → l'exécuter sur le standby créerait un split-brain). Le code du standby ne suit donc jamais `main` : il dérive derrière la DB. Le 16/06/2026, l'actif (rpi2) avait appliqué la migration `0111` ; la bascule nocturne a poussé cette DB vers rpi1 dont le code était resté à `0110` → `alembic upgrade head` au démarrage = `Can't locate revision identified by '0111'` → `start.sh` (`set -e`) → API en crash-loop → timeout phase 5 → bascule annulée. Correctif pérenne : `bascule.sh` phase 0 resynchronise le code du peer sur le commit de l'actif (`git reset --hard` + rebuild) **avant** toute opération destructive, et avorte proprement (prod intacte) si la resync échoue. Ce point 10 est le garde-fou amont : si les 2 HEAD diffèrent avant une MEP → resynchroniser le standby (`ssh <standby> 'cd /opt/5hostachy && git fetch origin main && git reset --hard origin/main && docker compose build'`, **sans** `up -d`).

**Point 11 — pourquoi :** `auto-deploy.sh` est le **seul cron utilisateur** (`ptressard`) ; tous les autres crons tournent en root. Or `/var/log` est `root:root` : si `hostachy-deploy.log` devient root-owned, la redirection `>> /var/log/hostachy-deploy.log` du cron user échoue en `Permission denied` et **cron n'exécute même pas le script** → l'actif cesse de se déployer **silencieusement**. Découvert le 15/07/2026 : rpi1 bloqué à v2.20.7 malgré 3 merges, chaque MEP exigeant un `bash auto-deploy.sh` manuel — invisible au point 8 (aucun log produit = angle mort). Cause structurelle : `maintenance.sh` (root, dimanche) faisait `mv .tmp log` → repassait le log root-owned **chaque semaine**, cassant le cron user de façon permanente après la 1ʳᵉ rotation. Corrigé (v2.20.10) : `chown 1000:1000` du log après rotation dans `maintenance.sh` (self-healing sur les 2 RPi) + contrôle automatisé **C13** dans `check-reliability.sh` (cron */15). Au pré-check : si le log est root-owned → `sudo chown ptressard:ptressard /var/log/hostachy-deploy.log` ; si HEAD actif ≠ `origin/main` alors que `dev` est mergé → auto-deploy ne tourne pas, diagnostiquer (ownership du log en premier) **avant** MEP.

**Point 12 — pourquoi :** le point 10 vérifie que le **git** du RPi est à jour, mais **la parité de HEAD ne garantit PAS que l'image Docker en cours a été construite depuis ce commit**. Le 18/07/2026, après la bascule nocturne rpi1 → rpi2, rpi2 était à jour côté git (`1211767`) mais son **image API datait du 16/07** (rebuild sauté par `bascule.sh` phase 0, qui ne rebuildait que si les HEAD différaient) → le conteneur servait l'ancien `flux.py` sans le filtre `_is_archived` (fix v2.20.16) → le bug de la publication épinglée résolue **réapparaissait** au tableau de bord. Diagnostic (lecture seule, **ne touche pas `app.db`**) : `docker inspect hostachy_api --format '{{.Created}}'` antérieur au dernier commit servi = image périmée ; confirmer avec `docker exec hostachy_api grep -c <marqueur> /app/...` vs le même `grep` sur `/opt/5hostachy/...` (disque). Remédiation (réversible, cycle standard, **pas** une violation de la règle d'or) : `cd /opt/5hostachy && docker compose build <svc> && docker compose up -d <svc>`. Correctif pérenne (v2.20.19) : `bascule.sh` phase 0 rebuild **toujours** l'image du peer, même à git égal (cache Docker → quasi instantané si rien n'a changé). Cf. [[project_bascule_image_stale]]. Ce point sert aussi de **contrôle post-MEP**.

**Protocole si anomalie :**
1. Diagnostiquer la cause
2. Proposer un plan de correction à l'utilisateur
3. Corriger après validation
4. Relancer le pré-check complet
5. MEP uniquement si tous les points sont verts

### Versioning (`front/package.json`)
Version affichée dans le footer du site. Règle **obligatoire à chaque MEP** :

| Incrément | Quand |
|-----------|-------|
| **Patch** `X.Y.Z+1` | Fix, correction, amélioration mineure, doc, refactor interne |
| **Minor** `X.Y+1.0` | Nouvelle fonctionnalité visible par les utilisateurs |
| **Major** `X+1.0.0` | Refonte majeure de l'interface ou rupture de compatibilité |

- Toujours bumper **avant** le push final sur `dev`
- Commit dédié : `chore(version): bump vX.Y.Z`
- Version courante : voir `front/package.json`
