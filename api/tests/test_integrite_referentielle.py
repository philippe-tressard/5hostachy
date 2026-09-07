"""Intégrité référentielle — ce qui est DÉJÀ vrai, verrouillé (#546).

## Pourquoi ces tests existent avant que le chantier soit fini

SQLite tourne avec `foreign_keys=OFF` — c'est son défaut, et l'application ne le
pose nulle part. **Aucune** des clés étrangères déclarées dans les modèles n'est
donc vérifiée par la base : l'intégrité repose entièrement sur le code applicatif.

L'étape 2 de #546 — rendre les fixtures référentiellement valides — est un lot à
part entière : avec les clés actives, la suite passe de **798 verts** à **39
erreurs et 6 échecs**, toutes des fixtures qui construisent des lignes orphelines.
Tant qu'elle n'est pas finie, activer les clés partout rendrait le job rouge en
permanence, donc désarmé (#419).

🔴 **Mais une correction qu'aucun test ne garde ne survit pas.** Ces tests
verrouillent ce qui est **déjà** réparé, en activant les clés sur leur propre
moteur — sans attendre que tout le soit. C'est la seule façon de faire avancer un
chantier par petits lots sans que le premier régresse pendant le second.

Pour rejouer la mesure complète :

    HOSTACHY_FK_STRICTES=1 pytest tests/ -q
"""
import os
import tempfile

