"""Parler à un modèle de langage — un seul point d'appel, trois fournisseurs.

## Ce que ce module porte

Le produit doit pouvoir interroger une IA (première usage : la synthèse d'un
contrat d'entretien, #899). Le fournisseur, la clé et le modèle se règlent depuis
l'administration — pas dans un fichier d'environnement, parce que c'est un
réglage de PRODUIT que le gestionnaire du site change, comme le SMTP.

## Où sont les fournisseurs

Dans `llm_fournisseurs.py`, depuis le 11/09/2026 : **ici on lit une
configuration et on passe un appel**, là-bas on décrit des services. Ce module
reste la porte d'entrée — les appelants importent d'ici, `__all__` le déclare, et
le découpage ne change aucun contrat.

## 🔴 Un appel qui ÉCOUTE le service

Un modèle récent a refusé `max_tokens` en réclamant `max_completion_tokens`
(constaté le 11/09/2026 au premier essai de `gpt-5.6-terra`). Deux voies :
tenir la liste des modèles qui veulent l'un ou l'autre nom — un catalogue, qui se
périme, et qu'on venait justement de supprimer du champ « Modèle » — ou lire le
paramètre que le service NOMME dans son refus, et reprendre l'appel corrigé.
C'est la seconde : voir `Fournisseur.adapter`, et `MAX_ADAPTATIONS` qui la borne.

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
from app.utils.llm_fournisseurs import (
    FOURNISSEUR_DEFAUT,
    FOURNISSEURS,
    ErreurLLM,
    Fournisseur,
    FournisseurAnthropic,
    FournisseurAzure,
    PieceJointe,
)

#: 🔴 Ce module reste **la porte d'entrée unique**, même depuis que les
#: fournisseurs vivent à côté (11/09/2026). Les appelants — routers, synthèse de
#: contrat, tests — importent d'ici et n'ont pas à savoir qu'il y a deux
#: fichiers : le découpage est une affaire de lisibilité, pas un changement de
#: contrat. C'est ce que déclare ce `__all__`, et c'est pourquoi les noms
#: réexportés y figurent.
__all__ = [
    "CLE_ACTIF",
    "CLE_API",
    "CLE_BASE_URL",
    "CLE_DELAI",
    "CLE_ENVOI_DOCUMENT",
    "CLE_FOURNISSEUR",
    "CLE_MAX_JETONS",
    "CLE_MODELE",
    "CLE_VERSION_API",
    "FOURNISSEUR_DEFAUT",
    "FOURNISSEURS",
    "ConfigLLM",
    "ErreurLLM",
    "Fournisseur",
    "FournisseurAnthropic",
    "FournisseurAzure",
    "PieceJointe",
    "Reponse",
    "config_llm",
    "demander",
    "modeles_disponibles",
    "tester",
]

logger = logging.getLogger("hostachy.llm")

#: Délai au-delà duquel on renonce. Une requête d'écran ne peut pas attendre
#: indéfiniment : le geste doit rendre la main, fût-ce sur un échec.
DELAI_DEFAUT_S = 45

#: Plafond de jetons rendus — c'est un garde-fou de COÛT autant que de longueur.
MAX_JETONS_DEFAUT = 1500

@dataclass(frozen=True)
class Reponse:
    """Ce que le modèle a rendu, ET ce qu'il a réellement reçu.

    🔴 Le second point n'est pas un détail de journal : quand le service refuse
    les pièces jointes, l'appel aboutit quand même — sur la seule fiche. Sans
    `documents_joints`, l'écran présenterait cette synthèse appauvrie comme si
    elle avait lu les contrats. Une réponse qui ne dit pas ce qu'elle a lu est
    invérifiable (11/09/2026).
    """

    texte: str
    documents_joints: int

    def __str__(self) -> str:  # pragma: no cover - confort d'écriture
        return self.texte


#: Combien de fois au plus on corrige la requête après un refus de paramètre.
#: Deux suffisent aux cas connus (le plafond de jetons, la température) ; le
#: plafond existe pour qu'un service qui refuserait tout ne soit pas appelé en
#: boucle — il est facturé à l'appel.
MAX_ADAPTATIONS = 2


def _charge(reponse: Any) -> dict[str, Any]:
    """Le JSON d'une réponse, ou un objet vide — un corps illisible n'est pas
    une panne de plus à distinguer ici."""
    try:
        charge = reponse.json()
    except ValueError:
        return {}
    return charge if isinstance(charge, dict) else {}


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
    fichiers: tuple[PieceJointe, ...] = (),
    exiger_actif: bool = True,
) -> Reponse:
    """Pose une question au modèle configuré et rend sa réponse.

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
        #  C'est ici, et nulle part ailleurs, que le format de message du
        #  fournisseur rencontre les fichiers du métier.
        joints = tuple(f.bloc_document(j.nom, j.mime, j.donnees_b64) for j in fichiers)
        corps = f.corps(cfg.modele, consigne, message, max_jetons or cfg.max_jetons, joints)
        #  Vrai tant qu'on n'a pas dû renoncer aux pièces jointes.
        avec_documents = bool(joints)
        async with httpx.AsyncClient(timeout=cfg.delai_s) as client:
            #  Le plafond de reprises est BORNÉ : chaque tour retire ou renomme
            #  un paramètre, il y en a peu, et une boucle sans fin sur un service
            #  facturé à l'appel serait pire que l'échec qu'elle évite.
            #  +2 : un tour pour l'appel initial, un pour le repli sans pièces
            #  jointes qui ne doit pas consommer le budget des adaptations.
            for _ in range(MAX_ADAPTATIONS + 2):
                reponse = await client.post(
                    f.url(cfg.modele, cfg.base_url, cfg.version_api),
                    headers=f.entetes(cfg.cle),
                    json=corps,
                )
                if reponse.status_code != 400:
                    break
                param, code = f.lire_erreur(_charge(reponse))
                suite = f.adapter(corps, param, code)
                if suite is not None:
                    logger.info(
                        "LLM %s : paramètre « %s » refusé (%s) — réessai", f.code, param, code
                    )
                    corps = suite
                    continue
                if avec_documents:
                    #  🔴 Dernier recours : le service n'a pas voulu des fichiers
                    #  joints. On repose la MÊME question sans eux plutôt que de
                    #  rendre un échec — une synthèse fondée sur la seule fiche
                    #  vaut mieux que pas de synthèse, et elle le DIT (l'appelant
                    #  lit `documents_refuses` pour l'écrire dans l'encart).
                    #
                    #  ⚠️ Ce repli est distinct de `adapter()` : celui-là corrige
                    #  un RÉGLAGE, celui-ci renonce à du CONTENU. Les confondre
                    #  ferait disparaître des documents sans que personne le sache.
                    logger.info("LLM %s : documents joints refusés — reprise sans eux", f.code)
                    avec_documents = False
                    #  ⚠️ On ne reconstruit QUE les messages : les adaptations de
                    #  paramètres déjà obtenues (un plafond renommé, une
                    #  température retirée) doivent survivre, sinon on les repaie
                    #  en tours de boucle et on épuise le budget avant d'aboutir.
                    sans = f.corps(cfg.modele, consigne, message, max_jetons or cfg.max_jetons, ())
                    corps = {**corps, "messages": sans["messages"]}
                    continue
                break
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
        #  Le paramètre refusé, lui, se DIT : c'est un champ structuré, il ne
        #  porte aucun contenu, et sans lui l'écran affiche « répondu 400 » —
        #  un message sur lequel personne ne peut agir (constaté le 11/09/2026).
        charge = _charge(reponse)
        explication = f.diagnostiquer(charge)
        if explication:
            raise ErreurLLM(explication)
        param, _code = f.lire_erreur(charge)
        precision = f" — réglage refusé : « {param} »" if param else ""
        raise ErreurLLM(f"Le fournisseur a répondu {reponse.status_code}{precision}.")

    texte = f.lire(reponse.json())
    if not texte:
        raise ErreurLLM("Le modèle a répondu sans contenu.")
    logger.info(
        "LLM %s/%s : %d caractères en %.1f s (%d document(s) joint(s))",
        f.code,
        cfg.modele,
        len(texte),
        duree,
        len(fichiers) if avec_documents else 0,
    )
    return Reponse(texte=texte, documents_joints=len(fichiers) if avec_documents else 0)


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
    reponse = await demander(
        session,
        consigne="Tu réponds en un seul mot, sans ponctuation.",
        message="Réponds exactement : opérationnel",
        #  🔴 Plus de plafond serré ici (11/09/2026). Il valait 16 jetons — assez
        #  pour un mot, trop peu pour un modèle qui RAISONNE avant de répondre :
        #  il épuisait le plafond sans rien écrire, et le test déclarait en panne
        #  une configuration parfaitement bonne. Un test qui n'éprouve pas la
        #  configuration réelle n'éprouve rien (`standards/04` — vérifier le fait).
        #  Le coût ne change pas : un plafond n'est pas facturé, seuls les jetons
        #  produits le sont, et la réponse attendue fait un mot.
        #  Le test ne demande pas l'activation : il sert à décider de l'activer.
        exiger_actif=False,
    )
    return {
        "ok": True,
        "fournisseur": cfg.fournisseur.libelle,
        "modele": cfg.modele,
        "reponse": reponse.texte[:80],
        "duree_ms": int((time.monotonic() - debut) * 1000),
    }
