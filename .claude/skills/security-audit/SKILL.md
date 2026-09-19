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

### 3. Path Traversal (A01:2021)

**Rechercher** les uploads qui utilisent `file.filename` directement :
```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "os\.path\.join.*filename"
```

**Fix obligatoire** :
```python
import os, re, uuid
safe_name = re.sub(r"[^\w.\-]", "_", os.path.basename(file.filename))
final_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
```

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
