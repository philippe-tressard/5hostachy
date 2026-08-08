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


def _conditions_de_partage(arbre: ast.AST) -> list[str]:
    """Conditions résolues des `if` qui décident d'un partage WhatsApp."""
    trouvees = []
    for fonction in ast.walk(arbre):
        if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for n in ast.walk(fonction):
            if isinstance(n, ast.If) and "partager_whatsapp" in ast.unparse(n.test):
                trouvees.append(_condition_resolue(fonction, n.test))
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
    for condition in conditions:
        assert "has_role" in condition, (
            "Le partage sur le groupe WhatsApp n'est plus réservé au CS/admin — "
            f"condition sans contrôle de rôle : {condition}"
        )
        for attendu in ("conseil_syndical", "admin"):
            assert attendu in condition, (
                f"Le garde du partage WhatsApp ne mentionne pas `{attendu}` : {condition}"
            )


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
