"""Garde-fou : aucune règle d'accès n'est réécrite hors des modules centraux.

## Ce qui a rendu ce contrôle nécessaire (29/08/2026)

Question posée par l'utilisateur : *« pour les règles de sécurité, tout est
centralisé ? aucune règle en dur dans un bout de code ? »*. Le relevé a répondu
**presque** — et le « presque » valait un audit :

  • aucun contrôle de rôle par chaîne littérale (`has_role("admin")`) ;
  • aucune comparaison directe `user.role == …` ;
  • les sept fonctions de visibilité vivent toutes dans `utils/visibility/` ;
  • **mais** `objet.auteur_id != user.id` était réécrit à la main dans QUATORZE
    sites, avec **cinq** définitions différentes de « ou quelqu'un de plus haut » :

        auteur ou CS/admin    annonces, idées
        auteur ou admin       calendrier_historique, publications, tickets, sondages ×3
        auteur ou modérateur  sondages/participation
        auteur seul           annonces ×2
        composite             tickets/evolutions

Un membre du CS pouvait supprimer la réponse d'un autre sur une annonce, mais pas
sur un sondage. Rien ne disait si c'était voulu — et c'est bien le problème : une
règle écrite quatorze fois n'a plus d'auteur, seulement des copies.

La cause était en amont : `est_auteur` s'appelait `_est_concerne` et était
**privée**. Une règle d'accès privée n'est pas centralisée, elle est seulement
inaccessible — alors chacun la réécrit.

## Ce que ce test vérifie — le fait, pas l'intention

Aucun fichier de `app/routers/` ne compare un `auteur_id` à l'identité de
l'utilisateur pour en DÉDUIRE un droit. Les trois régimes vivent dans
`app/auth/deps.py` :

    est_auteur(objet, user)       l'auteur seul (« saisi pour » compris)
    peut_editer(objet, user)      + admin
    peut_commenter(objet, user)   + admin + conseil syndical

⚠️ Les exceptions sont déclarées avec leur motif, et le test **échoue si l'une
d'elles cesse de servir** : une tolérance qui ne protège plus rien finit par
couvrir autre chose.
"""
import ast
import pathlib
import re

ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
DEPS = pathlib.Path(__file__).resolve().parents[1] / "app" / "auth" / "deps.py"

#: Les trois régimes publics. Leur absence fait échouer le contrôle (cas zéro) :
#: sans eux, la recherche ci-dessous ne mesurerait plus rien de ce qu'elle croit.
REGIMES = ("est_auteur", "peut_editer", "peut_commenter")

#: `auteur_id` comparé à l'utilisateur courant — la forme réécrite à la main.
_MOTIF = re.compile(r"auteur_id\s*[!=]=\s*(user|current_user)\.id")

#: Ce qui n'est PAS une décision d'accès, déclaré avec sa raison.
#:
#: 🔴 Ces deux-là décident s'il faut **notifier** l'auteur, pas s'il a le droit
#: de lire. Les convertir aurait changé qui reçoit un e-mail, sans rapport avec
#: la sécurité — et aurait masqué la distinction dans le contrôle lui-même.
EXCEPTIONS = {
    "tickets/evolutions.py": "décide d'une NOTIFICATION à l'auteur, pas d'un droit",
    "tickets/messages.py": "décide d'une NOTIFICATION à l'auteur, pas d'un droit",
    #  🔴 Celle-ci est d'une autre nature, et c'est la plus délicate des trois.
    #
    #  `list_tickets` filtre en SQL (`WHERE auteur_id = :id OR saisi_pour = :id`).
    #  Une clause SQL ne peut pas appeler `ticket_visible`, qui est du Python :
    #  il faudrait charger TOUS les tickets pour les filtrer ensuite. La règle est
    #  donc écrite DEUX fois — une en Python, une en SQL — et rien dans le langage
    #  ne peut les rendre solidaires.
    #
    #  C'est pour cela que `test_le_filtre_sql_dit_la_meme_chose_que_ticket_visible`
    #  existe plus bas : puisqu'on ne peut pas supprimer la seconde écriture, on
    #  vérifie qu'elle dit la même chose que la première.
    "tickets/crud.py": "filtre SQL — solidarité vérifiée par le test de concordance",
}


def _fichiers():
    return sorted(p for p in ROUTERS.rglob("*.py") if "__pycache__" not in p.parts)


def test_les_trois_regimes_existent_et_sont_publics():
    """Cas zéro : sans eux, le contrôle ci-dessous ne mesurerait plus rien.

    Le défaut d'origine était précisément qu'un des trois était privé
    (`_est_concerne`). Un régime redevenu privé ferait revenir la duplication,
    et ce test resterait vert s'il ne regardait que les routers.
    """
    arbre = ast.parse(DEPS.read_text(encoding="utf-8"))
    publiques = {
        n.name
        for n in arbre.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not n.name.startswith("_")
    }
    manquants = [r for r in REGIMES if r not in publiques]
    assert not manquants, (
        f"Régime(s) d'accès absent(s) ou redevenu(s) privé(s) dans auth/deps.py : {manquants}. "
        "Une règle d'accès privée n'est pas centralisée — elle est inaccessible, "
        "et chacun la réécrit."
    )


