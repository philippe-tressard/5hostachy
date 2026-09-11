"""Proposer la synthèse d'un contrat d'entretien — le format, et ce qu'on envoie.

## Ce que ce module fait

Il assemble une demande et la pose au modèle configuré (`utils/llm.py`) :

1. **le gabarit** — les sept sections arrêtées par le conseil syndical ;
2. **des exemples** — les synthèses que le CS a déjà écrites, qui apprennent le
   ton et la longueur mieux qu'aucune consigne ne saurait les décrire ;
3. **ce que la base sait** du contrat — libellé, prestataire, dates, périmètre ;
4. **le texte des documents joints**, sans lesquels quatre sections sur sept
   resteraient vides.

Il ne rend qu'un TEXTE. Rien n'est enregistré : c'est le conseil syndical qui
relit, corrige et valide — une synthèse fausse au carnet d'entretien serait pire
que pas de synthèse, ce carnet étant un document réglementaire (décret
n° 2001-477).

## 🔴 Pourquoi le document part, et ce qui ne part pas

Arbitré le 11/09/2026. Les sept sections réclament l'adresse et le RCS du
fournisseur, les clauses de reconduction et de résiliation, les prestations
incluses et exclues, le détail des montants : **rien de tout cela n'existe dans
les champs d'un contrat**. Sans le PDF, la fonctionnalité n'a pas d'objet.

Ce qui part est donc le contrat lui-même, et lui seul :

| | |
|---|---|
| **tous les documents du contrat** | envoyés, en texte extrait — jamais les fichiers |
| une pièce jointe d'un ticket, d'une actualité, d'un autre objet | **jamais** |

⚠️ **Tous**, et pas seulement celui que le contrat désigne : un contrat en a
plusieurs — l'initial, ses avenants, les conditions générales (signalé à l'écran
le 11/09/2026). N'en lire qu'un rendrait la section 6 fausse dès le premier
avenant, puisque c'est là que le prix change.

⚠️ Ce sont des données **d'entreprise** — montants, RCS, clauses. Un contrat
d'entretien de copropriété ne porte pas de donnée personnelle de résident. La
réserve honnête tient au nom et à la signature du président du conseil syndical,
qui figurent parfois au pied d'un contrat signé : ils partiraient avec le reste.

⚠️ L'envoi se coupe depuis l'administration (`llm_envoi_document`). La synthèse
reste alors possible, mais elle ne remplit que ce que la base sait — et elle le
DIT, plutôt que de rendre des sections vides sans explication.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime

from sqlmodel import Session, select

from app.models.documents import Document
from app.models.prestataires import ContratEntretien, Prestataire
from app.utils.dates_fr import datetime_longue_paris
from app.utils.llm import ConfigLLM, ErreurLLM, config_llm, demander
from app.utils.perimetres import parse_json_perimetres, perimetre_label_liste

logger = logging.getLogger("hostachy.synthese")

#: Combien de caractères du contrat au plus. Un contrat d'ascenseur fait deux à
#: dix pages ; au-delà de ce plafond on coupe, et on le dit au modèle plutôt que
#: de le laisser conclure sur un texte tronqué sans le savoir.
MAX_CARACTERES_DOCUMENT = 60_000

#: Combien de synthèses déjà écrites servent d'exemples. Trois suffisent à faire
#: passer un format ; au-delà on paie des jetons pour répéter la même leçon.
MAX_EXEMPLES = 3

#: 🔴 LE FORMAT, tel que le conseil syndical l'a arrêté (11/09/2026).
#:
#: Il est imposé au modèle, il ne se négocie pas : c'est le format du carnet
#: d'entretien de CETTE copropriété, pas celui qu'un modèle trouverait joli. Les
#: exemples ci-dessous apprennent le ton ; ce gabarit impose la structure.
GABARIT = """1. Identification du fournisseur
2. Dates clés / Validité (début, durée initiale, reconduction, résiliation)
3. Objet du contrat
4. Prestations incluses
5. Prestations non incluses
6. Conditions financières
7. Points d'attention pour la copropriété"""

