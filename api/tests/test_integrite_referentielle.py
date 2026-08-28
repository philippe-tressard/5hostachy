"""Intégrité référentielle — ce qui est DÉJÀ vrai, verrouillé (#546).

## Pourquoi ces tests existent avant que le chantier soit fini

SQLite tourne avec `foreign_keys=OFF` — c'est son défaut, et l'application ne le
pose nulle part. **Aucune** des clés étrangères déclarées dans les modèles n'est
donc vérifiée par la base : l'intégrité repose entièrement sur le code applicatif.

L'étape 2 de #546 — rendre les fixtures référentiellement valides — est un lot à
part entière : avec les clés actives, la suite passe de **798 verts** à **83
erreurs et 4 échecs**, toutes des fixtures qui construisent des lignes orphelines.
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

from app.models.core import Batiment, Copropriete  # noqa: E402
from app.models.perimetre import Perimetre  # noqa: E402
from tests.conftest import vider_patrimoine  # noqa: E402


@pytest.fixture()
def moteur_strict():
    """Un moteur JETABLE avec `foreign_keys=ON`, isolé de celui de la suite.

    ⚠️ On ne touche pas au moteur partagé : l'activer là rendrait rouges les 83
    montages que l'étape 2 doit encore réparer, et ces tests-ci ne pourraient plus
    rien affirmer — un test noyé dans 83 erreurs voisines ne se lit pas.
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
