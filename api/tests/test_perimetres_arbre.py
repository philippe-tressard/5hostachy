"""L'arborescence des périmètres ne change **aucun** verdict d'accès.

Le périmètre décide qui voit une actualité ou un événement
(`utils/visibility.perimetre_visible`) et qui reçoit un e-mail
(`utils/destinataires.batiments_du_perimetre`). Le remplacer par un arbre en base
change la nature de la règle : une comparaison de chaînes devient une question
d'ascendance. Ce fichier est ce qui autorise ce changement.

Le contrôle central n'est pas « la nouvelle règle est-elle correcte ? » — cette
question ne se vérifie pas — mais **« rend-elle exactement les mêmes verdicts que
l'ancienne ? »**. L'ancienne implémentation est donc recopiée ici, telle qu'elle
était avant le remplacement, et rejouée contre la nouvelle sur tous les couples
(périmètre × utilisateur). Un écart fait échouer la suite.

Deux comportements changent **volontairement**, et sont testés comme tels :

1. une donnée illisible **refuse** au lieu d'élargir (`_codes_json_pour_acces`) ;
2. un arbre vide ou inconnu ne restreint rien, ce qui permet de servir une autre
   copropriété sans qu'aucun code de périmètre existe dans le code.
"""
import ast
import itertools
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.perimetre import Perimetre
from app.models.core import (
    Batiment, ConfigSite, Copropriete, Publication, RoleUtilisateur, Utilisateur,
)
from app.seed.patrimoine import CLE_SEMEE, GABARIT_BATIMENT, poser_arborescence
from app.utils import perimetres as P
from tests.conftest import vider_patrimoine
from app.utils.destinataires import batiments_du_perimetre
from app.utils.visibility import perimetre_visible, publication_visible

RACINE_API = Path(__file__).resolve().parents[1]


# ── L'ancienne implémentation, recopiée telle quelle ──────────────────────────

#: `utils/visibility.SCOPES_RESIDENCE`, supprimée par ce lot.
ANCIENS_SCOPES = frozenset({"résidence", "parking", "cave", "aful"})


def ancien_perimetre_visible(perimetres: list[str], roles: list[str],
                             batiment_id: int | None) -> bool:
    """`utils/visibility.perimetre_visible` d'avant le remplacement."""
    if "admin" in roles or "conseil_syndical" in roles:
        return True
    if not perimetres:
        return True
    perims_lower = {p.lower() for p in perimetres}
    if perims_lower & ANCIENS_SCOPES:
        return True
    if batiment_id is None:
        return True
    return f"bat:{batiment_id}" in perims_lower


def ancien_batiments_du_perimetre(perimetres: list[str]) -> set[int] | None:
    """`utils/destinataires.batiments_du_perimetre` d'avant le remplacement."""
    if not perimetres:
        return None
    ids: set[int] = set()
    for p in perimetres:
        p = p.lower()
        if p in ANCIENS_SCOPES:
            return None
        if p.startswith("bat:"):
            ident = p.split(":", 1)[1]
            if ident.isdigit():
                ids.add(int(ident))
    return ids or None


#: Les libellés que produisait la table en dur (`PERIMETRE_LABELS`), pour les codes
#: réellement en service. Le seed doit les reproduire à l'identique : ils
#: s'affichent sur des contenus déjà publiés.
ANCIENS_LIBELLES = {
    "résidence": "Copropriété entière",
    "parking": "Parking",
    "cave": "Cave",
    "aful": "AFUL",
}


# ── Montage ───────────────────────────────────────────────────────────────────

#  Le montage (quatre bâtiments + arbre semé) et la purge vivent dans
#  `conftest.py` depuis le 14/08/2026 : ils étaient écrits à l'identique ici et
#  dans `test_perimetres_router.py`, et leurs deux `_vider` avaient déjà divergé.
#  La fixture `batiments` est donc injectée sans être déclarée dans ce fichier.
_vider = vider_patrimoine


def utilisateur(roles: str, batiment_id: int | None) -> Utilisateur:
    return Utilisateur(
        nom="X", prenom="Y", email=f"{roles}-{batiment_id}@test.fr",
        roles_json=roles, batiment_id=batiment_id, actif=True,
    )


PROFILS = ["résident", "propriétaire", "conseil_syndical", "admin"]


