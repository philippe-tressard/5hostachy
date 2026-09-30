"""Chercher le TARIF du modèle d'un usage et l'enregistrer — l'usage `tarif_modele`
(30/09/2026).

## Demandé le 30/09/2026, en deux temps

> « créer un nouveau use case IA pour demander la tarification de l'IA
>   concernée. Ajouter l'icône IA à côté du modèle de tous les use case IA.
>   L'IA questionne et remplit ces 2 valeurs »
>
> « l'appel à l'IA de ce use case recherche le prix sur l'opérateur concerné du
>   modèle du use case concerné, remplit les prix et enregistre »

Les deux valeurs sont les prix de la section « Coût et plafond » d'un usage —
jetons envoyés, jetons produits, en centimes d'euro par million — que lit
`llm_journal` pour chiffrer la consommation (#1383).

## Qui fait quoi

| Étape | Qui | Pourquoi pas l'autre |
|---|---|---|
| lire la grille du fournisseur | le serveur (`tarif_sources`) | une adresse fixe, pas une recherche au hasard |
| trouver la ligne du modèle | l'assistant | « claude-haiku-4-5-20251001 » s'écrit « Claude Haiku 4.5 » dans la grille |
| convertir en euros | le serveur, au taux BCE du jour | le modèle inventerait un taux |
| enregistrer | le serveur | demandé : le geste finit le travail |

## 🔴 Le modèle cherché est celui ENREGISTRÉ pour l'usage

C'est son prix qu'on enregistre. Si l'écran montre un autre modèle, pas encore
enregistré, on refuse plutôt que de poser sur l'un le prix de l'autre.

## Ce qui part

Vers le fournisseur de l'assistant : son nom, l'identifiant du modèle et la
grille publique. **Aucune donnée d'un résident, d'un contrat ou d'une affaire.**
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlmodel import Session

from app.utils.description_format import ReponseIllisible, lire_objet

logger = logging.getLogger("hostachy.assistant")

USAGE_TARIF_MODELE = "tarif_modele"

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu lis la grille tarifaire publique d'un fournisseur de modèles d'IA et tu "
    "y trouves le prix d'UN modèle, désigné par son identifiant d'API.\n"
    "- L'identifiant peut porter une date ou un suffixe que la grille n'écrit "
    "pas (« claude-haiku-4-5-20251001 » est « Claude Haiku 4.5 ») : retiens la "
    "ligne du même modèle, jamais celle d'un modèle voisin.\n"
    "- Retiens le tarif standard d'un appel par API : ni traitement par lots, "
    "ni cache, ni priorité, ni contexte long s'il existe un palier ordinaire.\n"
    "- Donne le prix des jetons envoyés (entrée) et des jetons produits "
    "(sortie), par million de jetons, dans la devise de la grille.\n"
    "- Sur Azure, l'identifiant est un nom de déploiement : retiens le modèle "
    "qu'il désigne si son nom le laisse reconnaître.\n"
    "- Si la grille ne porte pas ce modèle, ne devine pas : réponds null."
)

#: La forme de la réponse — tenue par le code, ajoutée APRÈS le prompt.
FORMAT_REPONSE = (
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour :\n"
    '{"ligne": "<le nom du modèle tel que la grille l\'écrit, ou null>", '
    '"devise": "USD" ou "EUR", '
    '"prix_entree": <nombre ou null>, "prix_sortie": <nombre ou null>}\n'
    "Les prix sont par million de jetons, en nombre décimal avec un point."
)

#: Au-delà, ce n'est plus un tarif mais une erreur d'unité (un prix par millier
#: pris pour un prix par million) : le modèle le plus cher reste très en deçà.
MAX_PAR_MILLION = 1_000
MAX_CARACTERES_LIGNE = 120


@dataclass(frozen=True)
class Lecture:
    """Ce que l'assistant a lu dans la grille, dans la devise de la grille."""

    ligne: str
    devise: str
    prix_entree: Optional[float]
    prix_sortie: Optional[float]


@dataclass(frozen=True)
class Tarif:
    """Ce qui a été ENREGISTRÉ — en centimes d'euro par million, l'unité des
    champs (`llm_usages.CHAMPS_USAGE`) ; `None` pour un prix que la grille ne
    donne pas, et qui n'a donc pas été touché."""

    prix_entree: Optional[int]
    prix_sortie: Optional[int]
    remarque: str


def construire_message(fournisseur: str, modele: str, grille: str) -> str:
    return (
        f"Fournisseur : {fournisseur}\nIdentifiant du modèle : {modele}\n\n"
        f"Grille tarifaire publiée par le fournisseur :\n\n{grille}"
    )


def _prix(valeur: object, champ: str) -> Optional[float]:
    if valeur is None:
        return None
    #  `True` est un `int` pour Python : un booléen n'est pas un prix.
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise ReponseIllisible(f"« {champ} » n'est pas un nombre.")
    if not 0 <= valeur <= MAX_PAR_MILLION:
        raise ReponseIllisible(f"« {champ} » hors bornes : {valeur}.")
    return float(valeur)


