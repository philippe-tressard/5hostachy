"""Garde-fous du canal WhatsApp côté API (08/08/2026).

Pendant backend de `front/scripts/check-notifications.mjs`. Deux défauts réels,
tous deux invisibles à la relecture d'un diff :

1. **La liste des clés de configuration WhatsApp était écrite quatre fois** — et
   la copie de `publications.py` contenait `site_url` que les trois autres
   n'avaient pas. Conséquence concrète : le lien « consultez l'application »
   d'un message restreint ne pouvait apparaître que dans une actualité. Une
   notion, une écriture (`standards/02-factorisation.md` §2).

2. **Le groupe WhatsApp est un canal de diffusion vers tous les résidents.**
   L'ouvrir à l'auteur d'un ticket quelconque en ferait un mégaphone : le
   partage doit rester réservé au CS et aux admins, contrôlé **côté serveur**,
   la case de l'interface n'étant qu'un confort (`standards/03-securite.md` §1).
"""
import ast
import pathlib

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Les clés qui composent la configuration du canal.
_MARQUEURS = ("whatsapp_api_url", "whatsapp_group_jid", "whatsapp_enabled")


def _sources() -> list[tuple[pathlib.Path, str]]:
    """Tous les modules de l'application. C'est la PORTÉE, donc une partie du contrôle."""
    fichiers = [
        (f, f.read_text(encoding="utf-8"))
        for f in sorted(_APP.rglob("*.py"))
        if "__pycache__" not in f.parts
    ]
    assert len(fichiers) >= 40, (
        f"Seulement {len(fichiers)} module(s) trouvé(s) sous {_APP} — la portée du "
        "contrôle est cassée, ne pas lire ces tests comme verts."
    )
    return fichiers


def test_les_cles_de_configuration_whatsapp_ne_sont_ecrites_qu_une_fois():
    """Un seul module a le droit d'énumérer les clés du canal WhatsApp."""
    porteurs = {
        f.relative_to(_APP).as_posix()
        for f, src in _sources()
        #  Deux marqueurs au moins : une mention isolée (un log, un commentaire,
        #  une lecture ciblée comme celle du moniteur de santé) n'est pas une
        #  redéfinition de l'ensemble.
        if sum(m in src for m in _MARQUEURS) >= 2
    }
    assert porteurs == {"utils/whatsapp.py"}, (
        "Les clés de configuration WhatsApp doivent vivre dans `app/utils/whatsapp.py` "
        "(`CLES_CONFIG`) et nulle part ailleurs. Modules fautifs : "
        f"{sorted(porteurs - {'utils/whatsapp.py'})}. Utiliser `config_whatsapp(session)`."
    )


def _condition_resolue(fonction: ast.AST, test: ast.AST) -> str:
    """La condition d'un `if`, variables locales d'un niveau remplacées.

    Sans cela, extraire `est_cs = user.has_role(...)` — parfaitement légitime
    quand le rôle sert six fois dans la même fonction — sortirait l'autorisation
    du champ du contrôle. C'est le même angle mort que celui corrigé sur le fil
    d'activité le 08/08/2026 : un garde-fou ne doit pas obliger à dupliquer pour
    rester visible.
    """
    affectations: dict[str, ast.AST] = {}
    for n in ast.walk(fonction):
        if isinstance(n, ast.Assign):
            for cible in n.targets:
                if isinstance(cible, ast.Name):
                    affectations[cible.id] = n.value
    morceaux = [ast.unparse(test)]
    for n in ast.walk(test):
        if isinstance(n, ast.Name) and n.id in affectations:
            morceaux.append(ast.unparse(affectations[n.id]))
    return " ".join(morceaux)


#: Les appels qui font PARTIR un message sur le groupe. C'est eux qui désignent
#: un point de partage — pas le nom du champ.
_ENVOIS = ("_partager_sur_le_groupe", "envoyer_whatsapp")


