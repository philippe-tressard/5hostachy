"""« Ce lot est-il le mien ? » s'écrit à UN endroit, et il exige le lien ACTIF (#1028).

## 🔴 Le défaut que ce contrôle refuse

La question était écrite **deux fois**, et les deux écritures ne disaient pas la
même chose :

| Écriture | Lien désactivé |
|---|---|
| `routers/lots.py::_lot_rattache` | refusé (`ul.actif`) |
| `routers/acces/resident.py::creer_commande` | **accepté** |

Un ancien occupant, dont le rattachement au lot avait été désactivé, pouvait
donc encore **commander un badge Vigik ou une télécommande** pour ce lot. Le
refus existait à dix lignes de là, dans un autre fichier.

La docstring de `_lot_rattache` disait déjà pourquoi : « une règle d'accès en
deux exemplaires ne diverge pas sur le cas nominal : elle diverge le jour où
l'un des deux apprend quelque chose ». Elle a été écrite en généralisant un
défaut passé — et le second exemplaire existait déjà, ailleurs, au moment où
elle a été écrite.

## Pourquoi un accès dupliqué ne se signale jamais

Un accès donné à trop de monde **ne fait aucun bruit** : personne ne se plaint
de pouvoir faire quelque chose. Le seul moment où on l'apprend est celui où
quelqu'un s'en sert. C'est le même raisonnement que
`test_regle_acces_source_unique.py` et `test_destinataires_source_unique.py`.

## Ce que le contrôle vérifie

1. La fonction centrale existe, et elle **exige `actif`**. Un contrôle de source
   unique qui laisserait la source se relâcher ne protégerait plus rien : il
   garantirait seulement que tout le monde se trompe au même endroit.
2. Aucune fonction qui **décide** — qui lève une `HTTPException` — ne lit
   `UserLot` pour son propre compte, hors des exceptions ci-dessous.

⚠️ Le contrôle ne cherche **pas** tous les `select(UserLot)` du projet : il y en
a dix-sept, et la plupart listent ou réparent des liens sans rien autoriser
(appariement, import, écran d'administration). Interdire la lecture aurait
demandé quinze exceptions, c'est-à-dire un contrôle que l'on contourne par
habitude. Ce qui se recopie ici, c'est la **décision d'accès**, et c'est elle qui
est tenue.

## 🔴 3. Une route qui reçoit un lot sans poser la question (#1535)

Les deux contrôles ci-dessus refusent une question **mal écrite**. Ils ne
voyaient pas une question **absente** : `POST /bailleur/baux/creer-multi`
recevait des `lot_ids` et ne demandait jamais « est-il le vôtre ? ». Tout
propriétaire posait un bail sur le lot d'un voisin et devenait porteur de ses
badges. Rien ne relisait `UserLot` : il n'y avait rien à refuser.

Le troisième contrôle part donc de l'**entrée** : toute route dont un paramètre
— chemin, requête, formulaire ou champ du corps — s'appelle `lot_id` ou
`lot_ids` doit, au choix :

- appeler une des questions d'appartenance (`QUESTIONS`) ;
- être réservée au conseil syndical ou à l'administration (`require_cs_or_admin`,
  `require_admin`) : eux gèrent tous les lots ;
- figurer dans `ROUTES_SANS_QUESTION`, avec sa raison.

⚠️ Il lit les routes **déclarées** (paramètres résolus par FastAPI), pas le
texte : un schéma de corps qui porte `lot_id` est vu au même titre qu'un
paramètre de chemin. Ce qu'il ne voit pas : un lot désigné sous un autre nom
(`bien_id`…), ou déduit d'un autre objet reçu — la question se pose alors sur
cet objet (`exiger_bail_du_bailleur`).
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import textwrap
import typing

from tests.aides_sources import modules_app, routes_declarees

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Où la question s'écrit, et le nom qu'elle porte.
SOURCE = ("auth/deps.py", "est_rattache_au_lot")

#: Les fonctions qui lisent `UserLot` en levant une `HTTPException`, **sans**
#: décider d'une appartenance — elles **gèrent** les liens eux-mêmes, ce qui est
#: l'inverse : elles ne se demandent pas si un lot est le leur, elles rattachent
#: ou détachent pour le compte d'un autre.
#:
#: Chacune est une route d'administration, donc déjà derrière `require_admin` ou
#: `require_cs_or_admin`. Elles sont nommées **une par une** : le jour où l'une
#: d'elles disparaît ou cesse de lire `UserLot`, ce test échoue et l'exception se
#: retire. Une exception qui survit à son motif finit par couvrir autre chose.
EXCEPTIONS = {
    (
        "routers/admin/utilisateurs.py",
        "supprimer_utilisateur",
    ): "détache les liens d'un compte supprimé — l'exception porte sur la "
    "suppression, pas sur une appartenance",
    (
        "routers/lots_imports.py",
        "resoudre_import",
    ): "crée et retire les liens d'un import de lots — c'est elle qui décide "
    "quels rattachements existent",
    (
        "routers/admin/comptes.py",
        "traiter_compte",
    ): "recopie les rattachements d'un compte aidé vers celui qu'il aide, en "
    "ne lisant que les liens actifs — elle fabrique l'appartenance, elle ne "
    "s'y fie pas",
}


def _fonctions_decidant_sur_userlot():
    """(fichier, fonction) pour chaque fonction qui lit `UserLot` ET lève."""
    for module in modules_app():
        if "UserLot" not in module.source:
            continue
        for noeud in ast.walk(module.arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            corps = ast.unparse(noeud)
            if "select(UserLot)" in corps and "HTTPException" in corps:
                yield module.rel, noeud.name, corps


def test_le_controle_voit_bien_quelque_chose():
    """Cas zéro de la portée : une liste vide se lirait comme un succès."""
    vues = list(_fonctions_decidant_sur_userlot())
    assert vues, (
        "aucune fonction lisant UserLot n'a été trouvée — le contrôle a perdu sa "
        "portée (rangement de fichiers, renommage du modèle) et ne vérifie plus rien"
    )
    fichier, fonction = SOURCE
    assert (_APP / fichier).exists(), f"{fichier} a disparu"


def test_la_source_unique_exige_le_lien_ACTIF():
    """Une source unique relâchée fait se tromper tout le monde au même endroit."""
    fichier, fonction = SOURCE
    arbre = ast.parse((_APP / fichier).read_text(encoding="utf-8"))
    corps = {
        n.name: ast.unparse(n)
        for n in ast.walk(arbre)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert fonction in corps, (
        f"`{fonction}` a disparu de {fichier} : la question « ce lot est-il le "
        "mien ? » n'a plus de source unique"
    )
    assert "actif" in corps[fonction], (
        f"`{fonction}` ne regarde plus `actif` : un rattachement désactivé "
        "redonnerait accès au lot — c'est le défaut de #1028, à sa source."
    )


def test_aucune_decision_d_acces_ne_relit_UserLot_elle_meme():
    """Le défaut exact : `creer_commande` interrogeait `UserLot` sans `actif`."""
    fichier_source, nom_source = SOURCE
    fautes = []
    for fichier, fonction, corps in _fonctions_decidant_sur_userlot():
        if fichier == fichier_source:
            continue
        if (fichier, fonction) in EXCEPTIONS:
            continue
        fautes.append(f"  {fichier}::{fonction}")

    assert not fautes, (
        "Ces fonctions décident d'un accès en interrogeant `UserLot` pour leur "
        "propre compte :\n" + "\n".join(fautes) + "\n\n"
        f"La question s'écrit dans `{fichier_source}::{nom_source}`, qui exige le "
        "lien ACTIF. Une seconde écriture ne diverge pas le premier jour — elle "
        "diverge le jour où l'une des deux apprend quelque chose."
    )


def test_aucune_exception_ne_survit_a_son_motif():
    """Une exception qui ne sert plus finit par couvrir autre chose."""
    vues = {(f, n) for f, n, _ in _fonctions_decidant_sur_userlot()}
    perimees = [
        f"  {f}::{n} — « {raison} »" for (f, n), raison in EXCEPTIONS.items() if (f, n) not in vues
    ]
    assert not perimees, (
        "Ces exceptions ne correspondent plus à rien : la fonction a disparu, a "
        "été renommée, ou ne lit plus `UserLot`.\n"
        + "\n".join(perimees)
        + "\n\nLes retirer de EXCEPTIONS."
    )


#  ── 3. Une route qui reçoit un lot pose la question (#1535) ──────────────────

#: Les paramètres qui désignent un lot.
NOMS_DE_LOT = {"lot_id", "lot_ids"}

#: Les questions d'appartenance — appelées par la route elle-même.
QUESTIONS = {"est_rattache_au_lot", "exiger_lot_du_bailleur"}

#: Les routes qui reçoivent un lot SANS poser la question, et pourquoi. Nommées
#: une par une, vérifiées dans les deux sens comme `EXCEPTIONS`.
ROUTES_SANS_QUESTION = {
    (
        "app.routers.tickets.crud",
        "create_ticket",
    ): "le lot d'une affaire est une ÉTIQUETTE : il n'ouvre aucun droit (ni "
    "visibilité, ni badge, ni destinataire). Qu'un résident puisse désigner le "
    "lot d'un autre reste à trancher — signalé au rapport de #1535",
    (
        "app.routers.tickets.mise_a_jour",
        "update_ticket",
    ): "le champ `lot_id` n'y est écrit que par le conseil syndical ou "
    "l'administration (`extra_fields` → 403 sinon), à l'intérieur de la route",
}


def _types(annotation):
    yield annotation
    for argument in typing.get_args(annotation):
        yield from _types(argument)


def _recoit_un_lot(dependant) -> bool:
    from pydantic import BaseModel

    for p in dependant.path_params + dependant.query_params + dependant.body_params:
        if p.name in NOMS_DE_LOT:
            return True
        for t in _types(p.field_info.annotation):
            if (
                isinstance(t, type)
                and issubclass(t, BaseModel)
                and NOMS_DE_LOT & set(t.model_fields)
            ):
                return True
    return any(_recoit_un_lot(d) for d in dependant.dependencies)


def _dependances(dependant):
    for d in dependant.dependencies:
        yield d.call
        yield from _dependances(d)


def _routes_recevant_un_lot():
    """`{(module, fonction): (route, décision)}` — décision : question, rôle ou rien."""
    from app.auth.deps import require_admin, require_cs_or_admin

    vues = {}
    for route in routes_declarees():
        if not _recoit_un_lot(route.dependant):
            continue
        fn = inspect.unwrap(route.endpoint)
        arbre = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        appels = {
            n.func.id
            for n in ast.walk(arbre)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        reservee = any(
            c in (require_admin, require_cs_or_admin) for c in _dependances(route.dependant)
        )
        decision = "question" if appels & QUESTIONS else "rôle" if reservee else None
        vues[(fn.__module__, fn.__name__)] = (route, decision)
    return vues


def test_le_releve_des_routes_voit_les_trois_decisions():
    """Cas zéro : un relevé vide, ou qui ne reconnaît plus une question, serait vert."""
    vues = _routes_recevant_un_lot()
    decisions = {d for _, d in vues.values()}
    assert {"question", "rôle", None} <= decisions, (
        f"le relevé ne reconnaît plus toutes les décisions ({decisions}) — une "
        "question renommée, ou une portée cassée, le rendrait vert sur rien"
    )
    assert ("app.routers.bailleur.baux", "creer_bail_multi") in vues, (
        "la route de #1535 n'est plus relevée : le contrôle a perdu le cas qui l'a fait naître"
    )


def test_toute_route_qui_recoit_un_lot_pose_la_question():
    """🔴 Le défaut exact de #1535 : un `lot_ids` reçu, aucune question posée."""
    fautes = [
        f"  {' '.join(sorted(route.methods))} {route.path} — {module}::{fonction}"
        for (module, fonction), (route, decision) in _routes_recevant_un_lot().items()
        if decision is None and (module, fonction) not in ROUTES_SANS_QUESTION
    ]
    assert not fautes, (
        "Ces routes reçoivent un lot et ne demandent jamais s'il est celui du "
        "demandeur :\n" + "\n".join(fautes) + "\n\n"
        f"Appeler l'une de {sorted(QUESTIONS)} (`auth/`), réserver la route au "
        "conseil syndical ou à l'administration, ou la déclarer dans "
        "ROUTES_SANS_QUESTION avec sa raison. Un écran qui ne propose que « mes "
        "lots » n'est pas un refus : le corps de la requête est libre."
    )


def test_aucune_route_sans_question_ne_survit_a_son_motif():
    """Une exception qui ne sert plus finit par couvrir autre chose."""
    vues = _routes_recevant_un_lot()
    perimees = [
        f"  {m}::{f}"
        for (m, f) in ROUTES_SANS_QUESTION
        if (m, f) not in vues or vues[(m, f)][1] is not None
    ]
    assert not perimees, (
        "Ces exceptions ne servent plus — la route a disparu, ne reçoit plus de "
        "lot, ou pose désormais la question :\n" + "\n".join(perimees)
    )
