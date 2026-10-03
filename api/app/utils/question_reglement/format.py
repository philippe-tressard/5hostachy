"""Ce que l'assistant reçoit pour une question au règlement, et la forme de sa réponse.

| Partie | Qui l'écrit | Pourquoi |
|---|---|---|
| `CONSIGNE` | l'administration (prompt de l'usage, initialisé par la 0256) | la méthode du juriste se relit et s'adapte |
| `FORMAT_REPONSE` | **le code** — `lire_reponse` sait relire cette forme et aucune autre | ajouté à l'appel, jamais exposé à l'édition |
| le message | **le code** (`construire_message`) | le texte du règlement EN TÊTE, la question à la fin |

## Pourquoi le règlement passe avant la question

Le règlement ne change pas d'une question à l'autre, la question si. Placé en
tête, après une consigne elle aussi stable, il forme un préfixe identique que le
fournisseur garde en cache — OpenAI le fait seul au-delà de 1 024 jetons — et
chaque question suivante en paie une fraction (`appel_ia.jetons_cache`).

🔴 Ce module n'importe ni `llm` ni la base : `llm_usages` le lit pour son prompt
d'origine, et `llm` lit `llm_usages` — le moindre import en retour formerait un
cycle.
"""

from __future__ import annotations

from app.utils.description_format import ReponseIllisible, lire_objet

#: Le code de l'usage — lu par `llm_usages`, qui ne peut pas importer la production.
USAGE_QUESTION_REGLEMENT = "question_reglement"

#: Les verdicts, et leur libellé — la SEULE liste : l'écran le reçoit avec la réponse.
VERDICTS: dict[str, str] = {
    "oui": "Oui",
    "non": "Non",
    "sous_conditions": "Oui, sous conditions",
    "non_prevu": "Le règlement ne le prévoit pas",
    "incertain": "Incertain",
}

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu es juriste, spécialiste du droit français de la copropriété (loi n° 65-557 du "
    "10 juillet 1965, décret n° 67-223 du 17 mars 1967, jurisprudence). Le conseil "
    "syndical te transmet la question d'un résident et le texte de travail du règlement "
    "de copropriété de la résidence : état descriptif de division, règlement et leurs "
    "modificatifs, transcrits des actes notariés.\n"
    "\n"
    "Ta méthode :\n"
    "- Lis TOUT le texte avant de répondre : une règle posée dans un chapitre peut être "
    "précisée, restreinte ou modifiée ailleurs (destination de l'immeuble, usage des "
    "parties privatives et communes, charges, annexes, modificatifs).\n"
    "- Les actes se lisent dans l'ordre chronologique : un modificatif l'emporte sur "
    "l'acte qu'il modifie, pour ce qu'il modifie seulement.\n"
    "- Fonde ta réponse sur le règlement. Quand la loi impose autre chose — une clause "
    "réputée non écrite (article 43 de la loi de 1965), un droit que le règlement ne peut "
    "pas retirer, une décision qui relève de l'assemblée générale et de sa majorité —, "
    "dis-le dans les réserves, en distinguant toujours ce que dit le règlement de ce que "
    "dit la loi.\n"
    "- Si le règlement ne traite pas la question, dis-le franchement (verdict "
    "« non_prevu ») et indique ce qui s'applique alors, sans inventer de clause.\n"
    "- Si un passage décisif est marqué [?] ou [illisible], ou si deux clauses se "
    "contredisent, dis-le et ne tranche pas au-delà de ce que le texte permet (verdict "
    "« incertain » si la réponse en dépend).\n"
    "\n"
    "Les extraits :\n"
    "- Chaque affirmation sur le règlement s'appuie sur au moins un extrait.\n"
    "- Un extrait est recopié MOT POUR MOT depuis le texte fourni : même orthographe, même "
    "ponctuation, sans reformuler ni corriger la transcription. Ne recopie pas les repères "
    "de page ⟦ … ⟧. Si tu dois couper, marque la coupure par […].\n"
    "- Donne la référence de chaque extrait : l'acte (le livre), le chapitre ou l'article, "
    "et la page indiquée par le repère ⟦ … ⟧ qui le précède dans le texte.\n"
    "- Préfère des extraits courts et décisifs, d'une à trois phrases ; cinq au plus, "
    "sauf nécessité.\n"
    "\n"
    "La réponse :\n"
    "- En français, claire pour un non-juriste : commence par la réponse à la question, "
    "puis explique.\n"
    "- Ne cite aucun nom de personne figurant dans les actes : désigne chacun par sa "
    "qualité (le vendeur, le notaire, le syndic).\n"
    "- C'est un avis indicatif : ne promets rien au nom du syndicat des copropriétaires."
)

