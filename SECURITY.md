# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.x     | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, **please do not open a public issue**.

Instead, send a private report via **GitHub Security Advisories**:

1. Go to the [Security tab](../../security/advisories) of this repository.
2. Click **New draft security advisory**.
3. Provide a description of the vulnerability, steps to reproduce it, and the potential impact.

You can also reach us privately via the contact details listed in your GitHub profile.

### What to expect

- We will acknowledge receipt within **48 hours**.
- We will provide an initial assessment within **7 days**.
- Critical fixes will be prioritized and deployed as soon as possible.

## Scope

The following components are in scope:

- **Backend API** (`api/`) — FastAPI, authentication, authorization, database access
- **Frontend** (`front/`) — SvelteKit, client-side data handling
- **Infrastructure** — Docker configuration, Caddy reverse proxy, Cloudflare Worker
- **WhatsApp Bridge** (`whatsapp-bridge/`) — Message relay

## Security Measures

This project implements the following security controls:

- **Authentication**: JWT with HttpOnly/Secure/SameSite cookies, bcrypt password hashing
- **Rate Limiting**: slowapi on authentication endpoints
- **Input Validation**: Pydantic/SQLModel schema validation
- **CORS**: Explicit origin allowlist (no wildcard with credentials)
- **XSS Protection**: DOMPurify sanitization for user-generated HTML
- **Path Traversal Protection**: UUID-prefixed filenames with basename sanitization
- **SQL Injection Protection**: SQLAlchemy ORM (parameterized queries)
- **Security Headers**: Caddy serves HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy
