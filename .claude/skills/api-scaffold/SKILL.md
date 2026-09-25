---
name: api-scaffold
description: "Scaffold a complete FastAPI endpoint for 5Hostachy: SQLModel model + Alembic migration + router CRUD + Pydantic schemas + frontend API client module. Use when: creating a new feature, adding a new entity, adding a new API resource."
argument-hint: "Describe the entity to create (e.g. 'Fournisseur with nom, siret, email')"
---

# API Scaffold — 5Hostachy

Génère un endpoint complet (backend + frontend client) en respectant toutes les conventions du projet.

## Procédure

> 🔴 **Réécrite le 23/09/2026 (#1046).** Cette skill enseignait un backend disparu :
> modèle dans `core.py`, trois schémas dans `schemas.py`, colonne `actif` sur toute
> table, `session.get` + 404, `body.dict()`, client ajouté à `api.ts`. La suivre
> violait la modularité (rang 1) — et une skill se relit exactement au moment où
> l'on crée quelque chose, c'est-à-dire là où elle fait le plus de dégâts.
>
> Règle d'écriture : elle dit **où la vérité se lit**, elle ne la recopie pas. Les
> chiffres (nombre de modules, dernier numéro de migration) se mesurent dans le
> dépôt au moment du geste.

### 1. Modèle SQLModel — `api/app/models/<domaine>.py`

Le modèle va dans le module de **son domaine** (`acces`, `communaute`,
`prestataires`, `gouvernance`, `tickets`…). Un domaine neuf reçoit son propre
module. **Jamais `core.py`** : il dépasse 500 lignes, et le garde-fou de
modularité refuse qu'il grossisse.

```python
class NouvelleEntite(SQLModel, table=True):
    __tablename__ = "nouvelle_entite"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str                                           # français, snake_case
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    cree_le: datetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: Optional[datetime] = None
```

⚠️ **L'heure s'écrit `horloge.maintenant()`** (`from app.utils import horloge`),
jamais `datetime.utcnow()` : déprécié depuis Python 3.12, et refusé par Ruff
`DTZ003` sur `api/app/` (#1047). Elle rend de l'**UTC naïf**, la forme de
toutes les dates en base — `now(timezone.utc)` rendrait une date consciente,
qui lève à la première comparaison avec une date lue en base. Et **par son
module**, jamais importée seule : treize fichiers ont une variable `maintenant`.

Puis **l'enregistrer** dans `app/models/__init__.py` — c'est cet import qui
déclare la table à SQLModel. Oublié, elle manque à `create_all` sans un mot.

⚠️ `core.py` **ré-exporte** les modèles extraits — et ces imports enregistrent :
`alembic/env.py` n'importe que `core`. Pour un modèle NEUF, importer depuis son
module de domaine, et le déclarer dans `models/__init__.py` (#1157).
🔒 `test_modeles_enregistres.py` refuse un module que `import app.models.core`
ne charge pas.

**Règles modèle :**
- `__tablename__` = snake_case français ; champs en français snake_case
- Timestamps : suffixe `_le` → `cree_le`, `mis_a_jour_le`
- FK : `{modele}_id = Field(default=None, foreign_key="table.id")`
- Enums : `class MonEnum(str, Enum)` → slugs français lowercase
- JSON stocké en `str` → parsé par `@field_validator` dans le schéma Read
- 🔴 **Pas de colonne `actif` par réflexe.** Un objet qui doit quitter les listes
  se déclare dans `utils/archivage.REGLES` — la règle unique, testée contre les
  modèles réels. Un booléen de plus ferait une seconde façon de disparaître.
- Une relation (`Relationship`) empêche plus tard de DÉPLACER le modèle sans
  cycle d'import : c'est pourquoi `Ticket` et `Publication` sont restés dans
  `core.py`. Ne l'ajouter que si un `select` explicite ne suffit pas.

### 2. Schémas Pydantic — là où ils servent

Trois formes par entité exposée :

```python
class EntiteCreate(BaseModel):      # entrée : ni id, ni horodatage
    nom: str

class EntiteRead(BaseModel):        # sortie
    id: int
    nom: str
    cree_le: datetime

    class Config:                   # la forme de TOUT le dépôt — pas `model_config`
        from_attributes = True

class EntiteUpdate(BaseModel):      # PATCH partiel : tout Optional
    nom: Optional[str] = None
```

**Où les mettre :**
- partagés par plusieurs routeurs → `app/schemas_<domaine>.py`, ré-exporté par
  `schemas.py` ;
- propres à UN routeur (le corps d'un geste, la réponse d'un écran) → à côté de
  lui, dans le routeur ou son `_schemas.py`.
- ⚠️ `schemas_communs.py` n'importe RIEN du projet : c'est ce qui évite le cycle
  `schemas` ⇄ `schemas_tickets`. Ne pas lui en ajouter.

### 3. Migration Alembic — `api/alembic/versions/NNNN_slug.py`

Le numéro suit le plus élevé présent dans `alembic/versions/` (le lire, ne pas le
deviner) ; le fichier porte un **slug** qui dit ce qu'il fait.

```python
"""Ce que la migration fait, et pourquoi — en français."""
import sqlalchemy as sa
from alembic import op

revision = "NNNN"
down_revision = "NNNN-1"
branch_labels = None
depends_on = None

TABLE = "nouvelle_entite"   # un IDENTIFIANT s'interpole depuis une constante


def upgrade():
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nom", sa.String, nullable=False),
        sa.Column("cree_le", sa.DateTime, nullable=False),
        sa.Column("mis_a_jour_le", sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_table(TABLE)
```

**Règles migration :** `CLAUDE.md` → « Migrations Alembic » (liaison des
valeurs, identifiants depuis une constante, jamais de `foreign_key` dans un
`add_column`) et `standards/06-donnees-et-integrite.md` §3 pour le générique — seules copies
(claude-config#122). Ce qui n'est écrit que là :
- tester l'existence d'une colonne avant `add_column` par
  `sa.inspect(conn).get_columns(TABLE)` — **pas** par un `PRAGMA table_info` en
  f-string, qui compterait contre le plafond de `test_migrations.py`.
- BDD = **SQLite** — pas de `ALTER TYPE`, pas de `CREATE TYPE`
- **Jamais** modifier une migration existante : en créer une nouvelle.
- Corriger un texte **livré** en base (FAQ, modèle d'e-mail) : `utils/textes_livres.remplacer_si_intact` — il ne touche que les lignes intactes. Recopié quinze fois avant le 24/09/2026 ; `test_textes_livres.py` refuse la seizième copie.

### 4. Routeur FastAPI — `api/app/routers/`

```python
"""Ce que ce routeur sert, à qui, et pourquoi il est à part."""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.<domaine> import NouvelleEntite
from app.models.core import Utilisateur
from app.schemas_<domaine> import EntiteCreate, EntiteRead, EntiteUpdate
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/nouvelle-entite", tags=["nouvelle-entite"])


@router.get("", response_model=list[EntiteRead])
def lister(session: Session = Depends(get_session), _: Utilisateur = Depends(get_current_user)):
    return session.exec(select(NouvelleEntite).order_by(NouvelleEntite.cree_le.desc())).all()


@router.get("/{entite_id}", response_model=EntiteRead)
def lire(entite_id: int, session: Session = Depends(get_session),
         _: Utilisateur = Depends(get_current_user)):
    return ou_404(session, NouvelleEntite, entite_id, "entité")


@router.post("", response_model=EntiteRead, status_code=201)
def creer(body: EntiteCreate, session: Session = Depends(get_session),
          _: Utilisateur = Depends(require_cs_or_admin)):
    obj = NouvelleEntite(**body.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.patch("/{entite_id}", response_model=EntiteRead)
def modifier(entite_id: int, body: EntiteUpdate, session: Session = Depends(get_session),
             _: Utilisateur = Depends(require_cs_or_admin)):
    obj = ou_404(session, NouvelleEntite, entite_id, "entité")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.mis_a_jour_le = horloge.maintenant()
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
```

- **`ou_404(session, Modele, id, "libellé")`**, jamais `session.get` + `raise
  HTTPException(404)` : le 404 nomme ce qui manque, et c'est écrit une fois.
- **`model_dump()`**, pas `.dict()` (déprécié).
- **Suppression** : physique réservée à `require_admin`. Ce que le résident voit
  disparaître s'**archive** (`utils/archivage`), il ne se supprime pas.
- Une règle d'appartenance (« cet objet est-il le mien ? ») va dans
  `auth/appartenance.py`, jamais dans le routeur (#1028).

**Monter le routeur** : `app.include_router(<module>.router)` dans `main.py`, ou
dans le `__init__.py` de son paquet s'il en a un.
🔒 `api/tests/test_routeurs_montes.py` refuse un routeur que personne ne monte —
ses URL rendraient 404, et rien d'autre ne le dirait.

⚠️ **Dans un paquet, l'ORDRE d'inclusion décide.** FastAPI retient la première
route qui correspond : un `/admin/{type}/{id}` inclus avant `/admin/imports/{id}`
l'avale. C'est ce qui a tué les deux écrans d'import le 22/09/2026 (#1151).
Inclure le plus spécifique d'abord ; `test_routes_masquees.py` le tient pour
`acces`.

⚠️ Un fichier de routeur qui dépasse 500 lignes se découpe par NOTION, pas par
intervalle de lignes, avec le même préfixe : les URL publiques ne bougent pas
(`copropriete_patrimoine`, `calendrier_historique`, `auth_profil`).

**Dépendances d'auth :** le tableau fait foi dans `CLAUDE.md` (« Dépendances
d'auth ») — avec les **prédicats** (`est_moderateur`, `peut_editer`…), qui
s'appellent et ne se redérivent jamais.

### 5. Client API frontend — `front/src/lib/api/<domaine>.ts`

Le client s'ajoute dans le **module de son domaine** du paquet
`front/src/lib/api/` (`acces`, `patrimoine`, `communaute`…) — **jamais** dans un
`api.ts` ressuscité à la racine, et jamais recopié dans un écran (38 routes
l'étaient avant le 06/09).

```typescript
export const nouvelleEntite = {
    list: () => api.get<NouvelleEntite[]>('/nouvelle-entite'),
    get: (id: number) => api.get<NouvelleEntite>(`/nouvelle-entite/${id}`),
    create: (body: Partial<NouvelleEntite>) => api.post<NouvelleEntite>('/nouvelle-entite', body),
    update: (id: number, body: Partial<NouvelleEntite>) =>
        api.patch<NouvelleEntite>(`/nouvelle-entite/${id}`, body),
};
```

Le type va dans `front/src/lib/api/types.ts`.

### 6. Dates affichées — `app/utils/dates_fr.py`, jamais un `strftime` local

Toute date **destinée à être lue** (email, PDF, réponse affichée telle quelle) passe
par les helpers partagés :

```python
date_longue(d)            # 25 juillet 2026
date_courte(d)            # 25/07/2026
datetime_longue(dt)       # 25 juillet 2026 à 09:05
datetime_longue_paris(dt) # horodatage naïf UTC de la base → heure de Paris
```

`api/tests/test_dates_fr.py` **échoue en CI** si `%B` `%b` `%A` `%a` apparaissent
dans `api/app/` : ces motifs traduisent le mois ou le jour selon `LC_TIME`, ce qui a
produit des mois en anglais sur la fiche arrivant (26/07/2026).

⚠️ Les `strftime("%Y-%m-%d")` / `("%Y-%m")` restants sont des **clés machine**
(requêtes SQL, agrégats de télémétrie, noms de sauvegarde) : **ne pas les
« factoriser »**, ce ne sont pas des formats d'affichage.

### 7. Checklist finale

- [ ] Modèle dans `app/models/<domaine>.py`, importé par `models/__init__.py` — jamais `core.py`
- [ ] Pas de colonne `actif` : l'archivage se déclare dans `utils/archivage.REGLES`
- [ ] Schémas dans `schemas_<domaine>.py` s'ils sont partagés, à côté du routeur sinon
- [ ] Migration `NNNN_slug.py` au bon numéro ; aucune `foreign_key` dans un `add_column`
- [ ] Routeur monté (`main.py` ou `__init__.py` du paquet), routes fixes avant routes à paramètre
- [ ] `ou_404` et `model_dump()` — ni `session.get` + 404, ni `.dict()`
- [ ] Client dans le module de domaine de `front/src/lib/api/`, type dans `types.ts`
- [ ] Dates affichées via `dates_fr.py` (pas de `%B`/`%A` dans `api/app/`)
- [ ] `cd api && pytest tests/ -q`, puis `bash scripts/poste/rejouer-ci.sh`