#: La forme de la réponse — tenue par le code, ajoutée APRÈS le prompt.
FORMAT_REPONSE = (
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour, à quatre clés :\n"
    '{"verdict": "oui" | "non" | "sous_conditions" | "non_prevu" | "incertain", '
    '"reponse": "<la réponse argumentée, en HTML simple : <p>, <ul>, <li>, <strong>>", '
    '"extraits": [{"citation": "<mot pour mot>", '
    '"reference": "<acte, chapitre ou article, page>", '
    '"apport": "<ce que l\'extrait établit, en une phrase>"}], '
    '"reserves": "<HTML simple, ou chaîne vide>"}'
)

#: Une question, pas un dossier.
MAX_CARACTERES_QUESTION = 2_000
#: Au-delà, la réponse n'est plus un avis d'une page.
MAX_CARACTERES_CHAMP = 12_000
#: Un extrait se lit d'un coup d'œil ; au-delà, c'est une page recopiée.
MAX_CARACTERES_EXTRAIT = 2_000
MAX_EXTRAITS = 12


def consigne_complete(prompt: str) -> str:
    """Le prompt de l'usage, puis le format — que l'administration ne peut pas retirer."""
    return prompt.rstrip() + "\n\n" + FORMAT_REPONSE


def construire_message(texte: str, question: str) -> str:
    """PURE. Le règlement en tête, la question à la fin — voir l'en-tête du module."""
    return (
        "Texte de travail du règlement de copropriété (Markdown) :\n"
        "<<<REGLEMENT\n"
        f"{texte.strip()}\n"
        "REGLEMENT>>>\n\n"
        f"Question : {question.strip()[:MAX_CARACTERES_QUESTION]}"
    )


def _texte(charge: dict, cle: str, *, obligatoire: bool = False) -> str:
    brut = charge.get(cle)
    if brut is None:
        brut = ""
    if not isinstance(brut, str):
        raise ReponseIllisible(f"« {cle} » n'est pas un texte.")
    brut = brut.strip()[:MAX_CARACTERES_CHAMP]
    if obligatoire and not brut:
        raise ReponseIllisible(f"Réponse du modèle sans « {cle} ».")
    return brut


def lire_reponse(texte: str) -> dict:
    """PURE. Verdict, réponse, extraits bruts et réserves, relus dans la réponse.

    Un verdict inconnu n'est pas deviné : il devient « incertain », et la
    réponse argumentée reste — c'est elle qui fait foi, le verdict la résume.
    Les extraits sont rendus BRUTS (citation, référence, apport) : leur
    vérification contre le texte est l'affaire d'`extraits.verifier`.
    """
    charge = lire_objet(texte)
    verdict = charge.get("verdict")
    verdict = verdict.strip() if isinstance(verdict, str) else ""
    extraits = charge.get("extraits") or []
    if not isinstance(extraits, list):
        raise ReponseIllisible("« extraits » n'est pas une liste.")
    bruts = []
    for e in extraits[:MAX_EXTRAITS]:
        if not isinstance(e, dict) or not isinstance(e.get("citation"), str):
            continue
        citation = e["citation"].strip()[:MAX_CARACTERES_EXTRAIT]
        if not citation:
            continue
        bruts.append(
            {
                "citation": citation,
                "reference": str(e.get("reference") or "").strip()[:300],
                "apport": str(e.get("apport") or "").strip()[:600],
            }
        )
    return {
        "verdict": verdict if verdict in VERDICTS else "incertain",
        "reponse": _texte(charge, "reponse", obligatoire=True),
        "extraits": bruts,
        "reserves": _texte(charge, "reserves"),
    }


__all__ = [
    "CONSIGNE",
    "FORMAT_REPONSE",
    "MAX_CARACTERES_QUESTION",
    "USAGE_QUESTION_REGLEMENT",
    "VERDICTS",
    "consigne_complete",
    "construire_message",
    "lire_reponse",
]
