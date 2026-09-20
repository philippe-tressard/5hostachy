"""`.env.example` est le gabarit d'installation — il doit démarrer la stack.

## L'incident (#1029, audit du 19/09/2026)

`scripts/installation/setup-rpi5.sh` était **le** script d'installation d'un nœud
neuf. Il générait son propre `.env`, et ce `.env` ne pouvait pas démarrer la
stack :

| Ce qu'il écrivait | Le réel |
|---|---|
| `DATABASE_URL=sqlite:////data/db/app.db` | le volume est `app_data:/app/data` → **base hors volume, perdue à la recréation** |
| `MAIL_TLS`, `APP_ENV`, `PI_IP`, `DOMAIN` | aucun champ correspondant dans `Settings` |
| — | **`WHATSAPP_API_KEY` absente**, et `docker-compose.yml` la rend obligatoire (`:?`) → `docker compose up` **refuse de démarrer** |

Le script a été supprimé et `docs/restauration-complete.md` est désormais la
seule procédure. Mais supprimer ne protège de rien : le défaut n'était pas le
script, c'était que **personne ne confrontait le gabarit d'installation à ce que
le code lit réellement**. Trois fichiers écrivent des noms de variables —
`.env.example`, `config.py`, `docker-compose.yml` — et aucun langage ne les
compare.

## Ce que ces tests verrouillent

1. une variable **obligatoire** de compose figure dans le gabarit (sinon
   l'installation échoue au premier `up`) ;
2. une variable du gabarit est **lue par quelqu'un** (sinon elle promet une
   capacité qui n'existe pas — c'est ainsi que quatre clés `APPLE_*` y
   annonçaient un OAuth Apple jamais écrit) ;
3. tout réglage de `Settings` est **visible** de l'exploitant, ou déclaré hors
   gabarit avec sa raison — `INSTANCE_ID` ne l'était nulle part, et le pied de
   page restait muet sur le nœud servant ;
4. la valeur d'exemple de `DATABASE_URL` est **celle du code**, donc dans le
   volume monté ;
5. aucun script versionné ne **regénère** un `.env` ou un `Caddyfile` — c'est le
   geste exact qui a produit l'incident, et rien n'empêchait de le réintroduire.

⚠️ Le point 3 porte une liste d'exceptions **déclarée** : trois champs de
`Settings` n'ont volontairement pas leur place dans le gabarit. Le test échoue
aussi quand l'une d'elles cesse de servir — sinon la liste grossit jusqu'à tout
couvrir (`standards/05` §2).
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
EXEMPLE = RACINE / ".env.example"
COMPOSE_TXT = (RACINE / "docker-compose.yml").read_text(encoding="utf-8")
CONFIG_TXT = (RACINE / "api" / "app" / "config.py").read_text(encoding="utf-8")

#: Champs de `Settings` qui n'ont PAS à figurer dans le gabarit, et pourquoi.
#: Une entrée devenue fausse fait échouer `test_les_exceptions_servent_encore`.
HORS_GABARIT = {
    "algorithm": "l'algorithme JWT n'est pas un réglage d'exploitant : le changer "
    "invaliderait tous les jetons en circulation",
    "uploads_dir": "chemin INTERNE au conteneur, fixé par le volume "
    "`uploads:/app/uploads` — le déclarer dans .env laisserait croire qu'on peut "
    "le déplacer sans toucher au volume",
    "wa_photo_budget_ko": "posé par l'ancre `x-budget-photo-whatsapp` de "
    "docker-compose.yml, lue des DEUX côtés (API et bridge) ; une seconde source "
    "les ferait diverger (#1057)",
}


#: Écritures dans `.env` qui ne sont PAS une regénération : la bascule ajuste
#: deux réglages qui dépendent du nœud servant. Clé = (script, extrait de ligne).
#: Le test échoue aussi quand l'un de ces ajustements disparaît — sinon
#: l'exception survit à ce qu'elle protégeait.
AJUSTEMENTS_DECLARES = {
    (
        "bascule.sh",
        "COOKIE_SECURE=false",
    ): "la bascule bascule aussi l'origine servie (http://192.168.1.22x) : un cookie "
    "`Secure` ne repartirait pas sur cette origine en clair. ⚠️ Ce réglage reste posé "
    "quand le trafic public repasse en HTTPS par le tunnel — traité par #1077",
}


def _cles_du_gabarit() -> list[str]:
    return [
        m.group(1)
        for m in re.finditer(r"(?m)^([A-Z][A-Z0-9_]*)=", EXEMPLE.read_text(encoding="utf-8"))
    ]


def _champs_de_settings() -> set[str]:
    """Les champs déclarés par `Settings` — l'indentation de 4 les distingue."""
    return {m.group(1) for m in re.finditer(r"(?m)^\s{4}([a-z][a-z0-9_]*)\s*:", CONFIG_TXT)}


