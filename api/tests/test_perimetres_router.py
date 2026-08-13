"""`GET /perimetres` — le router, qui n'était couvert par aucun test.

Livré sans test dans la v2.55.0, il a répondu **500 en production** dès le premier
appel : `_codes_cites` dépaquetait `(valeur,)` alors que
`session.exec(select(<colonne>))` rend des scalaires. `ValueError: too many values
to unpack` tombait sur toute chaîne de plus d'un caractère — donc sur toutes.

Le lot portait 23 tests sur les RÈGLES (voir `test_perimetres_arbre.py`) et aucun
sur le chemin qui les sert. Fichier séparé pour que cette distinction reste
visible : les règles d'un côté, le point d'entrée de l'autre.

La vérification en navigateur, elle, avait bien exercé l'écran — mais sur une base
fraîchement semée où aucun contenu ne citait de périmètre, si bien que la boucle
fautive n'était jamais atteinte. Ces tests écrivent donc du contenu AVANT de lire.
"""
from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Batiment,
    Copropriete,
    Evenement,
    Publication,
    TypeEvenement,
    Utilisateur,
)
from app.models.perimetre import Perimetre
from app.routers.patrimoine import _codes_cites, _en_lecture
from app.seed.patrimoine import poser_arborescence
from app.utils import perimetres as P


def _vider(session: Session) -> None:
    #  Le marqueur de semis part avec l'arborescence : sans lui, `poser_arborescence`
    #  croirait avoir déjà semé et laisserait les tests sur une base vide.
    from app.models.core import ConfigSite
    from app.seed.patrimoine import CLE_SEMEE

    marqueur = session.get(ConfigSite, CLE_SEMEE)
    if marqueur:
        session.delete(marqueur)
    for modele in (Publication, Evenement, Perimetre, Batiment, Copropriete):
        for ligne in session.exec(select(modele)).all():
            session.delete(ligne)
    session.commit()


@pytest.fixture()
def batiments() -> list[int]:
    """Arbre semé sur quatre bâtiments réels. Renvoie leurs identifiants."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _vider(session)
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        for numero in ("1", "2", "3", "4"):
            session.add(Batiment(copropriete_id=copro.id, numero=numero))
        session.commit()
        ids = list(session.exec(select(Batiment.id).order_by(Batiment.id)).all())
        poser_arborescence(session)
        session.commit()
    P.invalider_cache()
    yield ids
    P.invalider_cache()


def _auteur(session: Session) -> int:
    """`Publication.auteur_id` et `Evenement.auteur_id` sont NOT NULL."""
    existant = session.exec(
        select(Utilisateur).where(Utilisateur.email == "auteur@test.fr")
    ).first()
    if existant:
        return existant.id
    u = Utilisateur(nom="A", prenom="B", email="auteur@test.fr", actif=True)
    session.add(u)
    session.commit()
    return u.id


def test_lecture_de_l_arborescence_par_le_router(batiments):
    """`GET /perimetres` rend l'arbre — le contrôle qui manquait.

    Livré sans test, ce router a répondu **500 en production** dès le premier
    appel : `_codes_cites` dépaquetait `(valeur,)` alors que
    `session.exec(select(<colonne>))` rend des scalaires, et `ValueError: too many
    values to unpack` tombait sur toute chaîne de plus d'un caractère — donc sur
    toutes. L'écran d'administration restait vide et les libellés retombaient sur
    leur calcul de repli.

    Les tests portaient sur les règles, jamais sur le chemin qui les sert : un
    module entier était hors de portée, et rien ne le signalait.
    """

    with Session(engine) as session:
        auteur = _auteur(session)
        #  Un contenu qui cite deux périmètres, pour que `utilise` ait à les trouver
        #  dans les deux formats stockés (JSON et CSV).
        session.add(Publication(titre="T", contenu="C", auteur_id=auteur,
                                perimetre_cible='["aful", "bat:%d"]' % batiments[0]))
        session.commit()

        cites = _codes_cites(session)
        assert "aful" in cites
        assert f"bat:{batiments[0]}" in cites

        lus = _en_lecture(list(session.exec(select(Perimetre)).all()), cites)

    assert len(lus) == 63, f"63 nœuds semés, {len(lus)} rendus"

    par_code = {n.code: n for n in lus}
    #  L'ordre est un parcours en profondeur : un enfant suit son parent.
    assert lus[0].code == "résidence"
    assert par_code["bat:%d/hall" % batiments[0]].profondeur == 2
    assert par_code["bat:%d/hall" % batiments[0]].parent == f"bat:{batiments[0]}"
    #  Héritage de la portée : le portail du parking concerne tout le monde.
    assert par_code["parking/portail"].concerne_tous is True
    assert par_code["parking/portail"].portee_globale is False
    #  Un espace de bâtiment ne concerne pas tout le monde.
    assert par_code["bat:%d/hall" % batiments[0]].concerne_tous is False
    #  `utilise` distingue ce qui est cité de ce qui ne l'est pas.
    assert par_code["aful"].utilise is True
    assert par_code["cheminements"].utilise is False


def test_codes_cites_lit_les_trois_formats_de_stockage(batiments):
    """JSON, CSV et champ vide : les cinq entités n'écrivent pas pareil."""

    with Session(engine) as session:
        auteur = _auteur(session)
        session.add(Publication(titre="J", contenu="C", auteur_id=auteur,
                                perimetre_cible='["parking"]'))
        session.add(Evenement(titre="E", type=TypeEvenement.travaux, auteur_id=auteur,
                              debut=datetime(2026, 8, 12, 9, 0),
                              perimetre="espaces-verts,cheminements"))
        session.commit()
        cites = _codes_cites(session)

    assert {"parking", "espaces-verts", "cheminements"} <= cites


