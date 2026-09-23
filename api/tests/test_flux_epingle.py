"""Garde-fous du registre « Épinglé » du fil d'activité (01/08/2026).

Deux règles décidées avec l'utilisateur, toutes deux invisibles à la relecture
d'un diff ultérieur — d'où ces tests :

1. **Un élément épinglé ne s'auto-archive pas.** Épingler veut dire « garder en
   vue » : disparaître au bout de 30 jours contredirait le marqueur. La règle vit
   dans `utils/archivage.est_archivable`, partagée par la liste des affaires et
   par le fil, pour que les deux vues tranchent pareil (un élément visible dans
   l'une et pas dans l'autre est le bug du 17/07/2026). Depuis le 23/09/2026,
   une actualité est une affaire de catégorie « Actualité » (#1091) : ces tests
   l'éprouvent sur l'affaire.

2. **Agir sur un marqueur ne republie rien.** Décocher « Épinglé » ou « Urgent »
   écrit `mis_a_jour_le` ; tant que le fil datait ses lignes sur ce champ, un
   simple décochage remontait la publication en tête à la date du jour, pastille
   NEW comprise. Le second test empêche la réintroduction de `mis_a_jour_le`
   dans la date d'une ligne du fil — le correctif ne tient pas si un futur appel
   le remet.
"""
import ast
from datetime import datetime, timedelta
from pathlib import Path

from app.models.core import Ticket
from app.utils.archivage import est_archivable

_FLUX = Path(__file__).resolve().parents[1] / "app" / "routers" / "flux"


def _actualite(**kwargs) -> Ticket:
    """Actualité en mémoire — aucune session, aucune base ouverte."""
    defauts = dict(numero="TK-A1", titre="Titre", description="Contenu", auteur_id=1,
                   categorie="actualite", statut="publie")
    defauts.update(kwargs)
    return Ticket(**defauts)


def _archivee(actu: Ticket) -> bool:
    return est_archivable("ticket", actu, seuil_jours=30)


# ── 1. L'épinglage résiste au vieillissement ────────────────────────────────

def test_actualite_epinglee_ne_s_archive_pas_avec_l_age():
    vieille = datetime.utcnow() - timedelta(days=365)
    assert _archivee(_actualite(epingle=True, cree_le=vieille, mis_a_jour_le=vieille)) is False


def test_archivage_manuel_prime_sur_l_epinglage():
    """Archiver est une décision humaine explicite : elle gagne toujours."""
    assert _archivee(_actualite(epingle=True, archive_manuel=True)) is True


def test_actualite_non_epinglee_s_archive_toujours_avec_l_age():
    """Non-régression : l'exemption ne doit valoir QUE pour les épinglés."""
    vieille = datetime.utcnow() - timedelta(days=365)
    assert _archivee(_actualite(epingle=False, cree_le=vieille, mis_a_jour_le=vieille)) is True


def test_actualite_recente_reste_visible():
    maintenant = datetime.utcnow()
    assert _archivee(_actualite(cree_le=maintenant, mis_a_jour_le=maintenant)) is False


# ── 2. Un marqueur ne redate pas une ligne du fil ───────────────────────────
#
# Ce contrôle lisait UNE ligne de `flux.py` à la regex. Deux défauts, tous deux
# apparus au découpage du 08/08/2026 :
#
# 1. **Sa portée était un chemin de fichier.** `flux.py` devenu le paquet `flux/`,
#    il ne lisait plus rien — bruyamment ici (FileNotFoundError), mais c'est un
#    coup de chance : la même erreur sur un `glob` aurait rendu une liste vide et
#    un vert à blanc (`standards/04` §2, cas zéro).
# 2. **Une variable intermédiaire lui échappait.** `dv_date = dv.mis_a_jour_le or
#    dv.cree_le` puis `date=dv_date` ne correspondait à aucun motif : les devis ET
#    les petites annonces dataient sur `mis_a_jour_le` depuis toujours, sans que
#    le contrôle le sache. Il ne surveillait donc pas ce qu'il annonçait.
#
# La version ci-dessous lit l'arbre syntaxique, résout l'indirection d'un niveau,
# et porte des exemptions justifiées vérifiées **dans les deux sens**.

#: Modules autorisés à dater une carte sur `mis_a_jour_le`, avec la raison.
#: Le critère est factuel : la rubrique porte-t-elle un marqueur (`epingle`,
#: `urgente`) ? Seuls `Publication` et `Evenement` en ont — pour les autres,
#: `mis_a_jour_le` n'est écrit que par une modification réelle, qui est une
#: nouvelle en soi et mérite donc de redater la ligne.
#:
#: 🔴 **VIDE depuis le 01/09/2026, et la prémisse de la seule exemption était
#: fausse.** `communaute.py` était exempté au motif que « `PetiteAnnonce` ne
#: porte ni `epingle` ni `urgente` : son `mis_a_jour_le` n'est écrit que par une
#: modification RÉELLE ». C'est faux : le `PATCH` d'une annonce l'écrit aussi,
#: donc corriger une faute de frappe remontait l'annonce en tête du fil, à la
#: date du jour, pastille NEW comprise. Signalé à l'écran :
#:
#:     « l'édition ne change pas la date de modification (correction d'erreurs) »
#:     « ne modifie pas la mise à jour dans le fil d'actualité »
#:
#: ⚠️ Le critère « la rubrique porte-t-elle un marqueur ? » distinguait mal :
#: ce qui compte n'est pas ce que l'objet PORTE, c'est ce qui ÉCRIT le champ. Et
#: une correction l'écrit partout. Aucune rubrique n'a donc de raison de dater
#: sur lui — sur les quinze sources du fil, quatorze l'avaient déjà compris.
_DATATION_SUR_MISE_A_JOUR_ADMISE: dict[str, str] = {}