def _sources_python() -> str:
    return " ".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (RACINE / "api" / "app").rglob("*.py")
    )


def test_les_variables_obligatoires_de_compose_sont_dans_le_gabarit():
    """`${X:?…}` fait échouer `docker compose up` — le gabarit doit la porter.

    C'est le défaut exact qui rendait `setup-rpi5.sh` inapplicable : il écrivait
    un `.env` sans `WHATSAPP_API_KEY`, et l'installation s'arrêtait au démarrage
    des conteneurs, après toute la préparation du système.
    """
    obligatoires = set(re.findall(r"\$\{([A-Z0-9_]+):\?", COMPOSE_TXT))
    assert obligatoires, (
        "aucune variable obligatoire trouvée dans docker-compose.yml : le motif "
        "`${X:?…}` a changé de forme, et ce test ne mesure plus rien"
    )
    manquantes = obligatoires - set(_cles_du_gabarit())
    assert not manquantes, (
        f"docker-compose.yml exige {sorted(manquantes)} (`:?`) mais .env.example ne "
        f"la/les déclare pas : une installation faite depuis le gabarit ne démarrera pas"
    )


def test_aucune_variable_du_gabarit_n_est_morte():
    """Une clé du gabarit doit être lue par `Settings`, compose, ou `os.getenv`.

    Une clé que personne ne lit n'est pas inoffensive : elle annonce une capacité.
    Quatre clés `APPLE_*` y promettaient une connexion Apple qui n'a jamais été
    écrite, et `DOMAIN` survivait à l'époque où Caddy servait un nom de domaine
    local — aujourd'hui le TLS est chez Cloudflare et le Caddyfile écoute `:80`.
    """
    champs = {c.upper() for c in _champs_de_settings()}
    lues_par_compose = set(re.findall(r"\$\{([A-Z0-9_]+)", COMPOSE_TXT))
    motif_getenv = r"getenv\(\s*[\"']([A-Z0-9_]+)"
    lues_par_getenv = set(re.findall(motif_getenv, _sources_python()))
    mortes = [
        c
        for c in _cles_du_gabarit()
        if c not in champs and c not in lues_par_compose and c not in lues_par_getenv
    ]
    assert not mortes, (
        f".env.example déclare {mortes} que personne ne lit — ni `Settings` "
        f"(api/app/config.py), ni docker-compose.yml, ni un `os.getenv`. Soit le "
        f"code a perdu la variable, soit le gabarit promet ce qui n'existe pas"
    )


def test_tout_champ_de_settings_est_dans_le_gabarit_ou_declare_hors():
    """L'autre sens : un réglage que l'exploitant ne voit pas n'est pas réglable.

    `INSTANCE_ID` en était l'exemple : lue par compose, par `config.py`, par
    `utils/noeud.py` et affichée au pied de page, déclarée **nulle part** — le
    nœud s'annonçait donc vide sur toute installation neuve.
    """
    cles = {c.lower() for c in _cles_du_gabarit()}
    absents = sorted(_champs_de_settings() - cles - set(HORS_GABARIT))
    assert not absents, (
        f"`Settings` déclare {absents}, que .env.example ne montre pas : ajoutez-les "
        f"au gabarit, ou inscrivez-les dans HORS_GABARIT avec la raison qui les en exclut"
    )


