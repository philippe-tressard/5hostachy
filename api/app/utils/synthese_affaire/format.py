"""Ce que l'assistant reçoit pour une synthèse, et la forme de ce qu'il rend (#1643).

| Partie | Qui l'écrit | Pourquoi |
|---|---|---|
| `CONSIGNE` | l'administration (prompt de l'usage, initialisé par la 0255) | le ton et le contenu se relisent et s'adaptent |
| le complément | le conseil, dans la boîte « Relancer » | ajouté au prompt, jamais à la place |
| `FORMAT_REPONSE` | **le code** — `lire_reponse` sait relire cette forme et aucune autre | ajouté à l'appel, jamais exposé à l'édition |
| le message | **le code** (`construire_message`) | les métriques sont CALCULÉES, données au modèle, jamais devinées |

🔴 Ce module n'importe ni `llm` ni la base : `llm_usages` le lit pour son prompt
d'origine, et `llm` lit `llm_usages` — le moindre import en retour formerait un
cycle.
"""

from __future__ import annotations

from typing import Optional

from app.utils.description_format import ReponseIllisible, lire_objet

#: Le code de l'usage — lu par `llm_usages`, qui ne peut pas importer la production.
USAGE_SYNTHESE_AFFAIRE = "synthese_affaire"

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu rédiges la synthèse d'une affaire close d'une copropriété, pour le carnet "
    "d'entretien. Elle sera relue et validée par le conseil syndical, puis lue par "
    "les copropriétaires.\n"
    "- Écris en français, au passé, sur un ton factuel et sobre, environ 350 mots "
    "au total.\n"
    "- Raconte ce qui s'est passé : le problème, les étapes, qui a agi, comment "
    "l'affaire s'est conclue. Si elle a été annulée, dis pourquoi et combien de "
    "temps elle a duré.\n"
    "- Les chiffres te sont DONNÉS (jours ouvrés, relances, semaines sans suite) : "
    "reprends-les tels quels, n'en calcule et n'en invente aucun. Si l'affaire est "
    "passée par l'assemblée générale, explique ce délai.\n"
    "- Si l'affaire a été rouverte, dis-le : la synthèse couvre toute sa vie.\n"
    "- Les difficultés : ce qui a ralenti ou compliqué l'affaire (attentes, "
    "relances restées sans réponse, informations manquantes). Rien d'autre.\n"
    "- L'amélioration : une suggestion concrète pour la prochaine affaire du même "
    "type, seulement si le fil en justifie une ; sinon laisse-la vide.\n"
    "- Ne cite aucune adresse, aucun numéro de téléphone ; désigne les personnes "
    "par leur rôle (le syndic, le conseil syndical, un résident, le prestataire)."
)

#: La forme de la réponse — tenue par le code, ajoutée APRÈS le prompt.
FORMAT_REPONSE = (
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour, à trois clés :\n"
    '{"synthese": "<le récit, en HTML simple : <p>, <ul>, <li>, <strong>>", '
    '"difficultes": "<HTML simple, ou chaîne vide>", '
    '"amelioration": "<HTML simple, ou chaîne vide si rien de pertinent>"}'
)

#: Au-delà, la réponse n'est plus une synthèse d'une page.
MAX_CARACTERES_CHAMP = 12_000
#: Le complément saisi au « Relancer » — une consigne, pas un second récit.
MAX_CARACTERES_COMPLEMENT = 1_000
CLES = ("synthese", "difficultes", "amelioration")


def consigne_complete(prompt: str, complement: Optional[str]) -> str:
    """Le prompt de l'usage, le complément du conseil s'il y en a un, puis le format."""
    blocs = [prompt.rstrip()]
    if complement and complement.strip():
        blocs.append(
            "Consigne complémentaire du conseil syndical pour cette synthèse : "
            + complement.strip()[:MAX_CARACTERES_COMPLEMENT]
        )
    blocs.append(FORMAT_REPONSE)
    return "\n\n".join(blocs)


def lire_reponse(texte: str) -> dict[str, str]:
    """PURE. Les trois champs relus dans ce que le modèle a rendu.

    `synthese` ne peut pas manquer ni être vide : une réponse sans récit n'est
    pas une synthèse, et la ranger en brouillon ferait relire du vide.
    `difficultes` et `amelioration` peuvent être vides — c'est même la consigne
    pour l'amélioration quand rien n'est pertinent.
    """
    charge = lire_objet(texte)
    sortie: dict[str, str] = {}
    for cle in CLES:
        brut = charge.get(cle)
        if brut is None:
            brut = ""
        if not isinstance(brut, str):
            raise ReponseIllisible(f"« {cle} » n'est pas un texte.")
        sortie[cle] = brut.strip()[:MAX_CARACTERES_CHAMP]
    if not sortie["synthese"]:
        raise ReponseIllisible("Réponse du modèle sans synthèse.")
    return sortie


__all__ = [
    "CLES",
    "CONSIGNE",
    "FORMAT_REPONSE",
    "MAX_CARACTERES_COMPLEMENT",
    "USAGE_SYNTHESE_AFFAIRE",
    "consigne_complete",
    "lire_reponse",
]
