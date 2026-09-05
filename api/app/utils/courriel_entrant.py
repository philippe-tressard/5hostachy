"""Répondre à un ticket **par courriel** — le jeton, et rien d'autre.

## Le besoin (#703)

> « les mails reçus dans `noreply@5hostachy.fr` en réponse à un ticket par le
>   syndic sont-ils traitables automatiquement en complétant le ticket ? »

Aujourd'hui une réponse arrive dans cette boîte et **personne ne la voit**.
L'adresse s'appelle « noreply » mais reçoit de vraies réponses, écrites par
quelqu'un qui attend qu'on les lise.

## Ce fichier ne fait qu'UNE chose : le jeton

Il porte la fabrication et la lecture de l'adresse de réponse, et **pas** la
relève de la boîte (`courriel_ingestion.py`) ni la décision d'écrire dans le
ticket. C'est ce qui rend la décision **pure** : elle s'éprouve sur des chaînes,
sans IMAP, sans base et sans réseau — la leçon de `check-reliability`, où l'on
testait la décision et jamais le tuyau qui la nourrit.

## Pourquoi un jeton dans l'ADRESSE, et pas le numéro du ticket

Trois voies existaient pour retrouver le ticket d'une réponse :

| Voie | Ce qu'elle vaut |
|---|---|
| le jeton dans l'adresse (`tickets+<jeton>@`) | ✅ survit à un transfert, à une réécriture de sujet, à tout client — **quand le serveur de courriel accepte le sous-adressage** |
| `In-Reply-To` / `References` | ⚠️ certains clients et passerelles les perdent |
| le numéro dans le sujet (`Ticket #42`) | ⚠️ un sujet se réécrit, se traduit, se tronque — **et se falsifie** |

🔴 **REVIREMENT DU 05/09/2026 — le sujet devient un REPLI, jamais le premier
choix.** Ce fichier écrivait « la troisième voie est écartée définitivement », et
c'était un bon raisonnement sur une hypothèse fausse : *que la première marche*.
L'utilisateur a constaté l'inverse — *« cette adresse pour le suivi du syndic ne
semble pas marcher, peux-tu faire une solution de repli en te basant sur l'objet
du ticket »*. Une voie sûre qui n'achemine rien ne protège personne : elle perd
la réponse du syndic, en silence.

L'ordre est donc : **jeton d'abord** ; à défaut, **numéro dans le sujet**. Et
parce que le sujet se falsifie, le repli est payé par un contrôle que le jeton
n'exigeait pas — l'expéditeur doit être quelqu'un que le site aurait ÉCRIT à
propos de ce ticket (`courriel_boite.correspondant_du_ticket`). Le jeton, lui,
prouvait déjà cela par sa seule possession.

La seconde voie sert toujours seulement à reconnaître qu'un message RÉPOND à
quelque chose — ce qui distingue « je ne sais pas rattacher » de « je refuse » —
et non à désigner un ticket : conserver le `Message-ID` de chaque envoi serait un
travail de plus.

🔴 **Le jeton est opaque et non devinable.** Il voyage dans l'adresse, donc dans
tous les carnets d'adresses et toutes les archives de la chaîne : y écrire
l'identifiant du ticket en clair donnerait à quiconque le moyen d'écrire sur
n'importe quel ticket en devinant `tickets+42@`. Il est tiré au sort à la
création, jamais dérivé.

⚠️ **Et il ne suffit pas.** Connaître le jeton prouve seulement qu'on a reçu un
message du site ; l'authentification de l'expéditeur est une décision **séparée**
(`courriel_ingestion.expediteur_authentifie`). Les confondre reviendrait à faire
d'un jeton lisible dans un carnet d'adresses un droit d'écriture signé du syndic.
"""
from __future__ import annotations

import re
import secrets
from email.utils import parseaddr

#: La boîte locale qui reçoit les réponses. Le sous-adressage `+<jeton>` est la
#: partie qui identifie le ticket ; ce préfixe-ci ne change jamais.
PREFIXE_BOITE = "tickets"

#: Longueur du jeton en caractères hexadécimaux. 32 = 128 bits : le deviner par
#: essais successifs demanderait plus de messages qu'aucune boîte n'en reçoit.
LONGUEUR_JETON = 32

#: Une adresse de réponse valide, dans un `To:`, un `Delivered-To:` ou un
#: `Envelope-To:`. Insensible à la casse, et tolérante aux formes
#: « Nom <adresse> » : on ne cherche que la partie qui compte.
_ADRESSE = re.compile(
    rf"{PREFIXE_BOITE}\+([0-9a-f]{{{LONGUEUR_JETON}}})@",
    re.IGNORECASE,
)


