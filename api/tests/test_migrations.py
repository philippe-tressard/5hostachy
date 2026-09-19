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


# ─────────────────────────────────────────────────────────────────────────────
#  🔴 Aucune f-string dans un `execute()` de migration — sauf les 27 d'avant
#
#  CLAUDE.md dit « **jamais** de f-string dans `op.execute()` →
#  `text(...).bindparams(...)` ». La règle n'avait **aucun** garde-fou, et
#  l'écart continuait : au 19/09/2026, **40** appels `execute` portaient une
#  f-string sur 26 migrations, dont **27 sans `bindparams`** — et trois d'entre
#  elles (0193, 0194, 0196) datent du même mois que ce relevé (#1032).
#
#  ⚠️ Un `grep 'op.execute(f"'` en rend **zéro** : la f-string est presque
#  toujours à la ligne suivante de l'appel. C'est pourquoi ce contrôle lit
#  l'arbre syntaxique et non le texte — et c'est pourquoi personne ne l'avait vu.
#
#  ## Pourquoi la liste est FIGÉE et non décroissante
#
#  Une dette se résorbe par un plafond qui baisse (`standards/05` §2). Pas
#  celle-ci : **une migration appliquée ne se modifie jamais**. Ces 27 lignes
#  sont de l'HISTORIQUE, pas un retard — les corriger réécrirait le schéma déjà
#  déployé. La liste ne bougera donc plus, sauf pour retirer une entrée dont le
#  fichier disparaîtrait, ce que le dernier test vérifie.
#
#  ## La règle réelle, celle qu'on peut tenir
#
#  | Ce qu'on interpole | Verdict |
#  |---|---|
#  | une **valeur** (contenu, identifiant de ligne, date) | jamais — `bindparams` |
#  | un **identifiant** (nom de table ou de colonne) depuis une constante du fichier | toléré : SQLite n'accepte pas de paramètre à cette place |
#
#  Le second cas est celui des treize f-strings qui lient déjà leurs valeurs. Il
#  n'était écrit nulle part avant ce lot — or une dérogation non écrite n'est pas
#  une dérogation, c'est un oubli qui ressemble à une décision.
# ─────────────────────────────────────────────────────────────────────────────

#: Les 27 appels `execute(f"…")` sans `bindparams` présents au 19/09/2026,
#: `fichier:ligne`. Figée : voir ci-dessus.
FSTRINGS_HISTORIQUES = {
    "0065_whatsapp_scheduled.py:52",
    "0074_update_berteaux_message.py:40",
    "0074_update_berteaux_message.py:44",
    "0074_update_berteaux_message.py:51",
    "0074_update_berteaux_message.py:55",
    "0102_publication_syndic_contenu_complet.py:38",
    "0102_publication_syndic_contenu_complet.py:44",
    "0103_publication_syndic_lien_ancre.py:38",
    "0103_publication_syndic_lien_ancre.py:44",
    "0105_fichiers_urls_email_externe.py:13",
    "0109_publication_syndic_commentaire.py:138",
    "0109_publication_syndic_commentaire.py:145",
    "0110_ticket_syndic_commentaire.py:177",
    "0110_ticket_syndic_commentaire.py:184",
    "0122_execution_taches_planifiees.py:47",
    "0124_documents_prives_hors_tronc_servi.py:87",
    "0124_documents_prives_hors_tronc_servi.py:110",
    "0130_intention_modele_email.py:43",
    "0134_publication_photos_urls.py:31",
    "0143_libelle_long_des_batiments.py:106",
    "0152_annonce_workflow.py:95",
    "0160_cr_ag_perimetre_cible.py:94",
    "0190_acces_perimetre_cible.py:110",
    "0190_acces_perimetre_cible.py:144",
    "0193_saisi_pour_publication_evenement.py:63",
    "0194_assistant_ia_par_usage.py:75",
    "0196_declenchement_un_vocabulaire.py:78",
}


def _fstrings_sans_bindparams() -> set[str]:
    """Les `execute(...)` de migration qui interpolent sans lier, par AST."""
    import ast

    trouves = set()
    for fichier in sorted((_API_DIR / "alembic" / "versions").glob("*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            if not ast.unparse(noeud.func).endswith("execute"):
                continue
            if not any(isinstance(x, ast.JoinedStr) for x in ast.walk(noeud)):
                continue
            if "bindparams" in ast.unparse(noeud):
                continue
            trouves.add(f"{fichier.name}:{noeud.lineno}")
    return trouves


def test_le_controle_voit_bien_les_migrations():
    """Cas zéro de la portée : un glob vide se lirait comme « aucun écart »."""
    versions = list((_API_DIR / "alembic" / "versions").glob("*.py"))
    assert len(versions) > 100, (
        f"seulement {len(versions)} migration(s) vue(s) — le contrôle a perdu sa "
        "portée, et rendrait un vert parfait sur un répertoire vide"
    )


def test_aucune_NOUVELLE_fstring_sans_bindparams():
    """La 28e est refusee. Les 27 d'avant sont de l'historique, pas un retard."""
    nouvelles = sorted(_fstrings_sans_bindparams() - FSTRINGS_HISTORIQUES)
    saut = chr(10) + "  "
    assert not nouvelles, (
        "Ces `execute()` interpolent une f-string sans lier de parametre :"
        + saut
        + saut.join(nouvelles)
        + chr(10) * 2
        + "Une VALEUR se lie : text('... :x ...').bindparams(x=valeur)."
        + chr(10)
        + "Un IDENTIFIANT (nom de table ou de colonne) ne peut pas se lier en "
        + "SQLite : le prendre dans une constante du fichier, et ecrire en "
        + "commentaire que c'est un identifiant."
        + chr(10)
        + "Ne PAS ajouter la ligne a FSTRINGS_HISTORIQUES : cette liste est "
        + "l'etat du 19/09/2026, pas une tolerance ouverte."
    )


def test_aucune_entree_historique_ne_survit_a_son_fichier():
    """Une exception qui ne correspond plus a rien finit par couvrir autre chose."""
    perimees = sorted(FSTRINGS_HISTORIQUES - _fstrings_sans_bindparams())
    saut = chr(10) + "  "
    assert not perimees, (
        "Ces entrees de FSTRINGS_HISTORIQUES ne correspondent plus a rien :"
        + saut
        + saut.join(perimees)
        + chr(10) * 2
        + "La migration a ete supprimee, ou sa ligne a bouge. Les retirer."
    )
