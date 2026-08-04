"""Les mots de passe se hachent et se vérifient encore — y compris les anciens.

POURQUOI CE TEST (04/08/2026) :

Une PR Dependabot proposait `bcrypt` 4.0.1 → 5.0.0. Elle était **verte** : les quatre
jobs passaient. Elle aurait mis l'authentification par terre.

`app/auth/jwt.py` utilise **passlib 1.7.4** (dernière version : 2020) avec le backend
bcrypt. Avec `bcrypt` 5.0.0, l'initialisation même du backend lève :

    ValueError: password cannot be longer than 72 bytes, truncate manually if
    necessary — passlib/handlers/bcrypt.py, detect_wrap_bug()

Ce n'est pas une dégradation : `hash_password()` et `verify_password()` lèvent, donc
**plus personne ne se connecte et aucun compte ne peut être créé**. Aucun test de
cette suite ne touchait ces deux fonctions ; la CI ne pouvait que dire vert.

Ce fichier ferme ce trou. Il couvre trois choses distinctes, et la deuxième est la
plus importante — c'est celle qu'une migration d'algorithme casserait en silence.
"""
import pytest

from app.auth.jwt import hash_password, verify_password

#: Empreinte produite le 04/08/2026 par la configuration de production
#: (passlib 1.7.4 + bcrypt 4.0.1, `bcrypt__rounds=10`), pour le mot de passe
#: ci-dessous. Elle représente les comptes DÉJÀ en base : ce sont eux qu'une
#: montée de version ne doit jamais rendre invérifiables.
EMPREINTE_TEMOIN = "$2b$10$b94ialnjwcjUR1iDDo9yfe98DskRFInZqUQ76AuTWYCEeoTkzdh.y"
MOT_DE_PASSE_TEMOIN = "MotDePasseTemoin2026!"


def test_hachage_et_verification_fonctionnent():
    """Le contrôle le plus bête, et celui qui manquait.

    S'il échoue, personne ne peut se connecter ni créer de compte. C'est
    exactement ce que produit `bcrypt` 5.0.0 avec le passlib actuellement figé.
    """
    empreinte = hash_password(MOT_DE_PASSE_TEMOIN)
    assert empreinte, "aucune empreinte produite"
    assert empreinte != MOT_DE_PASSE_TEMOIN, "le mot de passe n'est pas haché !"
    assert verify_password(MOT_DE_PASSE_TEMOIN, empreinte)


def test_une_empreinte_deja_en_base_reste_verifiable():
    """LE test qui protège les comptes existants.

    Une bibliothèque peut très bien continuer à hacher et à vérifier ses PROPRES
    empreintes tout en cessant de reconnaître celles produites avant elle : le test
    précédent resterait vert, et tous les comptes de la base deviendraient
    inutilisables au premier déploiement. Le témoin ci-dessus est figé pour cette
    raison — il ne doit jamais être régénéré pour « faire passer » le test.
    """
    assert verify_password(MOT_DE_PASSE_TEMOIN, EMPREINTE_TEMOIN), (
        "une empreinte produite par la configuration de production n'est plus "
        "vérifiable : TOUS les comptes existants seraient bloqués"
    )


def test_un_mauvais_mot_de_passe_est_rejete():
    """Une vérification qui rend toujours vrai serait pire que pas de vérification."""
    assert not verify_password("mauvais", EMPREINTE_TEMOIN)
    assert not verify_password("", EMPREINTE_TEMOIN)


@pytest.mark.parametrize("longueur", [8, 71, 72, 73, 200])
def test_les_mots_de_passe_longs_ne_font_pas_tomber_la_connexion(longueur):
    """bcrypt ne traite que 72 octets. Ce qu'il advient au-delà doit être DÉCIDÉ.

    passlib tronque silencieusement ; `bcrypt` 5.0 lève à la place. Un utilisateur
    ayant choisi une phrase de passe un peu longue verrait donc sa connexion partir
    en erreur 500 — un cas de figure invisible au test nominal, et impossible à
    diagnostiquer depuis l'écran de connexion.
    """
    secret = "é" * longueur  # accentué : la limite est en OCTETS, pas en caractères
    empreinte = hash_password(secret)
    assert verify_password(secret, empreinte)


def test_le_format_produit_reste_du_bcrypt():
    """Un changement d'algorithme se verrait ici, pas en production.

    `$2b$` est le préfixe bcrypt, `10` le nombre de tours configuré dans
    `CryptContext(..., bcrypt__rounds=10)`. Si l'un des deux change, les empreintes
    existantes et les nouvelles cessent d'être homogènes — à décider consciemment,
    jamais à subir.
    """
    empreinte = hash_password(MOT_DE_PASSE_TEMOIN)
    assert empreinte.startswith("$2b$10$"), f"format inattendu : {empreinte[:10]}"