# ── Le seed ne doit plus jamais annuler une suppression ───────────────────────

def test_le_seed_ne_repose_pas_ce_qui_a_ete_supprime(batiments):
    """Une suppression doit survivre au déploiement suivant.

    `seed()` tourne au démarrage de l'API, donc à CHAQUE déploiement. La première
    écriture reposait « ce qui manque » : un périmètre supprimé depuis
    l'administration ressuscitait à la mise à jour suivante — « à chaque mise à
    jour mes périmètres ajoutés, supprimés sont perdus » (13/08/2026).

    La règle du paquet `seed` protège les MODIFICATIONS, pas les SUPPRESSIONS :
    un seed ne distingue pas un nœud supprimé d'un nœud jamais posé. D'où le
    marqueur `ConfigSite["perimetres_semes"]`.
    """
    from app.models.core import ConfigSite
    from app.seed.patrimoine import CLE_SEMEE

    with Session(engine) as session:
        assert session.get(ConfigSite, CLE_SEMEE) is not None, (
            "le premier semis doit poser son marqueur"
        )

        #  L'administrateur supprime un périmètre, et en ajoute un à lui.
        cible = session.exec(select(Perimetre).where(Perimetre.code == "cheminements")).one()
        for enfant in session.exec(
            select(Perimetre).where(Perimetre.parent_id == cible.id)
        ).all():
            session.delete(enfant)
        session.delete(cible)
        session.add(Perimetre(code="piscine", libelle="Piscine", portee_globale=True))
        session.commit()

        #  Un déploiement plus tard : le seed repasse.
        assert poser_arborescence(session) == 0, "le seed ne doit plus rien poser"
        session.commit()

        codes = {n.code for n in session.exec(select(Perimetre)).all()}
        assert "cheminements" not in codes, "la suppression a été annulée par le seed"
        assert "piscine" in codes, "l'ajout de l'administrateur a disparu"
        assert "résidence" in codes, "le reste de l'arborescence doit être intact"


def test_le_seed_pose_bien_l_arbre_sur_une_base_vierge():
    """Le marqueur ne doit pas empêcher le premier semis.

    C'est le cas zéro : une installation neuve doit obtenir son arborescence.
    """
    from app.models.core import ConfigSite
    from app.seed.patrimoine import CLE_SEMEE

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _vider(session)
        marqueur = session.get(ConfigSite, CLE_SEMEE)
        if marqueur:
            session.delete(marqueur)
        session.commit()

        poses = poser_arborescence(session)
        session.commit()
        assert poses > 0, "une base vierge doit recevoir l'arborescence"
        assert session.get(ConfigSite, CLE_SEMEE) is not None

        #  Et une seconde exécution ne pose plus rien.
        assert poser_arborescence(session) == 0


# ── Icônes : initialisation, jamais écrasement ────────────────────────────────

def test_le_seed_pose_les_icones_initiales(batiments):
    """Chaque périmètre semé porte une icône que `Icon.svelte` sait rendre."""
    from app.seed.patrimoine import icone_pour

    with Session(engine) as session:
        noeuds = session.exec(select(Perimetre)).all()
        sans = [n.code for n in noeuds if not n.icone and icone_pour(n.code)]
        assert not sans, f"périmètre(s) sans icône alors qu'une était prévue : {sans}"

        par_code = {n.code: n.icone for n in noeuds}
        assert par_code["parking"] == "car"
        assert par_code["aful"] == "square-parking"
        assert par_code[f"bat:{batiments[0]}/ascenseur"] == "arrow-up-down"
        assert par_code[f"bat:{batiments[0]}"] == "building-2"


def test_les_icones_proposees_existent_toutes_dans_le_composant():
    """Une icône inconnue de `Icon.svelte` s'affiche en point d'interrogation.

    Le contrôle est statique parce que le couplage est implicite : la table du
    seed et celle du composant vivent dans deux langages et deux dossiers, et rien
    à l'exécution ne signale qu'un nom a été inventé.
    """
    import re
    from pathlib import Path

    from app.seed.patrimoine import ICONES_GABARIT, ICONES_INITIALES

    composant = (
        Path(__file__).resolve().parents[2]
        / "front" / "src" / "lib" / "components" / "Icon.svelte"
    )
    disponibles = set(re.findall(r"^\s*'([a-z0-9-]+)':", composant.read_text(encoding="utf-8"), re.M))
    assert disponibles, "cas zéro : aucune icône lue dans Icon.svelte"

    voulues = set(ICONES_INITIALES.values()) | set(ICONES_GABARIT.values()) | {"building-2"}
    manquantes = sorted(voulues - disponibles)
    assert not manquantes, (
        "icône(s) citée(s) par le seed mais absente(s) d'Icon.svelte — elles "
        f"s'afficheraient en « ? » : {manquantes}"
    )