def test_aucun_router_ne_reecrit_la_regle_de_l_auteur():
    coupables = {}
    for chemin in _fichiers():
        rel = chemin.relative_to(ROUTERS).as_posix()
        if rel in EXCEPTIONS:
            continue
        trouves = [
            f"{rel}:{i}"
            for i, ligne in enumerate(chemin.read_text(encoding="utf-8").split("\n"), 1)
            if _MOTIF.search(ligne) and not ligne.strip().startswith("#")
        ]
        if trouves:
            coupables[rel] = trouves

    assert not coupables, (
        f"Règle d'accès réécrite à la main : {coupables}.\n"
        "Appeler `est_auteur`, `peut_editer` ou `peut_commenter` "
        "(`app/auth/deps.py`) selon le régime voulu. Quatorze sites la "
        "réécrivaient avec CINQ définitions différentes de « ou quelqu'un de "
        "plus haut » — un CS pouvait supprimer la réponse d'un autre sur une "
        "annonce, mais pas sur un sondage."
    )


def test_les_exceptions_declarees_servent_encore():
    """Une tolérance qui ne protège plus rien finit par couvrir autre chose."""
    mortes = []
    for rel, motif in EXCEPTIONS.items():
        chemin = ROUTERS / rel
        if not chemin.exists():
            mortes.append(f"{rel} (fichier absent — {motif})")
        elif not _MOTIF.search(chemin.read_text(encoding="utf-8")):
            mortes.append(f"{rel} (ne réécrit plus la règle — {motif})")
    assert not mortes, f"Exceptions à retirer de EXCEPTIONS : {mortes}"


def test_aucun_controle_de_role_par_chaine():
    """`has_role("admin")` au lieu de l'enum : un renommage le rendrait muet.

    Trouvé à deux endroits par l'audit du 26/07/2026, corrigé depuis. Ce test
    empêche le retour — la forme est indistinguable de la bonne à la relecture.
    """
    coupables = []
    motif = re.compile(r"""has_role\(\s*['"]""")
    for chemin in _fichiers():
        for i, ligne in enumerate(chemin.read_text(encoding="utf-8").split("\n"), 1):
            if motif.search(ligne):
                coupables.append(f"{chemin.relative_to(ROUTERS).as_posix()}:{i}")
    assert not coupables, (
        f"Rôle comparé par CHAÎNE au lieu de l'enum : {coupables}. "
        "Utiliser `RoleUtilisateur.<nom>` — une chaîne survit à un renommage "
        "en devenant silencieusement fausse."
    )


def test_aucune_comparaison_directe_de_role_ou_de_statut():
    """`user.role == 'admin'` contourne `has_role`, qui gère les rôles multiples."""
    coupables = []
    motif = re.compile(r"""(user|current_user)\.(role|statut)\s*[!=]=\s*['"]""")
    for chemin in _fichiers():
        for i, ligne in enumerate(chemin.read_text(encoding="utf-8").split("\n"), 1):
            if motif.search(ligne) and not ligne.strip().startswith("#"):
                coupables.append(f"{chemin.relative_to(ROUTERS).as_posix()}:{i}")
    assert not coupables, (
        f"Rôle ou statut comparé directement : {coupables}. "
        "`has_role` sait qu'un utilisateur en porte plusieurs ; `==` non."
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Le filtre SQL et la règle Python doivent dire la même chose
# ═══════════════════════════════════════════════════════════════════════════════
#
#  `GET /tickets` ne peut pas appeler `ticket_visible` : une clause `WHERE` ne
#  sait pas exécuter du Python, et charger tous les tickets pour les filtrer
#  ensuite ne tient pas. La règle existe donc en DEUX exemplaires.
#
#  ⚠️ C'est le seul cas du dépôt où la duplication d'une règle d'accès est
#  inévitable — et c'est exactement pour cela qu'il lui faut un test. Sans lui,
#  durcir `ticket_visible` laisserait la LISTE ouverte, ou l'inverse : deux
#  chemins vers la même donnée, d'accord entre eux jusqu'au jour où l'un change.

def test_le_filtre_sql_dit_la_meme_chose_que_ticket_visible():
    """Les deux écritures de « qui voit un ticket », comparées cas par cas."""
    import types

    from app.models.core import RoleUtilisateur
    from app.utils.visibility import ticket_visible

    def _user(uid, cs=False):
        u = types.SimpleNamespace(id=uid)
        u.has_role = lambda *r: cs and RoleUtilisateur.conseil_syndical in r or (
            cs and RoleUtilisateur.admin in r
        )
        return u

    def _ticket(auteur, saisi_pour=None):
        return types.SimpleNamespace(auteur_id=auteur, saisi_pour_user_id=saisi_pour)

    def _filtre_sql(ticket, user) -> bool:
        """La transcription du `WHERE` de `list_tickets`, en Python.

        ⚠️ Recopiée à la main — c'est assumé, et c'est ce que le test compare.
        Si elle cesse de correspondre au vrai `WHERE`, c'est le test qui devient
        faux : le relire fait partie de toute modification de `list_tickets`.
        """
        if user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
            return True
        return ticket.auteur_id == user.id or ticket.saisi_pour_user_id == user.id

    cas = [
        ("son propre ticket", _ticket(7), _user(7)),
        ("ticket d'un autre", _ticket(9), _user(7)),
        ("saisi POUR lui", _ticket(9, saisi_pour=7), _user(7)),
        ("saisi pour un autre", _ticket(9, saisi_pour=8), _user(7)),
        ("le CS voit tout", _ticket(9), _user(7, cs=True)),
        ("sans auteur ni saisi_pour", _ticket(None), _user(7)),
    ]
    ecarts = [
        f"{libelle} : SQL={_filtre_sql(t, u)} / Python={ticket_visible(t, u)}"
        for libelle, t, u in cas
        if _filtre_sql(t, u) != ticket_visible(t, u)
    ]
    assert not ecarts, (
        "Le filtre SQL de `list_tickets` et `ticket_visible` divergent : "
        f"{ecarts}. Deux chemins vers la même donnée qui ne disent pas la même "
        "chose — l'un des deux laisse voir ce que l'autre refuse."
    )
