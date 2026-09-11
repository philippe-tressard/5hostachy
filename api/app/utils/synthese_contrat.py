"""La SYNTHÈSE d'un contrat, proposée à partir de ses documents.

Le conseil syndical rédigeait cette synthèse à la main, en collant dans le champ
« Notes » le résultat obtenu ailleurs auprès d'un modèle de langage. Le geste
existait donc déjà — il vivait simplement hors du produit, sans trace de ce qui
avait été lu ni de quand.

## Trois décisions, et elles ne se rediscutent pas au cas par cas

**1. Le modèle rend des DONNÉES, le serveur rend le HTML.** La réponse attendue
est un objet dont les clés sont celles de `SQUELETTE` ; `rendre_html()` compose
le balisage à partir d'elles, en échappant chaque valeur. Deux conséquences, et
la seconde est la vraie raison :

- le squelette est tenu par **construction** — une rubrique absente le reste, une
  rubrique inventée est ignorée, l'ordre est celui du squelette et de rien
  d'autre ;
- **aucun balisage écrit par le modèle n'atteint la page.** Le champ `notes` est
  rendu par `{@html safeHtml(...)}` côté écran : laisser le modèle produire du
  HTML reviendrait à faire transiter du balisage d'origine externe jusqu'à un
  `{@html}`. DOMPurify le nettoierait, et ce serait quand même la mauvaise
  frontière — on ne désinfecte pas ce qu'on peut ne jamais laisser entrer.

**2. Rien n'est enregistré ici.** L'endpoint RENVOIE une proposition ; c'est
l'écran qui la place dans le formulaire, et c'est le conseil syndical qui
enregistre. Écrire directement dans `notes` écraserait sans filet une synthèse
rédigée à la main — et l'archivage, ici, n'existe pas pour la rattraper.

**3. Ce qui n'est pas dans le document ne s'invente pas.** La consigne l'impose
rubrique par rubrique, et `NON_PRECISE` est la réponse attendue. Sur un contrat,
une valeur plausible et fausse coûte plus cher qu'une case vide : c'est le
raisonnement que ce dépôt applique déjà à `_appliquer_perimetre`, qui refuse de
désigner « le premier » bâtiment quand plusieurs sont visés.

## Ce qui vit AILLEURS, exprès

La clé d'API et le modèle employé sont dans `settings` (donc dans `.env`, non
versionné). Ce module ne les lit qu'au moment de l'appel : importer
`synthese_contrat` sur une installation sans clé ne lève rien, et
`synthese_active()` répond simplement « non ».

⚠️ **L'appel sort de la résidence.** Le PDF du contrat est transmis à un
prestataire tiers. C'est une décision du conseil syndical, pas un détail
technique : elle se prend en connaissance de cause, et le fait que la
fonctionnalité soit *désactivée tant qu'aucune clé n'est posée* en est la forme
technique — personne ne l'active par accident.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from html import escape
from typing import Any

import httpx
from sqlmodel import Session, select

from app.config import get_settings
from app.models.core import ContratEntretien, Document

#: Ce que le modèle doit écrire quand le contrat ne dit rien. Une seule écriture :
#: la consigne l'emploie, le rendu la reconnaît pour griser la ligne.
NON_PRECISE = "Non précisé au contrat"

#: Seuls les PDF sont transmis. Les autres formats ne sont pas *refusés par
#: principe* — ils ne sont simplement pas lus de la même façon par l'API, et un
#: format accepté à moitié est pire qu'un format refusé clairement.
MIME_ACCEPTE = "application/pdf"

#: Plafonds de charge utile. Ils protègent deux choses différentes : le nombre de
#: documents évite d'envoyer tout l'historique d'un prestataire, la taille évite
#: le rejet côté API — un scan mal compressé atteint 20 Mo plus vite qu'on ne
#: croit, et l'erreur renvoyée alors ne dit pas ce qu'il faut faire.
MAX_DOCUMENTS = 3
MAX_OCTETS = 20 * 1024 * 1024


class SyntheseIndisponible(Exception):
    """Ce qui empêche la génération, dit en français à qui a cliqué.

    Toujours une phrase qui nomme le geste suivant. « Erreur 400 » n'en est pas
    une : c'est ce que l'écran afficherait sinon, et le conseil syndical ne peut
    rien en faire.
    """


@dataclass(frozen=True)
class Rubrique:
    """Une ligne du squelette : sa clé, son titre affiché, ce qu'on en attend."""

    cle: str
    titre: str
    consigne: str
    #: Rendue en liste à puces plutôt qu'en paragraphe. Le modèle renvoie alors
    #: un tableau de chaînes — et un texte simple reste accepté (voir `_lignes`).
    liste: bool = False


#: 🔴 LE SQUELETTE — source unique, et le seul endroit à modifier pour changer la
#: forme d'une synthèse. Il sert À LA FOIS de consigne au modèle, de schéma de
#: lecture de sa réponse et de plan du HTML rendu. Le recopier ailleurs (dans le
#: prompt, dans un gabarit d'affichage) rouvrirait la divergence que ce dépôt a
#: déjà payée quatre fois — c'est `standards/02` §2.
SQUELETTE: tuple[Rubrique, ...] = (
    Rubrique(
        "objet",
        "Objet du contrat",
        "Ce que le contrat couvre, en deux ou trois phrases.",
    ),
    Rubrique(
        "prestataire",
        "Prestataire et interlocuteurs",
        "Raison sociale, coordonnées et interlocuteurs désignés, tels qu'écrits au contrat.",
    ),
    Rubrique(
        "perimetre",
        "Périmètre et équipements couverts",
        "Bâtiments, locaux et équipements nommément visés.",
    ),
    Rubrique(
        "inclus",
        "Prestations incluses",
        "Ce que le forfait comprend. Une prestation par entrée.",
        liste=True,
    ),
    Rubrique(
        "exclus",
        "Prestations exclues ou hors forfait",
        "Ce qui est facturé en sus ou explicitement exclu. Une entrée par exclusion.",
        liste=True,
    ),
    Rubrique(
        "frequence",
        "Fréquence et planning des visites",
        "Nombre de visites, périodicité, délais d'intervention sur appel.",
    ),
    Rubrique(
        "duree",
        "Durée, prise d'effet et reconduction",
        "Date d'effet, durée initiale, tacite reconduction et sa durée.",
    ),
    Rubrique(
        "resiliation",
        "Résiliation",
        "Préavis, forme exigée, dates auxquelles la résiliation peut intervenir.",
    ),
    Rubrique(
        "finances",
        "Conditions financières",
        "Montant, périodicité de facturation, clause de révision des prix, pénalités.",
    ),
    Rubrique(
        "obligations",
        "Obligations de la copropriété",
        "Ce que le contrat met à la charge du syndicat : accès, fluides, travaux préalables.",
        liste=True,
    ),
    Rubrique(
        "vigilance",
        "Points de vigilance pour le conseil syndical",
        "Ce qui mérite un examen : clause déséquilibrée, échéance proche, reconduction "
        "difficile à dénoncer, prestation absente. S'appuyer UNIQUEMENT sur le document.",
        liste=True,
    ),
)


def synthese_active() -> bool:
    """La génération est-elle configurée sur cette installation ?

    Une clé absente n'est pas une panne : c'est le cas NOMINAL d'une copropriété
    qui n'a pas souscrit. L'écran n'affiche alors pas le bouton — plutôt que de
    le proposer et de répondre 503 à qui le presse.
    """
    return bool(get_settings().openai_api_key)


# ── Les documents transmis ───────────────────────────────────────────────────

def documents_transmissibles(session: Session, contrat_id: int) -> list[Document]:
    """Les PDF rattachés à ce contrat, du plus récent au plus ancien.

    ⚠️ Le tri n'est pas décoratif : au-delà de `MAX_DOCUMENTS`, ce sont les plus
    récents qui partent. Un contrat porte souvent son avenant à côté de sa
    version d'origine, et c'est l'avenant qui fait foi.
    """
    docs = session.exec(
        select(Document)
        .where(Document.contrat_id == contrat_id)
        .order_by(Document.publie_le.desc())
    ).all()
    return [d for d in docs if (d.mime_type or "").lower() == MIME_ACCEPTE]


def _charger(doc: Document) -> bytes:
    chemin = doc.fichier_chemin
    if not chemin or not os.path.exists(chemin):
        raise SyntheseIndisponible(
            f"Le fichier « {doc.fichier_nom} » est introuvable sur le serveur. "
            "Le téléverser à nouveau depuis la fiche du contrat."
        )
    with open(chemin, "rb") as f:
        return f.read()


# ── La requête ───────────────────────────────────────────────────────────────

