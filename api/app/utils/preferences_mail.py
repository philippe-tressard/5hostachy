"""Qui reçoit un e-mail — la décision, écrite à un seul endroit.

## Ce que ce module remplace

Le réglage des notifications comptait **huit** cases : quatre rubriques (tickets,
actualités, documents, communauté) × deux canaux (application, e-mail). Le
résident devait donc comprendre une matrice pour dire une chose simple : « je
veux les e-mails de chez moi, pas ceux d'à côté ».

Deux choix depuis le 14/08/2026 (#339), et rien d'autre :

- `mon_batiment_mail` — **coché** par défaut ;
- `autres_batiments_mail` — **décoché** par défaut. Personne n'a jamais consenti
  à recevoir les autres bâtiments : le défaut ne peut donc pas être « oui ».

## Ce que la simplification coûte, et c'est assumé

Le réglage **par rubrique** disparaît : on ne peut plus recevoir les actualités
par mail sans recevoir les tickets. Les notifications **dans l'application** ne
sont plus réglables non plus — elles restent actives, ce qui était déjà leur
valeur par défaut pour les quatre rubriques. Un compte qui avait décoché
`ticket_app` les retrouvera donc.

C'est une demande explicite de l'utilisateur, faite trois fois, et le compromis
est net : huit cases que personne ne règle contre deux que tout le monde
comprend.

## La lecture était écrite trois fois

`email/__init__.py` (deux fois) et `utils/reponses.py` portaient chacun leur
`json.loads(user.preferences_notifications)` avec leur propre valeur par défaut.
Trois copies d'une règle de consentement, c'est trois façons d'être en désaccord
sur ce que l'utilisateur a demandé.
"""
from __future__ import annotations

import json
import logging
from typing import Iterable, Optional

logger = logging.getLogger("hostachy.preferences_mail")

#: Les deux seules clés. Le défaut de chacune est ici, et nulle part ailleurs.
MON_BATIMENT = "mon_batiment_mail"
AUTRES_BATIMENTS = "autres_batiments_mail"
DEFAUTS: dict[str, bool] = {MON_BATIMENT: True, AUTRES_BATIMENTS: False}

#: Valeur du champ pour un compte neuf.
DEFAUT_JSON = json.dumps(DEFAUTS)


def lire(utilisateur) -> dict[str, bool]:
    """Les deux préférences d'un utilisateur, valeurs par défaut comprises.

    Un JSON illisible rend les **défauts** plutôt que rien : la préférence règle
    un confort, pas un accès. Refuser tout envoi sur une donnée abîmée priverait
    le résident d'informations qu'il a demandées, ce qui est le mauvais côté de
    l'erreur — à l'inverse exact d'une décision de visibilité, où l'on refuse
    (`utils/visibility._codes_json_pour_acces`).
    """
    brut = getattr(utilisateur, "preferences_notifications", None)
    try:
        prefs = json.loads(brut or "{}")
        if not isinstance(prefs, dict):
            prefs = {}
    except (json.JSONDecodeError, TypeError):
        logger.warning("Préférences illisibles pour l'utilisateur %s — défauts appliqués",
                       getattr(utilisateur, "id", "?"))
        prefs = {}
    return {cle: bool(prefs.get(cle, defaut)) for cle, defaut in DEFAUTS.items()}


def mail_autorise(utilisateur, batiments_concernes: Optional[Iterable[int]] = None) -> bool:
    """Cet utilisateur veut-il l'e-mail d'un contenu visant ces bâtiments ?

    `batiments_concernes` vaut `None` quand l'appelant ne sait pas de quel
    bâtiment il s'agit — un rappel de mot de passe, une validation de compte, un
    message qui ne cible personne en particulier. C'est alors **`mon_batiment`**
    qui décide : ces envois s'adressent au destinataire lui-même, pas à un
    ailleurs qu'il aurait choisi d'ignorer. Traiter l'inconnu comme « les autres
    bâtiments » couperait des e-mails que personne n'a demandé à couper.

    Un contenu à portée globale (`batiments_concernes` vide) relève de la même
    logique : il concerne tout le monde, donc aussi le destinataire.
    """
    prefs = lire(utilisateur)
    if batiments_concernes is None:
        return prefs[MON_BATIMENT]

    cibles = set(batiments_concernes)
    if not cibles:
        return prefs[MON_BATIMENT]

    from app.utils.mes_batiments import batiments_de_l_utilisateur

    miens = batiments_de_l_utilisateur(utilisateur)
    #  Aucun bâtiment connu : on ne peut pas dire que le contenu vient d'ailleurs,
    #  donc on ne s'autorise pas à le couper (cas zéro, `standards/04` §2).
    if not miens or (miens & cibles):
        return prefs[MON_BATIMENT]
    return prefs[AUTRES_BATIMENTS]
