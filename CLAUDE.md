# CLAUDE.md — 5Hostachy

Règles de développement à appliquer dans toutes les sessions sur ce projet.

## Principe fondamental

Avant toute implémentation : **grep le pattern existant**. Si le pattern existe ≥ 2 fois → l'appliquer à l'identique. Si une demande contredit un pattern établi → signaler le conflit et demander confirmation.

Les références canoniques sont dans `.claude/skills/` (voir le tableau ci-dessous).

---

## Stack

- **Backend** : FastAPI + SQLModel + SQLite WAL + Alembic (`api/`)
- **Documents imprimables** : HTML/CSS → PDF via WeasyPrint (libs système dans `api/Dockerfile`)
- **Frontend** : SvelteKit v2 + TypeScript strict + Vite + PWA (`front/`)
- **Infra** : Docker Compose + Caddy + Raspberry Pi 5
- **Langue** : français exclusif (interface + nommage des champs)

---

## Consignes chargées à la demande

Ce fichier ne porte que ce qui doit être vrai **en permanence**. Le détail vit dans
`.claude/skills/`, découvert automatiquement par Claude Code et chargé **seulement
quand la tâche le demande** — ouvrir la skill *avant* d'agir, jamais après.

| Tâche | Skill à charger |
|---|---|
| MEP, déploiement, pré-check, post-check, rollback | `.claude/skills/mep-precheck` |
| Infra, bascule, RPi, base, WhatsApp, monitoring, incident | `.claude/skills/infra-rpi` |
| Écran, composant, libellé, pattern d'interface | `.claude/skills/ux-patterns` |
| Page ou composant SvelteKit, store, appel API côté front | `.claude/skills/svelte-patterns` |
| Nouveau modèle, schéma, router, migration | `.claude/skills/api-scaffold` |
| Auth, droits, secrets, exposition publique | `.claude/skills/security-audit` |
| Documentation utilisateur — manuel **et** `README.md` | `.claude/skills/user-manual` |

Les bonnes pratiques **génériques** — valables pour un autre projet — sont dans le
socle `~/.claude/standards/`. Ce fichier-ci ne contient que leur **instanciation
5Hostachy** : chemins, seuils, commandes.

> 📖 **Routage du socle : `~/.claude/CLAUDE.md` §1** (source unique, déjà en contexte
> — quel standard charger avant quelle tâche). Mode d'emploi, règle de placement et
> entretien : `standards/INDEX.md`. Une règle générique ne se recopie **jamais** ici :
> elle s'écrit dans le socle et bénéficie alors aux quatre projets.

---

## 🚨 Règle d'or anti-corruption DB — ne dépend d'aucun chargement à la demande

**Ne JAMAIS ouvrir `app.db` depuis un process tiers tant que l'API tourne — même en
lecture seule.** `docker exec … PRAGMA` et `sqlite3` hôte sont **interdits** : le
process tiers se croit dernière connexion, `unlink` le WAL sous le pool SQLAlchemy,
et l'API écrit ensuite dans des inodes orphelins → `disk I/O error`, 503, puis
**perte des données** au prochain arrêt. À chaud, passer par les endpoints
in-process : `POST /admin/db/checkpoint`, `GET /admin/db/integrite`. VACUUM, copie ou
swap de fichier → **stopper l'API d'abord** (0 writer).

Signature de diagnostic, conduite à tenir et historique des trois incidents :
`.claude/skills/infra-rpi`.

> 📖 `standards/06-donnees-et-integrite.md` §1 — le principe généralisé à **tout état
> multi-fichiers qu'un processus tient ouvert**, pas seulement une base : il s'est
> reproduit à l'identique sur l'état d'authentification WhatsApp (24/07/2026).

---

## Front — les quatre règles qui ne se négocient pas

Le détail des patterns est dans `.claude/skills/ux-patterns` et
`.claude/skills/svelte-patterns` — les charger avant d'écrire un écran.

> 📖 `standards/11-interface-et-ux.md` (un pattern par notion, accessibilité,
> formulaires, archiver ≠ supprimer) · `standards/03-securite.md` §4 (assainissement)
> · `standards/02-factorisation.md` §2 (pourquoi dates et montants sont les deux
> récidivistes de la duplication).