def consignes() -> str:
    """Le texte envoyé avec les PDF — DÉRIVÉ du squelette, jamais retapé."""
    lignes = [
        "Tu analyses le ou les contrats joints pour le conseil syndical d'une copropriété.",
        "",
        "Réponds UNIQUEMENT par un objet JSON, sans texte autour et sans bloc de code.",
        "Il porte exactement les clés suivantes :",
        "",
    ]
    for r in SQUELETTE:
        forme = "tableau de chaînes" if r.liste else "chaîne"
        lignes.append(f'- "{r.cle}" ({forme}) — {r.titre} : {r.consigne}')
    lignes += [
        "",
        "Règles impératives :",
        f'- Ce que le document ne dit pas s\'écrit exactement "{NON_PRECISE}". '
        "N'invente aucune date, aucun montant, aucun délai.",
        "- N'écris aucune balise HTML ni Markdown : du texte brut dans chaque valeur.",
        "- Reprends les termes du contrat plutôt que de les reformuler quand ils sont précis "
        "(montants, préavis, articles).",
        "- Rédige en français, au présent, sans formule d'introduction ni de conclusion.",
    ]
    return "\n".join(lignes)


def construire_requete(documents: list[tuple[str, bytes]], modele: str) -> dict[str, Any]:
    """La charge utile envoyée à l'API, composée à part pour être éprouvable.

    Séparée de l'envoi exprès : c'est la seule partie qui porte des décisions
    (quels documents, dans quel ordre, avec quelle consigne), et c'est donc la
    seule qui mérite un test. Le tuyau, lui, se branche — même coupure que
    `composer_html` / `html_to_pdf` pour le manuel, ou `courriel_ingestion` /
    `courriel_boite`.
    """
    contenu: list[dict[str, Any]] = []
    for nom, octets in documents:
        b64 = base64.b64encode(octets).decode("ascii")
        contenu.append(
            {
                "type": "input_file",
                "filename": nom,
                "file_data": f"data:{MIME_ACCEPTE};base64,{b64}",
            }
        )
    contenu.append({"type": "input_text", "text": consignes()})
    return {"model": modele, "input": [{"role": "user", "content": contenu}]}


# ── La réponse ───────────────────────────────────────────────────────────────

def _texte_de_la_reponse(donnees: dict[str, Any]) -> str:
    """Le texte rendu par le modèle, quelle que soit la forme de l'enveloppe.

    ⚠️ Deux chemins, et le second n'est pas une précaution de style : `output_text`
    est une commodité que l'API expose aujourd'hui, la structure `output[].content[]`
    est ce qu'elle garantit. Ne lire que la commodité ferait dépendre la
    fonctionnalité d'un champ d'agrément.
    """
    direct = donnees.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    morceaux: list[str] = []
    for bloc in donnees.get("output") or []:
        for part in (bloc or {}).get("content") or []:
            texte = (part or {}).get("text")
            if isinstance(texte, str):
                morceaux.append(texte)
    if not morceaux:
        raise SyntheseIndisponible(
            "Le service a répondu sans contenu exploitable. Réessayer dans un instant."
        )
    return "\n".join(morceaux)


def extraire_objet(texte: str) -> dict[str, Any]:
    """L'objet JSON contenu dans la réponse, même entouré de bavardage.

    ⚠️ La consigne demande du JSON nu et ce n'est PAS une garantie : un modèle
    encadre volontiers sa réponse d'un bloc ``` ou d'une phrase. Échouer là-dessus
    donnerait une erreur incompréhensible pour un défaut cosmétique — on retire
    donc la clôture, puis on retient le plus grand objet accolé.
    """
    nu = texte.strip()
    nu = re.sub(r"^```(?:json)?\s*", "", nu)
    nu = re.sub(r"\s*```$", "", nu).strip()
    try:
        objet = json.loads(nu)
    except json.JSONDecodeError:
        debut, fin = nu.find("{"), nu.rfind("}")
        if debut == -1 or fin <= debut:
            raise SyntheseIndisponible(
                "Le service n'a pas renvoyé une synthèse lisible. Réessayer dans un instant."
            ) from None
        try:
            objet = json.loads(nu[debut : fin + 1])
        except json.JSONDecodeError:
            raise SyntheseIndisponible(
                "Le service n'a pas renvoyé une synthèse lisible. Réessayer dans un instant."
            ) from None
    if not isinstance(objet, dict):
        raise SyntheseIndisponible(
            "Le service n'a pas renvoyé une synthèse lisible. Réessayer dans un instant."
        )
    return objet


def _lignes(valeur: Any) -> list[str]:
    """Les entrées d'une rubrique en liste, quelle que soit la forme reçue.

    Une chaîne est acceptée là où un tableau est demandé : le modèle s'y trompe
    régulièrement, et refuser la réponse entière pour cela ferait perdre les dix
    autres rubriques. On coupe alors sur les retours à la ligne et les puces.
    """
    if isinstance(valeur, list):
        return [str(v).strip() for v in valeur if str(v).strip()]
    if isinstance(valeur, str):
        brut = [re.sub(r"^[-•*]\s*", "", l).strip() for l in valeur.splitlines()]
        return [l for l in brut if l]
    return []


