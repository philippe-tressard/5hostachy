"""Garde-fou préventif : intégrité de la chaîne de migrations Alembic.

Une migration avec un mauvais `down_revision` crée plusieurs *heads* : en prod,
`start.sh` lance `alembic upgrade head` avec `set -e` → le conteneur reste
bloqué au démarrage. Ce test attrape ces erreurs structurelles avant la MEP
(la cause des fix « migration 0094/0105 » de l'historique).

Note : on ne teste pas `upgrade head` depuis une base vierge car le schéma de
base est créé par `SQLModel.create_all` puis ajusté par des migrations
incrémentales (non rejouables seules sur une base vide / déjà au schéma final).
La validation porte donc sur la cohérence du graphe de révisions.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_API_DIR = Path(__file__).resolve().parents[1]


def _script_dir() -> ScriptDirectory:
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_un_seul_head():
    """Pas de divergence : un unique head (sinon upgrade head échoue en prod)."""
    heads = _script_dir().get_heads()
    assert len(heads) == 1, f"Plusieurs heads de migration : {heads} (down_revision incorrect ?)"


def test_une_seule_base():
    """Un unique point de départ dans le graphe de migrations."""
    bases = _script_dir().get_bases()
    assert len(bases) == 1, f"Plusieurs bases de migration : {bases}"


def test_revisions_uniques():
    """Aucun identifiant de révision dupliqué."""
    revs = [s.revision for s in _script_dir().walk_revisions()]
    doublons = sorted({r for r in revs if revs.count(r) > 1})
    assert not doublons, f"Identifiants de révision dupliqués : {doublons}"


def test_les_migrations_qui_lisent_le_seed_y_trouvent_leur_modele():
    """Un modèle retiré du seed ne doit pas bloquer le démarrage du conteneur.

    Plusieurs migrations vont chercher le corps d'un modèle dans
    `seed.EMAIL_TEMPLATES` plutôt que d'en garder une copie — c'est voulu, deux
    copies du même HTML divergent. Mais elles l'extraient par
    `next(t for t in EMAIL_TEMPLATES if t[0] == "<code>")` : le jour où ce code
    disparaît du seed, `next` lève `StopIteration`. Sur une base neuve, cela
    fait échouer `alembic upgrade head`, et `start.sh` a `set -e` — le conteneur
    ne démarre plus du tout.

    Le risque n'est pas théorique : l'audit du 05/08/2026 a retiré dix modèles
    du seed en une journée. Une migration est figée ; c'est au code d'aujourd'hui
    de rester compatible avec elle, et ce test le vérifie.
    """
    import re

    from app.seed import EMAIL_TEMPLATES

    codes = {row[0] for row in EMAIL_TEMPLATES}
    motif = re.compile(r"""t\[0\]\s*==\s*["']([a-z0-9_]+)["']""")
    manquants: list[str] = []
    for chemin in sorted((_API_DIR / "alembic" / "versions").glob("*.py")):
        source = chemin.read_text(encoding="utf-8")
        if "EMAIL_TEMPLATES" not in source:
            continue
        for code in motif.findall(source):
            if code not in codes:
                manquants.append(f"{chemin.name} cherche « {code} »")

    assert not manquants, (
        "Migrations qui cherchent dans seed.EMAIL_TEMPLATES un modèle qui n'y "
        "est plus :\n  " + "\n  ".join(manquants)
        + "\nSur une base neuve, `next(...)` lève StopIteration et le conteneur "
        "reste bloqué au démarrage. Garder une copie du contenu dans la "
        "migration concernée plutôt que de la laisser lire le seed."
    )


def test_aucune_cle_etrangere_dans_un_add_column():
    """🔴 SQLite ne sait pas ajouter une contrainte à une table existante.

    ## Ce qui s'est passé (01/09/2026, migration 0165)

        NotImplementedError: No support for ALTER of constraints in SQLite
        dialect. Please refer to the batch mode feature…

    `op.add_column(..., sa.ForeignKey(...))` **crashe en production**. Et il
    crashe APRÈS avoir exécuté le `ADD COLUMN` : la colonne existe, sans sa
    contrainte, et la révision n'est pas marquée. `start.sh` a `set -e`, donc le
    conteneur s'arrête — le déploiement n'a tenu que parce que la migration
    portait une garde d'idempotence, que le second passage a vue.

    🔴 **Et ce n'était pas la première fois.** Ce test, écrit pour 0165, a
    immédiatement trouvé la migration **0117** (25/07/2026), qui portait le même
    défaut depuis cinq semaines. Elle avait crashé de la même façon, et personne
    ne l'avait su : même redémarrage, même garde d'idempotence, même silence.
    Deux occurrences, aucune vue — c'est la définition d'un défaut qu'aucun
    contrôle ne regarde.

    ⚠️ **Le mode batch n'est pas le remède** : il recopie la table entière, ce
    qui est disproportionné pour un champ dont la contrainte n'apporte rien. Une
    colonne entière non contrainte suffit — et le modèle SQLModel ne doit pas
    déclarer `foreign_key` non plus, sinon une base neuve (`create_all`) et une
    base migrée portent deux schémas différents.

    ⚠️ L'analyse passe par l'**arbre syntaxique**, pas par une recherche de
    texte : la première écriture de ce test lisait le source brut, et s'est
    accusée elle-même dès qu'un commentaire a expliqué le défaut en le nommant
    (`standards/04` §29 — neutraliser les commentaires, là où ils existent).
    """
    import ast

    fautives: list[str] = []
    for chemin in sorted((_API_DIR / "alembic" / "versions").glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            if getattr(noeud.func, "attr", None) != "add_column":
                continue
            #  Un `ForeignKey(...)` n'importe où DANS l'appel — il est imbriqué
            #  dans le `sa.Column(...)`, pas au premier niveau.
            for inner in ast.walk(noeud):
                nom = getattr(inner.func, "attr", None) if isinstance(inner, ast.Call) else None
                nom = nom or (getattr(inner.func, "id", None) if isinstance(inner, ast.Call) else None)
                if nom == "ForeignKey":
                    fautives.append(f"{chemin.name}:{noeud.lineno}")
                    break

    assert not fautives, (
        "Clé étrangère posée dans un `add_column` — SQLite refuse d'ajouter une "
        "contrainte à une table existante, et le conteneur s'arrête au "
        "démarrage :\n  " + "\n  ".join(fautives) + "\n\n"
        "  Poser une colonne entière simple, et ne pas déclarer la clé dans le "
        "modèle non plus : une base neuve et une base migrée doivent porter le "
        "même schéma."
    )
