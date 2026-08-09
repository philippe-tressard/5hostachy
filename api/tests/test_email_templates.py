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
    "reinitialisation_mdp": {"destinataire", "lien"},
    "compte_en_attente": {"utilisateur"},
    "compte_active": {"destinataire"},
    "compte_refuse": {"destinataire"},
    "ticket_bug_admin": {"auteur", "ticket"},
    "ticket_syndic": {
        "messages", "date_creation", "commentaire", "is_commentaire", "ticket",
        "fichiers", "reference_copro", "date_commentaire", "historique", "auteur",
    },
    "ticket_statut_change": {"destinataire", "ticket"},
    "ticket_nouveau_message": {"ticket", "auteur_action", "message"},
    "reponse_communaute": {"reponse"},
    "idee_statut": {"idee"},
    "relance_syndic": {
        "tickets", "reference_copro", "interlocuteurs", "anciennete",
    },
    "vigik_commande_recue": {"lot", "demandeur", "type"},
    "vigik_accepte": {"destinataire", "type"},
    "vigik_refuse": {"type", "destinataire", "motif"},
    "calendrier_evenement_cree": {"evenement"},
    "document_publie": {"document"},
    "publication_syndic": {
        "date_publication", "evolutions", "commentaire", "is_commentaire",
        "fichiers", "reference_copro", "publication", "date_commentaire", "auteur",
    },
    # Remplace `sauvegarde_echec` et `alerte_espace_disque` : le contrôle
    # quotidien découvre les problèmes ensemble et n'envoie qu'un message.
    "alerte_systeme": {"problemes", "nb_problemes", "date_controle"},
    "verification_email": {"expire_heures", "lien", "prenom"},
    "annonce_hall": {"annonce", "auteur"},
    # Prévient le gestionnaire du site quand l'appariement a créé des accès
    # sans validation préalable. `resultat` porte aussi les accords en français,
    # calculés au point d'appel : un modèle n'a pas à porter la grammaire.
    "acces_apparies_auto": {"utilisateur", "resultat"},
    # Les trois modèles destinés à des destinataires EXTERNES (syndic, tiers),
    # longtemps déclarés en migration seulement et donc sans contrat ici.
    "nouvel_arrivant_bal": {"nom_complet", "batiment", "ancien_resident", "reference_copro"},
    "publication_externe": {
        "date_publication", "evolutions", "commentaire", "is_commentaire",
        "fichiers", "publication", "date_commentaire", "auteur",
    },
    "ticket_externe": {
        "messages", "date_creation", "commentaire", "is_commentaire", "ticket",
        "fichiers", "date_commentaire", "auteur",
    },
}

_env = SandboxedEnvironment(loader=BaseLoader())


def _required_vars(sujet: str | None, corps_html: str | None) -> set[str]:
    """Variables de premier niveau référencées par le template (hors base_ctx)."""
    source = f"{sujet or ''} {corps_html or ''}"
    ast = _env.parse(source)  # lève TemplateSyntaxError si le template est cassé
    return meta.find_undeclared_variables(ast) - BASE_CTX_VARS


def test_chaque_modele_declare_son_intention():
    """Tout modèle doit dire ce qu'il attend du destinataire.

    Le bandeau d'intention ne vaut que s'il est là partout : un seul e-mail qui
    n'annonce pas la couleur ramène le lecteur au tri à l'aveugle, et comme
    l'absence d'intention ne rend simplement aucun bandeau, rien ne le
    signalerait. C'est le genre d'oubli qui arrive au modèle suivant, pas à
    ceux d'aujourd'hui.
    """
    from app.seed import INTENTIONS_PAR_MODELE
    from app.utils.email import INTENTIONS

    codes = {row[0] for row in EMAIL_TEMPLATES}
    sans_intention = codes - set(INTENTIONS_PAR_MODELE)
    assert not sans_intention, (
        f"Modèles sans intention déclarée : {sorted(sans_intention)}. Ajoute-les "
        "à `seed.INTENTIONS_PAR_MODELE` — information, action_requise, "
        "reponse_attendue ou archive."
    )

    inconnues = {
        code: valeur
        for code, valeur in INTENTIONS_PAR_MODELE.items()
        if valeur not in INTENTIONS
    }
    assert not inconnues, (
        f"Intentions non reconnues par le gabarit : {inconnues}. Elles ne "
        "rendraient aucun bandeau, en silence."
    )

    orphelines = set(INTENTIONS_PAR_MODELE) - codes
    assert not orphelines, (
        f"Intentions déclarées pour des modèles inexistants : {sorted(orphelines)}."
    )


def test_le_bandeau_dintention_est_rendu_dans_le_gabarit():
    """Cas zéro : le bandeau doit réellement apparaître dans le HTML envoyé."""
    from app.utils.email import INTENTIONS, _wrap_email

    html = _wrap_email(
        "<p>corps</p>", "Résidence", "https://exemple.fr", "", 2026,
        intention="action_requise",
    )
    assert INTENTIONS["action_requise"][0] in html, (
        "Le bandeau d'intention n'apparaît pas dans le gabarit : les modèles "
        "déclarent une intention que personne n'affiche."
    )
    # Une intention absente ou inconnue ne doit rien ajouter, jamais une
    # étiquette fausse.
    for valeur in ("", None, "inconnue"):
        neutre = _wrap_email(
            "<p>corps</p>", "Résidence", "https://exemple.fr", "", 2026, intention=valeur
        )
        assert all(lib not in neutre for lib, _, _ in INTENTIONS.values()), (
            f"Une intention {valeur!r} affiche pourtant un bandeau."
        )


def test_tous_les_templates_ont_un_contrat():
    """EXPECTED_VARS et EMAIL_TEMPLATES doivent lister exactement les mêmes codes.

    La vérification est **bidirectionnelle**, et le second sens est le plus
    important depuis que les modèles vivent dans quatre modules assemblés par
    `seed/emails/__init__.py` (05/08/2026) : une famille oubliée à l'assemblage
    ferait disparaître cinq ou six modèles d'un coup.

    Rien ne l'aurait vu. Les contrôles qui comparent la base à `EMAIL_TEMPLATES`
    comparent alors une liste amputée à elle-même et restent verts — vérifié en
    retirant une famille, ils passaient tous. EXPECTED_VARS est la seule liste de
    codes maintenue **indépendamment** de l'assemblage : c'est elle qui sert
    d'ancre, et c'est ce qui rend ce test non circulaire (`standards/04` §16).
    """
    codes = {row[0] for row in EMAIL_TEMPLATES}
    sans_contrat = codes - set(EXPECTED_VARS)
    assert not sans_contrat, (
        f"Templates sans contrat déclaré dans EXPECTED_VARS : {sorted(sans_contrat)}. "
        "Ajoute leur jeu de variables et vérifie le point d'appel send_email."
    )

    disparus = set(EXPECTED_VARS) - codes
    assert not disparus, (
        f"Modèles déclarés dans EXPECTED_VARS mais absents de EMAIL_TEMPLATES : "
        f"{sorted(disparus)}. Soit une famille manque à l'assemblage de "
        "`seed/emails/__init__.py` — et ces e-mails ne partiront plus du tout —, "
        "soit la suppression est voulue et EXPECTED_VARS doit suivre, avec la "
        "migration qui retire les modèles de la base."
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
