"""Le TEXTE d'un message pour le groupe de la résidence — sa composition seule.

Extrait de `utils/whatsapp.py` le 28/09/2026, au fil de l'eau (#779) : le module
faisait 532 lignes et mêlait deux notions — COMPOSER le message (titre, contenu
converti du HTML, périmètre, version restreinte d'un message réservé, lien) et
le TRANSPORTER (bridge, journal, verdict d'envoi). Le premier ne dépend d'aucun
réseau ni d'aucune base : c'est ce qui se teste et s'aperçoit sans rien envoyer
(`apercu_diffusion`, `test_actualite_acces`).

⚠️ `whatsapp.py` ré-exporte `construire_message`, `message_sans_contenu` et
`TITRE_CONFIDENTIEL` : les importeurs existants ne bougent pas.
"""

import html
import json
import re

from app.utils.liens import base_site


def _build_message(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    footer: str | None = None,
    lien: str | None = None,
) -> str:
    """Construit le texte du message WhatsApp.

    `lien` ajoute, avant la signature, un renvoi vers l'application — « voir
    le contenu complet ». Demandé le 18/08/2026 pour le SUIVI d'un événement,
    dont le commentaire est souvent lu hors de son contexte : sans lien, le
    lecteur du groupe voit un commentaire sans savoir sur quoi il porte.

    ⚠️ Le message **restreint** en portait déjà un, codé chez lui
    (`_build_message_restreint`), et c'était le seul du site. Le paramètre est
    donc facultatif et ne change RIEN aux appels existants : une actualité
    ordinaire continue de partir sans lien tant que personne ne l'a demandé à
    l'écran (R5 — un enrichissement se propage, donc il se constate d'abord
    sur UN cas).
    """
    # Périmètre
    try:
        lieux = (
            json.loads(perimetre_cible)
            if isinstance(perimetre_cible, str)
            else (perimetre_cible or [])
        )
    except Exception:
        lieux = []
    if lieux and not (len(lieux) == 1 and lieux[0] == "résidence"):
        perimetre_label = ", ".join(lieux)
    else:
        perimetre_label = "Copropriété"

    if urgente:
        header = f"🚨 URGENT — 🔹 {perimetre_label} — *{titre}*"
    else:
        header = f"📢 🔹 {perimetre_label} — *{titre}*"

    # Contenu : convertir le formatage HTML en markdown WhatsApp
    # Gras : <b>, <strong>  → *texte*
    text = re.sub(
        r"<(b|strong)(\s[^>]*)?>(.+?)</(b|strong)>",
        r"*\3*",
        contenu,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Italique : <i>, <em>  → _texte_
    text = re.sub(
        r"<(i|em)(\s[^>]*)?>(.+?)</(i|em)>", r"_\3_", text, flags=re.IGNORECASE | re.DOTALL
    )
    # Barré : <s>, <strike>, <del>  → ~texte~
    text = re.sub(
        r"<(s|strike|del)(\s[^>]*)?>(.+?)</(s|strike|del)>",
        r"~\3~",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Saut de ligne : <br>, </p>
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    # Supprimer les balises HTML restantes
    text = re.sub(r"<[^>]+>", "", text)
    # Décoder les entités HTML (&nbsp; → espace, &amp; → &, etc.)
    text = html.unescape(text)
    # Remplacer les espaces insécables résiduels par des espaces normaux
    text = text.replace("\u00a0", " ")
    text = text.strip()

    footer = (footer or "").strip() or "— Conseil Syndical 5Hostachy"
    #  Le lien vient APRÈS le texte et AVANT la signature : c'est la place
    #  qu'il occupe déjà dans le message restreint, et le lecteur d'un groupe
    #  WhatsApp cherche l'action en bas du message, jamais au milieu.
    renvoi = f"\n\n👉 Voir le contenu complet :\n{(lien or chr(32)).strip()}"
    renvoi = renvoi if (lien or "").strip() else ""
    return f"{header}\n\n{text}{renvoi}\n\n{footer}"


def _is_restreint(public_cible: str | list | None) -> bool:
    """Retourne True si la publication n'est pas destinée à tous les résidents."""
    if public_cible is None:
        return False
    try:
        lst = json.loads(public_cible) if isinstance(public_cible, str) else public_cible
    except Exception:
        return False
    return "résidents" not in lst


#: Titre de repli, employé quand une actualité n'en a pas.
#:
#: 🔴 **CE N'EST PLUS LE TITRE DES CONFIDENTIELLES** — #347 renversé par #623
#: le 29/08/2026 : le titre part, et l'écran avertit son auteur de n'y rien
#: mettre de confidentiel. Le contenu, lui, ne sort jamais.
TITRE_CONFIDENTIEL = "Information réservée au périmètre concerné"


def _build_message_restreint(
    titre: str,
    urgente: bool,
    perimetre_cible: str | None,
    site_url: str,
    footer: str | None = None,
    lien: str | None = None,
) -> str:
    """Construit un message WhatsApp court pour une publication à audience restreinte.

    `titre` est le titre **à afficher**, pas nécessairement celui de la
    publication : le cas confidentiel y passe `TITRE_CONFIDENTIEL`. C'est la
    seule différence entre les deux usages, et elle tient dans un argument — une
    seconde fonction jumelle aurait divergé dès la première retouche de l'en-tête
    ou du lien (`standards/02-factorisation.md` §2).
    """
    try:
        lieux = (
            json.loads(perimetre_cible)
            if isinstance(perimetre_cible, str)
            else (perimetre_cible or [])
        )
    except Exception:
        lieux = []
    if lieux and not (len(lieux) == 1 and lieux[0] == "résidence"):
        perimetre_label = ", ".join(lieux)
    else:
        perimetre_label = "Copropriété"

    if urgente:
        header = f"🚨 URGENT — 🔹 {perimetre_label} — *{titre}*"
    else:
        header = f"📢 🔹 {perimetre_label} — *{titre}*"

    avertissement = (
        "🔒 Cette publication est réservée à un public ciblé.\n"
        "Elle n'est pas accessible à tous.\n"
        "Si vous êtes concerné(e), connectez-vous sur 5Hostachy pour la consulter :"
    )
    #  🔴 Le lien FOURNI (#1091) : l'actualité est devenue une affaire, son
    #  adresse est celle de sa fiche. `pub_id` et `/actualites#pub-<id>` ont été
    #  retirés avec l'entité ; sans lien, le message renvoie à l'accueil du site.
    if not lien:
        lien = site_url.rstrip("/") + "/"

    footer = (footer or "").strip() or "— Conseil Syndical 5Hostachy"
    return f"{header}\n\n{avertissement}\n{lien}\n\n{footer}"


def message_sans_contenu(public_cible: str | list | None, confidentiel: bool = False) -> bool:
    """Ce message doit-il se réduire à « avertissement + périmètre + lien » ?

    Deux raisons, une seule forme de message :
      - **public restreint** — le groupe est commun, le contenu ne s'adresse pas
        à tous ceux qui le liraient ;
      - **confidentiel** (#347) — même raison, sur l'axe bâtiment cette fois, et
        le titre lui-même est retiré.
    """
    return bool(confidentiel) or _is_restreint(public_cible)


def construire_message(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    config: dict,
    public_cible: str | None = None,
    confidentiel: bool = False,
    *,
    lien: str | None = None,
) -> str:
    """Le texte du message, décidé **une seule fois**.

    `envoyer_whatsapp` et `envoyer_whatsapp_avec_log` construisaient chacun leur
    message avec le même `if _is_restreint(...)`, si bien que le texte journalisé
    et le texte envoyé étaient deux calculs distincts d'une même chose. Ajouter
    le cas confidentiel en aurait fait deux copies à tenir alignées — dont l'une
    décide de ce qui part dans le groupe, l'autre de ce qu'on croit y avoir
    envoyé.
    """
    footer = config.get("whatsapp_footer", "").strip()
    if message_sans_contenu(public_cible, confidentiel):
        site_url = base_site(config.get("site_url"))
        #  🔴 Le titre PART, confidentiel compris (#623) ; le repli ne sert
        #  plus qu'aux actualités sans titre.
        titre_affiche = titre or TITRE_CONFIDENTIEL
        return _build_message_restreint(
            titre_affiche, urgente, perimetre_cible, site_url, footer, lien
        )
    #  Le lien ne concerne QUE le message normal : le message restreint en porte
    #  déjà un, qui renvoie vers l'application parce que le contenu n'y est pas.
    #  Lui en ajouter un second en donnerait deux, dont l'un ferait double emploi.
    return _build_message(titre, contenu, urgente, perimetre_cible, footer, lien)