def _gardes_des_envois(fonction: ast.AST) -> list[str]:
    """Pour chaque envoi WhatsApp, TOUTES les conditions qui l'englobent, résolues.

    ⚠️ **Trois repères ont été essayés avant celui-ci** (05/09/2026), chacun
    aveugle d'un côté différent :

    1. le texte écrit du `if` — aveugle à `if partage_whatsapp:`, alimenté par
       une variable locale, c'est-à-dire au point d'envoi qu'on venait de garder ;
    2. la condition **résolue** — attrapait en plus un `if` qui ne fait rien
       partir : la validation des champs réservés, qui énumère `partager_whatsapp`
       dans un tuple ;
    3. le `if` **immédiat** de l'appel — aveugle à une garde portée par un `if`
       englobant, ce qui décrit littéralement l'envoi des évolutions, niché sous
       `if whatsapp_actif(...)`.

    Un envoi n'a pas lieu « sous une condition » mais sous **la conjonction de
    toutes celles qu'il faut franchir**. C'est donc elle qu'on lit — le fait, et
    non l'un de ses symptômes.
    """
    gardes: list[str] = []

    def descendre(noeud: ast.AST, pile: list[str]) -> None:
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, ast.If):
                condition = _condition_resolue(fonction, enfant.test)
                for instruction in enfant.body:
                    descendre(instruction, pile + [condition])
                #  Le `else` ne bénéficie PAS de la condition du `if`.
                for instruction in enfant.orelse:
                    descendre(instruction, pile)
                continue
            if any(m in ast.unparse(enfant) for m in _ENVOIS) and pile:
                gardes.append(" et ".join(pile))
            descendre(enfant, pile)

    descendre(fonction, [])
    return gardes


def _conditions_de_partage(arbre: ast.AST) -> list[str]:
    """Les gardes de tous les envois WhatsApp d'un module, dédoublonnées."""
    trouvees: list[str] = []
    for fonction in ast.walk(arbre):
        if isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for garde in _gardes_des_envois(fonction):
                if garde not in trouvees:
                    trouvees.append(garde)
    return trouvees


def test_le_partage_whatsapp_d_un_ticket_est_reserve_au_cs():
    """`partager_whatsapp` à la création d'un ticket doit être gardé par un rôle.

    Vérifie le FAIT (la condition qui entoure l'envoi), pas le symptôme : une
    case masquée dans l'interface ne protège rien, le client peut poster le
    champ directement.
    """
    source = (_APP / "routers" / "tickets" / "crud.py").read_text(encoding="utf-8")
    conditions = _conditions_de_partage(ast.parse(source))

    assert conditions, (
        "Aucune condition portant `partager_whatsapp` dans tickets/crud.py : le "
        "partage sur le groupe WhatsApp n'est plus gardé du tout."
    )
    #  Deux formes valables du MÊME contrôle :
    #    • `has_role(conseil_syndical, admin)` écrit sur place ;
    #    • `peut_commander(user)`, le prédicat central d'`auth/deps.py`.
    #  La seconde est arrivée le 16/08/2026 : la règle « ces champs sont réservés
    #  au CS » était recopiée à côté de CHAQUE champ — cinq fois — et une règle
    #  d'autorisation recopiée ne se durcit pas, on en corrige quatre sur six.
    #  Ce test vérifiait la FORME (« le mot has_role est là ») et non le FAIT
    #  (« un contrôle de rôle a lieu ») : il tombait donc sur une centralisation
    #  qui renforce la garde au lieu de l'affaiblir. Il connaît maintenant les
    #  deux formes — et reste rouge si AUCUNE n'est présente.
    for condition in conditions:
        centralise = "peut_commander" in condition
        assert centralise or "has_role" in condition, (
            "Le partage sur le groupe WhatsApp n'est plus réservé au CS/admin — "
            f"condition sans contrôle de rôle : {condition}"
        )
        #  La forme écrite sur place doit nommer les deux rôles ; la forme
        #  centralisée les porte dans `peut_commander`, dont le contenu est
        #  vérifié par `test_peut_commander_est_reserve_au_cs` ci-dessous.
        if not centralise:
            for attendu in ("conseil_syndical", "admin"):
                assert attendu in condition, (
                    f"Le garde du partage WhatsApp ne mentionne pas `{attendu}` : {condition}"
                )