def _auteur(session: Session) -> int:
    """Un utilisateur persisté — `Publication.auteur_id` et `Evenement.auteur_id`
    sont NOT NULL, et un contenu sans auteur ne s'écrit pas."""
    existant = session.exec(
        select(Utilisateur).where(Utilisateur.email == "auteur@test.fr")
    ).first()
    if existant:
        return existant.id
    u = Utilisateur(nom="A", prenom="B", email="auteur@test.fr", actif=True)
    session.add(u)
    session.commit()
    return u.id


# ── Le contrôle central : aucun verdict ne change ─────────────────────────────

def test_equivalence_stricte_sur_les_codes_en_service(batiments):
    """Personne ne gagne ni ne perd un accès. C'est ce qui autorise le changement."""
    codes = list(ANCIENS_SCOPES) + [f"bat:{i}" for i in batiments]
    #  Combinaisons de 0, 1 et 2 périmètres : le cas à deux est celui qui distingue
    #  une intersection d'ensembles d'une remontée d'arbre.
    cibles = [[]] + [[c] for c in codes] + [list(p) for p in itertools.combinations(codes, 2)]
    #  `batiments[-1] + 1` : un utilisateur rattaché à un bâtiment qui n'a pas de
    #  nœud, pour vérifier que l'absence ne devient pas une autorisation.
    rattachements = [None] + batiments + [batiments[-1] + 1]

    ecarts = []
    for cible, roles, batiment_id in itertools.product(cibles, PROFILS, rattachements):
        attendu = ancien_perimetre_visible(cible, [roles], batiment_id)
        obtenu = perimetre_visible(cible, utilisateur(roles, batiment_id))
        if attendu != obtenu:
            ecarts.append((cible, roles, batiment_id, attendu, obtenu))
    assert not ecarts, f"{len(ecarts)} verdict(s) de visibilité modifié(s) : {ecarts[:5]}"


def test_equivalence_des_destinataires(batiments):
    """Les mêmes membres du conseil syndical sont notifiés, pour les mêmes ciblages."""
    codes = list(ANCIENS_SCOPES) + [f"bat:{i}" for i in batiments]
    cibles = [[]] + [[c] for c in codes] + [list(p) for p in itertools.combinations(codes, 2)]

    ecarts = []
    for cible in cibles:
        attendu = ancien_batiments_du_perimetre(cible)
        obtenu = batiments_du_perimetre(cible)
        if attendu != obtenu:
            ecarts.append((cible, attendu, obtenu))
    assert not ecarts, f"{len(ecarts)} verdict(s) de notification modifié(s) : {ecarts}"


def test_libelles_des_codes_en_service_inchanges(batiments):
    """Un libellé qui change, c'est un changement visible sur du contenu publié."""
    for code, libelle in ANCIENS_LIBELLES.items():
        assert P.perimetre_label_un(code) == libelle

    #  ⚠️ Les bâtiments font exception depuis le 14/08/2026, et c'est un changement
    #  VOULU, pas une dérive : le seed remplissait `libelle` et `libelle_court` à
    #  l'identique (« Bât. {id} »), ce qui rendait le second inutile et imposait
    #  l'abréviation jusque sur le document imprimé remis aux arrivants. Le long
    #  sert aux documents et aux e-mails, l'abrégé aux badges contraints.
    #
    #  Ce test garde tout son sens : il continue d'interdire qu'un libellé bouge
    #  SANS qu'on l'ait décidé — il fallait venir l'éditer ici pour que le lot
    #  passe, et c'est exactement ce qu'on lui demande de faire.
    #  Migration correspondante : `0143_libelle_long_des_batiments`.
    for identifiant in batiments:
        assert P.perimetre_label_un(f"bat:{identifiant}") == f"Bâtiment {identifiant}"
        noeud = P.arbre()[f"bat:{identifiant}"]
        assert noeud.libelle_court == f"Bât. {identifiant}", (
            "l'abrégé doit rester court : c'est lui que lisent le calendrier et le "
            "sélecteur de périmètre, où la place est contrainte"
        )
    #  Le séparateur du rendu multiple ne bouge pas non plus.
    assert P.perimetre_label(["bat:1", "parking"]) == "Bâtiment 1 · Parking"


# ── Le repli permissif, épinglé pour qu'il ne bouge pas par accident ──────────

def test_utilisateur_sans_batiment_voit_tout(batiments):
    """Repli permissif conservé volontairement — suivi à part, pas corrigé ici.

    Le changer modifierait qui voit quoi aujourd'hui. Ce test existe pour qu'il ne
    se corrige pas *par inadvertance* au détour d'une refonte de l'arbre.
    """
    sans_batiment = utilisateur("résident", None)
    assert perimetre_visible([f"bat:{batiments[0]}"], sans_batiment) is True


