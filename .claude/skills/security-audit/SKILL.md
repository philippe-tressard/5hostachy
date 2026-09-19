---
name: security-audit
description: "Run a complete OWASP Top 10 security audit on the 5Hostachy project (FastAPI + SvelteKit + SQLite). Use when: checking for vulnerabilities, reviewing security posture, before a release, after adding auth/upload/API features."
argument-hint: "Optional: scope the audit (e.g. 'auth only', 'uploads', 'full')"
---

# Security Audit — 5Hostachy (OWASP Top 10)

Audit de sécurité complet du projet. Exécuter chaque vérification dans l'ordre, reporter les findings, et proposer des fixes.

## Stack technique

- **Backend** : FastAPI + SQLModel + SQLite
- **Frontend** : SvelteKit (SSR + CSR)
- **Auth** : JWT en cookie HTTP-only (bcrypt)
- **Déploiement** : Docker sur Raspberry Pi 5, Caddy reverse proxy

## Procédure d'audit

### 1. SQL Injection (A03:2021)

**Rechercher** les requêtes SQL brutes avec interpolation :
```powershell
Get-ChildItem -Recurse -Filter "*.py" | Where-Object { $_.FullName -notmatch "__pycache__|alembic" } | Select-String -Pattern "text\(f[`"']|\.format\(|%\s" | Where-Object { $_.Line -match "SELECT|INSERT|UPDATE|DELETE" }
```

**Règle** : SQLAlchemy ORM = safe. `text()` avec f-string/format = CRITIQUE.
**Fix** : `text("... :val").bindparams(val=...)` — toujours des paramètres liés.

### 2. XSS — Cross-Site Scripting (A07:2021)

**Rechercher** les usages de `{@html}` dans Svelte :
```powershell
Get-ChildItem -Recurse -Filter "*.svelte" | Select-String -Pattern "@html"
```

**Règle** : Tout `{@html}` DOIT passer par une fonction de `$lib/sanitize.ts` — elles sont **trois** (`safeHtml`, `safeRichContent`, `safeDescription`), toutes adossées à DOMPurify. Vérifié en CI par `npm run lint:html` depuis le 19/08/2026, qui exige que le nom vienne de l'**import** : une fonction locale homonyme ne prouve rien (#429).
**Exception** : `Icon.svelte` (SVG hardcodé côté serveur).
**Fix** : `import { safeDescription } from '$lib/sanitize'` → `{@html safeDescription(contenu)}` — et jamais un helper local, fût-il correct : c'est ainsi que trois copies de `safeDescription` ont coexisté.

Configuration DOMPurify (`src/lib/sanitize.ts`) :
- ALLOWED_TAGS : `p br b i u s strong em ul ol li blockquote pre code h1-h6 a img hr span div`
- ALLOWED_ATTR : `href src alt title class target rel`
- `ALLOW_DATA_ATTR: false`

### 3. Téléversement : une seule porte (A01:2021)

🔴 **Le geste ne se réécrit pas, il s'appelle.** Un fichier reçu s'écrit sur
disque par `utils/fichiers.enregistrer_fichier_recu`, et nulle part ailleurs.
Les règles vivent dans `FAMILLES` du même module — liste blanche de types,
plafond de taille, extensions autorisées —, une entrée par famille :
`image`, `document`, `document_prive`, `tableur`.

**Un routeur nomme une famille**, il ne redéfinit pas ce qu'il accepte.

#### Ce que l'audit du 19/09/2026 a trouvé (#1026)

Le téléversement avait **trois écritures**, appliquant des règles différentes :

| Chemin | Types | Plafond | Signature |
|---|---|---|---|
| documents privés (`utils/fichiers`) | **aucun** | **aucun** | oui |
| images (`routers/uploads`) | oui | oui | réencodage PIL |
| documents joints (`routers/uploads`) | oui | oui | oui, **recopiée** |

Et **trois imports de tableur n'avaient aucun contrôle** : ni type, ni taille.
Ils n'étaient pas dans la portée du test de signature, dont le critère était
« les endpoints qui **écrivent** sur le disque » — or un import analyse en
mémoire. La portée était juste, et elle laissait dehors trois chemins par
lesquels un fichier arbitraire entrait.

⚠️ **Une duplication de règle de sécurité ne produit aucun signal** : un fichier
accepté à tort est stocké, servi, et personne ne s'en plaint. C'est pourquoi
cette question se mesure par des contrôles, et non en relisant les routeurs.

#### Les contrôles, et ce que chacun tient

| Contrôle | Ce qu'il refuse |
|---|---|
| `test_televersement_source_unique.py` | une écriture de fichier reçu hors du module ; une liste MIME ou un plafond redéclaré dans un routeur ; une famille qui oublie l'une des trois règles |
| `test_signature_fichiers.py` | un point de réception qui n'appelle pas la règle — **les sept**, imports de tableur compris |
| `test_pieces_jointes.py` | une divergence entre ce que le front propose et ce que le serveur accepte |

Le PDF d'affiche de hall est la **seule** écriture déclarée hors du module :
l'application le **produit**, il n'est pas reçu, donc il n'a ni type à vérifier
ni signature à confronter. La distinction est écrite dans le contrôle.

#### Le nom stocké

`nom_stocke` : préfixe UUID, radical assaini, et **extension dérivée du type**,
jamais du nom fourni. `/uploads/*` est servi en statique et Caddy pose le
`Content-Type` d'après l'extension sur disque : un `.html` téléversé sous un
type MIME autorisé s'exécuterait sur notre origine.

#### La racine du volume

`Settings.uploads_dir`, **seule** lecture de la variable d'environnement. Elle
était écrite six fois. Un fichier posé hors du volume n'est ni répliqué vers le
standby par `bascule.sh`, ni sauvegardé par `backup.py` — il est perdu à la
première bascule, sans aucun signal.

### 4. Authentication & Session (A07:2021)

#### Cookies JWT
```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "secure=|samesite=|httponly="
```

**Vérifier dans `auth.py`** :
- `secure=settings.cookie_secure` (True en prod, False en dev via `.env`)
- `samesite="strict"`
- `httponly=True`

#### SECRET_KEY
```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "secret_key.*=.*\""
```

**Vérifier dans `config.py`** :
- `field_validator` rejetant les valeurs connues insécurisées
- Longueur minimale 32 caractères

#### Password hashing
```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "bcrypt|passlib|sha256|md5|hashlib|plaintext"
```
**Attendu** : bcrypt uniquement (via `passlib` ou `bcrypt` direct).

#### Poser un mot de passe = fermer les sessions qu'il ouvrait

🔴 Deux routes posent un mot de passe — « changer le mien » et « j'ai oublié le
mien » — et elles ont **divergé** jusqu'au 19/09/2026 : la seconde révoquait les
sessions actives, la première ne révoquait rien. Un attaquant qui détenait une
session la conservait sept jours après que la victime avait changé son mot de
passe (#1027).

**Le geste s'écrit une fois** : `app/utils/mots_de_passe.poser_mot_de_passe()` —
hachage, révocation des autres sessions, et la session appelante conservée quand
elle se présente. `api/tests/test_reinitialisation_mot_de_passe.py` refuse qu'une
route hache un mot de passe elle-même.

⚠️ **Ce que la révocation ne couvre pas** : le jeton d'accès est un JWT
autoporteur de 120 minutes, que rien ne révoque côté serveur. La fenêtre passe de
sept jours à deux heures, pas à zéro — #1063 porte la décision.

### 5. CORS (A05:2021)

```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "CORSMiddleware|allow_origins|allow_methods|allow_credentials"
```

**Vérifier dans `main.py`** :
- `allow_origins` : liste explicite (JAMAIS `["*"]` avec `credentials=True`)
- `allow_methods` : liste explicite (`["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]`)
- `allow_credentials=True` seulement si origins explicites

### 6. Rate Limiting (A04:2021)

```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "slowapi|RateLimiter|throttle|limiter"
```

**Les limites vivent dans `api/app/utils/limiter.py`**, une constante par
**intention** (secret éprouvé, courriel déclenché, session, contrôle de fichier,
lecture authentifiée, journal, lecture publique). Chaque constante dit pourquoi
elle vaut ce qu'elle vaut — et c'est là qu'on lit la valeur, pas ici.

🔴 Ce tableau les recopiait, et il a été **faux** : `/auth/change-password` et
`/auth/verifier-email` n'avaient aucune limite alors que les deux éprouvent un
secret, et les quatre routes de `auth_profil.py` non plus. Une liste recopiée ne
dit rien des routes qu'elle omet — c'est précisément ce qui manquait (#1027).

🔒 **Le contrôle qui remplace ce tableau** : `api/tests/test_limites_debit_auth.py`
exige que **toute** route d'un module `auth*.py` porte un `@limiter.limit`, que sa
valeur vienne d'une constante de `utils.limiter`, que le décorateur soit **sous**
celui de la route (au-dessus, il n'a aucun effet, en silence) et que la fonction
reçoive une `request` (sans elle, slowapi lève au premier visiteur, pas au
démarrage).

**Ce qu'il reste à faire à la main** : juger si le plafond d'une route est *bien
réglé*. Le contrôle vérifie qu'il existe et qu'il est nommé, jamais qu'il est
prudent.

### 7. Refresh Token Rotation (A07:2021)

**Vérifier** que `/auth/refresh` :
1. Invalide l'ancien refresh token (`revoked=True`)
2. Crée un nouveau refresh token
3. Retourne le nouveau token en cookie

### 8. Secrets & Configuration (A02:2021)

```powershell
# Secrets hardcodés
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "secret_key.*=.*\"|password.*=.*\"|api_key.*=.*\""

# .env dans .gitignore
Get-Content .gitignore | Select-String -Pattern "\.env"

# .env.example sans vraies valeurs
if (Test-Path .env.example) { Get-Content .env.example }
```

### 9. Dépendances vulnérables (A06:2021)

```powershell
# Python
pip audit --requirement api/requirements.txt

# Node.js
cd front; npm audit
```

### 10. Headers de sécurité (A05:2021)

**Vérifier dans `Caddyfile`** :
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy`

## Rapport d'audit

Pour chaque finding, reporter :

| Champ | Description |
|-------|-------------|
| **Sévérité** | CRITICAL / HIGH / MEDIUM / LOW / INFO |
| **Catégorie OWASP** | A01-A10 |
| **Fichier** | Chemin du fichier affecté |
| **Ligne** | Numéro de ligne |
| **Description** | Ce qui a été trouvé |
| **Fix** | Code correctif proposé |

## Sévérités

| Niveau | Critères |
|--------|----------|
| CRITICAL | Exploitation directe, accès données, RCE |
| HIGH | Contournement auth, injection, path traversal |
| MEDIUM | CORS mal configuré, headers manquants, rate limit absent |
| LOW | Bonnes pratiques non respectées, info disclosure |
| INFO | Recommandation d'amélioration |
