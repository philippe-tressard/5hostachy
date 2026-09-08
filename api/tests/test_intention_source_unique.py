"""Garde-fou — **l'intention d'un message a UNE source à l'envoi** (#850).

## Le défaut, trouvé le 08/09/2026

Philippe : *« peux-tu vérifier la cohérence de tous les templates pour être sûr
que c'est correct ? »*. La vérification a montré que le dépôt était cohérent avec
lui-même — et qu'une même notion se lisait à **deux** endroits :

===============================  ============================================
Ce qui décide                    Lu depuis
===============================  ============================================
le **bandeau** vu par le lecteur la BASE — `template.intention`
l'**adresse d'expédition**       le CODE — `INTENTIONS_PAR_MODELE`
===============================  ============================================

🔴 Et **rien ne les resynchronise**. `_poser_les_absents` ne touche jamais une
ligne existante : changer une intention dans le code n'atteint pas une
installation en service. L'écran Admin → Emails, lui, permet de la modifier —
c'est une capacité voulue — et cette modification ne changeait que le bandeau.

Un message pouvait donc partir de `contact@` en affichant « Information : rien
n'est attendu de vous », ou de `noreply@` en affichant « Action requise ». Le
lecteur voit les deux dans le même message.

## Qui gagne, et pourquoi

**L'intention servie**, celle de la ligne. C'est celle que le lecteur voit, et
celle qu'un administrateur a choisie s'il l'a changée. Le code reste le repli,
pour un modèle sans ligne ou dont la ligne ne la porte pas — jamais l'inverse,
sinon l'écran d'administration mentirait sur ce qu'il permet.
"""
from __future__ import annotations

import pytest

from app.seed.emails import (
    EXPEDITEUR_MUET,
    EXPEDITEUR_REPONSE,
    INTENTIONS_PAR_MODELE,
    expediteur_du_modele,
)


def test_l_intention_SERVIE_prime_sur_celle_du_code():
    """🔴 Le défaut lui-même.

    `compte_active` est déclaré `information` dans le code — donc `noreply@`. Si
    un administrateur le passe à « Action requise » depuis l'écran, l'adresse
    doit suivre : sinon le bandeau dit « agissez » et l'adresse dit « ne
    répondez pas ».
    """
    assert INTENTIONS_PAR_MODELE["compte_active"] == "information"
    assert expediteur_du_modele("compte_active") == EXPEDITEUR_MUET

    assert (
        expediteur_du_modele("compte_active", intention_servie="action_requise")
        == EXPEDITEUR_REPONSE
    ), (
        "l'adresse d'expédition ignore l'intention de la ligne : le bandeau et "
        "l'expéditeur se contrediraient dans le même message."
    )


def test_l_inverse_aussi_ce_n_est_pas_un_sens_unique():
    """Un modèle passé à « Information » doit devenir muet.

    Sans ce cas, une implémentation qui ne saurait qu'AJOUTER la possibilité de
    répondre passerait le test précédent en n'ayant rien compris.
    """
    assert expediteur_du_modele("ticket_syndic") == EXPEDITEUR_REPONSE
    assert (
        expediteur_du_modele("ticket_syndic", intention_servie="information")
        == EXPEDITEUR_MUET
    )


@pytest.mark.parametrize("servie", [None, "", "   "])
def test_sans_intention_servie_le_CODE_reprend_la_main(servie):
    """Le repli, pour un modèle sans ligne ou dont la ligne ne porte rien.

    ⚠️ La chaîne vide est un repli, **pas** une intention « aucun bandeau ». Les
    deux se ressemblent et ne veulent pas dire la même chose : une ligne qui ne
    déclare rien doit hériter du choix du code, pas devenir muette par accident.
    """
    assert expediteur_du_modele("compte_active", intention_servie=servie) == EXPEDITEUR_MUET
    assert expediteur_du_modele("ticket_syndic", intention_servie=servie) == EXPEDITEUR_REPONSE


def test_le_JETON_de_reponse_prime_sur_TOUT():
    """`Reply-To: tickets+<jeton>@` dit « répondez » — `noreply@` le contredirait.

    Cette règle existait avant (#703, #754) et ne doit pas être perdue en
    ajoutant l'intention servie : elle passe AVANT les deux.
    """
    assert (
        expediteur_du_modele(
            "compte_active", jeton_reponse="abc123", intention_servie="information"
        )
        == EXPEDITEUR_REPONSE
    ), (
        "un envoi portant une adresse de réponse de ticket partirait de "
        "`noreply@` : le message se contredirait lui-même."
    )


def test_l_ENVOI_transmet_bien_l_intention_de_la_ligne():
    """Le branchement, sans lequel tout ce fichier ne prouverait rien.

    ⚠️ Contrôle **statique** : reconstruire un envoi complet demanderait SMTP,
    une session et un modèle en base. Ce qui doit être vrai — que le point
    d'envoi passe `template.intention` — se lit dans le code.
    """
    import inspect

    from app.utils import email

    source = inspect.getsource(email)
    assert "intention_servie=template.intention" in source, (
        "le point d'envoi ne transmet plus l'intention de la ligne : l'adresse "
        "redeviendrait celle du code, et la seconde source reviendrait."
    )


def test_cas_zero_les_deux_expediteurs_sont_bien_DEUX():
    """Sans cet écart, tous les tests ci-dessus passeraient sans rien mesurer.

    `standards/04` §40 : la portée d'un contrôle fait partie du contrôle.
    """
    assert EXPEDITEUR_REPONSE != EXPEDITEUR_MUET
