"""Garde-fou : la connexion SMTP se construit à un seul endroit (08/08/2026).

Les dix-sept lignes qui composent `ConnectionConfig` depuis la configuration en
base — avec repli sur le `.env` champ par champ — étaient écrites **trois fois** :
deux dans `app/utils/email.py` (envoi simple, envoi groupé) et une dans
`app/routers/config.py`, pour le bouton « tester la configuration SMTP ».

C'est la duplication la plus coûteuse qui soit sur ce chemin. Un bouton de test
n'a d'intérêt que s'il emprunte **exactement** la même construction que les
envois réels : trois écritures, c'est trois occasions de tester autre chose que
ce qui part vraiment, et de conclure « SMTP OK » pendant que les e-mails
échouent. Personne ne l'aurait vu — un e-mail qui ne part pas ne fait pas de
bruit.
"""
import ast
import pathlib

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Le seul module autorisé à instancier la connexion.
_MODULE_AUTORISE = "utils/smtp.py"


def _modules() -> list[tuple[str, str]]:
    """(chemin relatif, source) de tous les modules — c'est la PORTÉE du contrôle."""
    fichiers = [
        (f.relative_to(_APP).as_posix(), f.read_text(encoding="utf-8"))
        for f in sorted(_APP.rglob("*.py"))
        if "__pycache__" not in f.parts
    ]
    assert len(fichiers) >= 40, (
        f"Seulement {len(fichiers)} module(s) sous {_APP} — la portée du contrôle "
        "est cassée, ne pas lire ce test comme vert."
    )
    return fichiers


def test_la_connexion_smtp_n_est_construite_qu_a_un_endroit():
    porteurs = {
        rel for rel, src in _modules()
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "ConnectionConfig"
    }
    assert porteurs == {_MODULE_AUTORISE}, (
        "`ConnectionConfig(...)` ne doit être construit que dans "
        f"`app/{_MODULE_AUTORISE}` (`connexion_smtp`). Modules fautifs : "
        f"{sorted(porteurs - {_MODULE_AUTORISE})}. Un envoi qui compose sa propre "
        "connexion peut viser un autre serveur que celui que le bouton de test "
        "vérifie."
    )


def test_les_envois_passent_par_le_helper_partage():
    """Cas zéro : si plus personne n'appelle `connexion_smtp`, le test ci-dessus
    resterait vert en ne surveillant rien — un ensemble vide est égal à lui-même
    seulement quand le helper existe et sert (`standards/04` §2)."""
    appelants = {
        rel for rel, src in _modules()
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "connexion_smtp"
    }
    assert len(appelants) >= 2, (
        f"`connexion_smtp` n'est appelé que depuis {sorted(appelants)} — il en "
        "desservait 2 modules (envois et bouton de test) au moment du "
        "regroupement. Un chemin d'envoi a-t-il repris une construction à la main ?"
    )


def test_le_repli_sur_le_env_reste_champ_par_champ():
    """Une configuration partielle en base doit hériter du reste du `.env`.

    Le piège serait de remplacer le repli champ par champ par un « bloc en base
    OU bloc du .env » : renseigner le seul serveur en base ferait alors perdre
    d'un coup identifiants, port et expéditeur. Le contrôle vise le FAIT — chaque
    clé porte son propre repli.
    """
    source = (_APP / "utils" / "smtp.py").read_text(encoding="utf-8")
    arbre = ast.parse(source)
    fonction = next(
        n for n in ast.walk(arbre)
        if isinstance(n, ast.FunctionDef) and n.name == "connexion_smtp"
    )
    corps = ast.unparse(fonction)
    for cle in (
        "smtp_server", "smtp_port", "smtp_from", "smtp_from_name",
        "smtp_username", "smtp_password", "smtp_starttls", "smtp_ssl_tls",
    ):
        assert cle in corps, f"`{cle}` n'a plus de repli propre dans connexion_smtp"

    #  Les deux booléens se testent par présence de clé et NON par `or` : une case
    #  décochée vaut « 0 » en base, qu'un `or` remplacerait par la valeur du .env.
    #  L'utilisateur ne pourrait alors jamais désactiver STARTTLS.
    for booleen in ("smtp_starttls", "smtp_ssl_tls"):
        assert f"'{booleen}' in smtp_cfg" in corps or f'"{booleen}" in smtp_cfg' in corps, (
            f"`{booleen}` doit être lu par présence de clé, pas par `or` : sinon "
            "une case décochée (« 0 ») retombe sur la valeur du .env et ne peut "
            "plus jamais être désactivée."
        )