def test_les_exceptions_servent_encore():
    """Une exception qui ne correspond plus à rien fait échouer le contrôle."""
    champs = _champs_de_settings()
    perimees = sorted(set(HORS_GABARIT) - champs)
    assert not perimees, (
        f"HORS_GABARIT retient {perimees}, qui n'existe(nt) plus dans `Settings` : "
        f"retirez l'entrée, sinon la liste protège un champ disparu"
    )
    dans_les_deux = sorted(set(HORS_GABARIT) & {c.lower() for c in _cles_du_gabarit()})
    assert not dans_les_deux, (
        f"{dans_les_deux} est à la fois déclaré hors gabarit et présent dans "
        f".env.example : l'une des deux décisions est fausse"
    )


def test_la_base_de_l_exemple_est_celle_du_code_et_dans_le_volume():
    """`DATABASE_URL` hors du volume monté = base perdue à la recréation.

    L'installeur écrivait `sqlite:////data/db/app.db` quand le volume est
    `app_data:/app/data`. Rien ne l'aurait signalé : la stack démarre, la base se
    crée, et elle disparaît au premier `docker compose down -v`.
    """
    exemple = re.search(r"(?m)^DATABASE_URL=(.+)$", EXEMPLE.read_text(encoding="utf-8"))
    assert exemple, ".env.example ne déclare plus DATABASE_URL"
    defaut = re.search(r'database_url:\s*str\s*=\s*"([^"]+)"', CONFIG_TXT)
    assert defaut, "config.py ne déclare plus de défaut pour database_url"
    assert exemple.group(1).strip() == defaut.group(1), (
        f"DATABASE_URL du gabarit ({exemple.group(1).strip()}) diffère du défaut du "
        f"code ({defaut.group(1)}) : l'un des deux pointe hors du volume "
        f"`app_data:/app/data`"
    )
    chemin = defaut.group(1).split("////")[-1]
    assert chemin.startswith("app/data/"), (
        f"la base est déclarée en `{chemin}`, hors du volume monté par "
        f"docker-compose.yml (`app_data:/app/data`) : elle serait perdue à la recréation"
    )


def test_aucun_script_ne_regenere_env_ni_caddyfile():
    """Le geste qui a produit l'incident : un script qui réécrit la configuration.

    Un installeur qui génère son `.env` et son `Caddyfile` fabrique une seconde
    vérité, qui dérive en silence — celle de `setup-rpi5.sh` posait des en-têtes
    de sécurité plus faibles que le Caddyfile versionné (`SAMEORIGIN` au lieu de
    `DENY`, ni HSTS, ni CSP, ni Permissions-Policy) et un Caddyfile que compose ne
    montait même pas.

    La référence unique est le dépôt : `.env.example` pour les secrets,
    `Caddyfile` à la racine pour le service.
    """
    fautes = []
    restants = dict(AJUSTEMENTS_DECLARES)
    for script in sorted((RACINE / "scripts").rglob("*.sh")):
        for numero, ligne in enumerate(
            script.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            nue = ligne.strip()
            if nue.startswith("#"):
                continue
            #  Une REDIRECTION vers .env ou un Caddyfile — pas une simple lecture
            #  (`source .env`, `grep … .env`), qui reste légitime.
            if not re.search(r">\s*[\"']?\S*(\.env\b|Caddyfile)", nue):
                continue
            declare = next(
                (cle for cle in restants if cle[0] == script.name and cle[1] in nue), None
            )
            if declare:
                restants.pop(declare)
            else:
                fautes.append(f"{script.relative_to(RACINE)}:{numero} : {nue[:90]}")
    assert not fautes, (
        "un script versionné réécrit la configuration, au lieu de s'en remettre au "
        "dépôt :\n"
        + "\n".join(fautes)
        + "\n\nSi c'est un AJUSTEMENT de rôle et non une regénération, déclarez-le "
        "dans AJUSTEMENTS_DECLARES avec sa raison."
    )
    assert not restants, (
        f"AJUSTEMENTS_DECLARES retient {sorted(restants)}, qu'aucun script n'écrit "
        f"plus : une exception qui ne sert plus finit par couvrir autre chose"
    )