CONSIGNE = f"""Tu rédiges la synthèse d'un contrat de COPROPRIÉTÉ — entretien, maintenance,
assurance, prestation de services — pour le conseil syndical. Elle sera lue par
des bénévoles, pas par des juristes.

🔴 Tu ne tires tes FAITS que des documents de CE contrat, joints ci-dessous, et
des champs de sa fiche. Rien d'autre : ni ta connaissance générale du
fournisseur, ni ce que contiennent habituellement les contrats de ce type, ni les
exemples de rédaction qui te sont donnés — ceux-là ne montrent que le TON et la
STRUCTURE attendus. Reprendre un montant, une durée ou une clause lus ailleurs
que dans ce contrat serait la pire erreur possible : la synthèse alimente le
carnet d'entretien, qui est un document réglementaire.

Respecte EXACTEMENT ces sept sections, numérotées, dans cet ordre :

{GABARIT}

Règles :
- une section sans information disponible est écrite avec la mention
  « non précisé dans les éléments fournis » — n'invente jamais un montant, une
  date, un numéro RCS ni une clause, et ne comble jamais un manque par ce qui
  est « habituel » ;
- des puces courtes, pas de paragraphes ;
- reprends les termes du contrat, sans les reformuler en langage commercial ;
- la section 7 est une LECTURE : ce que la copropriété doit surveiller
  (reconduction tacite, préavis, exclusions coûteuses, options facturées) ;
- pas de formule d'introduction ni de conclusion, la synthèse commence par le
  titre de la première section.

Rends du HTML SIMPLE, et rien d'autre : un `<h3>` par section (« 1. Identification
du fournisseur »), un `<ul><li>` par liste de puces, un `<p>` pour une phrase
isolée. Pas de `<html>`, pas de `<body>`, pas de bloc de code, pas de Markdown —
le texte est déposé tel quel dans un champ de notes enrichi."""


def documents_du_contrat(session: Session, contrat: ContratEntretien) -> list[Document]:
    """TOUS les documents du contrat, du plus ancien au plus récent.

    🔴 **Un contrat en a plusieurs**, et c'est le cas normal (signalé à l'écran
    le 11/09/2026). Le contrat initial, ses avenants, les conditions générales,
    une attestation. N'en lire qu'un — fût-ce celui que le contrat désigne —
    produirait une synthèse fausse dès le premier avenant : les conditions
    financières y changent, et la section 6 annoncerait l'ancien prix.

    L'ordre CHRONOLOGIQUE porte le sens : ce qui vient après modifie ce qui
    précède. C'est pourquoi on ne trie ni par titre ni par taille.

    ⚠️ Le document DÉSIGNÉ (`document_id`) vient en tête s'il n'est pas déjà
    joint : c'est le contrat de référence, celui que les autres amendent.
    """
    joints = list(
        session.exec(
            select(Document)
            .where(Document.contrat_id == contrat.id)
            .order_by(Document.publie_le)
        ).all()
    )
    if contrat.document_id and not any(d.id == contrat.document_id for d in joints):
        designe = session.get(Document, contrat.document_id)
        if designe:
            joints.insert(0, designe)
    return joints


def texte_du_document(doc: Document) -> str:
    """Le texte d'un PDF, extrait côté serveur — jamais le fichier lui-même.

    Rend une chaîne vide quand il n'y a rien à lire : un PDF scanné sans couche
    de texte, un format non géré, un fichier absent. L'appelant le traite comme
    « pas de document », ce qui est vrai de son point de vue.
    """
    chemin = doc.fichier_chemin
    if not chemin or not (doc.mime_type or "").lower().endswith("pdf"):
        return ""
    try:
        from pypdf import PdfReader

        lecteur = PdfReader(chemin)
        morceaux = []
        total = 0
        for page in lecteur.pages:
            t = (page.extract_text() or "").strip()
            if not t:
                continue
            morceaux.append(t)
            total += len(t)
            if total >= MAX_CARACTERES_DOCUMENT:
                break
        return "\n\n".join(morceaux)[:MAX_CARACTERES_DOCUMENT]
    except Exception as exc:  # noqa: BLE001 — un PDF illisible n'est pas une panne
        logger.warning("Lecture du document %s impossible : %s", doc.id, exc)
        return ""


