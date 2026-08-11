"""Garde-fou : l'alerte système rend réellement les problèmes détectés.

`test_email_contexte_appel.py` vérifie que le contexte fournit les variables de
**premier niveau** du modèle. Il ne peut rien dire de leur forme : `problemes`
est une liste de dictionnaires dont le modèle lit `titre` et `details`, et rien
ne relie ce contrat au découpage fait dans `health_monitor._en_problemes`.
Renommer une de ces deux clés laisserait les deux tests verts et produirait une
alerte aux puces vides.

Ce n'est pas un e-mail comme un autre : c'est celui qui prévient qu'une
sauvegarde a échoué ou que la base est corrompue. S'il part vide, il est pire
qu'absent — il donne à croire que le contrôle a tourné et n'a rien trouvé.

Le fichier vérifie donc le rendu de bout en bout : chaînes brutes des `_check_*`
→ découpage → modèle → HTML final.
"""
import pytest
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from app.seed import EMAIL_TEMPLATES
from app.utils.health_monitor import _en_problemes

# Forme réelle des chaînes rendues par les `_check_*` : première ligne = titre,
# lignes suivantes = précisions techniques, indentées.
_ISSUES = [
    "Espace disque faible : 8.2% libre (4.1 Go).",
    "Sauvegarde en échec depuis 3 jours.\n  archive: hostachy-2026-08-02.tar.gz\n  erreur: No space left on device",
]

_CONTEXTE = {
    "problemes": _en_problemes(_ISSUES),
    "nb_problemes": len(_ISSUES),
    "date_controle": "mercredi 5 août 2026 à 06:00",
    "residence": {"nom": "Les Hostachy"},
    "app": {"url": "https://exemple.fr"},
    "annee": 2026,
}


def _rendu() -> tuple[str, str]:
    modele = next((t for t in EMAIL_TEMPLATES if t[0] == "alerte_systeme"), None)
    if modele is None:
        pytest.fail(
            "Le modèle `alerte_systeme` a disparu de seed.EMAIL_TEMPLATES : le "
            "contrôle quotidien enverrait dans le vide (send_email se tait quand "
            "le modèle est absent)."
        )
    _code, _libelle, sujet, corps, _desactivable = modele
    env = SandboxedEnvironment(loader=BaseLoader())
    return (
        env.from_string(sujet).render(**_CONTEXTE),
        env.from_string(corps).render(**_CONTEXTE),
    )


def test_le_decoupage_separe_titre_et_details():
    problemes = _en_problemes(_ISSUES)
    assert [p["titre"] for p in problemes] == [
        "Espace disque faible : 8.2% libre (4.1 Go).",
        "Sauvegarde en échec depuis 3 jours.",
    ]
    assert problemes[0]["details"] == []
    assert problemes[1]["details"] == [
        "archive: hostachy-2026-08-02.tar.gz",
        "erreur: No space left on device",
    ]


def test_chaque_probleme_apparait_dans_le_corps():
    """Le cœur du message : ce qui a été détecté doit être lisible."""
    _sujet, corps = _rendu()
    for probleme in _CONTEXTE["problemes"]:
        assert probleme["titre"] in corps, (
            f"Le problème « {probleme['titre']} » n'apparaît pas dans l'alerte. "
            "Le modèle et `_en_problemes` ne s'accordent plus sur la forme de "
            "`problemes` — l'e-mail partirait avec des puces vides."
        )
        for detail in probleme["details"]:
            assert detail in corps, (
                f"Le détail « {detail} » est perdu : le modèle ne parcourt plus "
                "`probleme.details`, et l'alerte n'annonce plus que le symptôme."
            )


def test_le_sujet_porte_le_nombre_et_la_residence():
    sujet, _corps = _rendu()
    assert "Les Hostachy" in sujet
    assert "2 problème(s)" in sujet


def test_aucun_marqueur_jinja_ne_subsiste():
    """Une variable mal nommée laisse `{{ … }}` visible chez le destinataire."""
    sujet, corps = _rendu()
    for rendu, ou in ((sujet, "le sujet"), (corps, "le corps")):
        assert "{{" not in rendu and "{%" not in rendu, (
            f"Un marqueur Jinja subsiste dans {ou} de l'alerte système."
        )


# ── Référence de copropriété ────────────────────────────────────────────────
#
# Ce contrôle est la seule chose qui empêche la règle « la référence figure dans
# tout message au syndic » d'être vraie sur le modèle et fausse à l'envoi. Les
# objets la portent derrière un `{% if reference_copro %}` — nécessaire, sinon
# une installation sans référence enverrait « 🏢  — Ticket #… » — mais ce `{% if
# %}` rend l'omission totalement silencieuse : pas d'erreur, pas d'objet dégradé,
# aucune trace. Aucun test de modèle ne peut voir ça, ils resteraient tous verts.

def _base_jetable():
    """Base SQLite en mémoire portant la seule table dont le contrôle a besoin."""
    from sqlmodel import Session, SQLModel, create_engine

    from app.models.core import ConfigSite

    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur, tables=[ConfigSite.__table__])
    return Session(moteur), ConfigSite


@pytest.mark.parametrize("valeur", ["", "   ", None])
def test_reference_copro_absente_est_signalee(valeur):
    """Vide, blanche ou jamais posée : les trois doivent alerter."""
    from app.utils.health_monitor import _check_reference_copro

    session, ConfigSite = _base_jetable()
    with session:
        if valeur is not None:
            session.add(ConfigSite(cle="reference_copro", valeur=valeur))
            session.commit()
        issues = _check_reference_copro(session)

    assert len(issues) == 1, (
        f"Référence {valeur!r} : aucune alerte. Les messages au syndic partiraient "
        "sans référence, sans que rien ne le signale."
    )
    assert "syndic" in issues[0].lower()
    #  Une alerte doit dire quoi faire : le gestionnaire du site n'a pas à
    #  chercher où se règle la clé.
    assert "Admin" in issues[0], "L'alerte ne dit pas où corriger."


def test_reference_copro_renseignee_ne_declenche_rien():
    """Cas zéro : sur une installation correcte, le contrôle doit se taire.

    Sans cette moitié, un contrôle qui alerterait *toujours* passerait pour bon —
    et une alerte permanente est une alerte qu'on cesse de lire.
    """
    from app.utils.health_monitor import _check_reference_copro

    session, ConfigSite = _base_jetable()
    with session:
        session.add(ConfigSite(cle="reference_copro", valeur="00213"))
        session.commit()
        assert _check_reference_copro(session) == []


def test_le_controle_est_branche_dans_le_job_quotidien():
    """Un contrôle que personne n'appelle ne contrôle rien.

    C'est arrivé ici : `sauvegarde_echec` et `alerte_espace_disque` ont dormi en
    base sans que rien ne les envoie. Le test lit la source de `run_health_check`
    plutôt que de l'exécuter — le job touche le disque, la base et SMTP.
    """
    import inspect

    from app.utils import health_monitor

    source = inspect.getsource(health_monitor.run_health_check)
    assert "_check_reference_copro" in source, (
        "`_check_reference_copro` n'est pas appelé par `run_health_check` : il ne "
        "s'exécutera jamais et la référence pourra rester vide sans que personne "
        "ne l'apprenne."
    )
