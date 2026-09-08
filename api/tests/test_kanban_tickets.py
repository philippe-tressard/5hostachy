"""Un ticket « Étude & travaux » au kanban — la correspondance ne dérive pas (#833).

## Ce que ce fichier verrouille

1. la **correspondance** statut → colonne, dans les deux langages ;
2. les **colonnes visées existent** dans le kanban — une carte rangée dans une
   colonne inconnue disparaît sans rien dire ;
3. `fournisseur` reste **inatteignable** depuis un ticket, et c'est un constat
   déclaré, pas un oubli.

⚠️ La table est écrite **deux fois** — `app/utils/kanban_tickets.py` et
`front/src/lib/kanban.ts` — parce que les contextes de build sont `./api` et
`./front` : le partage d'un fichier est impossible, seule la copie l'est. C'est
le même dispositif que `KANBAN_LABELS` de `calendrier_historique.py`, et c'est ce
test qui rend la copie tenable.
"""
from __future__ import annotations

import pathlib
import re

from app.models.tickets import StatutTicket
from app.utils.kanban_tickets import (
    CATEGORIES_SUIVIES,
    COLONNE_PAR_STATUT,
    colonne_du_ticket,
    suivi_par_defaut,
)

_KANBAN_TS = (
    pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "kanban.ts"
)


def _table_ts(nom: str) -> dict[str, str]:
    source = _KANBAN_TS.read_text(encoding="utf-8")
    debut = source.index(f"export const {nom}")
    corps = source[source.index("{", debut) + 1 : source.index("};", debut)]
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r"^\t(\S+?):\s*'([^']*)',", corps, re.MULTILINE)
    }


def _colonnes_du_front() -> set[str]:
    """Les identifiants de `KANBAN_COLS` — la source unique des colonnes."""
    source = _KANBAN_TS.read_text(encoding="utf-8")
    debut = source.index("export const KANBAN_COLS")
    corps = source[debut : source.index("];", debut)]
    return set(re.findall(r"id:\s*'([^']+)'", corps))


def test_TOUS_les_statuts_de_ticket_ont_une_colonne():
    """🔴 Un statut sans colonne fait disparaître la carte, en silence.

    L'énumération fait foi : si un cinquième état apparaît, ce test l'exige ici
    avant que le tableau ne se mette à perdre des tickets.
    """
    for statut in StatutTicket:
        assert statut.value in COLONNE_PAR_STATUT, (
            f"statut sans colonne kanban : {statut.value}. Le ticket "
            "disparaîtrait du tableau sans que rien ne le signale."
        )


def test_les_colonnes_visees_EXISTENT_dans_le_kanban():
    """Une colonne inventée range la carte nulle part."""
    colonnes = _colonnes_du_front()
    assert len(colonnes) >= 6, "extraction de `KANBAN_COLS` cassée — rien ne serait mesuré"
    inconnues = set(COLONNE_PAR_STATUT.values()) - colonnes
    assert not inconnues, f"colonnes inconnues du kanban : {sorted(inconnues)}"


def test_la_colonne_FOURNISSEUR_reste_inatteignable():
    """⚠️ Un constat déclaré, pas un oubli.

    Aucun statut de ticket ne dit « chez le prestataire ». L'écrire ici rend la
    décision visible : le jour où un cinquième statut apparaîtra, ce test posera
    la question au lieu de laisser quelqu'un l'ajouter en passant.
    """
    assert "fournisseur" not in COLONNE_PAR_STATUT.values()
    assert "fournisseur" in _colonnes_du_front(), (
        "la colonne a disparu du kanban — ce test ne dit alors plus rien"
    )


def test_le_FRONT_ecrit_EXACTEMENT_la_meme_table():
    """🔴 Le garde-fou de la copie assumée.

    Deux écritures d'une même correspondance divergent au premier ajustement, et
    le tableau rangerait alors les cartes autrement que le serveur ne le croit.
    """
    du_front = _table_ts("COLONNE_PAR_STATUT_TICKET")
    assert du_front == COLONNE_PAR_STATUT, (
        "la table du front et celle du serveur ont divergé :\n"
        f"  serveur : {COLONNE_PAR_STATUT}\n"
        f"  front   : {du_front}"
    )


def test_un_statut_INCONNU_ne_range_nulle_part():
    """⚠️ `None`, jamais un repli sur `cs`.

    Une carte posée dans la mauvaise colonne se lit comme une information, et
    personne ne la remet en cause. Mieux vaut qu'elle n'apparaisse pas.
    """
    assert colonne_du_ticket("chez_le_notaire") is None
    assert colonne_du_ticket(None) is None
    assert colonne_du_ticket("") is None


def test_seule_ETUDE_TRAVAUX_entre_au_tableau_d_office():
    """Le défaut par catégorie — et le fait que les autres n'y entrent pas.

    Sans le second cas, « coché d'office » pourrait vouloir dire « coché pour
    tout le monde », et le tableau du conseil se remplirait d'ampoules grillées.
    """
    assert suivi_par_defaut("etude_travaux") is True
    for autre in ("panne", "nuisance", "sinistre", "bug", None):
        assert suivi_par_defaut(autre) is False, f"{autre} entre au tableau d'office"


def test_la_categorie_visee_EXISTE_vraiment():
    """Un identifiant de catégorie mal orthographié ne lève pas : il n'apparie rien.

    `suivi_par_defaut` rendrait alors `False` pour tout le monde, et la
    fonctionnalité serait silencieusement morte.
    """
    from app.utils.categories_ticket import LIBELLES_CATEGORIE

    for categorie in CATEGORIES_SUIVIES:
        assert categorie in LIBELLES_CATEGORIE, (
            f"catégorie inconnue : {categorie}. `suivi_par_defaut` rendrait "
            "toujours False, et aucun ticket n'entrerait au tableau."
        )
