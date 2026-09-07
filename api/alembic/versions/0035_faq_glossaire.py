"""0035 — FAQ : entrées Glossaire (acteurs de la copropriété + application & numérique)"""

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import text

CAT_ACT = "🏛️ Acteurs & Gouvernance"
CAT_NUM = "📱 Application & Numérique"

ENTRIES = [
    # ── Acteurs & Gouvernance ───────────────────────────────────────────────
    (
        CAT_ACT, 50,
        "Qu'est-ce que l'Assemblée Générale (AG) ?",
        "L'Assemblée Générale est la réunion annuelle obligatoire de tous les copropriétaires. "
        "Elle vote les décisions importantes : budget prévisionnel, gros travaux, élection du "
        "conseil syndical, choix du syndic. Chaque copropriétaire peut y assister ou se faire "
        "représenter par un mandataire.",
    ),
    (
        CAT_ACT, 51,
        "Qu'est-ce que le Conseil Syndical (CS) ?",
        "Le Conseil Syndical est un groupe de copropriétaires élus en AG pour représenter les "
        "résidents. Il contrôle la gestion du syndic, approuve certaines dépenses et peut "
        "prendre des décisions dans la limite du budget autorisé. Dans 5Hostachy, le CS gère "
        "les tickets, les accès, les documents et les actualités.",
    ),
    (
        CAT_ACT, 52,
        "Quelle est la différence entre le Conseil Syndical et le Syndic ?",
        "Le **Conseil Syndical** est composé de copropriétaires bénévoles élus. Le **Syndic** "
        "est un cabinet professionnel mandaté et rémunéré pour administrer la copropriété "
        "(comptabilité, contrats, entretien). Ce sont deux entités distinctes : le CS contrôle "
        "le syndic.",
    ),
    (
        CAT_ACT, 53,
        "Qu'est-ce qu'un lot ?",
        "Un lot désigne une unité de la copropriété appartenant à un propriétaire : un "
        "appartement, une cave ou un parking. Un même propriétaire peut posséder plusieurs "
        "lots. Dans l'application, vos lots apparaissent dans la section « Mon lot ».",
    ),
    (
        CAT_ACT, 54,
        "Qu'est-ce qu'un bâtiment ?",
        "La résidence est composée de plusieurs immeubles appelés bâtiments, chacun identifié "
        "par une lettre ou un nom. Certaines informations dans l'application (documents, "
        "événements, actualités) peuvent être ciblées sur un bâtiment précis.",
    ),
    (
        CAT_ACT, 55,
        "Quelle est la différence entre copropriétaire résident et copropriétaire bailleur ?",
        "Un **copropriétaire résident** habite lui-même son lot. Un **copropriétaire bailleur** "
        "loue son lot à un locataire, soit directement soit via un mandataire (agence). "
        "Les droits d'accès dans l'application sont identiques pour les deux.",
    ),
    (
        CAT_ACT, 56,
        "Qu'est-ce qu'un locataire dans l'application ?",
        "Un locataire est une personne qui loue un lot appartenant à un copropriétaire. "
        "Dans 5Hostachy, il dispose d'un accès limité : actualités, calendrier, demandes, "
        "FAQ et consultation de ses accès (badges). Il ne peut pas gérer les lots ni "
        "commander des accès directement.",
    ),
    (
        CAT_ACT, 57,
        "Qu'est-ce qu'un mandataire ?",
        "Un mandataire est un représentant du copropriétaire propriétaire (agence de location, "
        "notaire). Il a accès à l'application en lecture pour les lots dont il a la gestion, "
        "mais ne peut pas être admin ni membre du conseil syndical.",
    ),
    # ── Application & Numérique ─────────────────────────────────────────────
    (
        CAT_NUM, 60,
        "Qu'est-ce qu'un ticket (demande) ?",
        "Un ticket est une demande soumise par un résident : signalement de panne, nuisance, "
        "question ou situation urgente. Il suit un cycle de traitement : ouvert → en cours → "
        "résolu → fermé. Vous pouvez suivre l'avancement en temps réel dans « Mes demandes ».",
    ),
    (
        CAT_NUM, 61,
        "Qu'est-ce qu'un Vigik (badge d'accès) ?",
        "Le Vigik est un badge électronique qui ouvre les portails, halls et parkings de la "
        "résidence. Il est lié à votre lot. Depuis l'application, vous pouvez déclarer un "
        "badge perdu, demander un remplacement ou consulter vos badges actifs.",
    ),
    (
        CAT_NUM, 62,
        "Qu'est-ce qu'une télécommande de parking ?",
        "La télécommande permet d'ouvrir les portails du parking. Comme le badge Vigik, elle "
        "est associée à un lot. Vous pouvez en demander une via l'application ; la commande "
        "est soumise à validation du CS.",
    ),
    (
        CAT_NUM, 63,
        "Qu'est-ce qu'une PWA ? Puis-je installer 5Hostachy sur mon téléphone ?",
        "5Hostachy est une PWA (*Progressive Web App*) : une application web que vous pouvez "
        "installer sur l'écran d'accueil de votre smartphone sans passer par l'App Store ou "
        "Google Play. Sur iOS : Safari → Partager → « Sur l'écran d'accueil ». Sur Android : "
        "Chrome → menu ⋮ → « Ajouter à l'écran d'accueil ».",
    ),
    (
        CAT_NUM, 64,
        "Qu'est-ce que l'extranet de copropriété ?",
        "L'extranet est un espace en ligne sécurisé, rendu obligatoire par la loi ALUR, "
        "donnant aux résidents accès aux documents et informations de la copropriété. "
        "5Hostachy constitue cet extranet : PV d'AG, règlement, diagnostics, contrats "
        "d'entretien et bien plus y sont publiés par le CS.",
    ),
    (
        CAT_NUM, 65,
        "Qu'est-ce que le RGPD ? Mes données sont-elles protégées ?",
        "Le RGPD (Règlement Général sur la Protection des Données) est une loi européenne "
        "qui encadre la collecte et l'utilisation de vos données personnelles. Dans "
        "5Hostachy, seules les données nécessaires au fonctionnement de la résidence sont "
        "collectées. Vous pouvez consulter, modifier ou demander la suppression de vos "
        "données depuis Mon profil. La CNIL est l'autorité française de contrôle "
        "(www.cnil.fr).",
    ),
]


def upgrade() -> None:
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


def downgrade() -> None:
    for cat, _ordre, question, _reponse in ENTRIES:
        op.execute(
            text("DELETE FROM faq_item WHERE categorie = :cat AND question = :q")
            .bindparams(cat=cat, q=question)
        )
