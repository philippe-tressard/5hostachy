---
name: api-scaffold
description: "Scaffold a complete FastAPI endpoint for 5Hostachy: SQLModel model + Alembic migration + router CRUD + Pydantic schemas + frontend API client module. Use when: creating a new feature, adding a new entity, adding a new API resource."
argument-hint: "Describe the entity to create (e.g. 'Fournisseur with nom, siret, email, actif')"
---

# API Scaffold — 5Hostachy

Génère un endpoint complet (backend + frontend client) en respectant toutes les conventions du projet.

## Procédure

### 1. Modèle SQLModel (`api/app/models/core.py`)

Ajouter le modèle dans `core.py` en suivant ces conventions :

```python
class NouvelleEntite(SQLModel, table=True):
    __tablename__ = "nouvelle_entite"
    id: Optional[int] = Field(default=None, primary_key=True)
    # Champs métier (français, snake_case)
    nom: str
    # FK : {model}_id = Field(default=None, foreign_key="table.id")
    # Timestamps
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: Optional[datetime] = None
    actif: bool = Field(default=True)
    # Relationships
    # items: List["AutreModele"] = Relationship(back_populates="parent")
```

**Règles modèle :**
- `__tablename__` = snake_case français
- Champs en **français snake_case** : `statut_validation`, `date_debut`, `perimetre_cible`
- Timestamps : suffixe `_le` → `cree_le`, `mis_a_jour_le`
- FK : `{modele}_id` → `field(foreign_key="table.id")`
- Enums : `class MonEnum(str, Enum)` → slugs français lowercase
- JSON stocké en `str` → parsé via `@field_validator` dans le schema Read
- Soft delete : `actif: bool = True` (pas de suppression physique sauf admin)

### 2. Schémas Pydantic (`api/app/schemas.py`)

Créer 3 schémas par entité :

```python
class EntiteCreate(BaseModel):
    """Champs d'entrée (pas d'id, pas de timestamps)."""
    nom: str
    champ_optionnel: Optional[str] = None

class EntiteRead(BaseModel):
    """Champs de sortie (inclut id + timestamps)."""
    id: int
    nom: str
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None

    # Parser les champs JSON stockés en str
    @field_validator('champ_json', mode='before')
    @classmethod
    def parse_json_field(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v

    class Config:
        from_attributes = True

class EntiteUpdate(BaseModel):
    """Tous les champs Optional pour PATCH partiel."""
    nom: Optional[str] = None
```

### 3. Migration Alembic (`api/alembic/versions/`)

**Déterminer le prochain numéro** : lister les fichiers existants, prendre le plus élevé + 1.

```python
"""Ajouter table nouvelle_entite

Revision ID: 00XX
Revises: 00XX-1
Create Date: YYYY-MM-DD
"""
import sqlalchemy as sa
from alembic import op

revision = "00XX"
down_revision = "00XX-1"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "nouvelle_entite",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nom", sa.String, nullable=False),
        sa.Column("cree_le", sa.DateTime, nullable=False),
        sa.Column("mis_a_jour_le", sa.DateTime, nullable=True),
        sa.Column("actif", sa.Boolean, nullable=False, server_default="1"),
    )

def downgrade() -> None:
    op.drop_table("nouvelle_entite")
```

**Règles migration :**
- ID séquentiel 4 chiffres : `0087`, `0088`...
- JAMAIS de f-string dans `op.execute()` → toujours `text(...).bindparams(...)`
- BDD = **SQLite** — pas de `ALTER TYPE`, pas de `CREATE TYPE`
- Vérifier existence colonnes avant `add_column` : `PRAGMA table_info('table')`
- `start.sh` a `set -e` : une migration qui crash = conteneur bloqué

### 4. Router FastAPI (`api/app/routers/`)

Créer `api/app/routers/nouvelle_entite.py` :

```python
"""Router nouvelle_entite — CRUD complet."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin, require_admin
from app.database import get_session
from app.models.core import NouvelleEntite, Utilisateur
from app.schemas import EntiteCreate, EntiteRead, EntiteUpdate

router = APIRouter(prefix="/nouvelle-entite", tags=["nouvelle-entite"])

@router.get("", response_model=list[EntiteRead])
def list_entites(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return session.exec(
        select(NouvelleEntite).where(NouvelleEntite.actif == True)
        .order_by(NouvelleEntite.cree_le.desc())
    ).all()

@router.get("/{id}", response_model=EntiteRead)
def get_entite(
    id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    obj = session.get(NouvelleEntite, id)
    if not obj:
        raise HTTPException(404, "Non trouvé")
    return obj

@router.post("", response_model=EntiteRead, status_code=201)
def create_entite(
    body: EntiteCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    obj = NouvelleEntite(**body.dict())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj

@router.patch("/{id}", response_model=EntiteRead)
def update_entite(
    id: int,
    body: EntiteUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    obj = session.get(NouvelleEntite, id)
    if not obj:
        raise HTTPException(404, "Non trouvé")
    for k, v in body.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.mis_a_jour_le = datetime.utcnow()
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj

@router.delete("/{id}", status_code=204)
def delete_entite(
    id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    obj = session.get(NouvelleEntite, id)
    if not obj:
        raise HTTPException(404, "Non trouvé")
    session.delete(obj)
    session.commit()
```

**Puis enregistrer le router** dans `api/app/main.py` :
```python
from app.routers.nouvelle_entite import router as nouvelle_entite_router
app.include_router(nouvelle_entite_router)
```

**Dépendances d'auth disponibles :**

| Dependency | Usage |
|-----------|-------|
| `get_current_user` | Tout utilisateur connecté |
| `require_cs_or_admin` | Création/modification de contenu |
| `require_admin` | Suppression définitive, config système |
| `require_proprietaire` | Fonctions propriétaires |
| `get_acting_user` | Délégation (header `X-Acting-As`) |

### 5. Client API frontend (`front/src/lib/api.ts`)

Ajouter le module dans `api.ts` :

```typescript
// --- Nouvelle Entite ---
export interface NouvelleEntite {
    id: number;
    nom: string;
    cree_le: string;
    mis_a_jour_le: string | null;
}

export const nouvelleEntite = {
    list: (): Promise<NouvelleEntite[]> => api.get('/nouvelle-entite'),
    get: (id: number): Promise<NouvelleEntite> => api.get(`/nouvelle-entite/${id}`),
    create: (body: Partial<NouvelleEntite>): Promise<NouvelleEntite> => api.post('/nouvelle-entite', body),
    update: (id: number, body: Partial<NouvelleEntite>): Promise<NouvelleEntite> => api.patch(`/nouvelle-entite/${id}`, body),
    delete: (id: number): Promise<void> => api.delete(`/nouvelle-entite/${id}`),
};
```

### 6. Checklist finale

- [ ] Modèle ajouté dans `models/core.py`
- [ ] Schémas Create/Read/Update dans `schemas.py`
- [ ] Migration créée avec le bon numéro séquentiel
- [ ] Router créé + enregistré dans `main.py`
- [ ] Client API ajouté dans `front/src/lib/api.ts`
- [ ] Types TypeScript exportés
- [ ] Imports vérifiés (pas d'import circulaire)
