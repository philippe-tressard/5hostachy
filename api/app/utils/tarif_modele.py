"""Demander à l'assistant le TARIF d'un modèle — l'usage `tarif_modele` (30/09/2026).

## Demandé le 30/09/2026

> « créer un nouveau use case IA pour demander la tarification de l'IA
>   concernée. Ajouter l'icône IA à côté du modèle de tous les use case IA.
>   L'IA questionne et remplit ces 2 valeurs »

Les deux valeurs sont les prix de la section « Coût et plafond » d'un usage :
jetons envoyés, jetons produits, en euros par million — ce que lit
`llm_journal` pour chiffrer la consommation (#1383).

## 🔴 Une PROPOSITION, jamais un enregistrement

Le ✨ remplit les deux champs du bloc ; c'est « Enregistrer » qui écrit. Un
modèle connaît les grilles de son apprentissage, pas celle du jour : un tarif
a pu baisser depuis, et les grilles sont publiées en dollars. La `remarque`
rendue le dit (prix d'origine, devise, taux, date des connaissances), et
l'écran la montre sous les champs.

## Ce qui part

Le nom du fournisseur et l'identifiant du modèle. **Rien d'autre** : aucune
donnée d'un résident, d'un contrat ou d'une affaire.

## Les deux textes, comme `description_format`

| Texte | Qui le tient |
|---|---|
| `CONSIGNE` | l'administrateur — semée en base par la 0240, modifiable |
| `FORMAT_REPONSE` | le code — ajouté après, c'est ce que `lire_tarif` relit |
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session

from app.utils.description_format import ReponseIllisible, lire_objet

logger = logging.getLogger("hostachy.assistant")

USAGE_TARIF_MODELE = "tarif_modele"

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu renseignes le tarif public d'un modèle d'intelligence artificielle, tel "
    "que son fournisseur le publie pour un appel par API : le tarif standard, "
    "hors traitement par lots, hors cache et hors remise.\n"
    "On te donne le fournisseur et l'identifiant d'API du modèle. Donne :\n"
    "- le prix des jetons envoyés (l'entrée, la question) ;\n"
    "- le prix des jetons produits (la sortie, raisonnement compris) ;\n"
    "en euros par million de jetons. Si le fournisseur publie en dollars, "
    "convertis au dernier taux de change que tu connais.\n"
    "Sur Azure, l'identifiant est un nom de déploiement : raisonne sur le modèle "
    "qu'il désigne si son nom le laisse reconnaître.\n"
    "Si tu ne connais pas ce tarif avec une confiance raisonnable, ne l'invente "
    "pas : réponds null.\n"
    "Dans la remarque, une phrase : le prix d'origine et sa devise, le taux "
    "appliqué, et la date de tes connaissances — le tarif a pu changer depuis."
)

#: La forme de la réponse — tenue par le code, ajoutée APRÈS le prompt.
FORMAT_REPONSE = (
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour :\n"
    '{"prix_entree": <nombre ou null>, "prix_sortie": <nombre ou null>, '
    '"remarque": "<une phrase>"}\n'
    "Les prix sont en euros par million de jetons, en nombre décimal avec un point."
)

#: Au-delà, ce n'est plus un tarif mais une erreur d'unité (un prix par millier,
#: des centimes pris pour des euros) : le modèle le plus cher du marché reste
#: très en deçà.
MAX_EUROS_PAR_MILLION = 1_000
MAX_CARACTERES_REMARQUE = 400
MAX_CARACTERES_MODELE = 200


@dataclass(frozen=True)
class Tarif:
    """Ce que l'écran pose dans les deux champs — en CENTIMES, l'unité stockée
    (`llm_usages.CHAMPS_USAGE`) ; `None` quand le modèle ne sait pas."""

    prix_entree: Optional[int]
    prix_sortie: Optional[int]
    remarque: str


def construire_message(fournisseur: str, modele: str) -> str:
    return f"Fournisseur : {fournisseur}\nIdentifiant du modèle : {modele}"


def _centimes(valeur: object, champ: str) -> Optional[int]:
    """PURE. Un prix en euros par million, rendu en centimes entiers — un
    montant ne se garde jamais en flottant. `None` reste `None`."""
    if valeur is None:
        return None
    #  `True` est un `int` pour Python : un booléen n'est pas un prix.
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise ReponseIllisible(f"« {champ} » n'est pas un nombre.")
    if not 0 <= valeur <= MAX_EUROS_PAR_MILLION:
        raise ReponseIllisible(f"« {champ} » hors bornes : {valeur}.")
    return round(valeur * 100)


def lire_tarif(texte: str) -> Tarif:
    """PURE. Le tarif relu dans la réponse du modèle.

    Lève `ReponseIllisible` sur un JSON absent, un prix qui n'est pas un nombre
    ou hors bornes. Deux `null` ne sont PAS illisibles : le modèle a dit qu'il
    ne savait pas, et c'est à l'appelant de le dire.
    """
    charge = lire_objet(texte)
    remarque = charge.get("remarque")
    return Tarif(
        prix_entree=_centimes(charge.get("prix_entree"), "prix_entree"),
        prix_sortie=_centimes(charge.get("prix_sortie"), "prix_sortie"),
        remarque=(remarque.strip() if isinstance(remarque, str) else "")[:MAX_CARACTERES_REMARQUE],
    )


async def proposer_tarif(session: Session, modele: str) -> Tarif:
    """Demande au modèle de l'usage le tarif de `modele`. N'enregistre RIEN.

    `modele` est celui qu'affiche le bloc — peut-être pas encore enregistré :
    c'est celui dont l'administrateur veut le prix. Le fournisseur, lui, est
    celui de la configuration enregistrée.
    """
    #  Import différé : `llm` lit `llm_usages`, qui lit la CONSIGNE ici — le
    #  geste de `reponse_courriel`.
    from app.utils.llm import ErreurLLM, config_llm, demander

    modele = (modele or "").strip()[:MAX_CARACTERES_MODELE]
    if not modele:
        raise ErreurLLM("Choisissez d'abord un modèle : c'est son tarif qui est demandé.")
    cfg = config_llm(session, USAGE_TARIF_MODELE)
    reponse = await demander(
        session,
        usage=USAGE_TARIF_MODELE,
        consigne=cfg.prompt.rstrip() + "\n\n" + FORMAT_REPONSE,
        message=construire_message(cfg.fournisseur.libelle, modele),
    )
    try:
        tarif = lire_tarif(reponse.texte)
    except ReponseIllisible as exc:
        logger.warning("Assistant tarif : %s — %s", exc, reponse.texte[:300])
        raise ErreurLLM("Le modèle n'a pas répondu dans le format attendu — réessayez.") from exc
    if tarif.prix_entree is None and tarif.prix_sortie is None:
        raise ErreurLLM(
            f"L'assistant ne connaît pas le tarif de « {modele} » : "
            "reportez celui de la grille du fournisseur."
        )
    return tarif


__all__ = [
    "CONSIGNE",
    "FORMAT_REPONSE",
    "Tarif",
    "USAGE_TARIF_MODELE",
    "construire_message",
    "lire_tarif",
    "proposer_tarif",
]