1. **XSS** : jamais `{@html contenu}`, toujours `{@html <assainisseur>(contenu)}`.
   Ils sont **trois**, tous exportés par `$lib/sanitize.ts` et tous adossés à
   DOMPurify : `safeHtml` (HTML riche), `safeRichContent` (riche ou texte, **sans**
   enveloppe — appelé à l'intérieur d'un `<p>`), `safeDescription` (idem, **avec**
   enveloppe `<p>`). Cette règle ne nommait que le premier alors que les trois
   étaient en service : c'est ce qui a fait croire à 19 écarts qui n'en étaient pas
   (#429).

   🔒 **Garde-fou : `npm run lint:html`** (`front/scripts/check-html.mjs`), en CI
   depuis le 18/08/2026. Il lit la liste des assainisseurs **dans `sanitize.ts`** —
   une liste recopiée diverge au premier ajout — et exige que le nom vienne de
   l'**import**, pas de la portée du fichier : une fonction locale homonyme qui ne
   ferait rien passerait sinon. C'est ainsi qu'a été trouvée `renderContent`
   (`tickets/[id]`), copie littérale de `safeDescription`, correcte par chance.

   **Deux** exceptions, et deux seulement — relevées par l'audit du 18/08/2026,
   qui en a trouvé une non déclarée ; elles sont **déclarées dans le contrôle**
   (`EXCEPTIONS`), qui échoue si l'une d'elles cesse de servir :
   - `Icon.svelte` — SVG codé en dur côté serveur ;
   - `QRCode.svelte` — SVG produit **localement** par `qrcode-generator` à partir
     d'une donnée encodée en modules, jamais interpolée dans le balisage.

   ⚠️ Une exception non écrite n'est pas une exception, c'est un oubli qui
   ressemble à une décision. Toute nouvelle exception s'ajoute **ici** avec sa
   raison, sinon la règle devient « sauf quand on a jugé que ça allait ».
2. **Dates et montants** : ne jamais réimplémenter un format dans une page.
   `$lib/date.ts` (`fmtDate`, `fmtDatetime`, `fmtMonthYear`…), `$lib/utils.ts`
   (`fmtMontant`, `perimetreLabel`), et côté API `app/utils/dates_fr.py`. Deux
   garde-fous échouent en CI : `api/tests/test_dates_fr.py` et `npm run lint:dates`.
3. **Accessibilité** : tout élément cliquable non-`<button>` porte `role="button"`,
   `tabindex="0"` et `on:keydown` (Enter/Space) ; `aria-label` sur les boutons
   icône-seule ; `role="dialog"` + `aria-modal="true"` sur les modales.
4. **Icônes de contexte** : 📍 = lieu physique, 🔹 = périmètre logique — **jamais
   mélangés**, et le périmètre n'est pas affiché quand il vaut `'résidence'`.

---

## Conventions Backend (Python / FastAPI)

> 📖 `standards/06-donnees-et-integrite.md` §3 (migrations : chaîne linéaire, jamais
> de f-string SQL, le code et le schéma voyagent ensemble) et §4–5 (suppression
> logique, montants en entiers) · `standards/03-securite.md` §1–5 (autorisation
> centralisée, liste blanche, entrées/sorties, session et transport).

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

`app/utils/destinataires.py` est la source unique, et elle porte **deux règles
distinctes** — les confondre envoie le bon message aux mauvaises personnes :

| Ce qu'on vise | Fonction | Employée par |
|---|---|---|
| le CS **concerné par un périmètre** | `membres_cs_notifiables(session, batiment_ids)` (+ `batiments_du_perimetre()`) | nouvel arrivant, annonces de hall |
| le CS **par le rôle**, sans périmètre | `membres_cs_avec_email(session)` | publications, sondages, calendrier, tickets |
| le **syndic principal** | `syndic_principal(session)` | ci-dessous, fiche copropriété, arrivants |
| **syndic puis CS, dédoublonnés** — qui reçoit un e-mail interne | `destinataires_syndic_cs(session, syndic=…, cs=…)` | les quatre entités qui cochent « envoyer au syndic / au CS » |

🔴 La dernière ligne a existé en **quatre exemplaires identiques** (tickets,
calendrier, publications, sondages) jusqu'au 31/08/2026 — et celui des tickets
affirmait, en toutes lettres, être *« le seul endroit où cette règle s'écrit »*.
Les trois autres n'avaient aucun commentaire : le seul fichier qui parlait du
sujet disait que le problème n'existait pas.

🔒 `api/tests/test_destinataires_source_unique.py` refuse une cinquième copie. Il
laisse passer les notifications **in-app**, qui visent « CS **ou** admin » et
rendent des `Utilisateur` — autre décision, autre destinataire.

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
- [ ] un assainisseur de `$lib/sanitize` sur tout `{@html}` — jamais un helper
      local, même correct (`npm run lint:html` le refuse)
- [ ] Accessibilité : `role`, `tabindex`, `aria-label`, `on:keydown`
- [ ] Périmètre : pas affiché si `'résidence'`
- [ ] Archiver (pas supprimer) sur la vue principale
- [ ] Champs requis : label + ` *`
- [ ] Tout champ libellé dans un `.field` — jamais une nomenclature locale
      (`npm run lint:champs` ; il y en avait **six** avant #413)

### Backend (nouveau endpoint)
- [ ] Modèle dans `models/core.py`
- [ ] Schémas Create/Read/Update dans `schemas.py`
- [ ] Migration créée avec bon numéro séquentiel
- [ ] Router créé + enregistré dans `main.py`
- [ ] Client TypeScript ajouté dans `front/src/lib/api.ts`

### Documentation utilisateur — **deux** documents de même rang
- [ ] `docs/manuel-utilisateur.html` — **comment on s'en sert** : mis à jour dans le
      même commit dès qu'un écran, un libellé, un geste ou un parcours change
- [ ] Synchronisé : `Copy-Item docs/manuel-utilisateur.html front/static/manuel-utilisateur.html`
- [ ] `README.md` — **ce que le produit est** : mis à jour dès qu'un module, un écran
      de premier niveau ou une capacité est **ajouté, retiré ou renommé**, que la pile
      change, ou qu'un document du tableau `docs/` bouge
- [ ] Un lot qui ne touche qu'un seul des deux, c'est possible — mais on **dit** lequel
      et pourquoi, on ne l'omet pas en silence

> ⚠️ Le manuel ne se modifie **jamais** avec `sed -i` : il est versionné en CRLF, que
> `sed` réécrit en LF — le diff passe de 3 lignes à 5 700. Vérifier `git diff --stat`.
>
> Le README était vérifié par personne alors que le point **0e** du pré-check le nomme
> depuis toujours au même rang que le manuel : cette checklist-ci ne citait que le
> manuel, et c'est la liste la plus courte qui a été suivie (11/08/2026, signalé par
> l'utilisateur). Détail et déclencheurs : `.claude/skills/user-manual`.

### Tests préventifs (CI : `api/tests/`, lancés à chaque PR)

> 📖 `standards/05-tests-et-garde-fous.md` — pourquoi un défaut corrigé sans garde-fou
> revient (trois récidives en deux mois ici), les quatre familles de garde-fous qui
> marchent, et l'analyse statique quand le couplage entre deux fichiers est implicite.

Garde-fous contre les classes d'erreurs récurrentes de l'historique GitHub :
- **`test_email_templates.py`** — verrouille les variables Jinja2 de chaque template
  (`EXPECTED_VARS`). Complète le **point 9** (réactif) côté template.
  ⚠️ Si tu modifies les variables d'un template (`seed.EMAIL_TEMPLATES`), **mets à jour
  `EXPECTED_VARS`** ET vérifie que le `send_email(code=...)` correspondant fournit ces
  variables — sinon échec silencieux à l'envoi (cf. bug `'destinataire' is undefined`).
- **`test_migrations.py`** — chaîne Alembic : head unique, base unique, révisions uniques
  (attrape un `down_revision` erroné qui bloquerait `alembic upgrade head` au démarrage).
- Lancer en local (deps requises) : `cd api && pytest tests/ -q`.

### Scripts d'infra — job CI `test-scripts` (depuis le 30/07/2026)
Les scripts qui décident d'arrêter la prod (`bascule.sh`, `health-watch.sh`,
`boot-role-guard.sh`, `check-reliability.sh`…) n'étaient couverts par **aucun**
test : ni Python ni Svelte, donc hors de portée des trois autres jobs. Le job
`test-scripts` vérifie à chaque PR la syntaxe (`bash -n`) de tous les `.sh`
versionnés, les modes git (0b), et exécute les **self-tests**.

**Règle pour toute nouvelle logique de décision d'infra** : l'isoler en fonction
**pure** (aucun SSH, docker, écriture ni `sudo`), exposer `--selftest`, et
l'ajouter au job. C'est le seul moyen de tester une décision de bascule sans les
deux RPi — pattern inauguré par `boot-role-guard.sh --selftest` (15/07/2026),
étendu à `health-watch.sh` et `check-reliability.sh` (30/07/2026).
Lancer en local : `bash <script>.sh --selftest`.

### Rejouer la CI en local — `bash scripts/poste/rejouer-ci.sh` (depuis le 13/08/2026)
Les quatre jobs ci-dessus se rejouent en **une minute** sur le poste, sans rien
recopier : le script **extrait** les commandes de `.github/workflows/ci.yml`. Une
liste tenue à la main divergerait au premier job ajouté — et c'est justement le job
ajouté, ou celui qu'on ne pense pas à lancer, qui échoue (#319 : Ruff, le 12/08).
Sa trace (`.git/rejeu-ci.ok`) est lue par le **point 16** du pré-check.
Un seul job : `bash scripts/poste/rejouer-ci.sh build-frontend` — mais alors aucune trace n'est
écrite, et le point 16 reste INCONNU.

---

## Infrastructure — l'essentiel

Production **HA sur 2 Raspberry Pi** : rpi1 `192.168.1.222` (PhT-RB5), rpi2
`192.168.1.223` (PhT-RB5i2). Les conteneurs ne tournent que sur le **RPi actif**
(`cat /opt/5hostachy/.active`) ; des conteneurs sur les deux = **split-brain**, à
traiter avant toute autre chose. Site HS : SSH sur l'actif →
`cd /opt/5hostachy && docker compose up -d`.

> 📇 **Les points d'entrée sont versionnés depuis le 15/08/2026** :
> `infra/points-entree/` porte les crons et l'unité systemd attendus, et le
> **point 17** du pré-check compare l'installé au dépôt. C18 ne compare que les
> nœuds entre eux, donc pas la dérive commune.

| Cron root (identique sur les 2 nœuds) | Rôle |
|---|---|
| `0 2 * * *` `bascule.sh` | bascule active/standby |
| `0 3 * * 0` `maintenance.sh` | purge, VACUUM, rotation des logs |
| `*/5 * * * *` `health-watch.sh` | failover automatique si le site est HS |
| `*/15 * * * *` `check-reliability.sh` | 26 contrôles de fiabilité + alerte e-mail sur `FAIL` |

⚠️ « Identique sur les 2 nœuds » **est un invariant, pas un constat** : il était faux
jusqu'au 06/08/2026, rpi2 portant en plus un `check-stack.sh` qui y échouait 144 fois
par jour. Le vérifier fait partie du point 8 du pré-check. `auto-deploy.sh` (`*/5`) est
à part : c'est le seul cron **utilisateur** (`ptressard`), et c'est ce qui fait
l'objet du point 11.

**Réflexe avant de suspecter un nœud** : depuis l'autre RPi, `curl
http://<actif>/api/health`. S'il répond 200, la panne est sur le **chemin** public
(box, DNS, Cloudflare) et non sur le nœud — ne pas basculer, ne pas redémarrer la
stack.

Toute intervention infra — bascule, base, WhatsApp, incident, coupure de courant,
panne réseau — commence par charger `.claude/skills/infra-rpi` : protections DB,
conduite à tenir en cas de corruption, panne de chemin ≠ panne de nœud, monitoring
APScheduler, bridge WhatsApp, sync DB manuelle et risques connus.

> 📖 `standards/04-fiabilite-des-controles.md` §10 — le réflexe ci-dessus généralisé :
> **deux sondes indépendantes avant toute décision destructive**, pour distinguer la
> panne d'un composant de celle d'une dépendance partagée · `standards/07-observabilite-et-alertes.md`
> §6–8 (rotation par motif, maintenance sur **tous** les nœuds, hygiène surveillée).

---

## Git & MEP — l'essentiel

**Premier réflexe de toute session, avant le moindre commit.** `origin/dev` et
`origin/main` avancent côté GitHub (PR fusionnées, merges `main → dev`) et ne
redescendent **jamais** seules : sans fetch explicite, le clone local dérive
d'exactement le nombre de PR fusionnées depuis le dernier pull manuel.

```bash
git fetch origin && git merge --ff-only origin/dev
```

Garde-fou mécanique : `.githooks/pre-commit` refuse un commit dont la branche est en
retard sur son upstream. Il est versionné mais doit être armé **une fois par clone** :
`git config core.hooksPath .githooks && git config pull.ff only`. Contournement
d'urgence : `ALLOW_STALE=1 git commit …`.

> 📖 `standards/08-git-et-versioning.md` §2–3 — un hook versionné **n'est pas** un
> hook actif (il a déjà été committé en `100644`, donc inerte), et Windows avale
> `chmod +x` en silence. Voir aussi la skill globale `avant-commit` : les six
> contrôles de deux minutes, dont `git diff --stat` et l'encodage.
>
> ⚠️ `standards/13-outillage-claude-code.md` §10 — avant de réécrire un fichier
> partagé, regarder `git worktree list` puis `git -C <autre> status` : rien ne
> signale le travail **non committé** d'une session voisine (vécu le 02/08/2026).

- `main` = production **réellement protégée depuis le 09/08/2026** : les 4 jobs de
  CI sont des *checks requis*, `enforce_admins` est actif, le push direct et le
  `--force` sont refusés. Toute modification passe par une PR depuis `dev`.
  ⚠️ Cette ligne affirmait « production protégé » alors que GitHub répondait
  « Branch not protected » : rien n'empêchait de fusionner une CI rouge — ce qui
  est arrivé trois fois le 08/08. Une consigne fausse est pire qu'absente.
- Préfixes de commit : `feat:` `fix:` `docs:` `refactor:` `test:` `chore:` `perf:`
- 🔴 **Claude crée ET fusionne la PR `dev → main`, et conduit la MEP** (28/08/2026).
  Cette ligne disait le contraire jusque-là — « Claude s'arrête au push sur `dev` » —
  et c'était l'exemple même de la consigne fausse que le point ci-dessus dénonce.
  La contrepartie demandée n'est pas une validation *avant*, c'est un **compte rendu
  après** : à chaque MEP, **la version et les fonctionnalités apportées**.
  Le pré-check ne s'allège pas pour autant : c'est lui qui remplace la relecture.
  `gh pr create` → attendre les **4 checks requis** → `gh pr merge --squash
  --delete-branch` → **réaligner `dev` sur `origin/main`** (la fusion est un squash
  et supprime la branche distante).
  ⚠️ `gh pr merge --delete-branch` supprime aussi la branche **locale** et bascule
  sur `main` : committer sans regarder `git branch --show-current` met le lot suivant
  sur `main`, où le push est refusé.
- MEP : elle n'est **pas** la fusion. `auto-deploy.sh` (cron `*/5`) fait le `git pull`
  **puis** le build : entre les deux, les points 12 et 18 du pré-check échouent
  légitimement — le code est à jour, l'image ne l'est pas. Attendre la ligne
  `Déployé: <sha>` dans `/var/log/hostachy-deploy.log` **sur l'actif**, puis
  post-check. Ne jamais conclure sur le seul `git log` du nœud.
  Reprise en main : `scripts/exploitation/MaJ-Hostachy.sh` sur le **RPi actif**
  uniquement (le script bloque sur le standby)
- `.env` non versionné · `SECRET_KEY` ≥ 32 caractères · `ENABLE_API_DOCS=false` en prod
- Bascule manuelle (test) : `sudo bash /opt/5hostachy/scripts/exploitation/bascule.sh` depuis le RPi actif
  (chemin de **relais** ; le script vit dans `scripts/exploitation/` — cf. #337)

**Aucune MEP sans avoir chargé `.claude/skills/mep-precheck`.** Cette skill porte les
étapes 0 et 0 bis (poste de développement, exigences sans exception), le **pré-check**
(`scripts/poste/precheck-mep.sh`), le **post-check P1–P11**, le rollback, la rétrospective du 26/07/2026 et
l'état de la surveillance continue. Elle porte surtout les trois règles qui priment
sur la liste des contrôles :

1. **Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.**
2. **Ce qui est critique en continu ne doit pas être vérifié seulement en MEP.**
3. **Vérifier le fait, pas le symptôme attendu** — et le comportement, jamais l'artefact.

> 📖 Ces trois règles sont nées ici le 26/07/2026 ; le socle en porte **d'autres**,
> toutes issues d'incidents : `standards/04-fiabilite-des-controles.md`. Elles valent
> aussi pour ce projet — notamment le **cas zéro** (§2), le **battement manquant** (§4), le
> **contrôle sans destinataire** (§7) et **observer la chose, pas son enregistrement**
> (§14), qui ont tous produit un faux vert ici.
> Principes de livraison, pré-check générique et post-check :
> `standards/09-livraison-et-mep.md`.

---

## Versioning (`front/package.json`)

> 📖 `standards/08-git-et-versioning.md` §6 — la règle patch/minor/major, le commit
> dédié, et le bump **d'office** dès qu'une MEP est demandée, sans rappel.

Instanciation 5Hostachy :
- Le fichier est **`front/package.json`** ; la version s'affiche dans le **pied de
  page** du site — c'est ce que contrôle **P3** du post-check.
- Bump **avant** le push final sur `dev`, commit dédié `chore(version): bump vX.Y.Z`.
- ⚠️ Un onglet PWA resté ouvert peut servir une version en cache : le bandeau de mise
  à jour (v2.24.0) existe pour ça, et `api/tests/test_pwa_maj.py` le verrouille.