def nouveau_jeton() -> str:
    """Un jeton neuf, tiré au sort.

    `secrets` et non `random` : ce jeton est un secret de faible portée, mais un
    secret. `random` est prédictible à partir de quelques tirages observés, et
    les jetons voyagent en clair dans des messages archivés.
    """
    return secrets.token_hex(LONGUEUR_JETON // 2)


def adresse_de_reponse(jeton: str, domaine: str) -> str:
    """L'adresse à poser en `Reply-To` — « tickets+<jeton>@<domaine> »."""
    return f"{PREFIXE_BOITE}+{jeton}@{domaine}"


def domaine_de(adresse: str) -> str:
    """Le domaine d'une adresse d'expédition, pour composer le `Reply-To`.

    Une adresse vide ou sans `@` rend une chaîne vide, et l'appelant renonce à
    poser un `Reply-To` : mieux vaut pas de réponse possible qu'une adresse
    fabriquée sur un domaine inventé, qui partirait dans le vide.

    ⚠️ `parseaddr` et non un découpage sur `@` : `smtp_from` peut valoir
    « Ma Résidence <noreply@5hostachy.fr> ». Le découpage naïf rendait alors
    « 5hostachy.fr> », chevron compris, et le `Reply-To` fabriqué dessus était
    invalide — aucune réponse ne serait jamais arrivée, sans le moindre signal.
    Attrapé par le test, pas par la relecture.
    """
    brute = parseaddr(adresse or "")[1] or ""
    if "@" not in brute:
        return ""
    return brute.rsplit("@", 1)[1].strip().lower()


#: Le numéro de ticket tel que NOS sujets l'écrivent : « Ticket #TK-123456 — … ».
#: Les préfixes de réponse (`Re:`, `TR:`, `Fwd:`) et le préfixe de copropriété
#: passent devant sans gêner, puisqu'on cherche le motif n'importe où dans la
#: ligne. Le dièse est facultatif : certains clients le mangent en réécrivant le
#: sujet, et « Ticket TK-123456 » désigne aussi clairement.
#:
#: ⚠️ Le numéro est une CHAÎNE dans le modèle (`Ticket.numero`), aujourd'hui six
#: chiffres. Le motif accepte donc des lettres : ancrer sur `\d{6}` ferait
#: dépendre la relève du courriel d'un choix de génération qui n'a rien à voir
#: avec elle, et la panne serait silencieuse — le message deviendrait « sans
#: rapport avec un ticket ».
_SUJET_NUMERO = re.compile(r"ticket\s*#?\s*(TK-[0-9A-Za-z]{4,12})", re.IGNORECASE)


def numero_dans_sujet(sujet: str | None) -> str | None:
    """Le numéro de ticket écrit dans le sujet (« TK-123456 »), s'il y en a un.

    ⚠️ **Ce numéro ne prouve rien.** Il figure dans tous les courriels déjà
    envoyés, et n'importe qui peut l'écrire. Il DÉSIGNE un ticket ; c'est à
    l'appelant de vérifier que l'expéditeur avait quelque chose à y faire —
    `courriel_boite.correspondant_du_ticket`.

    Le motif exige le mot « Ticket » devant : sans lui, un sujet qui contient
    « TK-123456 » pour toute autre raison rattacherait un message au hasard.

    >>> numero_dans_sujet("Re: Ticket #TK-482910 — Fuite au 3e — Les Hostachys")
    'TK-482910'
    >>> numero_dans_sujet("Re: votre facture TK-482910")
    """
    if not sujet:
        return None
    trouve = _SUJET_NUMERO.search(sujet)
    #  Rendu TEL QUEL : c'est une clé, et rien ne dit qu'elle sera toujours
    #  insensible à la casse. La comparaison, elle, l'est (`courriel_boite`).
    return trouve.group(1) if trouve else None


def jeton_dans(*valeurs: str | None) -> str | None:
    """Le jeton porté par l'une de ces valeurs d'en-tête, s'il y en a un.

    Plusieurs en-têtes sont interrogés parce qu'aucun n'est garanti : `To:` sur
    une réponse directe, `Delivered-To:` / `Envelope-To:` quand un relais a
    réécrit le destinataire visible, et `Cc:` quand la réponse a été mise en
    copie plutôt qu'adressée.
    """
    for valeur in valeurs:
        if not valeur:
            continue
        trouve = _ADRESSE.search(valeur)
        if trouve:
            return trouve.group(1).lower()
    return None
