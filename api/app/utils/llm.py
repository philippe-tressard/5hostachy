"""Parler à un modèle de langage — un seul point d'appel, trois fournisseurs.

## Ce que ce module porte

Le produit doit pouvoir interroger une IA (première usage : la synthèse d'un
contrat d'entretien, #899). Le fournisseur, la clé et le modèle se règlent depuis
l'administration — pas dans un fichier d'environnement, parce que c'est un
réglage de PRODUIT que le gestionnaire du site change, comme le SMTP.

## 🔴 Un socle, deux adaptations — et pas trois copies

Les trois fournisseurs standards parlent presque la même langue :

| | URL | En-tête d'authentification | Corps | Réponse |
|---|---|---|---|---|
| OpenAI | `{base}/chat/completions` | `Authorization: Bearer` | `{model, messages, max_tokens}` | `choices[0].message.content` |
| Azure OpenAI | `{base}/openai/deployments/{modele}/chat/completions?api-version=…` | `api-key` | **le même** | **la même** |
| Anthropic | `{base}/v1/messages` | `x-api-key` + `anthropic-version` | `{model, max_tokens, system, messages}` | `content[0].text` |

Azure **est** OpenAI derrière une autre porte : il n'en redéfinit que l'URL et
l'en-tête, et hérite du reste. Écrire trois fournisseurs côte à côte aurait donné
trois fois le même corps de requête — et trois occasions de les désaccorder au
premier ajustement.

⚠️ C'est l'héritage qui porte la ressemblance, pas un `if fournisseur == …`
répété à chaque étape. Ajouter un quatrième fournisseur, c'est écrire une classe,
pas modifier cinq fonctions.

## Ce que ce module NE fait pas

Il ne sait rien des contrats, des synthèses ni d'aucun métier : il envoie une
consigne et un message, il rend du texte. Ce qu'on demande au modèle vit chez
l'appelant — sinon ce fichier deviendrait le catalogue de tous les usages.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.core import ConfigSite

logger = logging.getLogger("hostachy.llm")

#: Délai au-delà duquel on renonce. Une requête d'écran ne peut pas attendre
#: indéfiniment : le geste doit rendre la main, fût-ce sur un échec.
DELAI_DEFAUT_S = 45

#: Plafond de jetons rendus — c'est un garde-fou de COÛT autant que de longueur.
MAX_JETONS_DEFAUT = 1500


class ErreurLLM(RuntimeError):
    """Le modèle n'a pas répondu, ou a répondu ce qu'on ne sait pas lire.

    Porte un message destiné à l'écran : il est montré à l'administrateur, donc
    il dit ce qui s'est passé, pas une trace technique.
    """


@dataclass(frozen=True)
class Fournisseur:
    """Un service de modèle de langage, et la façon de lui parler."""

    code: str
    libelle: str
    base_url: str
    modele_defaut: str
    #: Vrai quand le service réclame autre chose que l'URL et la clé — Azure
    #: exige un point d'accès propre au client, il n'a pas d'URL publique.
    base_url_obligatoire: bool = False

    def url(self, modele: str, base: str, version_api: str) -> str:
        return f"{base.rstrip('/')}/chat/completions"

    def entetes(self, cle: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {cle}", "Content-Type": "application/json"}

    def corps(self, modele: str, consigne: str, message: str, max_jetons: int) -> dict[str, Any]:
        """Le corps de la requête — commun à OpenAI et à Azure."""
        return {
            "model": modele,
            "max_tokens": max_jetons,
            #  Température basse et non nulle : une synthèse de contrat doit être
            #  fidèle, pas créative. Zéro rendrait le modèle rigide sur les
            #  formulations sans le rendre plus exact.
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": consigne},
                {"role": "user", "content": message},
            ],
        }

    def lire(self, reponse: dict[str, Any]) -> str:
        try:
            return reponse["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ErreurLLM("Réponse du modèle illisible — format inattendu.") from exc

    def url_modeles(self, base: str, version_api: str) -> str | None:
        """L'adresse qui LISTE les modèles — ou `None` si le service n'en a pas.

        🔴 On demande au fournisseur ce que la clé peut atteindre, plutôt que de
        tenir un catalogue à jour dans le produit (11/09/2026, « on peut choisir
        un modèle plus intelligent ? »). Un catalogue recopié se périme sans
        prévenir, et il ment deux fois : il propose des modèles que la clé ne
        peut pas appeler, et il cache ceux qui sont sortis depuis.

        ⚠️ `None` n'est pas une erreur : Azure n'expose pas ses déploiements par
        l'API d'inférence. L'écran garde alors la saisie libre — il ne prétend
        pas connaître une liste qu'il n'a pas.
        """
        return f"{base.rstrip('/')}/models"

    def lire_modeles(self, reponse: dict[str, Any]) -> list[dict[str, str]]:
        """Les modèles de CONVERSATION, du plus récent au plus ancien.

        Le tri est un fait (`created`, rendu par le service), pas une
        appréciation : il n'y a pas de « meilleur » modèle à désigner depuis ici.

        ⚠️ Le filtre est nécessaire : la liste d'OpenAI mêle transcription,
        synthèse vocale, images et plongements, qui ne répondent pas à
        `/chat/completions`. Il vit ICI, dans le seul module qui parle à ce
        service — pas dans l'écran, qui n'a pas à connaître les familles de
        modèles d'un fournisseur.
        """
        familles = ("gpt-", "chatgpt-", "o1", "o3", "o4")
        exclus = (
            "-audio", "-realtime", "-transcribe", "-tts", "-search",
            "-instruct", "-image", "-moderation", "-embedding",
        )
        vus = []
        for m in reponse.get("data") or []:
            ident = str(m.get("id") or "")
            if not ident.startswith(familles) or any(x in ident for x in exclus):
                continue
            vus.append({"id": ident, "libelle": ident, "_rang": m.get("created") or 0})
        vus.sort(key=lambda m: m["_rang"], reverse=True)
        return [{"id": m["id"], "libelle": m["libelle"]} for m in vus]


@dataclass(frozen=True)
class FournisseurAzure(Fournisseur):
    """Azure OpenAI — le même service, derrière une autre porte.

    Il n'a pas d'URL publique : chaque client a son point d'accès, et le nom du
    « déploiement » y remplace celui du modèle. Tout le reste est hérité.
    """

    base_url_obligatoire: bool = True

    def url(self, modele: str, base: str, version_api: str) -> str:
        return (
            f"{base.rstrip('/')}/openai/deployments/{modele}"
            f"/chat/completions?api-version={version_api}"
        )

    def entetes(self, cle: str) -> dict[str, str]:
        return {"api-key": cle, "Content-Type": "application/json"}

    def url_modeles(self, base: str, version_api: str) -> str | None:
        """Aucune : sur Azure, ce qu'on choisit est un DÉPLOIEMENT, que seule
        l'API de gestion connaît — une autre porte, un autre jeton, un autre
        droit. Le champ reste libre, et l'écran le dit."""
        return None


