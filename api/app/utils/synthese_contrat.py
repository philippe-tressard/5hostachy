"""La SYNTHÈSE d'un contrat : aller la chercher auprès du service.

Le conseil syndical rédigeait cette synthèse à la main, en collant dans le champ
« Notes » le résultat obtenu ailleurs auprès d'un modèle de langage. Le geste
existait donc déjà — il vivait simplement hors du produit, sans trace de ce qui
avait été lu ni de quand.

📖 **Ce que la synthèse EST — squelette, consigne, lecture de la réponse et
rendu HTML — vit dans `synthese_contrat_squelette.py`**, avec les deux décisions
qui le gouvernent (le modèle rend des données, ce n'est pas lui qui écrit le
HTML ; ce qui n'est pas au contrat ne s'invente pas). Elles ne sont PAS recopiées
ici : deux écritures d'une même règle divergent au premier lot, et ce dépôt l'a
déjà payé quatre fois. Ce module-ci ne porte que le trajet.

## La décision qui vit ICI

🔴 **Rien n'est enregistré.** `generer_synthese` RENVOIE une proposition ; c'est
l'écran qui la place dans le formulaire, et c'est le conseil syndical qui
enregistre. Écrire directement dans `notes` écraserait sans filet une synthèse
rédigée à la main — et l'archivage, sur ce champ, n'existe pas pour la
rattraper. `test_synthese_contrat.py` refuse qu'un point d'écriture apparaisse
dans l'un ou l'autre des deux modules.

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
import os
from typing import Any

import httpx
from sqlmodel import Session, select

from app.config import get_settings
from app.models.core import ContratEntretien, Document

#  🔴 Réexportés : `synthese_contrat` reste LE point d'entrée de la
#  fonctionnalité. Le routeur et les tests n'ont pas à savoir que le squelette
#  vit dans un fichier voisin — c'est une décision de rangement, pas d'API.
from app.utils.synthese_contrat_squelette import (  # noqa: F401
    NON_PRECISE,
    SQUELETTE,
    SUFFIXE_CITATION,
    Rubrique,
    SyntheseIndisponible,
    consignes,
    extraire_objet,
    rendre_html,
)


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
