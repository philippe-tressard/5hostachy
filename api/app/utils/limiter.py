"""Instance partagée du rate limiter (slowapi), et les limites par **intention**.

## Pourquoi des constantes, et pas des chaînes dans les décorateurs (#1027)

Les onze limites du projet étaient des chaînes littérales posées route par
route : `"5/minute"` cinq fois, `"3/minute"` deux fois… Un littéral répété ne dit
pas *pourquoi* il vaut cinq, donc personne ne sait s'il faut le suivre en posant
une nouvelle route — et deux routes de même nature finissent avec deux plafonds
différents sans que ce soit une décision.

`.claude/skills/security-audit` recopiait par ailleurs le tableau de ces valeurs.
Une liste recopiée diverge à la première route ajoutée : la skill renvoie
désormais ici.

## Deux constantes peuvent partager une valeur — c'est le but

`LIMITE_SECRET_EPROUVE` et `LIMITE_DONNEES_PERSONNELLES` valent toutes deux
`5/minute` aujourd'hui. Ce n'est pas une duplication à fusionner : ce sont deux
intentions distinctes, qui doivent pouvoir **divergrer** le jour où l'une des
deux se révèle mal réglée. Les fusionner reviendrait à décider d'avance qu'elles
bougeront ensemble.

⚠️ Aucune valeur n'a été modifiée en introduisant ces noms : chaque route garde
exactement le plafond qu'elle avait. Renommer et rerégler sont deux gestes.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

#  🔴 PAR VISITEUR depuis #1300 (25/09/2026) : `get_remote_address` lit l'adresse
#  qu'uvicorn a établie (`--proxy-headers`, depuis ce que Caddy transmet). Avant,
#  toutes les requêtes portaient l'adresse de Caddy : un seul seau pour tout le
#  site, et un attaquant qui épuisait `/auth/login` bloquait tous les résidents.
#  Les valeurs ci-dessous n'ont pas changé : elles valent désormais par adresse.
limiter = Limiter(key_func=get_remote_address)

#: Une requête qui soumet un **secret devinable** — mot de passe, jeton de
#: réinitialisation, jeton de vérification d'adresse. C'est la limite qui
#: transforme une attaque par force brute en attaque impraticable : c'est donc la
#: seule dont l'absence est un défaut de sécurité, et non une imprudence.
LIMITE_SECRET_EPROUVE = "5/minute"

#: Une requête qui **fait partir un courriel** vers une adresse que l'appelant
#: choisit. Sans limite, la route sert de relais d'expédition gratuit — et c'est
#: la réputation du domaine qui paie.
LIMITE_COURRIEL_DECLENCHE = "3/minute"

#: Un courriel qu'un RÉSIDENT fait partir vers une adresse qu'il saisit — la
#: transmission d'une affaire (#1357). La limite ci-dessus, plus un plafond à
#: l'heure : trois par minute tenus une heure feraient 180 envois.
LIMITE_PARTAGE_COURRIEL = "3/minute;20/hour"

#: Une requête qui manipule une **session** sans éprouver de secret : rotation de
#: jeton, déconnexion.
LIMITE_SESSION = "10/minute"

#: Le **contrôle d'accès à un fichier**, que Caddy appelle une fois par fichier
#: servi.
#:
#: 🔴 Le plafond est large **par nécessité mesurée**, pas par prudence vague :
#: une galerie de vingt photos produit vingt appels en quelques secondes, et un
#: plafond de session (10/minute) aurait fait disparaître les images d'une page
#: chargée — une panne d'affichage causée par un durcissement de sécurité, et
#: attribuée à tout sauf à lui. Il protège encore d'un balayage massif, qui se
#: compte en milliers.
LIMITE_CONTROLE_FICHIER = "300/minute"

#: La **lecture de ses propres données** par un compte connecté : son profil, ses
#: demandes. Appelée à chaque chargement d'écran, parfois plusieurs fois.
LIMITE_LECTURE_AUTHENTIFIEE = "60/minute"

#: L'**export** ou l'**effacement** des données personnelles d'un compte. Une
#: intention de conformité, pas de sécurité : ces routes rendent ou détruisent
#: des données au porteur de la session, et une rafale coûte cher au serveur.
LIMITE_DONNEES_PERSONNELLES = "5/minute"

#: Le basculement d'une **préférence** du compte.
LIMITE_PREFERENCE = "10/minute"

#: Une **collecte passive** que le navigateur émet tout seul — rapport de
#: politique de sécurité du contenu, télémétrie d'usage. Haute par nécessité :
#: une page peut en produire plusieurs par visite, et les perdre rendrait le
#: journal muet sans que rien ne le signale.
LIMITE_JOURNAL = "60/minute"

#: Une **lecture publique**, sans secret ni écriture : la liste des bâtiments que
#: le formulaire d'inscription affiche. La limite n'y protège rien d'autre que le
#: serveur, d'où un plafond large.
LIMITE_LECTURE_PUBLIQUE = "60/minute"

#: Un appel qui **se facture** : le fournisseur d'IA (`utils.llm.demander`) —
#: synthèse de contrat, assistant de description, test de configuration.
#: Ailleurs une requête en trop coûte du CPU ; ici un double-clic, une tempête
#: de réessais, un onglet qui se recharge se lisent sur une facture (#1299).
#:
#: ⚠️ C'est un garde-BOUCLE, pas un plafond de dépense : il ne connaît ni le
#: prix d'un appel ni le solde. Le seul plafond qui vaille se pose sur le
#: compte du fournisseur. 10/minute reste hors d'atteinte d'un usage
#: légitime — une synthèse dure de quelques secondes à plusieurs minutes.
#: 🔒 `tests/test_limite_appel_facture.py` l'exige de TOUTE route qui atteint
#: `demander`, relevée dans le code.
LIMITE_APPEL_FACTURE = "10/minute"