@dataclass(frozen=True)
class FournisseurAnthropic(Fournisseur):
    """Claude — le seul des trois dont le corps et la réponse diffèrent.

    La consigne y est un champ à part (`system`) plutôt qu'un message de rôle
    `system` : c'est la seule divergence de forme qui justifie de redéfinir
    `corps()` au lieu d'en hériter.
    """

    def url(self, modele: str, base: str, version_api: str) -> str:
        return f"{base.rstrip('/')}/v1/messages"

    def entetes(self, cle: str) -> dict[str, str]:
        return {
            "x-api-key": cle,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def corps(self, modele: str, consigne: str, message: str, max_jetons: int) -> dict[str, Any]:
        return {
            "model": modele,
            "max_tokens": max_jetons,
            "temperature": 0.2,
            "system": consigne,
            "messages": [{"role": "user", "content": message}],
        }

    def url_modeles(self, base: str, version_api: str) -> str | None:
        return f"{base.rstrip('/')}/v1/models"

    def lire_modeles(self, reponse: dict[str, Any]) -> list[dict[str, str]]:
        """Anthropic ne rend que des modèles de conversation : aucun filtre.

        Il rend en revanche un `display_name` — « Claude Sonnet 4.5 » plutôt que
        `claude-sonnet-4-5-20250929` —, et c'est cela qu'un gestionnaire lit. La
        liste arrive déjà du plus récent au plus ancien.
        """
        return [
            {"id": str(m["id"]), "libelle": str(m.get("display_name") or m["id"])}
            for m in (reponse.get("data") or [])
            if m.get("id")
        ]

    def lire(self, reponse: dict[str, Any]) -> str:
        try:
            return reponse["content"][0]["text"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ErreurLLM("Réponse du modèle illisible — format inattendu.") from exc


#: Les fournisseurs proposés à l'écran. Trois suffisent : ce sont les standards
#: du marché, et tout service compatible OpenAI (un proxy, un modèle hébergé)
#: s'atteint déjà par « OpenAI » en changeant l'URL de base.
FOURNISSEURS: dict[str, Fournisseur] = {
    "openai": Fournisseur(
        code="openai",
        libelle="OpenAI",
        base_url="https://api.openai.com/v1",
        modele_defaut="gpt-4o-mini",
    ),
    "anthropic": FournisseurAnthropic(
        code="anthropic",
        libelle="Claude (Anthropic)",
        base_url="https://api.anthropic.com",
        modele_defaut="claude-haiku-4-5-20251001",
    ),
    "azure_openai": FournisseurAzure(
        code="azure_openai",
        libelle="Azure OpenAI",
        base_url="",
        modele_defaut="",
    ),
}

FOURNISSEUR_DEFAUT = "openai"

#: Les clés de `ConfigSite` qui décrivent l'accès au modèle.
#:
#: ⚠️ `llm_api_key` est déclarée dans `routers/config._SECRETS` : sa valeur ne
#: sort JAMAIS de l'API, même pour un administrateur. L'écran sait seulement
#: qu'une clé existe (03/09/2026 — `smtp_password` avait voyagé en clair dans la
#: réponse HTTP alors que l'écran ne l'affichait pas ; la protection était dans
#: le rendu, c'est-à-dire nulle part).
CLE_ACTIF = "llm_actif"
CLE_FOURNISSEUR = "llm_fournisseur"
CLE_API = "llm_api_key"
CLE_MODELE = "llm_modele"
CLE_BASE_URL = "llm_base_url"
CLE_VERSION_API = "llm_api_version"
CLE_MAX_JETONS = "llm_max_jetons"
CLE_DELAI = "llm_delai_s"
CLE_ENVOI_DOCUMENT = "llm_envoi_document"


@dataclass
class ConfigLLM:
    """La configuration lue, prête à servir — ou à dire pourquoi elle ne peut pas."""

    actif: bool
    fournisseur: Fournisseur
    cle: str
    modele: str
    base_url: str
    version_api: str
    max_jetons: int
    delai_s: int
    envoi_document: bool

    def verifier(self, *, exiger_actif: bool = True) -> None:
        """Lève `ErreurLLM` si l'appel ne peut pas aboutir — avant de le tenter.

        ⚠️ On échoue AVANT la requête réseau plutôt qu'après : un 401 met
        plusieurs secondes et rend un message du fournisseur, pas du produit.

        🔴 `exiger_actif=False` pour le TEST DE CONNEXION (11/09/2026, constaté à
        l'écran : « j'ai voulu tester » → *« l'assistant est désactivé »*).

        L'ordre naturel est : je saisis, je teste, **puis** j'active — on vérifie
        une configuration pour DÉCIDER de l'activer. Exiger l'activation avant de
        pouvoir tester obligeait à ouvrir le service au produit sans savoir s'il
        répond, c'est-à-dire à prendre le risque qu'on cherchait à écarter.
        """
        if exiger_actif and not self.actif:
            raise ErreurLLM("L'assistant est désactivé dans l'administration.")
        if not self.cle:
            raise ErreurLLM("Aucune clé d'API n'est enregistrée.")
        if not self.modele:
            raise ErreurLLM("Aucun modèle n'est indiqué.")
        if self.fournisseur.base_url_obligatoire and not self.base_url:
            raise ErreurLLM(
                f"{self.fournisseur.libelle} exige l'adresse de votre point d'accès."
            )


def _lire(session: Session) -> dict[str, str]:
    return {r.cle: r.valeur for r in session.exec(select(ConfigSite)).all()}


def config_llm(session: Session) -> ConfigLLM:
    """La configuration de l'assistant, telle que l'administration l'a posée."""
    cfg = _lire(session)
    code = cfg.get(CLE_FOURNISSEUR) or FOURNISSEUR_DEFAUT
    fournisseur = FOURNISSEURS.get(code) or FOURNISSEURS[FOURNISSEUR_DEFAUT]

    def entier(cle: str, defaut: int) -> int:
        #  Une valeur illisible retombe sur le défaut : ce réglage gouverne un
        #  confort et un coût, il ne doit jamais empêcher l'appel de partir.
        try:
            return int(cfg.get(cle) or defaut)
        except (TypeError, ValueError):
            return defaut

    return ConfigLLM(
        actif=cfg.get(CLE_ACTIF) == "1",
        fournisseur=fournisseur,
        cle=cfg.get(CLE_API) or "",
        modele=cfg.get(CLE_MODELE) or fournisseur.modele_defaut,
        base_url=cfg.get(CLE_BASE_URL) or fournisseur.base_url,
        version_api=cfg.get(CLE_VERSION_API) or "2024-06-01",
        max_jetons=entier(CLE_MAX_JETONS, MAX_JETONS_DEFAUT),
        delai_s=entier(CLE_DELAI, DELAI_DEFAUT_S),
        envoi_document=cfg.get(CLE_ENVOI_DOCUMENT, "1") == "1",
    )


async def demander(
    session: Session,
    *,
    consigne: str,
    message: str,
    max_jetons: Optional[int] = None,
    exiger_actif: bool = True,
) -> str:
    """Pose une question au modèle configuré et rend sa réponse en texte.

    Lève `ErreurLLM` — jamais autre chose : l'appelant est un écran, il doit
    pouvoir dire « ça n'a pas marché » sans distinguer un délai dépassé d'un
    502 du fournisseur.
    """
    import httpx

    cfg = config_llm(session)
    cfg.verifier(exiger_actif=exiger_actif)
    f = cfg.fournisseur

    debut = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=cfg.delai_s) as client:
            reponse = await client.post(
                f.url(cfg.modele, cfg.base_url, cfg.version_api),
                headers=f.entetes(cfg.cle),
                json=f.corps(cfg.modele, consigne, message, max_jetons or cfg.max_jetons),
            )
    except httpx.TimeoutException as exc:
        raise ErreurLLM(f"Pas de réponse après {cfg.delai_s} s.") from exc
    except httpx.HTTPError as exc:
        raise ErreurLLM("Le service n'a pas pu être joint.") from exc

    duree = time.monotonic() - debut
    if reponse.status_code == 401 or reponse.status_code == 403:
        raise ErreurLLM("Clé d'API refusée par le fournisseur.")
    if reponse.status_code == 404:
        raise ErreurLLM(f"Modèle « {cfg.modele} » introuvable chez {f.libelle}.")
    if reponse.status_code == 429:
        raise ErreurLLM("Quota atteint chez le fournisseur — réessayez plus tard.")
    if reponse.status_code >= 400:
        #  ⚠️ On journalise le corps, on ne le RECOPIE PAS à l'écran : il peut
        #  contenir la requête, donc le contrat qu'on vient d'envoyer.
        logger.warning("LLM %s → %s : %s", f.code, reponse.status_code, reponse.text[:400])
        raise ErreurLLM(f"Le fournisseur a répondu {reponse.status_code}.")

    texte = f.lire(reponse.json())
    if not texte:
        raise ErreurLLM("Le modèle a répondu sans contenu.")
    logger.info("LLM %s/%s : %d caractères en %.1f s", f.code, cfg.modele, len(texte), duree)
    return texte


async def modeles_disponibles(session: Session) -> dict[str, Any]:
    """Ce que la clé enregistrée peut RÉELLEMENT appeler, demandé au fournisseur.

    🔴 Le fait, pas le catalogue. Le champ « Modèle » était libre et adossé à
    trois exemples écrits en dur, avec le commentaire « le catalogue bouge
    vite » — ce qui est l'aveu même du défaut : un repère recopié propose des
    modèles que la clé ne peut pas appeler et cache ceux qui sont sortis depuis.
    Le gestionnaire découvrait l'écart au test de connexion, une saisie plus
    tard.

    Rend toujours une réponse LISIBLE, jamais une exception :

    | `listable` | Ce que l'écran en fait |
    |---|---|
    | `True` | une liste déroulante, avec le modèle en place toujours proposé |
    | `False` | la saisie libre, et le `motif` dit pourquoi |

    ⚠️ `False` couvre trois cas qu'il ne faut PAS confondre avec une panne :
    Azure (pas d'inventaire par cette porte), une clé restreinte en lecture, et
    un service injoignable. Aucun n'empêche de configurer l'assistant à la main —
    c'est pourquoi l'absence de liste n'est pas une erreur.
    """
    import httpx

    cfg = config_llm(session)
    cfg.verifier(exiger_actif=False)
    url = cfg.fournisseur.url_modeles(cfg.base_url, cfg.version_api)
    if url is None:
        return {
            "listable": False,
            "motif": f"{cfg.fournisseur.libelle} n'expose pas la liste de ses déploiements.",
            "modeles": [],
        }
    try:
        async with httpx.AsyncClient(timeout=cfg.delai_s) as client:
            reponse = await client.get(url, headers=cfg.fournisseur.entetes(cfg.cle))
    except httpx.HTTPError:
        return {"listable": False, "motif": "Le service n'a pas pu être joint.", "modeles": []}
    if reponse.status_code in (401, 403):
        #  Le cas le plus fréquent : une clé créée en écriture seule, ou
        #  restreinte à `/chat/completions`. Elle SYNTHÉTISE très bien et ne
        #  peut pas s'inventorier — le dire évite de la croire invalide.
        return {
            "listable": False,
            "motif": "Cette clé n'a pas le droit de lister les modèles (permission « models »).",
            "modeles": [],
        }
    if reponse.status_code >= 400:
        logger.warning("Liste des modèles %s → %s", cfg.fournisseur.code, reponse.status_code)
        return {
            "listable": False,
            "motif": f"Le fournisseur a répondu {reponse.status_code}.",
            "modeles": [],
        }
    try:
        modeles = cfg.fournisseur.lire_modeles(reponse.json())
    except (ValueError, KeyError, TypeError):
        return {"listable": False, "motif": "Liste illisible — format inattendu.", "modeles": []}
    #  Une liste VIDE n'est pas une liste : la rendre ferait choisir dans un
    #  menu sans entrée (`standards/04` §2 — le cas zéro).
    if not modeles:
        return {"listable": False, "motif": "Aucun modèle de conversation proposé.", "modeles": []}
    return {"listable": True, "motif": "", "modeles": modeles}


async def tester(session: Session) -> dict[str, Any]:
    """Vérifie que la configuration PARLE au modèle — le fait, pas le réglage.

    🔴 Un écran qui dit « configuré » parce que trois champs sont remplis ne
    prouve rien : la clé peut être révoquée, le modèle renommé, le point d'accès
    fermé. Ce test envoie une vraie question et attend une vraie réponse
    (`standards/04` — vérifier le comportement, jamais l'artefact).
    """
    cfg = config_llm(session)
    debut = time.monotonic()
    texte = await demander(
        session,
        consigne="Tu réponds en un seul mot, sans ponctuation.",
        message="Réponds exactement : opérationnel",
        max_jetons=16,
        #  Le test ne demande pas l'activation : il sert à décider de l'activer.
        exiger_actif=False,
    )
    return {
        "ok": True,
        "fournisseur": cfg.fournisseur.libelle,
        "modele": cfg.modele,
        "reponse": texte[:80],
        "duree_ms": int((time.monotonic() - debut) * 1000),
    }
