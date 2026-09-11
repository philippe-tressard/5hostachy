"""Les trois services de modèle de langage, et la façon de parler à chacun.

## 🔴 Un socle, deux adaptations — et pas trois copies

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

## Pourquoi ce fichier est SÉPARÉ de `llm.py` (11/09/2026)

La modularité l'a imposé — `llm.py` passait 560 lignes — mais la ligne de coupe
n'est pas arbitraire : **ici on décrit des services**, là-bas on lit une
configuration et on passe un appel. Un quatrième fournisseur se lit et s'écrit
ici sans ouvrir l'autre fichier, et `llm.py` ne grossit pas d'un service de plus.

Il ne connaît ni `ConfigSite`, ni `Session`, ni le réseau : ce sont des
descriptions, pas des appels. C'est ce qui les rend testables sans rien monter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

class ErreurLLM(RuntimeError):
    """Le modèle n'a pas répondu, ou a répondu ce qu'on ne sait pas lire.

    Porte un message destiné à l'écran : il est montré à l'administrateur, donc
    il dit ce qui s'est passé, pas une trace technique.
    """


@dataclass(frozen=True)
class PieceJointe:
    """Un fichier à faire lire au modèle, décrit sans forme de transport.

    Le métier (la synthèse d'un contrat) dit QUOI joindre ; c'est le fournisseur
    qui sait sous quelle forme — `bloc_document()`. Sans cette séparation, la
    synthèse connaîtrait le format de message d'OpenAI, et un quatrième
    fournisseur obligerait à rouvrir un fichier qui parle de contrats.
    """

    nom: str
    mime: str
    donnees_b64: str


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

    def bloc_document(self, nom: str, mime: str, donnees_b64: str) -> dict[str, Any]:
        """Un fichier JOINT au message, pour que le modèle le lise lui-même.

        🔴 Pourquoi ce n'est pas un luxe (11/09/2026, premier vrai contrat) :
        les deux PDF d'un contrat de porte de parking étaient des **scans sans
        couche de texte**. `pypdf` en tirait zéro caractère, quatre sections sur
        sept sortaient « non précisé », et rien ne ressemblait autant à un
        mauvais modèle. La plupart des contrats de copropriété sont signés, donc
        scannés : sans cette voie, la fonctionnalité ne sert que la minorité des
        documents nés numériques.

        ⚠️ Le fichier ne part QUE si son texte n'a pas pu être extrait —
        l'envoyer sinon coûterait beaucoup plus cher pour le même contenu.
        """
        return {
            "type": "file",
            "file": {"filename": nom, "file_data": f"data:{mime};base64,{donnees_b64}"},
        }

    def corps(
        self,
        modele: str,
        consigne: str,
        message: str,
        max_jetons: int,
        documents: tuple[dict[str, Any], ...] = (),
    ) -> dict[str, Any]:
        """Le corps de la requête — commun à OpenAI et à Azure.

        Sans document joint, le message reste une CHAÎNE : c'est la forme que
        tous les services acceptent, y compris les plus anciens. Le tableau de
        blocs n'apparaît que lorsqu'il porte quelque chose.
        """
        contenu: Any = message
        if documents:
            contenu = [*documents, {"type": "text", "text": message}]
        return {
            "model": modele,
            "max_tokens": max_jetons,
            #  Température basse et non nulle : une synthèse de contrat doit être
            #  fidèle, pas créative. Zéro rendrait le modèle rigide sur les
            #  formulations sans le rendre plus exact.
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": consigne},
                {"role": "user", "content": contenu},
            ],
        }

    def lire(self, reponse: dict[str, Any]) -> str:
        try:
            return reponse["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ErreurLLM("Réponse du modèle illisible — format inattendu.") from exc

    #: Les paramètres qui ont CHANGÉ DE NOM d'une génération de modèles à la
    #: suivante. On ne s'en sert que lorsque le service a refusé l'ancien nom :
    #: ce n'est pas une table de modèles — ce serait le catalogue recopié qu'on
    #: vient justement de supprimer — mais une traduction appliquée à la demande.
    RENOMMAGES: ClassVar[dict[str, str]] = {"max_tokens": "max_completion_tokens"}

    def lire_erreur(self, charge: dict[str, Any]) -> tuple[str, str]:
        """Le paramètre refusé et le code, SANS recopier le message.

        ⚠️ `message` peut citer la requête, donc le contrat qu'on vient
        d'envoyer. `param` et `code` sont des champs structurés et courts : ils
        nomment le réglage fautif sans rien dire de son contenu.
        """
        err = (charge or {}).get("error") or {}
        return str(err.get("param") or ""), str(err.get("code") or "")

    #: Ce qu'on RECONNAÎT dans un refus qui ne nomme aucun paramètre, et le
    #: message de produit qui lui correspond. On lit le texte du fournisseur pour
    #: le CLASSER, jamais pour le recopier : le message rendu ci-dessous est le
    #: nôtre, et il dit quoi faire.
    DIAGNOSTICS: ClassVar[tuple[tuple[tuple[str, ...], str], ...]] = (
        (
            ("max_tokens", "output limit"),
            "Le plafond de jetons est trop bas pour ce modèle — augmentez "
            "« Longueur maximale de la réponse ».",
        ),
    )

    def diagnostiquer(self, charge: dict[str, Any]) -> str | None:
        """Un refus SANS `param` que l'on sait quand même expliquer, ou `None`.

        🔴 11/09/2026 : *« Could not finish the message because max_tokens or
        model output limit was reached »*, avec `param: null` et `code: null`.
        Les modèles qui raisonnent avant de répondre consomment le plafond sans
        écrire un mot — et l'écran affichait « répondu 400 », donc rien.

        ⚠️ Le texte du fournisseur est lu pour être CLASSÉ, jamais transmis : il
        peut citer la requête, donc le contrat. Ce qui sort d'ici est notre
        propre phrase, et elle dit quel réglage changer.
        """
        message = str(((charge or {}).get("error") or {}).get("message") or "").lower()
        if not message:
            return None
        for motifs, explication in self.DIAGNOSTICS:
            if any(m in message for m in motifs):
                return explication
        return None

    def adapter(self, corps: dict[str, Any], param: str, code: str) -> dict[str, Any] | None:
        """Le même appel, corrigé du paramètre que le service vient de refuser.

        🔴 11/09/2026, au premier essai d'un modèle récent : *« Unsupported
        parameter: 'max_tokens' is not supported with this model. Use
        'max_completion_tokens' instead. »* Le geste échouait sur un 400 opaque.

        Deux voies étaient possibles. Tenir la liste des modèles qui veulent
        l'un ou l'autre nom : c'est un catalogue, il se périme, et on venait de
        supprimer le précédent pour cette raison exacte. Ou **écouter le
        service**, qui nomme lui-même le paramètre fautif — c'est ce qu'on fait.

        Rend `None` quand on ne sait pas s'adapter : l'appel échoue alors
        normalement, en disant quel réglage a été refusé.
        """
        if code not in ("unsupported_parameter", "unsupported_value"):
            return None
        if param not in corps:
            return None
        suite = dict(corps)
        valeur = suite.pop(param)
        remplacant = self.RENOMMAGES.get(param)
        if remplacant and remplacant not in suite:
            #  Un nom qui change : on reporte la valeur, le plafond est tenu.
            suite[remplacant] = valeur
        #  Sinon on RETIRE le paramètre : `temperature` refusée, par exemple, le
        #  modèle prend la sienne. Une synthèse moins pilotée vaut mieux que pas
        #  de synthèse — et l'écran n'a rien à réapprendre à personne.
        return suite

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

    def bloc_document(self, nom: str, mime: str, donnees_b64: str) -> dict[str, Any]:
        """Même intention qu'OpenAI, autre forme — d'où la redéfinition."""
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": mime, "data": donnees_b64},
            "title": nom,
        }

    def corps(
        self,
        modele: str,
        consigne: str,
        message: str,
        max_jetons: int,
        documents: tuple[dict[str, Any], ...] = (),
    ) -> dict[str, Any]:
        contenu: Any = message
        if documents:
            contenu = [*documents, {"type": "text", "text": message}]
        return {
            "model": modele,
            "max_tokens": max_jetons,
            "temperature": 0.2,
            "system": consigne,
            "messages": [{"role": "user", "content": contenu}],
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
