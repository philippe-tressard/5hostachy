# Contributing to 5Hostachy

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Getting Started

### Prerequisites

- **Python 3.10+** — Backend API
- **Node.js 22+** — Frontend SvelteKit
- **Docker & Docker Compose** — Container orchestration
- **SQLite 3** — Database

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/philippe-tressard/5hostachy.git
cd 5hostachy

# Copy environment config
cp .env.example .env
# Edit .env with your local settings (especially SECRET_KEY)

# Start all services
docker compose up --build -d
```

The application will be available at `http://localhost`.

### Running Without Docker

**Backend:**
```bash
cd api
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd front
npm install
npm run dev
```

## How to Contribute

### Reporting Bugs

- Use **GitHub Issues** with the `bug` label.
- Include steps to reproduce, expected behavior, and actual behavior.
- Include browser/OS information if relevant.

### Suggesting Features

- Open a **GitHub Issue** with the `enhancement` label.
- Describe the use case and expected behavior.

### Submitting Code

> **Branch model:** `main` is production-protected (no direct push). All contributions go through `dev` first.

1. **Fork** the repository.
2. Create a **feature branch** from `dev`: `git checkout dev && git checkout -b feat/my-feature`
3. Make your changes with clear, atomic commits.
4. Ensure CI passes locally (see below).
5. Open a **Pull Request against `dev`** — PRs directly targeting `main` will be declined.

**Verify CI locally before opening a PR:**
```bash
# Backend
pip install ruff
ruff check api/app/ api/alembic/ --select E9,F63,F7,F82

# Frontend
cd front && npm install && npm run build
```

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add document upload progress bar
fix: correct badge count for expired access
docs: update deployment guide for Cloudflare Tunnel
```

Prefixes: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

## Code Style

- **Python**: Follow PEP 8. Use type hints where practical.
- **TypeScript/Svelte**: Follow existing project conventions. Use TypeScript types.
- **SQL Migrations**: Use Alembic. Never modify existing migrations; create new ones.

## Security

If you find a security vulnerability, **do not open a public issue**. See [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