def exemples(session: Session, contrat: ContratEntretien) -> list[str]:
    """Les synthèses déjà écrites, qui apprennent le format de la maison.

    Priorité aux contrats du MÊME type d'équipement : une synthèse d'ascenseur
    ressemble plus à une autre synthèse d'ascenseur qu'à celle d'un contrat
    d'espaces verts — c'est le voisinage qui rend l'exemple utile.
    """
    tous = session.exec(
        select(ContratEntretien).where(
            ContratEntretien.id != contrat.id,
            ContratEntretien.actif == True,  # noqa: E712
            ContratEntretien.notes != None,  # noqa: E711
        )
    ).all()
    avec_notes = [c for c in tous if (c.notes or "").strip()]
    meme_type = [c for c in avec_notes if c.type_equipement == contrat.type_equipement]
    autres = [c for c in avec_notes if c.type_equipement != contrat.type_equipement]
    return [(c.notes or "").strip() for c in (meme_type + autres)[:MAX_EXEMPLES]]


def ce_que_la_base_sait(session: Session, contrat: ContratEntretien) -> str:
    """Les champs du contrat, en clair — ils fondent les sections 1 à 3."""
    prest = session.get(Prestataire, contrat.prestataire_id)
    duree = (
        f"{contrat.duree_initiale_valeur} {contrat.duree_initiale_unite}"
        if contrat.duree_initiale_valeur
        else None
    )
    frequence = (
        f"{contrat.frequence_valeur} ({contrat.frequence_type})"
        if contrat.frequence_valeur
        else None
    )
    lignes = [
        ("Libellé", contrat.libelle),
        ("Type d'équipement", contrat.type_equipement),
        ("Prestataire", prest.nom if prest else None),
        ("Téléphone du prestataire", prest.telephone if prest else None),
        ("Courriel du prestataire", prest.email if prest else None),
        ("Numéro de contrat", contrat.numero_contrat),
        ("Date de début", contrat.date_debut.isoformat() if contrat.date_debut else None),
        ("Durée initiale", duree),
        ("Fréquence des visites", frequence),
        ("Périmètre couvert", perimetre_label_liste(parse_json_perimetres(contrat.perimetre_cible))),
    ]
    return "\n".join(f"- {k} : {v}" for k, v in lignes if v)


def construire_message(session: Session, contrat: ContratEntretien, *, avec_document: bool) -> str:
    """Le message posé au modèle : les exemples, les champs, puis le contrat."""
    blocs = []

    modeles = exemples(session, contrat)
    if modeles:
        blocs.append(
            "Voici des synthèses déjà rédigées par ce conseil syndical, pour d'AUTRES "
            "contrats. Reprends leur ton, leur longueur et leur façon de formuler — "
            "n'en reprends AUCUN fait : ni montant, ni durée, ni clause, ni "
            "fournisseur :\n\n"
            + "\n\n---\n\n".join(modeles)
        )

    blocs.append("Ce que la fiche du contrat indique :\n" + ce_que_la_base_sait(session, contrat))

    if avec_document:
        #  Chaque document est ANNONCÉ par son titre et sa date : sans eux, le
        #  modèle lit une seule masse de texte et ne peut pas savoir qu'un avenant
        #  remplace une clause du contrat initial.
        lus, budget = [], MAX_CARACTERES_DOCUMENT
        for doc in documents_du_contrat(session, contrat):
            if budget <= 0:
                break
            texte_doc = texte_du_document(doc)
            if not texte_doc:
                continue
            extrait = texte_doc[:budget]
            budget -= len(extrait)
            quand = doc.publie_le.date().isoformat() if doc.publie_le else "date inconnue"
            tronque = " — TRONQUÉ" if len(extrait) < len(texte_doc) else ""
            lus.append(f"--- Document « {doc.titre} » (déposé le {quand}){tronque} ---\n{extrait}")
        texte = "\n\n".join(lus)
        if texte:
            blocs.append(
                "Documents du contrat, du plus ancien au plus récent. Un document "
                "postérieur peut MODIFIER une clause d'un précédent — un avenant "
                "l'emporte sur le contrat initial :\n\n" + texte
            )
        else:
            #  ⚠️ On le DIT au modèle plutôt que de le laisser deviner : sans
            #  cette phrase, il comble les sections manquantes par des formules
            #  plausibles, ce qui est le pire résultat possible ici.
            blocs.append(
                "Aucun texte de contrat n'a pu être lu. Les sections 4 à 7 doivent porter "
                "« non précisé dans les éléments fournis »."
            )
    else:
        blocs.append(
            "L'envoi du document est désactivé. Les sections 4 à 7 doivent porter "
            "« non précisé dans les éléments fournis »."
        )

    return "\n\n".join(blocs)


