"""Les USAGES de l'assistant IA — ce que le produit demande à un modèle, et où
chacun règle son modèle, son prompt et son plafond.

## Pourquoi ce registre (17/09/2026, #984)

L'assistant n'avait qu'un usage — la synthèse d'un contrat — et sa
configuration était donc globale : un modèle, un plafond, une consigne écrite
en dur. Le second usage (retravailler une description, #985) n'a ni le même
modèle idéal, ni le même plafond (une synthèse demande 10 000 jetons, une
réécriture bien moins), ni la même consigne — et Philippe veut relire et
adapter ces consignes depuis l'administration.

D'où deux étages, arbitrés le 17/09/2026 :

| Commun (`llm_*`) | Par usage (`llm_<usage>_*`) |
|---|---|
| activation globale, fournisseur, clé, adresse, version d'API, délai | activation, **modèle** (obligatoire — pas de modèle commun), **prompt**, plafond de jetons |

## 🔴 Ce registre est la SEULE liste des usages

L'écran d'administration la lit par `GET /config/llm-usages` et rend un bloc
par entrée : ajouter un usage, c'est ajouter une ligne ici — pas un écran.
Une liste recopiée côté front divergerait au premier usage ajouté, et c'est le
défaut que ce dépôt connaît le mieux.

## Ce que ce module ne fait pas

Il ne lit pas la base et ne passe aucun appel : il DÉCRIT. La lecture de la
configuration vit dans `llm.py` (`config_llm(session, usage)`), la matière de
chaque usage chez son appelant (`synthese_contrat.py`, `assistant_description.py`).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.utils.description_format import CONSIGNE_DEFAUT as CONSIGNE_DESCRIPTION
from app.utils.reponse_courriel import CONSIGNE as CONSIGNE_REPONSE_COURRIEL
from app.utils.reponse_courriel import USAGE_REPONSE_COURRIEL
from app.utils.synthese_format import CONSIGNE as CONSIGNE_SYNTHESE


@dataclass(frozen=True)
class Usage:
    """Un usage de l'assistant, et ses valeurs d'origine."""

    code: str
    libelle: str
    #: Ce que l'écran d'administration dit de l'usage — où il sert, à qui.
    description: str
    #: Le prompt D'ORIGINE. Il initialise la valeur en base (migration) et sert
    #: de repli si la clé est vide ; « Rétablir le prompt d'origine » y revient.
    prompt_defaut: str
    #: Le plafond d'origine, pour la même raison.
    max_jetons_defaut: int

    def cle(self, champ: str) -> str:
        """La clé `ConfigSite` d'un réglage de cet usage."""
        return f"llm_{self.code}_{champ}"


#: Les réglages qu'un usage porte, dans l'ordre de l'écran.
CHAMPS_USAGE = ("actif", "modele", "prompt", "max_jetons")

USAGE_SYNTHESE_CONTRAT = "synthese_contrat"
USAGE_DESCRIPTION = "description"

USAGES: dict[str, Usage] = {
    USAGE_SYNTHESE_CONTRAT: Usage(
        code=USAGE_SYNTHESE_CONTRAT,
        libelle="Synthèse de contrat",
        description=(
            "L'icône ✨ dans l'en-tête d'un contrat propose une synthèse au format "
            "du carnet d'entretien, à relire avant d'enregistrer."
        ),
        prompt_defaut=CONSIGNE_SYNTHESE,
        max_jetons_defaut=10_000,
    ),
    USAGE_DESCRIPTION: Usage(
        code=USAGE_DESCRIPTION,
        libelle="Rédaction d'une description",
        description=(
            "L'icône ✨ de la section Description — tickets, actualités, calendrier, "
            "sondages, idées, annonces, commentaires — retravaille le titre et le "
            "texte saisis. Réservé au conseil syndical et à l'administration."
        ),
        prompt_defaut=CONSIGNE_DESCRIPTION,
        max_jetons_defaut=4_000,
    ),
    #  Le seul usage AUTOMATIQUE (#1322, 25/09/2026) : aucun clic, il tourne à
    #  la relève des courriels. Coupé ou non réglé, le texte nettoyé sans IA
    #  entre dans le fil — `utils/reponse_courriel.mettre_en_forme`.
    USAGE_REPONSE_COURRIEL: Usage(
        code=USAGE_REPONSE_COURRIEL,
        libelle="Mise en forme des réponses par courriel",
        description=(
            "Automatique : quand le syndic répond par courriel à une affaire, sa "
            "réponse entre dans le fil débarrassée de la signature, des mentions "
            "légales et des lignes vides. Le texte reçu reste consultable sous "
            "« Message d'origine »."
        ),
        prompt_defaut=CONSIGNE_REPONSE_COURRIEL,
        max_jetons_defaut=2_000,
    ),
}


def usage(code: str) -> Usage:
    """L'usage demandé — `KeyError` si personne ne l'a déclaré ici."""
    return USAGES[code]


def decrire() -> list[dict]:
    """Ce que l'écran d'administration reçoit : les usages, leurs clés et
    leurs valeurs d'origine. Les VALEURS courantes, elles, viennent de
    `GET /config/admin` comme toute autre clé."""
    return [
        {
            "code": u.code,
            "libelle": u.libelle,
            "description": u.description,
            "prompt_defaut": u.prompt_defaut,
            "max_jetons_defaut": u.max_jetons_defaut,
            "cles": {champ: u.cle(champ) for champ in CHAMPS_USAGE},
        }
        for u in USAGES.values()
    ]


__all__ = [
    "CHAMPS_USAGE",
    "USAGES",
    "USAGE_DESCRIPTION",
    "USAGE_SYNTHESE_CONTRAT",
    "Usage",
    "decrire",
    "usage",
]