def _modules_du_flux() -> list[Path]:
    """La PORTÉE du contrôle, donc une partie du contrôle (`standards/05` §9)."""
    fichiers = [f for f in sorted(_FLUX.rglob("*.py")) if "__pycache__" not in f.parts]
    assert len(fichiers) >= 10, (
        f"Seulement {len(fichiers)} module(s) trouvé(s) sous {_FLUX} — la portée du "
        "contrôle est cassée, ne pas lire ce test comme vert."
    )
    return fichiers


def _dates_des_cartes(arbre: ast.AST) -> list[tuple[int, ast.AST]]:
    """(ligne, expression) de chaque `FluxItem(date=…)`, indirection résolue.

    Un `date=` qui reçoit une variable locale est remplacé par les expressions
    affectées à cette variable dans la même fonction : c'est précisément ce qui
    permettait à `dv_date` de passer sous le radar.
    """
    trouvees: list[tuple[int, ast.AST]] = []
    for fonction in ast.walk(arbre):
        if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        affectations: dict[str, list[ast.AST]] = {}
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.Assign):
                for cible in noeud.targets:
                    if isinstance(cible, ast.Name):
                        affectations.setdefault(cible.id, []).append(noeud.value)
        for noeud in ast.walk(fonction):
            if not (isinstance(noeud, ast.Call) and getattr(noeud.func, "id", "") == "FluxItem"):
                continue
            for kw in noeud.keywords:
                if kw.arg != "date":
                    continue
                if isinstance(kw.value, ast.Name) and kw.value.id in affectations:
                    trouvees += [(noeud.lineno, v) for v in affectations[kw.value.id]]
                else:
                    trouvees.append((noeud.lineno, kw.value))
    return trouvees


def _date_sur_mise_a_jour(expression: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Attribute) and n.attr == "mis_a_jour_le"
        for n in ast.walk(expression)
    )


def test_le_fil_ne_date_aucune_ligne_sur_mis_a_jour_le():
    fautifs: list[str] = []
    exemptions_utilisees: set[str] = set()
    total_cartes = 0

    for chemin in _modules_du_flux():
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        dates = _dates_des_cartes(arbre)
        total_cartes += len(dates)
        for ligne, expression in dates:
            if not _date_sur_mise_a_jour(expression):
                continue
            if chemin.name in _DATATION_SUR_MISE_A_JOUR_ADMISE:
                exemptions_utilisees.add(chemin.name)
                continue
            fautifs.append(f"{chemin.name}:{ligne}")

    #  Garde-fou du garde-fou : sans carte trouvée, la boucle ne juge rien et le
    #  test passerait à vide — un parseur cassé produirait un vert.
    assert total_cartes >= 12, (
        f"Seulement {total_cartes} construction(s) de FluxItem détectée(s) — le "
        "détecteur est cassé, ne pas lire ce test comme vert."
    )

    assert not fautifs, (
        "Une ligne du fil est datée sur `mis_a_jour_le` : cocher ou décocher un "
        "marqueur (Épinglé, Urgent) la ferait remonter en tête à la date du jour, "
        "pastille NEW comprise. Utiliser `publiee_le or cree_le`.\n"
        + "\n".join(fautifs)
    )

    #  Vérification EN SENS INVERSE : une exemption qui ne sert plus doit tomber,
    #  sinon la liste grossit à chaque cas particulier et finit par tout couvrir.
    obsoletes = set(_DATATION_SUR_MISE_A_JOUR_ADMISE) - exemptions_utilisees
    assert not obsoletes, (
        f"Exemption(s) devenue(s) inutile(s) : {sorted(obsoletes)} — les retirer de "
        "`_DATATION_SUR_MISE_A_JOUR_ADMISE`."
    )


def test_la_lecon_reste_ecrite_ou_le_defaut_a_ete_vu():
    """Le commentaire qui porte la règle ne doit pas disparaître en silence.

    `flux/publications.py` est le seul endroit qui explique POURQUOI la date
    d'une publication n'est pas sa dernière écriture. Le supprimer rendrait le
    choix incompréhensible au prochain lecteur — qui le « corrigerait » de bonne
    foi. C'est déjà arrivé : la leçon, écrite là le 01/08/2026, n'a pas franchi
    le fichier voisin, et l'annonce a redaté sur `mis_a_jour_le` un mois de plus.
    """
    source = (_FLUX / "publications.py").read_text(encoding="utf-8")
    assert "PAS `mis_a_jour_le`" in source, (
        "Le commentaire qui porte la règle a disparu de flux/publications.py. "
        "S'il a été déplacé, mettre ce test à jour ; s'il a été supprimé, le "
        "rétablir : c'est le seul endroit où le choix s'explique."
    )