# ── Ce qui change volontairement : la donnée abîmée refuse ────────────────────

@pytest.mark.parametrize("cible_corrompue", [
    "ceci n'est pas du json",
    '{"pas": "une liste"}',
    "[",
    '"résidence"',
])
def test_ciblage_illisible_refuse_au_lieu_delargir(batiments, cible_corrompue):
    """Une donnée abîmée élargissait la visibilité : elle la refuse désormais."""
    publication = Publication(
        titre="T", contenu="C", perimetre_cible=cible_corrompue, public_cible='["résidents"]',
    )
    assert publication_visible(publication, utilisateur("résident", batiments[0])) is False


def test_ciblage_illisible_reste_visible_du_conseil_syndical(batiments):
    """Sans quoi personne ne pourrait plus corriger la publication abîmée."""
    publication = Publication(
        titre="T", contenu="C", perimetre_cible="[", public_cible='["résidents"]',
    )
    assert publication_visible(publication, utilisateur("conseil_syndical", None)) is True


def test_perimetre_absent_reste_permissif(batiments):
    """Champ vide ≠ champ corrompu : l'absence de ciblage n'a jamais rien restreint."""
    publication = Publication(
        titre="T", contenu="C", perimetre_cible=None, public_cible='["résidents"]',
    )
    assert publication_visible(publication, utilisateur("résident", batiments[0])) is True


# ── Échec fermé sur un arbre abîmé ───────────────────────────────────────────

def test_code_inconnu_naccorde_rien(batiments):
    """Un contenu qui cite un nœud supprimé n'ouvre aucun accès."""
    assert perimetre_visible(["periscope-imaginaire"], utilisateur("résident", batiments[0])) is False


def test_cycle_de_parente_ne_suspend_pas_et_refuse(batiments):
    """Une boucle dans l'arbre doit rendre la main, et ne rien accorder."""
    with Session(engine) as session:
        a = Perimetre(code="cycle-a", libelle="A")
        b = Perimetre(code="cycle-b", libelle="B")
        session.add(a)
        session.add(b)
        session.flush()
        a.parent_id, b.parent_id = b.id, a.id
        session.add(a)
        session.add(b)
        session.commit()
    P.invalider_cache()

    assert P.a_portee_globale(["cycle-a"]) is False
    assert P.batiments_cibles(["cycle-a"]) == set()
    assert perimetre_visible(["cycle-a"], utilisateur("résident", batiments[0])) is False


def test_parent_orphelin_ne_suspend_pas_et_refuse(batiments):
    """Un `parent_id` qui ne pointe sur rien arrête la remontée sans lever."""
    with Session(engine) as session:
        session.add(Perimetre(code="orphelin", libelle="Orphelin", parent_id=999_999))
        session.commit()
    P.invalider_cache()

    assert P.a_portee_globale(["orphelin"]) is False
    assert perimetre_visible(["orphelin"], utilisateur("résident", batiments[0])) is False


# ── L'arbre vide : servir une autre copropriété ──────────────────────────────

def test_arbre_vide_ne_leve_aucune_erreur(arbre_vide):
    """Aucun périmètre configuré est un état valide, pas une panne.

    C'est le contrôle qui prouve qu'aucun code de périmètre n'est en dur : une
    copropriété qui repart de zéro ne doit obtenir ni 500 ni exception.
    """
    assert P.arbre() == {}
    assert P.code_par_defaut() is None
    assert P.parse_perimetres(None) == []
    assert P.parse_json_perimetres(None) == []
    assert P.a_portee_globale(["quoi-que-ce-soit"]) is False
    assert P.batiments_cibles(["quoi-que-ce-soit"]) == set()
    #  Un contenu sans périmètre reste visible : c'est le sens de « rien ne casse ».
    assert perimetre_visible([], utilisateur("résident", 1)) is True
    #  Et le libellé ne sort jamais un code brut illisible.
    assert P.perimetre_label_un("bat:7") == "Bât. 7"


