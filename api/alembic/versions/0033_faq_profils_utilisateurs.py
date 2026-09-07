"""0033 — FAQ : entrées par profil utilisateur (résident, mandataire, locataire)"""

revision = '0033'
down_revision = '0032'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import text

CAT_APP   = "📱 Application 5Hostachy"
CAT_RES   = "🏠 Copropriétaire résident"
CAT_MAN   = "📋 Copropriétaire mandataire"
CAT_LOC   = "🔑 Locataire"

ENTRIES = [
    # ── Application 5Hostachy ───────────────────────────────────────────────
    (
        CAT_APP, 13,
        "Comment modifier mon adresse e-mail ou mon téléphone ?",
        "Allez dans Mon profil (icône en bas de menu) et mettez à jour vos coordonnées. "
        "Certaines modifications peuvent nécessiter une validation par le CS.",
    ),
    (
        CAT_APP, 14,
        "Je n'ai plus accès à mon compte. Que faire ?",
        "Depuis la page de connexion, cliquez « Mot de passe oublié » et entrez votre adresse "
        "e-mail pour recevoir un lien de réinitialisation. Vérifiez vos spams si vous ne "
        "recevez rien.",
    ),
    (
        CAT_APP, 15,
        "À quoi sert la plateforme 5Hostachy ?",
        "C'est votre espace numérique de résidence : suivre les actualités, soumettre des "
        "demandes au conseil syndical, gérer vos accès (badges, télécommandes) et consulter "
        "les documents de la copropriété — le tout en un seul endroit.",
    ),
    # ── Copropriétaire résident ─────────────────────────────────────────────
    (
        CAT_RES, 20,
        "Comment soumettre une demande (panne, nuisance, question) ?",
        "Allez dans Mes demandes → Nouvelle demande, choisissez une catégorie (panne, "
        "nuisance, question, urgence), décrivez le problème et envoyez. Vous pouvez suivre "
        "l'avancement depuis le même écran.",
    ),
    (
        CAT_RES, 21,
        "Où trouver mes informations de lot (appartement, cave, parking) ?",
        "Dans Mes lots : vous y voyez la liste de vos biens dans la résidence avec leur "
        "étage, bâtiment et référence.",
    ),
    (
        CAT_RES, 22,
        "Comment commander un badge ou une télécommande supplémentaire ?",
        "Dans Accès & badges : cliquez sur « Demander un accès », choisissez le type "
        "(télécommande ou Vigik), indiquez la quantité. Votre demande est soumise à "
        "validation du CS.",
    ),
    (
        CAT_RES, 23,
        "Où voir les prochains événements (AG, travaux…) ?",
        "Dans Calendrier : tous les événements planifiés y sont publiés par le CS ou le syndic.",
    ),
    (
        CAT_RES, 24,
        "Comment contacter le syndic en cas d'urgence ?",
        "Consultez Annuaire → Syndic pour trouver le nom, la fonction et le téléphone de "
        "l'interlocuteur principal.",
    ),
    # ── Copropriétaire mandataire ───────────────────────────────────────────
    (
        CAT_MAN, 30,
        "Quelle est la différence entre mon compte et celui de mon locataire ?",
        "Votre compte a le rôle copropriétaire mandataire : vous accédez à la gestion de "
        "vos lots et pouvez demander des accès. Votre locataire a un compte locataire avec "
        "des droits limités à son usage quotidien (demandes, calendrier, FAQ).",
    ),
    (
        CAT_MAN, 31,
        "Comment voir la liste de mes lots et vérifier leur statut ?",
        "Dans Mes lots : tous vos biens apparaissent (appartement, cave, parking) avec leur "
        "situation dans la résidence.",
    ),
    (
        CAT_MAN, 32,
        "Puis-je commander un badge pour mon locataire ?",
        "Oui, depuis Accès & badges : soumettez une demande au nom du lot concerné. "
        "La livraison du badge reste soumise à la validation du CS.",
    ),
    (
        CAT_MAN, 33,
        "Puis-je accéder aux documents de la résidence ?",
        "Oui, dans Ma résidence : règlement de copropriété, diagnostics, comptes-rendus "
        "d'AG et autres documents publiés par le CS y sont disponibles.",
    ),
    (
        CAT_MAN, 34,
        "Comment participer aux sondages et boîte à idées ?",
        "Dans Communauté : les sondages ouverts par le CS s'y trouvent. Vos réponses "
        "contribuent aux décisions de la copropriété.",
    ),
    # ── Locataire ───────────────────────────────────────────────────────────
    (
        CAT_LOC, 40,
        "Quelles fonctionnalités sont disponibles pour moi ?",
        "Actualités, Calendrier, Mes demandes, Annuaire, Ma résidence (documents publics), "
        "Accès & badges (consultation de vos accès), Communauté et FAQ.",
    ),
    (
        CAT_LOC, 41,
        "Je ne vois pas la page « Mes lots ». Est-ce normal ?",
        "Oui. La gestion des lots appartient au copropriétaire. Vous n'avez pas accès à "
        "cette section.",
    ),
    (
        CAT_LOC, 42,
        "Comment signaler un problème dans mon appartement ou dans les parties communes ?",
        "Dans Mes demandes → Nouvelle demande : décrivez le problème (panne, nuisance…). "
        "Le CS traite et suit votre demande.",
    ),
    (
        CAT_LOC, 43,
        "Puis-je demander un badge ou une télécommande ?",
        "Non directement — c'est votre propriétaire qui fait la demande depuis son compte. "
        "Si vous avez besoin d'un accès, contactez-le.",
    ),
    (
        CAT_LOC, 44,
        "Comment savoir si une intervention est prévue dans l'immeuble ?",
        "Consultez Calendrier et Actualités : le CS y publie les travaux, coupures d'eau ou "
        "toute intervention planifiée.",
    ),
    (
        CAT_LOC, 45,
        "Puis-je modifier mes informations personnelles ?",
        "Oui, depuis Mon profil : vous pouvez mettre à jour votre e-mail, téléphone et mot "
        "de passe. Toute modification importante peut nécessiter une validation.",
    ),
]


def upgrade():
    conn = op.get_bind()
    for cat, ordre, question, reponse in ENTRIES:
        exists = conn.execute(
            text("SELECT 1 FROM faq_item WHERE categorie = :cat AND question = :q"),
            {"cat": cat, "q": question}
        ).fetchone()
        if not exists:
            op.execute(
                text(
                    "INSERT INTO faq_item (categorie, question, reponse, ordre, actif, cree_le, mis_a_jour_le) "
                    "VALUES (:cat, :q, :r, :o, 1, datetime('now'), datetime('now'))"
                ).bindparams(cat=cat, q=question, r=reponse, o=ordre)
            )


def downgrade():
    for cat, _ordre, question, _reponse in ENTRIES:
        op.execute(
            text("DELETE FROM faq_item WHERE categorie = :cat AND question = :q")
            .bindparams(cat=cat, q=question)
        )
