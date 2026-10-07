"""Aucun interrupteur de service ne coupe un courriel de sécurité (#1718).

Mot de passe oublié, vérification et changement d'adresse, alerte système à
l'administration : un compte qu'on ne peut plus récupérer est un compte perdu.
Le registre des services (`utils/services`) les déclare HORS service
(`COURRIELS_DE_SECURITE`) ; ce fichier refuse qu'un de leurs envois — ou le
moteur d'envoi lui-même — lise un interrupteur de service.

⚠️ Ce qu'il ne voit pas : une garde posée chez l'APPELANT de la fonction qui
envoie. Les quatre envois vivent dans des fonctions qui ne sont appelées que par
leur route ou leur tâche ; c'est leur corps qu'on lit.
"""

from __future__ import annotations

import ast

import app.utils.services as registre
from app.utils.services import COURRIELS_DE_SECURITE
from tests.aides_sources import module_app, modules_app

#: Les noms qui posent la question « ce service est-il activé ? ».
#: Lus sur le registre lui-même : un code de service ajouté y entre seul.
NOMS_DU_REGISTRE = {
    "service_actif",
    "cle_actif",
    "SERVICES",
    "CLES_ACTIVATION",
    "config_diffusion",
} | {n for n in registre.__all__ if n.startswith("SERVICE_")}
MOTEUR_D_ENVOI = "utils/email/__init__.py"


def _envois_de_securite(arbre: ast.AST) -> list[tuple[str, int, ast.AST]]:
    """(code, ligne, fonction englobante) de chaque envoi d'un courriel de sécurité."""
    trouves = []
    for fonction in ast.walk(arbre):
        if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for appel in ast.walk(fonction):
            if not isinstance(appel, ast.Call):
                continue
            for mot in appel.keywords:
                if (
                    mot.arg == "code"
                    and isinstance(mot.value, ast.Constant)
                    and mot.value.value in COURRIELS_DE_SECURITE
                ):
                    trouves.append((mot.value.value, appel.lineno, fonction))
    return trouves


def _lit_un_service(noeud: ast.AST) -> list[str]:
    return sorted(
        {
            n.id if isinstance(n, ast.Name) else n.attr
            for n in ast.walk(noeud)
            if (isinstance(n, ast.Name) and n.id in NOMS_DU_REGISTRE)
            or (isinstance(n, ast.Attribute) and n.attr in NOMS_DU_REGISTRE)
        }
    )


def test_le_controle_refuse_un_envoi_soumis_a_un_service():
    """Le cas fautif d'abord : un mot de passe oublié qu'éteindrait l'assistant IA."""
    fautif = ast.parse(
        "def oublie(cfg):\n"
        "    if service_actif(cfg, SERVICE_IA):\n"
        "        send_email(code='reinitialisation_mdp', to=[])\n"
    )
    [(code, _, fonction)] = _envois_de_securite(fautif)
    assert code == "reinitialisation_mdp"
    assert _lit_un_service(fonction) == ["SERVICE_IA", "service_actif"]


def test_aucun_envoi_de_securite_ne_lit_un_service():
    trouves: dict[str, list[str]] = {code: [] for code in COURRIELS_DE_SECURITE}
    ecarts = []
    for m in modules_app(minimum=100):
        for code, ligne, fonction in _envois_de_securite(m.arbre):
            trouves[code].append(f"app/{m.rel}:{ligne}")
            if lus := _lit_un_service(fonction):
                ecarts.append(f"app/{m.rel}:{ligne} « {code} » sous {', '.join(lus)}")
    #  Le témoin : chaque courriel déclaré part réellement de quelque part. Un code
    #  renommé ferait sinon passer ce contrôle au vert sur rien.
    jamais_envoyes = sorted(code for code, ou in trouves.items() if not ou)
    assert not jamais_envoyes, f"déclarés mais envoyés nulle part : {jamais_envoyes}"
    assert not ecarts, "Un courriel de sécurité dépend d'un service :\n" + "\n".join(ecarts)


def test_le_moteur_d_envoi_ignore_les_services():
    """`send_email` ne connaît que l'infrastructure (SMTP) — jamais un service."""
    arbre = module_app(MOTEUR_D_ENVOI).arbre
    imports = {n.module for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom) and n.module}
    assert "app.utils.services" not in imports
    assert _lit_un_service(arbre) == []
