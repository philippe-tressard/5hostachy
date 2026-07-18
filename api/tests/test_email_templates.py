"""Garde-fou préventif : contrat des variables des templates email.

Contexte (cf. point 9 du pré-check MEP) : les emails partent en BackgroundTask
et échouent silencieusement si un template Jinja2 référence une variable que le
contexte du point d'appel ne fournit pas. Ce bug s'est produit deux fois en
12 jours (reinitialisation_mdp le 03/06, ticket_statut_change le 15/06 — tous
deux `'destinataire' is undefined`).

Ce test verrouille, pour chaque template de `seed.EMAIL_TEMPLATES`, l'ensemble
exact des variables de premier niveau qu'il utilise (EXPECTED_VARS). Toute
modification d'un template qui ajoute/retire une variable casse ce test et
force une revue consciente :

    → si tu ajoutes `{{ ma_var.x }}` à un template, ajoute `ma_var` à
      EXPECTED_VARS ET vérifie que le `send_email(code=...)` correspondant
      passe bien `ma_var` dans son `context`.

Limite assumée : ce test garde le **côté template**. Le côté point d'appel
(une clé oubliée dans le `context`) reste couvert *a posteriori* par le point 9
(inspection de `historique_email`). Les deux forment une défense en profondeur.
"""
import pytest
from jinja2 import BaseLoader, meta
from jinja2.sandbox import SandboxedEnvironment

from app.seed import EMAIL_TEMPLATES

# Variables injectées d'office par send_email/_group (base_ctx dans email.py)
BASE_CTX_VARS = {"annee", "app", "residence"}

# Contrat figé : variables de premier niveau requises par chaque template.
# Extrait de seed.EMAIL_TEMPLATES — à mettre à jour consciemment lors de toute
# modification d'un template (en alignant le point d'appel send_email).
EXPECTED_VARS: dict[str, set[str]] = {
    "invitation_resident": {"destinataire", "lien"},
    "reinitialisation_mdp": {"destinataire", "lien"},
    "compte_en_attente": {"utilisateur"},
    "compte_active": {"destinataire"},
    "compte_refuse": {"destinataire"},
    "locataire_validation_demande": {"lot", "destinataire", "locataire"},
    "locataire_valide": {"destinataire"},
    "locataire_refuse": {"destinataire"},
    "ticket_cree_cs": {"auteur", "ticket"},
    "ticket_bug_admin": {"auteur", "ticket"},
    "ticket_syndic": {
        "messages", "date_creation", "commentaire", "is_commentaire", "ticket",
        "fichiers", "reference_copro", "date_commentaire", "historique", "auteur",
    },
    "ticket_statut_change": {"destinataire", "ticket"},
    "ticket_nouveau_message": {"ticket", "auteur_action", "message"},
    "reponse_communaute": {"reponse"},
    "idee_statut": {"idee"},
    "ticket_urgence_bailleur": {"lot", "destinataire", "ticket"},
    "relance_syndic": {"tickets", "reference_copro", "civilite", "nom_gestionnaire"},
    "vigik_commande_recue": {"lot", "demandeur", "type"},
    "vigik_accepte": {"destinataire", "type"},
    "vigik_refuse": {"type", "destinataire", "motif"},
    "calendrier_evenement_cree": {"evenement"},
    "document_publie": {"document"},
    "publication_syndic": {
        "date_publication", "evolutions", "commentaire", "is_commentaire",
        "fichiers", "reference_copro", "publication", "date_commentaire", "auteur",
    },
    "digest_quotidien": {"destinataire"},
    "digest_hebdomadaire": {"destinataire"},
    "sauvegarde_echec": {"date", "erreur"},
    "alerte_espace_disque": {"espace_total", "espace_disponible", "pourcentage_libre"},
    "verification_email": {"expire_heures", "lien", "prenom"},
}

_env = SandboxedEnvironment(loader=BaseLoader())


def _required_vars(sujet: str | None, corps_html: str | None) -> set[str]:
    """Variables de premier niveau référencées par le template (hors base_ctx)."""
    source = f"{sujet or ''} {corps_html or ''}"
    ast = _env.parse(source)  # lève TemplateSyntaxError si le template est cassé
    return meta.find_undeclared_variables(ast) - BASE_CTX_VARS


def test_tous_les_templates_ont_un_contrat():
    """Chaque template de seed.EMAIL_TEMPLATES doit avoir une entrée EXPECTED_VARS."""
    codes = {row[0] for row in EMAIL_TEMPLATES}
    sans_contrat = codes - set(EXPECTED_VARS)
    assert not sans_contrat, (
        f"Templates sans contrat déclaré dans EXPECTED_VARS : {sorted(sans_contrat)}. "
        "Ajoute leur jeu de variables et vérifie le point d'appel send_email."
    )


@pytest.mark.parametrize("row", EMAIL_TEMPLATES, ids=lambda r: r[0])
def test_template_respecte_son_contrat(row):
    """Le template ne référence ni plus ni moins que les variables déclarées."""
    code, _libelle, sujet, corps_html, _desactivable = row
    if code not in EXPECTED_VARS:
        pytest.skip("contrat absent — couvert par test_tous_les_templates_ont_un_contrat")
    needs = _required_vars(sujet, corps_html)
    assert needs == EXPECTED_VARS[code], (
        f"{code}: variables utilisées {sorted(needs)} ≠ contrat {sorted(EXPECTED_VARS[code])}.\n"
        f"Si la modification est voulue : mets à jour EXPECTED_VARS ET assure-toi que "
        f"le send_email(code={code!r}) fournit exactement ces variables dans son context."
    )
