"""Modèles d'e-mail : assemblage des quatre familles et intention de chacun.

`EMAIL_TEMPLATES` reste la surface publique historique — quatre migrations
figées l'importent depuis `app.seed`, ainsi que l'administration et les tests.
L'ordre de la liste n'a aucune portée : chaque modèle est inséré indépendamment,
et le seed ne pose que ce qui manque.
"""
from app.seed.emails.comptes import MODELES as _COMPTES
from app.seed.emails.exploitation import MODELES as _EXPLOITATION
from app.seed.emails.tickets import MODELES as _TICKETS
from app.seed.emails.vie_collective import MODELES as _VIE_COLLECTIVE

    # ── Styles inline mutualisés (CTA = Call-to-action button) ──
    # Les templates sont encapsulés dans le gabarit email.py (_wrap_email)
    # => pas besoin de <html>/<body>, juste le contenu riche.
EMAIL_TEMPLATES = [
    *_COMPTES,
    *_TICKETS,
    *_VIE_COLLECTIVE,
    *_EXPLOITATION,
]

# Intention de chaque modèle : ce qui est attendu du destinataire, affiché en
# tête du message par le gabarit commun (cf. `email.INTENTIONS`).
#
# Table séparée, et non sixième élément des tuples ci-dessous : les migrations
# 0104 et 0108 déballent `EMAIL_TEMPLATES` en cinq valeurs. Leur ajouter un
# élément les ferait lever `ValueError` sur une base neuve — et `start.sh` a
# `set -e`, donc le conteneur resterait bloqué au démarrage. Une migration est
# figée : c'est le code d'aujourd'hui qui doit rester compatible avec elle.
INTENTIONS_PAR_MODELE: dict[str, str] = {
    # On attend un geste du destinataire.
    "reinitialisation_mdp": "action_requise",
    "verification_email": "action_requise",
    "compte_en_attente": "action_requise",
    "ticket_bug_admin": "action_requise",
    "vigik_commande_recue": "action_requise",
    "annonce_hall": "action_requise",
    "nouvel_arrivant_bal": "action_requise",
    "alerte_systeme": "action_requise",
    # On attend une réponse écrite — ce sont les envois vers l'extérieur, ceux
    # dont le silence est justement le problème qu'on cherche à traiter.
    "ticket_syndic": "reponse_attendue",
    "ticket_externe": "reponse_attendue",
    "relance_syndic": "reponse_attendue",
    # On informe, sans rien attendre en retour.
    "compte_active": "information",
    "compte_refuse": "information",
    "ticket_statut_change": "information",
    "ticket_nouveau_message": "information",
    "reponse_communaute": "information",
    "idee_statut": "information",
    "vigik_accepte": "information",
    "vigik_refuse": "information",
    "calendrier_evenement_cree": "information",
    "document_publie": "information",
    "publication_syndic": "information",
    "publication_externe": "information",
    "acces_apparies_auto": "information",
}