def entete_provenance(cfg: ConfigLLM, documents: list[Document], *, quand: datetime) -> str:
    """L'encart qui dit d'où vient le texte : quel modèle, quand, sur quoi.

    🔴 Demandé le 11/09/2026, et ce n'est pas une politesse. La synthèse atterrit
    dans les notes du contrat, où elle devient indiscernable de celles que le
    conseil syndical a écrites à la main — or elle n'a ni le même auteur, ni la
    même fiabilité, et elle VIEILLIT : un avenant déposé après coup la rend
    fausse sans rien changer à son texte.

    Les trois informations répondent chacune à une question qui se pose plus
    tard : *qui l'a écrite ?* (le modèle, nommé — deux modèles ne rendent pas la
    même chose), *de quand date-t-elle ?*, et *qu'a-t-elle lu ?* — c'est la
    dernière qui permet de voir qu'un document manquait.

    ⚠️ Il est ÉCHAPPÉ puis rendu en HTML : un nom de fichier peut porter un `&`
    ou un chevron, et il voyage jusqu'à un `{@html}` (assaini, mais on ne fait
    pas reposer la correction du rendu sur l'assainisseur).
    """
    e = html.escape
    sur = (
        " à partir de " + " ; ".join(e(d.titre) for d in documents)
        if documents
        else " à partir des seules données de la fiche du contrat"
    )
    return (
        "<blockquote><p><em>Synthèse proposée par "
        f"{e(cfg.fournisseur.libelle)} · {e(cfg.modele)} le "
        f"{e(datetime_longue_paris(quand))}{sur}. "
        "À relire et à corriger avant de l'enregistrer.</em></p></blockquote>"
    )


async def synthetiser(session: Session, contrat: ContratEntretien) -> str:
    """Propose la synthèse d'un contrat, précédée de sa provenance. N'enregistre RIEN."""
    cfg = config_llm(session)
    documents = documents_du_contrat(session, contrat) if cfg.envoi_document else []
    message = construire_message(session, contrat, avec_document=cfg.envoi_document)
    texte = await demander(session, consigne=CONSIGNE, message=message)
    #  L'horodatage est pris APRÈS la réponse : c'est la date de la synthèse
    #  rendue, pas celle de la demande — une requête peut durer une minute.
    entete = entete_provenance(cfg, documents, quand=datetime.utcnow())
    return entete + "\n" + texte.strip()


def synthese_disponible(session: Session, contrat: ContratEntretien) -> bool:
    """Le geste a-t-il un sens sur ce contrat ?

    🔴 C'est le SERVEUR qui le dit, pas l'écran. Une règle de disponibilité
    écrite dans une page serait une règle de plus à tenir à jour, et la
    configuration de l'assistant n'a rien à faire dans la session d'un membre du
    conseil syndical (`standards/03` §1 — l'autorisation est centralisée).

    ⚠️ Un contrat sans document reste éligible **si** l'envoi du document est
    désactivé : la synthèse est alors partielle, et c'est un choix assumé de
    l'administration. Ce qui n'a pas de sens, c'est de proposer une synthèse
    complète sans la matière qui la remplit.
    """
    cfg = config_llm(session)
    if not cfg.actif or not cfg.cle:
        return False
    if not cfg.envoi_document:
        return True
    return bool(documents_du_contrat(session, contrat))


__all__ = [
    "CONSIGNE",
    "GABARIT",
    "ErreurLLM",
    "construire_message",
    "entete_provenance",
    "documents_du_contrat",
    "exemples",
    "synthese_disponible",
    "synthetiser",
    "texte_du_document",
]