def lire_tarif(texte: str) -> Lecture:
    """PURE. La ligne retenue par l'assistant, relue et bornée.

    Deux `null` ne sont PAS illisibles : l'assistant dit que la grille ne porte
    pas ce modèle, et c'est à l'appelant de le dire.
    """
    charge = lire_objet(texte)
    devise = str(charge.get("devise") or "USD").strip().upper()
    if devise not in ("USD", "EUR"):
        raise ReponseIllisible(f"Devise inattendue : « {devise} ».")
    ligne = charge.get("ligne")
    return Lecture(
        ligne=(ligne.strip() if isinstance(ligne, str) else "")[:MAX_CARACTERES_LIGNE],
        devise=devise,
        prix_entree=_prix(charge.get("prix_entree"), "prix_entree"),
        prix_sortie=_prix(charge.get("prix_sortie"), "prix_sortie"),
    )


def _nombre(x: float | Decimal, decimales: int = 2) -> str:
    return f"{x:.{decimales}f}".replace(".", ",")


def remarque(lecture: Lecture, url: str, taux_usd: Optional[Decimal], date_taux: str) -> str:
    """PURE. D'où vient le chiffre — écrite par le CODE, jamais par le modèle :
    c'est la phrase qui permet de vérifier ce qui a été enregistré."""
    symbole = "$" if lecture.devise == "USD" else "€"
    prix = " et ".join(
        f"{_nombre(p)} {symbole}"
        for p in (lecture.prix_entree, lecture.prix_sortie)
        if p is not None
    )
    source = url.removeprefix("https://").removesuffix(".md")
    texte = f"Grille {source}, ligne « {lecture.ligne or '?'} » : {prix} par million"
    if taux_usd is not None:
        jour = "/".join(reversed(date_taux.split("-")))
        texte += f", au taux BCE du {jour} (1 € = {_nombre(taux_usd, 4)} $)"
    return texte + "."


async def chercher_et_enregistrer(session: Session, usage: str, modele_affiche: str) -> Tarif:
    """Lit la grille du fournisseur, y fait trouver le modèle de `usage`, convertit
    au taux BCE et ENREGISTRE les deux prix. Lève `ErreurLLM` — jamais autre chose.
    """
    #  Import différé : `llm` lit `llm_usages`, qui lit la CONSIGNE ici — le
    #  geste de `reponse_courriel`.
    from app.models.core import ConfigSite
    from app.utils import tarif_sources
    from app.utils.llm import ErreurLLM, config_llm, demander
    from app.utils.llm_usages import USAGES

    if usage not in USAGES:
        raise ErreurLLM(f"Usage inconnu : « {usage} ».")
    cible = config_llm(session, usage)
    modele = cible.modele
    if not modele:
        raise ErreurLLM(
            "Enregistrez d'abord un modèle pour cet usage : c'est son tarif qui est cherché."
        )
    if (modele_affiche or "").strip() != modele:
        raise ErreurLLM(
            "Le modèle affiché n'est pas celui qui est enregistré : cliquez sur "
            "« Enregistrer », puis relancez ✨."
        )

    url = cible.fournisseur.page_tarifs
    try:
        grille = await tarif_sources.lire_grille(url)
    except tarif_sources.SourceIndisponible as exc:
        raise ErreurLLM(f"Grille de {cible.fournisseur.libelle} indisponible : {exc}") from exc

    cfg = config_llm(session, USAGE_TARIF_MODELE)
    reponse = await demander(
        session,
        usage=USAGE_TARIF_MODELE,
        consigne=cfg.prompt.rstrip() + "\n\n" + FORMAT_REPONSE,
        message=construire_message(cible.fournisseur.libelle, modele, grille),
    )
    try:
        lecture = lire_tarif(reponse.texte)
    except ReponseIllisible as exc:
        logger.warning("Assistant tarif : %s — %s", exc, reponse.texte[:300])
        raise ErreurLLM("Le modèle n'a pas répondu dans le format attendu — réessayez.") from exc
    if lecture.prix_entree is None and lecture.prix_sortie is None:
        raise ErreurLLM(
            f"La grille de {cible.fournisseur.libelle} ne donne pas le tarif de « {modele} » : "
            "saisissez-le à la main."
        )

    taux = None
    if lecture.devise == "USD":
        try:
            taux = await tarif_sources.lire_taux()
        except tarif_sources.SourceIndisponible as exc:
            raise ErreurLLM(f"Conversion en euros impossible : {exc}") from exc
    centimes: dict[str, Optional[int]] = {}
    for champ, prix in (("prix_entree", lecture.prix_entree), ("prix_sortie", lecture.prix_sortie)):
        centimes[champ] = (
            None if prix is None else tarif_sources.en_centimes_euro(prix, lecture.devise, taux)
        )

    #  🔴 L'enregistrement : seulement les prix TROUVÉS. Un prix absent de la
    #  grille laisse celui que l'administrateur avait saisi.
    u = USAGES[usage]
    for champ, valeur in centimes.items():
        if valeur is None:
            continue
        cle = u.cle(champ)
        ligne = session.get(ConfigSite, cle) or ConfigSite(cle=cle, valeur="")
        ligne.valeur = str(valeur)
        session.add(ligne)
    session.commit()

    return Tarif(
        prix_entree=centimes["prix_entree"],
        prix_sortie=centimes["prix_sortie"],
        remarque=remarque(
            lecture, url, taux.usd_par_eur if taux else None, taux.date if taux else ""
        ),
    )


__all__ = [
    "CONSIGNE",
    "FORMAT_REPONSE",
    "Lecture",
    "Tarif",
    "USAGE_TARIF_MODELE",
    "chercher_et_enregistrer",
    "construire_message",
    "lire_tarif",
    "remarque",
]