def test_un_ticket_reserve_au_conseil_ne_part_JAMAIS_sur_le_groupe():
    """🔴 « Visibilité au seul conseil syndical » ⇒ aucune diffusion WhatsApp.

    Demandé à l'écran le 05/09/2026 :

    > « si "Visibilité du ticket au seul conseil syndical" est sélectionné, la
    >   diffusion WhatsApp est interdite »

    Le groupe WhatsApp rassemble **tous les résidents**. Un ticket qu'on vient
    de fermer au voisinage — un litige, un impayé, un signalement nominatif —
    y serait recopié en entier : la case cochée dans l'écran promettrait une
    confidentialité que le canal annulerait aussitôt.

    ## Pourquoi un test, et pas seulement une case grisée

    L'actualité tenait la règle depuis toujours (`and not pub.brouillon` à
    chaque canal) ; le ticket, non — **trois** points d'envoi, aucun gardé.
    Griser la case à l'écran ne protège rien : `partager_whatsapp` est un
    champ du corps de la requête, qui se poste directement
    (`standards/03-securite.md` §1 — l'interface est un confort, le serveur
    est le contrôle).

    Le contrôle porte sur les **deux** modules d'envoi, et il exige la
    condition là où l'envoi se décide : c'est le FAIT, pas le symptôme.
    """
    modules = ("crud.py", "evolutions.py")
    for nom in modules:
        source = (_APP / "routers" / "tickets" / nom).read_text(encoding="utf-8")
        conditions = _conditions_de_partage(ast.parse(source))
        assert conditions, (
            f"Aucune condition portant `partager_whatsapp` dans tickets/{nom} : "
            "soit le partage n'y est plus gardé, soit le contrôle a perdu sa "
            "portée — dans les deux cas, ne pas lire ce test comme vert."
        )
        for condition in conditions:
            assert "confidentiel" in condition, (
                f"tickets/{nom} : un ticket réservé au conseil syndical peut partir "
                "sur le groupe WhatsApp de tous les résidents. La condition doit "
                f"porter `not ticket.confidentiel`. Condition trouvée : {condition}"
            )


def test_peut_commander_est_reserve_au_cs():
    """Le prédicat central contrôle bien les deux rôles, et rien d'autre.

    Sans ce test, centraliser la règle la rendrait invérifiable : le test
    ci-dessus accepterait `peut_commander` sans jamais regarder ce qu'il fait.
    """
    source = (_APP / "auth" / "deps.py").read_text(encoding="utf-8")
    arbre = ast.parse(source)
    fn = next(
        (n for n in ast.walk(arbre)
         if isinstance(n, ast.FunctionDef) and n.name == "peut_commander"),
        None,
    )
    assert fn is not None, "`peut_commander` a disparu d'auth/deps.py"
    corps = ast.unparse(fn)
    assert "has_role" in corps, "`peut_commander` ne contrôle plus aucun rôle"
    for attendu in ("conseil_syndical", "admin"):
        assert attendu in corps, f"`peut_commander` ne mentionne plus `{attendu}`"


def test_le_schema_de_creation_de_ticket_porte_le_canal_whatsapp():
    """Le champ doit exister — c'est lui qui manquait, et rien ne le signalait."""
    source = (_APP / "schemas.py").read_text(encoding="utf-8")
    arbre = ast.parse(source)
    classes = {
        n.name: {c.target.id for c in n.body if isinstance(c, ast.AnnAssign)}
        for n in ast.walk(arbre)
        if isinstance(n, ast.ClassDef)
    }
    assert "TicketCreate" in classes, "TicketCreate introuvable dans schemas.py"
    champs = classes["TicketCreate"]
    #  Les trois canaux voyagent ensemble : en perdre un se voit ici, pas à l'écran.
    for canal in ("partager_whatsapp", "destinataire_syndic", "destinataire_cs"):
        assert canal in champs, (
            f"`{canal}` absent de TicketCreate — un canal de notification a disparu "
            "du contrat d'entrée ; l'interface l'affichera sans effet."
        )