def test_arbre_vide_naccorde_rien_sur_un_code_cite(arbre_vide):
    """Un arbre vide ou illisible n'est **pas** une autorisation.

    Première écriture de `perimetre_visible` : un court-circuit à `True` dès que
    l'arbre était vide. `tests/test_documents_acces.py` l'a attrapé — une pièce
    jointe ciblée sur un autre bâtiment devenait lisible dès que la table manquait.
    Un contrôle qui ne peut pas s'exécuter ne renvoie jamais OK (`standards/04`).
    """
    resident = utilisateur("résident", 1)
    assert perimetre_visible(["bat:1"], resident) is False
    assert perimetre_visible(["résidence"], resident) is False
    assert batiments_du_perimetre(["bat:1"]) is None

    #  Le conseil syndical et l'administration gardent l'accès : sans quoi personne
    #  ne pourrait reconstruire l'arborescence.
    assert perimetre_visible(["bat:1"], utilisateur("conseil_syndical", None)) is True
    assert perimetre_visible(["bat:1"], utilisateur("admin", None)) is True


def test_perimetre_par_defaut_vient_des_donnees(batiments):
    """La valeur par défaut est une donnée, pas la chaîne « résidence » en dur."""
    assert P.code_par_defaut() == "résidence"
    assert P.parse_perimetres(None) == ["résidence"]

    #  Renommer le nœud par défaut ne casse rien : le repli suit les données.
    with Session(engine) as session:
        racine = session.exec(select(Perimetre).where(Perimetre.code == "résidence")).one()
        racine.libelle = "Toute la copro"
        session.add(racine)
        session.commit()
    P.invalider_cache()
    assert P.perimetre_label_un("résidence") == "Toute la copro"
    assert P.parse_perimetres(None) == ["résidence"]


# ── La cave relève d'un bâtiment, sans casser l'historique ───────────────────

def test_cave_retiree_de_la_saisie_mais_toujours_rendue(batiments):
    """Historique préservé, pastille retirée : le seul compromis qui ne coûte rien."""
    with Session(engine) as session:
        cave = session.exec(select(Perimetre).where(Perimetre.code == "cave")).one()
        assert cave.selectionnable is False, "la cave ne doit plus être proposée à la saisie"
        assert cave.portee_globale is True, "les contenus déjà publiés gardent leur visibilité"

    #  Une actualité déjà publiée sur « cave » reste visible de tous, et affichée.
    assert perimetre_visible(["cave"], utilisateur("résident", batiments[1])) is True
    assert P.perimetre_label_un("cave") == "Cave"

    #  Et la façon normale de cibler une cave est désormais celle du bâtiment.
    code_bat = f"bat:{batiments[0]}"
    assert f"{code_bat}/caves" in P.arbre()


def test_espace_profond_concerne_son_batiment(batiments):
    """« Bât. 2 › Hall d'entrée » concerne le bâtiment 2, et lui seul.

    C'est la remontée d'arbre : le hall ne porte pas de `batiment_id`, il l'hérite.
    """
    premier, second = batiments[0], batiments[1]
    hall = f"bat:{second}/hall"

    assert P.batiments_cibles([hall]) == {second}
    assert perimetre_visible([hall], utilisateur("résident", second)) is True
    assert perimetre_visible([hall], utilisateur("résident", premier)) is False
    #  Les destinataires suivent la même remontée.
    assert batiments_du_perimetre([hall]) == {second}
    #  Et le libellé du parent n'écrase pas celui de l'espace.
    assert P.perimetre_label_un(hall) == "Hall d'entrée"


def test_enfant_dun_perimetre_global_est_global(batiments):
    """« Parking › Portail d'accès » concerne tout le monde, sans le redire."""
    assert P.a_portee_globale(["parking/portail"]) is True
    assert perimetre_visible(["parking/portail"], utilisateur("résident", batiments[0])) is True
    assert batiments_du_perimetre(["parking/portail"]) is None


def test_regroupement_batiments_ne_se_cible_pas(batiments):
    """Un nœud d'organisation n'est pas une cible : on choisit un bâtiment."""
    with Session(engine) as session:
        groupe = session.exec(select(Perimetre).where(Perimetre.code == "batiments")).one()
        assert groupe.selectionnable is False
        assert groupe.portee_globale is False, (
            "un regroupement de bâtiments à portée globale rendrait tous les espaces "
            "de tous les bâtiments visibles de tous les résidents"
        )


# ── Le seed ───────────────────────────────────────────────────────────────────

