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

**Règle** : Tout `{@html}` DOIT passer par `safeHtml()` de `$lib/sanitize.ts`.
**Exception** : `Icon.svelte` (SVG hardcodé côté serveur).
**Fix** : `import { safeHtml } from '$lib/sanitize'` → `{@html safeHtml(content)}`

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

**Endpoints critiques à protéger** :

| Endpoint | Limite |
|----------|--------|
| `/auth/login` | 5/minute |
| `/auth/register` | 5/minute |
| `/auth/refresh` | 10/minute |
| `/auth/mot-de-passe-oublie` | 3/minute |
| `/auth/reinitialiser-mot-de-passe` | 5/minute |

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
