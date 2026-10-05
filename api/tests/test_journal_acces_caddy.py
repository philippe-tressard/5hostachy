"""Le journal d'accès de Caddy survit aux déploiements, et il est ANONYME (#1588).

## Pourquoi

Il était écrit sur la sortie standard du conteneur, que `docker compose up -d`
recrée à chaque déploiement : au moment de l'audit du 02/10/2026, `docker logs
hostachy_caddy` comptait 70 lignes (conteneur créé le matin, 12 déploiements le
30/09). Aucun 5xx de la veille n'était observable.

Il va dans un fichier du volume `caddy_logs`, roulé par taille et par âge. Et il
ne porte aucune donnée personnelle — même arbitrage que #1300 pour uvicorn
(`test_journal_acces.py`) : ni l'adresse du visiteur, ni les en-têtes (cookie de
session), ni la chaîne de requête (`?token=…` d'un lien à usage unique). Un
journal qui porterait des adresses imposerait de déclarer sa durée dans la
politique de confidentialité.

## Ce que ce test juge

La FORME du `Caddyfile` : il ne peut pas lancer Caddy (le poste n'en a pas). Le
comportement — ce qui est réellement écrit — a été éprouvé sur Caddy 2.11 dans un
conteneur jetable : une requête portant `Cf-Connecting-Ip`, un cookie et
`?token=…` ne laisse que `/chemin`, méthode, statut, durée, taille.
"""

from __future__ import annotations

import re

from tests.aides_caddy import caddyfile
from tests.conftest import racine_depot

#: Ce que le filtre doit retirer, champ par champ — et pourquoi.
RETRAITS = {
    "request>remote_ip": "l'adresse du pair (la passerelle Docker, puis demain le visiteur)",
    "request>client_ip": "l'adresse du VISITEUR, lue dans Cf-Connecting-Ip",
    "request>remote_port": "complète l'adresse",
    "request>headers": "cookie de session, agent, Authorization",
    "request>tls": "empreinte de session TLS",
    "resp_headers": "Set-Cookie",
}


def _bloc_journal(contenu: str) -> str | None:
    """Le corps du `log journal { … }` de premier niveau du site, ou `None`."""
    m = re.search(r"^\tlog journal \{\n(.*?)\n\t\}$", contenu, re.S | re.M)
    return m.group(1) if m else None


def _ecarts(contenu: str) -> list[str]:
    """Ce qui manque au journal pour tenir ses deux promesses. (PURE)"""
    ecarts: list[str] = []
    logs = re.findall(r"^\tlog\b.*$", contenu, re.M)
    if len(logs) != 1:
        # Un second `log` est ignoré sans un mot (éprouvé sur Caddy 2.11).
        ecarts.append(f"il faut UN seul `log` dans le site, pas {len(logs)} : {logs}")
    bloc = _bloc_journal(contenu)
    if bloc is None:
        return ecarts + ["bloc `log journal { … }` introuvable"]
    if not re.search(r"output file /var/log/caddy/\S+", bloc):
        ecarts.append("le journal n'est pas écrit dans /var/log/caddy (volume `caddy_logs`)")
    for regle in ("roll_size", "roll_keep ", "roll_keep_for"):
        if regle not in bloc:
            ecarts.append(f"rotation absente : `{regle.strip()}` (le fichier grossirait sans fin)")
    if "format filter" not in bloc:
        ecarts.append("aucun filtre : le journal porterait l'adresse et les en-têtes")
    for champ, raison in RETRAITS.items():
        if not re.search(rf"^\s*{re.escape(champ)}\s+delete\s*$", bloc, re.M):
            ecarts.append(f"`{champ}` n'est pas retiré — {raison}")
    if not re.search(r"request>uri\s+regexp\s+\\\?\.\*\s+\"\"", bloc):
        ecarts.append("la chaîne de requête n'est pas coupée de `request>uri` (jeton d'un lien)")
    return ecarts


def test_le_journal_d_acces_est_persistant_et_anonyme():
    contenu = caddyfile()
    assert _ecarts(contenu) == []


def test_le_volume_du_journal_est_declare_et_monte():
    compose = (racine_depot() / "docker-compose.yml").read_text(encoding="utf-8")
    assert re.search(r"^\s+- caddy_logs:/var/log/caddy\b", compose, re.M), (
        "le volume caddy_logs n'est pas monté sur /var/log/caddy : le journal retomberait "
        "dans la couche du conteneur, recréée à chaque déploiement"
    )
    assert re.search(r"^  caddy_logs:\s*$", compose, re.M), "le volume caddy_logs n'est pas déclaré"


def test_le_motif_voit_les_journaux_d_avant():
    """Cas zéro : l'ancien journal, et chaque retrait oublié, sont refusés."""
    ancien = "\tlog {\n\t\toutput stdout\n\t\tformat console\n\t}\n"
    assert _ecarts(ancien) != []
    bon = caddyfile()
    for champ in RETRAITS:
        sans = re.sub(rf"^\s*{re.escape(champ)}\s+delete\n", "", bon, flags=re.M)
        assert sans != bon, f"cas zéro : `{champ}` n'est pas dans le Caddyfile"
        assert any(champ in e for e in _ecarts(sans)), f"retrait de `{champ}` non vu"
    #  Un second `log` (ici l'ancien, sur stdout) est refusé : Caddy l'ignorerait.
    double = bon.replace("\tlog journal {", "\tlog {\n\t\toutput stdout\n\t}\n\tlog journal {", 1)
    assert any("UN seul" in e for e in _ecarts(double))