os.environ.setdefault("SECRET_KEY", "x" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_API_DOCS", "false")
os.environ.setdefault("UPLOADS_DIR", os.path.join(tempfile.gettempdir(), "hostachy-tests-uploads"))

import pytest  # noqa: E402
from sqlalchemy import event, text  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402

from app.models.core import Batiment, Copropriete, Utilisateur  # noqa: E402
from app.models.perimetre import Perimetre  # noqa: E402
from tests.conftest import delier_references, vider_patrimoine  # noqa: E402


@pytest.fixture()
def moteur_strict():
    """Un moteur JETABLE avec `foreign_keys=ON`, isolé de celui de la suite.

    ⚠️ On ne touche pas au moteur partagé : l'activer là rendrait rouges les 39
    montages que l'étape 2 doit encore réparer, et ces tests-ci ne pourraient plus
    rien affirmer — un test noyé dans 39 erreurs voisines ne se lit pas.
    """
    moteur = create_engine("sqlite://", connect_args={"check_same_thread": False})

    @event.listens_for(moteur, "connect")
    def _pragma(dbapi_connection, _record):
        curseur = dbapi_connection.cursor()
        curseur.execute("PRAGMA foreign_keys=ON")
        curseur.close()

    SQLModel.metadata.create_all(moteur)
    yield moteur
    moteur.dispose()


def test_le_moteur_strict_applique_vraiment_les_cles(moteur_strict):
    """Cas zéro — sans lui, tous les tests de ce fichier passeraient pour rien.

    🔴 C'est le piège exact rencontré en instruisant #546 : l'écouteur posé sur un
    moteur dont la connexion est DÉJÀ ouverte (`SingletonThreadPool` de
    `sqlite:///:memory:`) n'émet jamais `connect`, le PRAGMA n'est jamais posé, et
    la suite reste **verte**. Un test d'intégrité sur un moteur permissif ne
    vérifie rien et ne le dit pas.
    """
    with Session(moteur_strict) as session:
        assert session.exec(text("PRAGMA foreign_keys")).one()[0] == 1

    #  Et la contrainte MORD réellement — le PRAGMA lu à 1 ne prouve que la
    #  lecture du réglage, pas son effet.
    with Session(moteur_strict) as session:
        session.add(Batiment(copropriete_id=99999, numero="fantôme"))
        with pytest.raises(Exception, match="FOREIGN KEY"):
            session.commit()


def test_la_purge_du_patrimoine_respecte_l_auto_reference(moteur_strict):
    """`Perimetre.parent_id` s'auto-référence : la purge doit aller des feuilles
    vers la racine.

    Avant #546, `vider_patrimoine` supprimait les périmètres dans un ordre
    arbitraire. La base l'acceptait — parce qu'elle ne vérifiait rien. Avec les
    clés actives, c'était **20 erreurs** dans quatre fichiers.
    """
    with Session(moteur_strict) as session:
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        racine = Perimetre(code="racine", libelle="Racine")
        session.add(racine)
        session.flush()
        enfant = Perimetre(code="enfant", libelle="Enfant", parent_id=racine.id)
        session.add(enfant)
        session.flush()
        session.add(Perimetre(code="petit", libelle="Petit-enfant", parent_id=enfant.id))
        session.commit()

        vider_patrimoine(session)
        assert session.exec(select(Perimetre)).all() == []
        assert session.exec(select(Copropriete)).all() == []


def test_la_purge_sait_defaire_un_cycle_de_parente(moteur_strict):
    """Un cycle `parent_id` ne doit ni bloquer la purge, ni la faire boucler.

    ⚠️ Ce n'est pas un cas théorique : `test_cycle_de_parente_ne_suspend_pas_et_refuse`
    en fabrique un **volontairement**, c'est son sujet. Une fixture de purge
    s'exécute précisément après les tests qui abîment les données exprès — elle
    n'a donc pas le droit de supposer un arbre sain.

    Sans ce cas, la première version de la purge par vagues tournait
    indéfiniment : plus aucune feuille à trouver, et une suite qui ne rend jamais
    la main ne dit pas qu'elle a échoué.
    """
    with Session(moteur_strict) as session:
        a = Perimetre(code="a", libelle="A")
        b = Perimetre(code="b", libelle="B")
        session.add(a)
        session.add(b)
        session.flush()
        a.parent_id = b.id
        b.parent_id = a.id
        session.add(a)
        session.add(b)
        session.commit()

        vider_patrimoine(session)
        assert session.exec(select(Perimetre)).all() == []


def test_un_noeud_qui_se_designe_lui_meme_ne_bloque_pas(moteur_strict):
    """Le cycle le plus court — et celui qui a fait échouer la première version.

    Un nœud dont le `parent_id` vaut son propre `id` n'est jamais une feuille : il
    est son propre parent. La purge doit le délier avant de l'effacer.
    """
    with Session(moteur_strict) as session:
        seul = Perimetre(code="seul", libelle="Seul")
        session.add(seul)
        session.flush()
        seul.parent_id = seul.id
        session.add(seul)
        session.commit()

        vider_patrimoine(session)
        assert session.exec(select(Perimetre)).all() == []


def test_la_purge_delie_les_references_au_batiment(moteur_strict):
    """Un bâtiment est référencé par ONZE colonnes, toutes nullables.

    La purge les effaçait sans s'en soucier : **132 violations**, la famille la
    plus nombreuse du relevé de #546. On délie, on ne supprime pas — un
    utilisateur ne cesse pas d'exister parce que le patrimoine de test est
    démonté, et une fixture qui l'effacerait retirerait des données que le test
    suivant attend peut-être.
    """
    with Session(moteur_strict) as session:
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        bat = Batiment(copropriete_id=copro.id, numero="1")
        session.add(bat)
        session.flush()
        session.add(
            Utilisateur(
                email="resident@test.fr",
                mot_de_passe_hash="x",
                nom="Résident",
                prenom="Test",
                batiment_id=bat.id,
            )
        )
        session.commit()

        vider_patrimoine(session)

        #  Le bâtiment est parti, l'utilisateur est resté — délié.
        assert session.exec(select(Batiment)).all() == []
        restant = session.exec(select(Utilisateur)).one()
        assert restant.batiment_id is None


def test_delier_ne_touche_PAS_les_colonnes_non_nullables(moteur_strict):
    """🔴 Le garde-fou du garde-fou.

    `delier_references` met à NULL ce qui est nullable. Une version qui
    tenterait aussi les colonnes NOT NULL échouerait — ou pire, les
    contournerait. `batiment.copropriete_id` est NOT NULL : délier les
    références à la copropriété doit le laisser intact.

    C'est ce qui distingue « délier » de « casser » : les porteurs NOT NULL
    doivent partir AVANT, et le contrôle doit le rendre visible plutôt que de le
    contourner en silence.
    """
    with Session(moteur_strict) as session:
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        session.add(Batiment(copropriete_id=copro.id, numero="1"))
        session.commit()

        delier_references(session, Copropriete)

        bat = session.exec(select(Batiment)).one()
        assert bat.copropriete_id == copro.id, (
            "une colonne NOT NULL a été déliée — la purge masquerait alors un "
            "ordre de suppression faux au lieu de le révéler"
        )


# ── Le garde-fou du garde-fou (#546, 29/08/2026) ─────────────────────────────

def test_la_suite_TOURNE_avec_les_cles_actives():
    """🔴 Sans ce test, tout le chantier peut redevenir inutile en silence.

    Les clés sont posées par un écouteur `connect` que `pytest_configure`
    enregistre sur le moteur de la suite. Si cet écouteur cesse d'être branché —
    une variable renommée, un `engine.dispose()` retiré, un import réordonné — la
    suite **reste verte** : elle se remet simplement à ne rien vérifier, comme
    avant les quatre lots.

    C'est exactement le faux vert que `standards/04` §1 décrit : un contrôle qui
    ne peut pas s'exécuter doit le DIRE, jamais conclure au succès. Ici, ce test
    est ce qui le fait dire.

    ⚠️ Il porte sur le moteur DE LA SUITE, pas sur un moteur jetable : les autres
    tests de ce fichier montent le leur, ce qui prouve la purge mais ne prouve
    rien du régime dans lequel les 870 autres tournent.

    ⚠️ Il tolère la porte de diagnostic `HOSTACHY_FK_STRICTES=0`, et seulement
    elle. Un lot qui a besoin de la fermer pour passer a un défaut à corriger.
    """
    import os

    from sqlmodel import Session, text

    from app.database import engine

    if os.environ.get("HOSTACHY_FK_STRICTES") == "0":
        pytest.skip("porte de diagnostic ouverte explicitement — régime non nominal")

    with Session(engine) as session:
        actif = session.exec(text("PRAGMA foreign_keys")).one()[0]
    assert actif == 1, (
        "les clés étrangères ne sont PAS actives sur le moteur de la suite : "
        "les 873 tests tournent sans vérifier une seule des 119 clés déclarées, "
        "et rien d'autre ne le dirait (#546)."
    )


def test_le_moteur_DE_L_APPLICATION_active_les_cles(tmp_path):
    """🔴 Le test précédent ne prouve PAS celui-ci, et c'est tout l'enjeu.

    `test_la_suite_TOURNE_avec_les_cles_actives` mesure le moteur de la SUITE,
    dont les clés sont posées par `conftest.pytest_configure`. Il resterait vert
    si `app/database.py` cessait de les activer : la production tournerait sans
    clés, et rien ne le dirait.

    Ce test-ci importe `app.database` dans un **sous-processus sans conftest**,
    et lit le PRAGMA sur une connexion réelle. C'est le seul montage qui mesure
    ce que fait le module pour de vrai.

    ## Ce qu'il verrouille précisément

    L'écouteur ne s'exécute qu'à l'OUVERTURE d'une connexion. Le bloc d'amorçage
    de `database.py` en ouvre une ; l'appel doit donc venir **avant** lui. Mesuré
    le 30/08/2026 en le plaçant après :

        appel APRÈS l'amorçage   → PRAGMA foreign_keys = 0
        appel AVANT l'amorçage   → PRAGMA foreign_keys = 1

    Déplacer cette ligne de vingt lignes suffit à désactiver les clés en
    production — sans qu'aucun test, aucun lint ni aucun démarrage ne bronche.
    C'est le piège que le docstring de `activer_cles_etrangeres` décrit, et qu'on
    peut refaire en la branchant.

    ⚠️ On vérifie AUSSI `synchronous` et `busy_timeout` : le `engine.dispose()`
    de la fonction recycle la connexion, et l'on doit établir qu'il n'emporte pas
    la durabilité choisie après les corruptions de juin 2026.
    """
    import json
    import pathlib
    import subprocess
    import sys

    programme = (
        "import os, json;"
        "os.environ['DATABASE_URL'] = 'sqlite:///' + %r;"
        "from sqlalchemy import text;"
        "from app.database import engine;"
        "c = engine.connect();"
        "print(json.dumps({p: c.execute(text('PRAGMA ' + p)).scalar()"
        " for p in ('foreign_keys', 'synchronous', 'busy_timeout')}))"
    ) % str(tmp_path / "essai.db").replace("\\", "/")

    api = pathlib.Path(__file__).resolve().parents[1]
    sortie = subprocess.run(
        [sys.executable, "-c", programme],
        cwd=str(api),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert sortie.returncode == 0, (
        "l'import de `app.database` a échoué dans un processus neuf — "
        f"c'est ce que fait le conteneur au démarrage.\n{sortie.stderr[-2000:]}"
    )
    reglages = json.loads(sortie.stdout.strip().splitlines()[-1])

    assert reglages["foreign_keys"] == 1, (
        "le moteur de l'APPLICATION ne pose pas `foreign_keys=ON`. Vérifier que "
        "`activer_cles_etrangeres(engine)` est appelé AVANT le bloc d'amorçage de "
        "`app/database.py` : après, l'écouteur ne prend pas effet (#546)."
    )
    assert reglages["synchronous"] == 2, (
        "`synchronous=FULL` a été perdu — le `dispose()` de l'activation des clés "
        "a emporté la durabilité posée après les corruptions de juin 2026."
    )
    assert reglages["busy_timeout"] == 5000, "`busy_timeout` a été perdu"