def rendre_html(objet: dict[str, Any]) -> str:
    """Le HTML de la synthèse — composé ICI, à partir du squelette.

    Chaque valeur passe par `escape()` : ce qui vient du modèle est du TEXTE, et
    il le reste jusqu'au bout. Les balises sont celles que `sanitize.ts` admet
    (`h3`, `p`, `ul`, `li`, `em`) — un rendu qui en emploierait d'autres serait
    nettoyé à l'affichage sans que rien ne le signale.
    """
    morceaux: list[str] = []
    for r in SQUELETTE:
        valeur = objet.get(r.cle)
        morceaux.append(f"<h3>{escape(r.titre)}</h3>")
        if r.liste:
            entrees = _lignes(valeur)
            if not entrees or (len(entrees) == 1 and entrees[0] == NON_PRECISE):
                morceaux.append(f"<p><em>{escape(NON_PRECISE)}</em></p>")
            else:
                puces = "".join(f"<li>{escape(e)}</li>" for e in entrees)
                morceaux.append(f"<ul>{puces}</ul>")
        else:
            texte = str(valeur).strip() if valeur is not None else ""
            if not texte or texte == NON_PRECISE:
                morceaux.append(f"<p><em>{escape(NON_PRECISE)}</em></p>")
            else:
                paragraphes = [p.strip() for p in texte.split("\n") if p.strip()]
                morceaux += [f"<p>{escape(p)}</p>" for p in paragraphes]
    return "".join(morceaux)


# ── L'appel ──────────────────────────────────────────────────────────────────

def _appeler(charge: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    try:
        reponse = httpx.post(
            f"{s.openai_base_url.rstrip('/')}/responses",
            headers={
                "Authorization": f"Bearer {s.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=charge,
            timeout=s.openai_timeout_s,
        )
    except httpx.TimeoutException:
        raise SyntheseIndisponible(
            "Le service n'a pas répondu dans le temps imparti. Le contrat est peut-être "
            "volumineux : réessayer, ou ne laisser que le document principal."
        ) from None
    except httpx.HTTPError:
        raise SyntheseIndisponible(
            "Le service est injoignable depuis le serveur. Vérifier l'accès réseau sortant."
        ) from None

    if reponse.status_code == 401:
        raise SyntheseIndisponible(
            "La clé d'API est refusée. Vérifier OPENAI_API_KEY dans le fichier .env du serveur."
        )
    if reponse.status_code == 429:
        raise SyntheseIndisponible(
            "Le quota du compte est atteint, ou trop d'appels en peu de temps. Réessayer plus tard."
        )
    if reponse.status_code >= 400:
        #  🔴 Le message du service est REPRIS TEL QUEL, et c'est délibéré : c'est
        #  lui qui nomme un modèle inconnu, un format refusé ou un document trop
        #  gros. Le remplacer par « Erreur du service » rendrait indiagnosticable
        #  la seule chose qu'on ne peut pas deviner d'ici.
        detail = ""
        try:
            detail = ((reponse.json() or {}).get("error") or {}).get("message") or ""
        except ValueError:
            detail = ""
        raise SyntheseIndisponible(
            f"Le service a refusé la demande ({reponse.status_code}). {detail}".strip()
        )
    try:
        return reponse.json()
    except ValueError:
        raise SyntheseIndisponible("Le service a renvoyé une réponse illisible.") from None


def generer_synthese(session: Session, contrat: ContratEntretien) -> str:
    """La synthèse proposée pour ce contrat, en HTML prêt pour le champ Notes.

    N'ÉCRIT RIEN : voir la décision 2 en tête de module.
    """
    s = get_settings()
    if not s.openai_api_key:
        raise SyntheseIndisponible(
            "La génération n'est pas configurée sur ce serveur (OPENAI_API_KEY absente)."
        )

    docs = documents_transmissibles(session, contrat.id)
    if not docs:
        raise SyntheseIndisponible(
            "Ce contrat n'a aucun document PDF rattaché. Ajouter le contrat signé "
            "dans la rubrique Documents, puis relancer."
        )

    retenus = docs[:MAX_DOCUMENTS]
    charges: list[tuple[str, bytes]] = []
    total = 0
    for d in retenus:
        octets = _charger(d)
        total += len(octets)
        if total > MAX_OCTETS:
            raise SyntheseIndisponible(
                f"Les documents dépassent {MAX_OCTETS // (1024 * 1024)} Mo au total. "
                "Ne conserver que le contrat lui-même, ou le recompresser."
            )
        charges.append((d.fichier_nom, octets))

    donnees = _appeler(construire_requete(charges, s.openai_modele))
    return rendre_html(extraire_objet(_texte_de_la_reponse(donnees)))