def test_seed_idempotent_et_respectueux(batiments):
    """Le seed pose ce qui manque et ne réécrit jamais ce qui existe."""
    with Session(engine) as session:
        avant = len(session.exec(select(Perimetre)).all())
        renomme = session.exec(select(Perimetre).where(Perimetre.code == "aful")).one()
        renomme.libelle = "Parking public (AFUL)"
        session.add(renomme)
        session.commit()

        assert poser_arborescence(session) == 0
        session.commit()
        assert len(session.exec(select(Perimetre)).all()) == avant

        toujours = session.exec(select(Perimetre).where(Perimetre.code == "aful")).one()
        assert toujours.libelle == "Parking public (AFUL)", (
            "le seed a écrasé une personnalisation faite depuis l'administration"
        )


def test_un_noeud_par_batiment_reel(batiments):
    """Les bâtiments sont lus en base, jamais énumérés par une constante.

    L'implémentation précédente générait `bat:1` à `bat:9` depuis `_BATIMENTS = 9`,
    sans rapport avec le contenu de la table — et le front s'arrêtait à `bat:4`.
    """
    arbre = P.arbre()
    for identifiant in batiments:
        assert f"bat:{identifiant}" in arbre
        for suffixe, _, _ in GABARIT_BATIMENT:
            assert f"bat:{identifiant}/{suffixe}" in arbre
    #  Aucun bâtiment inventé au-delà de ce que la base contient.
    assert f"bat:{batiments[-1] + 1}" not in arbre


# ── Analyse statique : la liste ne doit pas réapparaître ──────────────────────

#  Les deux contrôles ci-dessous sont statiques parce que le couplage est implicite :
#  rien, à l'exécution, ne signale qu'une quatrième copie de la liste est apparue
#  (`standards/05`). Ils travaillent sur l'AST et non sur le texte — un commentaire
#  qui *explique* pourquoi « résidence » a disparu est légitime, et un contrôle qui
#  le refuserait pousserait à supprimer les explications plutôt que les défauts.

def _constantes_texte_hors_docstring(fichier: Path) -> list[str]:
    """Les chaînes littérales du fichier, docstrings et commentaires exclus."""
    arbre_py = ast.parse(fichier.read_text(encoding="utf-8"))
    docstrings = set()
    for noeud in ast.walk(arbre_py):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corps = getattr(noeud, "body", [])
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)
                    and isinstance(corps[0].value.value, str)):
                docstrings.add(id(corps[0].value))
    return [
        noeud.value
        for noeud in ast.walk(arbre_py)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, str)
        and id(noeud) not in docstrings
    ]


def test_aucune_liste_de_perimetres_ne_subsiste_dans_le_code():
    """Les constantes supprimées ne doivent pas revenir, ici ou sous un autre nom.

    Une liste de périmètres dans le code, c'est le défaut d'origine : il y en avait
    trois exemplaires, et ils avaient divergé.
    """
    interdits = {"SCOPES_RESIDENCE", "_PERIMETRES_GLOBAUX", "PERIMETRE_LABELS"}
    fautifs = []
    for fichier in (RACINE_API / "app").rglob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            cibles = []
            if isinstance(noeud, ast.Assign):
                cibles = noeud.targets
            elif isinstance(noeud, ast.AnnAssign):
                cibles = [noeud.target]
            for cible in cibles:
                if isinstance(cible, ast.Name) and cible.id in interdits:
                    fautifs.append(f"{fichier.relative_to(RACINE_API)} → {cible.id}")
    assert not fautifs, "liste de périmètres réapparue : " + ", ".join(fautifs)


def test_les_regles_de_decision_ne_citent_aucun_code_de_perimetre():
    """`visibility`, `destinataires` et le fil ne connaissent plus aucun périmètre.

    Ils doivent fonctionner pour une copropriété sans AFUL et sans caves : ils ne
    peuvent donc pas nommer ces périmètres dans une décision. Sans ce contrôle, la
    tentation de « juste ajouter le cas » ferait revenir la liste par petits bouts.
    """
    surveilles = [
        RACINE_API / "app" / "utils" / "visibility.py",
        RACINE_API / "app" / "utils" / "destinataires.py",
        RACINE_API / "app" / "routers" / "flux" / "evenements.py",
    ]
    codes = {"résidence", "parking", "cave", "aful"}
    fautifs = []
    for fichier in surveilles:
        for valeur in _constantes_texte_hors_docstring(fichier):
            if valeur.strip().lower() in codes:
                fautifs.append(f"{fichier.name} → « {valeur} »")
    assert not fautifs, "code de périmètre en dur dans une règle : " + ", ".join(fautifs)
