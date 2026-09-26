"""Le VERDICT sur l'état du bridge WhatsApp : coupure ordinaire, ou blocage possible (#1061).

## Pourquoi un verdict distinct

Le bridge repose sur Baileys, qui parle WhatsApp Web sans être un client
officiel. Deux pannes se ressemblent à l'écran — « déconnecté » — et n'ont rien
en commun :

- la **coupure ordinaire** : le bridge boucle toutes les ~4 h 45 (`Connection
  closed 428`), se reconnecte seul en quelques minutes. Rien à faire ;
- le **compte déconnecté d'office** : WhatsApp ferme la session (401) ou la
  refuse (403). C'est le signe d'un appairage perdu — ou d'un numéro BLOQUÉ.
  Un redémarrage n'y change rien, et la conduite à tenir n'est pas la même
  (`.claude/skills/infra-rpi`, « Blocage du compte WhatsApp »).

Une déconnexion qui DURE au-delà de quelques heures relève du second cas tant
qu'on ne sait pas mieux : la boucle ordinaire ne dure jamais aussi longtemps.

PURE : l'état, la durée et le code viennent de l'appelant (`/status` du bridge).
"""

from __future__ import annotations

#: Au-delà, une déconnexion n'est plus la boucle ordinaire (qui dure des minutes).
SEUIL_DURABLE_H = 6

#: Les codes par lesquels WhatsApp ferme lui-même la session (Baileys
#: `DisconnectReason.loggedOut` = 401, `forbidden` = 403).
CODES_COMPTE_FERME = frozenset({401, 403})

CONDUITE = (
    "Conduite à tenir : ne pas ré-appairer en boucle ; vérifier le téléphone du "
    "numéro appairé ; prévenir les résidents par courriel (le canal de repli) — "
    "voir .claude/skills/infra-rpi, « Blocage du compte WhatsApp »."
)


def verdict_whatsapp(etat: str, hors_ligne_h: float | None, dernier_code: int | None) -> str | None:
    """Le problème à signaler, ou `None` si le bridge est connecté."""
    if etat == "open":
        return None
    if dernier_code in CODES_COMPTE_FERME:
        return (
            f"WhatsApp a fermé la session du bridge (code {dernier_code}) : appairage perdu "
            f"ou numéro BLOQUÉ. Un redémarrage n'y changera rien. {CONDUITE}"
        )
    if hors_ligne_h is not None and hors_ligne_h >= SEUIL_DURABLE_H:
        return (
            f"Bridge WhatsApp hors ligne depuis {int(hors_ligne_h)} h (état : {etat}) — bien "
            f"au-delà d'une coupure ordinaire, qui se rétablit en minutes. {CONDUITE}"
        )
    return (
        f"Bridge WhatsApp déconnecté (état : {etat}). Reconnexion requise via "
        "Admin → WhatsApp → Statut."
    )
