"""D'où part un message — `contact@` ou `noreply@` (#756).

Consigne de l'utilisateur, 05/09/2026 :

> « utiliser contact@5hostachy.fr ; réserver noreply@5hostachy.fr dans les cas
>   où il n'y a pas de réponse à obtenir »

Tout partait de `noreply@`, y compris ce qui espérait une réponse du syndic. Une
adresse qui s'annonce « ne répondez pas » décourage la réponse qu'on sollicite —
et quand elle arrive quand même, elle arrive dans une boîte dont le nom dit
qu'on ne la lit pas.

⚠️ Ces tests ne posent aucun réseau : la décision est **pure** (une intention et
un jeton en entrée, un genre d'expéditeur en sortie), et c'est ce qui permet de
l'éprouver modèle par modèle. Le tuyau, lui, est éprouvé par le fait qu'il n'y a
qu'un seul appel — `connexion_smtp(..., expediteur=…)`.
"""
from __future__ import annotations

from app.seed.emails import (
    EXPEDITEUR_MUET,
    EXPEDITEUR_PAR_INTENTION,
    EXPEDITEUR_REPONSE,
    INTENTIONS_PAR_MODELE,
    expediteur_du_modele,
)
from app.utils.smtp import adresse_expedition, adresses_a_tester

_CFG = {"smtp_from": "noreply@5hostachy.fr", "smtp_from_reponse": "contact@5hostachy.fr"}


def test_un_envoi_qui_attend_une_reponse_part_de_contact():
    """Le cas qui a motivé la consigne : le ticket envoyé au syndic."""
    assert expediteur_du_modele("ticket_syndic") == EXPEDITEUR_REPONSE
    assert expediteur_du_modele("relance_syndic") == EXPEDITEUR_REPONSE
    assert adresse_expedition(_CFG, EXPEDITEUR_REPONSE) == "contact@5hostachy.fr"


def test_un_envoi_qui_informe_seulement_part_de_noreply():
    """« Réserver noreply@ » — donc il sert, mais seulement là."""
    assert expediteur_du_modele("compte_active") == EXPEDITEUR_MUET
    assert expediteur_du_modele("document_publie") == EXPEDITEUR_MUET
    assert adresse_expedition(_CFG, EXPEDITEUR_MUET) == "noreply@5hostachy.fr"


def test_une_adresse_de_reponse_de_ticket_rend_l_envoi_parlant():
    """🔴 Un message ne peut pas dire deux choses contraires.

    `Reply-To: tickets+<jeton>@` dit « répondez à ce message », et le site sait
    rattacher cette réponse au dossier. L'expédier depuis `noreply@` se
    contredirait dans le même en-tête — quelle que soit l'intention déclarée.
    """
    assert expediteur_du_modele("ticket_nouveau_message") == EXPEDITEUR_MUET
    assert (
        expediteur_du_modele("ticket_nouveau_message", jeton_reponse="a" * 32)
        == EXPEDITEUR_REPONSE
    )


def test_un_modele_sans_intention_declaree_laisse_la_porte_ouverte():
    """Entre laisser une réponse possible et l'interdire par omission, on choisit
    la première : un modèle neuf ne doit pas devenir muet parce qu'on a oublié de
    l'inscrire dans la table.
    """
    assert expediteur_du_modele("modele_qui_nexiste_pas") == EXPEDITEUR_REPONSE


def test_sans_seconde_adresse_configuree_rien_ne_change():
    """Le repli, et c'est lui qui rend le lot sûr à déployer.

    Une installation qui n'a pas encore renseigné `contact@` continue d'envoyer
    exactement comme avant — jamais depuis une adresse vide, que le serveur
    refuserait pour un motif sans rapport avec le contenu.
    """
    cfg = {"smtp_from": "noreply@5hostachy.fr"}
    assert adresse_expedition(cfg, EXPEDITEUR_REPONSE) == "noreply@5hostachy.fr"
    assert adresse_expedition({**cfg, "smtp_from_reponse": "   "}, EXPEDITEUR_REPONSE) == (
        "noreply@5hostachy.fr"
    )


def test_chaque_intention_declaree_a_un_expediteur():
    """Cas zéro : une intention sans expéditeur retomberait sur le défaut sans
    que personne ne l'ait décidé — et la table ne servirait plus à rien.
    """
    intentions = set(INTENTIONS_PAR_MODELE.values())
    manquantes = intentions - set(EXPEDITEUR_PAR_INTENTION)
    assert not manquantes, (
        "ces intentions n'ont pas d'expéditeur déclaré, elles prendront le défaut "
        f"en silence : {sorted(manquantes)}"
    )


def test_le_bouton_de_test_exerce_les_DEUX_adresses():
    """🔴 Un contrôle doit exercer ce qui SERT.

    Le bouton « tester la configuration » n'envoyait que depuis `smtp_from`.
    Depuis que deux adresses servent, un serveur qui refuserait la seconde —
    cas courant quand elle est un **alias** et non un compte — aurait passé le
    test et échoué sur un vrai ticket, dans un journal que personne ne lit à ce
    moment-là.
    """
    assert adresses_a_tester(_CFG) == ["noreply@5hostachy.fr", "contact@5hostachy.fr"]


def test_une_seule_adresse_configuree_ne_fabrique_pas_un_second_envoi():
    """On n'envoie pas deux fois la même chose pour faire nombre : un test qui
    double sans rien prouver de plus finit par être perçu comme du bruit.
    """
    assert adresses_a_tester({"smtp_from": "a@x.fr"}) == ["a@x.fr"]
    assert adresses_a_tester({"smtp_from": "a@x.fr", "smtp_from_reponse": "a@x.fr"}) == ["a@x.fr"]
