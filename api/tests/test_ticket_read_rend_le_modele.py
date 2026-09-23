"""Ce qu'une affaire PORTE, sa lecture le REND (#1092, 23/09/2026).

## Le défaut

`ticket_read` construisait `TicketRead` champ par champ. Tout champ déclaré au
schéma et oublié dans l'appel prenait sa valeur par défaut, sans un mot :

| champ | conséquence |
|---|---|
| `debut`, `fin` | la section « Quand » ne se relisait pas : le calendrier et le filtre « Événement » n'avaient rien à lire, et une édition les effaçait |
| `suivi_kanban` | toujours `false` : le kanban des affaires était vide |
| `epingle` | toujours `false` : la case « épinglé » ne reflétait rien |
| `assiste_ia` | la marque « rédigé avec l'assistant » ne s'affichait jamais |

Le commentaire de `ticket_read` décrivait déjà ce défaut pour `confidentiel` —
corrigé à la main, pour ce champ-là seulement. `test_schemas_champs` vérifie le
sens inverse (un mot-clé inconnu du schéma) et écrit qu'il ne peut pas voir
celui-ci sans savoir « ce qui est facultatif ».

## Ce que ce test vérifie, sans avoir à le savoir

Une COLONNE du modèle qui porte le nom d'un champ du schéma doit revenir telle
quelle. On pose sur chacune une valeur qui n'est pas son défaut, et on relit.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import Ticket, Utilisateur
from app.routers.tickets.commun import ticket_read
from app.schemas import TicketRead

#: Les champs de lecture CALCULÉS à partir d'autre chose que la colonne du même
#: nom. Déclarés un par un, avec leur raison ; le test échoue si l'un cesse
#: d'être une colonne (l'exception ne servirait plus).
_DERIVES = {
    "perimetre_cible": "relu en liste depuis le JSON stocké",
    "photos_urls": "relu en liste depuis le JSON stocké",
    "fichiers_urls": "relu en liste depuis le JSON stocké",
}


def _valeur_non_defaut(nom: str, type_col) -> object:
    try:
        py = type_col.python_type
    except NotImplementedError:  # types SQLAlchemy sans équivalent Python direct
        return None
    if py is bool:
        return True
    if py is int:
        return None  # clés étrangères : on ne les invente pas
    if py is datetime:
        return datetime(2026, 10, 1, 9, 30)
    if py is date:
        return date(2026, 10, 2)
    if py is str:
        return None  # posées par la fabrique ci-dessous quand elles comptent
    return None


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


def test_chaque_colonne_partagee_revient_telle_quelle(session):
    auteur = Utilisateur(email=f"{uuid.uuid4().hex[:6]}@x.fr", mot_de_passe_hash="x", prenom="A", nom="B")
    session.add(auteur)
    session.commit()
    session.refresh(auteur)

    ticket = Ticket(
        numero="TK-000001", titre="T", description="D", categorie="panne",
        auteur_id=auteur.id, cree_le=datetime.utcnow(), mis_a_jour_le=datetime.utcnow(),
    )
    colonnes = Ticket.__table__.columns
    champs_lus = set(TicketRead.model_fields)
    partages = {c.name for c in colonnes} & champs_lus
    for nom in _DERIVES:
        assert nom in partages, f"`{nom}` déclaré dérivé, mais n'est plus une colonne partagée."

    poses: dict[str, object] = {}
    for c in colonnes:
        if c.name not in partages or c.name in _DERIVES or c.primary_key:
            continue
        v = _valeur_non_defaut(c.name, c.type)
        if v is not None:
            setattr(ticket, c.name, v)
            poses[c.name] = v
    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    #  Cas zéro : sans valeur posée, le test ne mesurerait rien.
    assert {"debut", "fin", "epingle", "suivi_kanban", "confidentiel"} <= set(poses), sorted(poses)

    lu = ticket_read(ticket, session)
    perdus = {
        nom: (attendu, getattr(lu, nom))
        for nom, attendu in poses.items()
        if getattr(lu, nom) != attendu
    }
    assert not perdus, (
        "Colonnes de l'affaire que sa lecture ne rend pas (valeur posée → valeur lue) : "
        f"{perdus}"
    )


# ── Et ce que le formulaire ENVOIE, le PATCH l'ÉCRIT (#1092) ──────────────────
#
#  `TicketUpdate` acceptait `debut`/`fin` ; `_appliquer_contenu` ne les
#  connaissait pas : 200, et rien d'écrit. Effacer une date, c'est envoyer
#  `null` — que « `is not None` » confond avec « absent ».

from app.routers.tickets.correction import _appliquer_contenu, _appliquer_quand  # noqa: E402
from app.routers.tickets.mise_a_jour import _touche_au_contenu  # noqa: E402
from app.schemas import TicketUpdate  # noqa: E402


def _affaire_datee() -> Ticket:
    return Ticket(numero="TK-1", titre="T", description="D", categorie="panne", auteur_id=1,
                  debut=datetime(2026, 10, 1, 9, 0), fin=datetime(2026, 10, 1, 12, 0))


def test_le_patch_ecrit_une_date_et_l_annonce():
    t = _affaire_datee()
    changes = _appliquer_quand(TicketUpdate(debut=datetime(2026, 10, 8, 9, 0)), t)
    assert t.debut == datetime(2026, 10, 8, 9, 0)
    assert t.fin == datetime(2026, 10, 1, 12, 0), "un champ absent ne se touche pas"
    assert any("Quand" in c for c in changes), changes


def test_le_patch_efface_une_date_envoyee_a_null():
    t = _affaire_datee()
    corps = TicketUpdate(debut=None, fin=None)
    #  « Quand » n'est plus du contenu (23/09/2026) : le conseil le planifie.
    assert not _touche_au_contenu(corps), "les dates ne sont pas le contenu de l'auteur"
    _appliquer_quand(corps, t)
    assert t.debut is None and t.fin is None


def test_la_meme_date_ne_s_annonce_pas():
    t = _affaire_datee()
    assert _appliquer_quand(TicketUpdate(debut=t.debut, fin=t.fin), t) == []
