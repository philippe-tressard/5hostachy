"""L'API voit l'adresse du VISITEUR, pas celle de Caddy (#1300, arbitré le 25/09/2026).

## Pourquoi

Uvicorn était lancé sans `--proxy-headers` : derrière Caddy, toute requête
portait l'adresse du proxy, et slowapi tenait UN seul seau pour tout le monde.
Un attaquant qui épuisait la limite de `/auth/login` bloquait la connexion de
TOUS les résidents ; la « limite anti-force brute » était en fait « N essais
pour tout le site ».

## La chaîne, mesurée en production le 25/09/2026

Cloudflare → `cloudflared` (service de l'HÔTE) → Caddy (`:80`, reçu depuis la
passerelle Docker `172.18.0.1`) → API (`172.18.0.2`, vue depuis Caddy
`172.18.0.5`).

- Caddy fait confiance au sous-réseau Docker et lit `Cf-Connecting-Ip`, posé par
  Cloudflare. PAS `X-Forwarded-For` : Cloudflare AJOUTE à celui qu'envoie le
  client, dont la partie gauche est donc falsifiable. Le LAN (`192.168.1.x`,
  sondes de `health-watch`) n'est pas de confiance : il ne peut rien forger.
- Caddy transmet à l'API UN `X-Forwarded-For` qu'il écrase : `{client_ip}`.
- Uvicorn fait confiance au même sous-réseau, et prend cet en-tête.

Les valeurs des limites ne changent pas (arbitré) : elles valent désormais PAR
ADRESSE. Le journal d'accès d'uvicorn est coupé (`test_journal_acces.py`) :
chaque ligne aurait porté l'adresse d'un résident.
"""

from __future__ import annotations

import asyncio
import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_START = _RACINE / "api" / "start.sh"
_CADDY = _RACINE / "Caddyfile"


def _lancement() -> list[str]:
    lignes = [
        ligne
        for ligne in _START.read_text(encoding="utf-8").splitlines()
        if "uvicorn " in ligne and ligne.strip().startswith("exec")
    ]
    assert len(lignes) == 1, lignes
    return lignes[0].split()


def _reseau_uvicorn() -> str:
    options = [o for o in _lancement() if o.startswith("--forwarded-allow-ips=")]
    assert len(options) == 1, "uvicorn doit déclarer les proxys de confiance"
    return options[0].split("=", 1)[1]


def _caddy() -> str:
    return _CADDY.read_text(encoding="utf-8")


def test_uvicorn_lit_l_adresse_transmise_par_un_proxy_de_confiance():
    assert "--proxy-headers" in _lancement()
    reseau = _reseau_uvicorn()
    assert reseau != "*", "`*` ferait confiance à n'importe qui : l'adresse se forgerait"


def test_caddy_lit_cf_connecting_ip_d_un_proxy_de_confiance_seulement():
    caddy = _caddy()
    m = re.search(r"trusted_proxies\s+static\s+(\S+)", caddy)
    assert m, "Caddy doit déclarer ses proxys de confiance (cloudflared, via la passerelle Docker)"
    assert m.group(1) == _reseau_uvicorn(), (
        "Caddy et uvicorn doivent faire confiance au MÊME réseau — le réseau Docker"
    )
    assert re.search(r"client_ip_headers\s+Cf-Connecting-Ip\b", caddy), (
        "l'adresse vient de `Cf-Connecting-Ip` (posé par Cloudflare), jamais de "
        "X-Forwarded-For, dont la partie gauche est fournie par le client"
    )


def test_chaque_passage_vers_l_api_transmet_l_adresse_du_client():
    caddy = _caddy()
    blocs = re.findall(r"reverse_proxy\s+api:8000\s*(\{[^}]*\})?", caddy)
    assert blocs, "aucun `reverse_proxy api:8000` — le contrôle ne mesure rien"
    for bloc in blocs:
        assert re.search(r"header_up\s+X-Forwarded-For\s+\{client_ip\}", bloc or ""), (
            "un passage vers l'API sans `header_up X-Forwarded-For {client_ip}` : "
            "l'API y verrait l'adresse de Caddy"
        )


def test_le_reseau_de_confiance_se_comporte_comme_prevu():
    """Le comportement, sur la valeur LUE dans start.sh — pas une valeur recopiée."""
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    vu: dict = {}

    async def application(scope, receive, send):
        vu["client"] = scope["client"][0]

    intergiciel = ProxyHeadersMiddleware(application, trusted_hosts=_reseau_uvicorn())

    def client(pair: str, xff: str | None) -> str:
        entetes = [(b"x-forwarded-for", xff.encode())] if xff else []
        asyncio.run(
            intergiciel(
                {"type": "http", "client": (pair, 1), "headers": entetes, "scheme": "http"},
                None,
                None,
            )
        )
        return vu["client"]

    #  Caddy (réseau Docker) transmet le visiteur : c'est lui qu'on voit.
    assert client("172.18.0.5", "203.0.113.7") == "203.0.113.7"
    #  Le SSR du front n'envoie rien : on voit le front.
    assert client("172.18.0.4", None) == "172.18.0.4"
    #  Un poste du LAN ne peut pas se faire passer pour un autre.
    assert client("192.168.1.50", "203.0.113.7") == "192.168.1.50"
