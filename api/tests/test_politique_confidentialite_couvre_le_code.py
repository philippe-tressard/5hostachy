"""La politique de confidentialité nomme ce que le code collecte et transmet (#1034).

## 🔴 Pourquoi — RANG 1 (`standards/14`)

Au 19/09/2026, le gabarit de la politique ne mentionnait **rien** de ceci :

| Ce que le code fait | Occurrences dans le texte |
|---|---|
| télémétrie nominative (`TelemetryEvent.user_id`, page, action) | **0** |
| photos (`photo_url`, `photos_urls`) | **0** |
| badges Vigik et télécommandes rattachés à une personne | **0** |
| relais vers un groupe **WhatsApp** (Meta) | **0** |
| descriptions et **contrats envoyés à un fournisseur de modèle** | **0** |
| sous-traitant, service d'acheminement des courriels | **0** |

Et le paragraphe « Destinataires » affirmait que les données ne sont « ni cédées
à des tiers » — alors que le produit **transmet** un message et une photo à un
groupe de messagerie, et le texte d'un contrat à un service de modèle de
langage.

**Un texte servi aux utilisateurs qui ment est un défaut de rang 1**, et celui-ci
est public : il se lit sans compte.

## Ce que ce contrôle vérifie, et ce qu'il ne peut pas vérifier

Il confronte le **code** au **gabarit du produit** (`seed/contenus_legaux.py`) :
pour chaque capacité que le code porte, un mot-clé attendu dans le texte.

⚠️ Il ne lit **pas** le texte servi par une instance : celui-ci vit en base, et
l'ouvrir depuis un process tiers est interdit (règle d'or). Le gabarit est ce
que tout déploiement reçoit, et ce que les migrations de correction recopient —
c'est donc lui qui doit être exact.

⚠️ Il ne juge pas la **qualité juridique** du texte : il vérifie qu'une capacité
présente dans le code est **nommée**. Un paragraphe mal rédigé lui conviendrait.
Ce qu'il empêche, c'est le silence — et le silence est ce qui s'installe quand
une fonctionnalité arrive sans que personne relise la page légale.

## Le contrat que ce contrôle crée

**Une fonctionnalité qui exporte une donnée fait échouer la CI tant que le texte
ne la nomme pas.** C'est le seul moment où quelqu'un y pensera : au moment de
l'écrire.
"""

from __future__ import annotations

import pathlib
import re

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: (libellé, déclencheur dans le code, mots-clés dont AU MOINS UN doit figurer)
#:
#: Le déclencheur est ce qui rend la mention **obligatoire** : tant qu'il est
#: présent dans le code, le texte doit en parler. Le jour où une capacité
#: disparaît, son entrée peut partir — et le dernier test le signale.
EXIGENCES = [
    (
        "la télémétrie d'usage, nominative",
        ("models/telemetrie.py", "user_id"),
        ("télémétrie", "telemetrie", "mesure d'audience", "audience"),
    ),
    (
        "les photos téléversées",
        ("models/core.py", "photo_url"),
        ("photo", "image"),
    ),
    (
        "les objets d'accès rattachés à une personne",
        ("models/acces.py", "user_id"),
        ("badge", "vigik", "télécommande", "telecommande"),
    ),
    (
        "le relais vers un groupe de messagerie",
        ("utils/whatsapp.py", "def envoyer"),
        ("whatsapp", "messagerie instantanée", "groupe de discussion"),
    ),
    (
        "l'envoi de contenus à un service de modèle de langage",
        ("utils/llm_fournisseurs.py", "class "),
        #  ⚠️ PAS « IA » seul : les deux lettres figurent dans
        #  « intermédiaire », que le texte contient déjà — le contrôle passait
        #  au vert sur une capacité non mentionnée. Un mot-clé de deux lettres
        #  n'est pas un mot-clé, c'est une coïncidence.
        ("modèle de langage", "intelligence artificielle", "assistant ia"),
    ),
    (
        #  #1322 : la SEULE transmission sans geste. Le texte disait « rien ne l'est
        #  automatiquement » — voir aussi le test qui refuse cette phrase.
        "la mise en forme automatique des réponses reçues par courriel",
        ("utils/reponse_courriel.py", "def mettre_en_forme"),
        ("réponse reçue par courriel",),
    ),
    (
        "l'acheminement des courriels par un tiers",
        ("utils/smtp.py", "def "),
        #  ⚠️ Pas « courriel » ni « e-mail » seuls : le texte les emploie déjà
        #  pour les envois transactionnels. Ce qui doit être nommé ici, c'est le
        #  TIERS qui les achemine — ou la place laissée à l'instance pour le
        #  nommer.
        ("acheminement", "sous-traitant", "prestataire technique"),
    ),
    (
        "l'historique des envois de courriels",
        ("models/exploitation.py", "class HistoriqueEmail"),
        ("historique des envois", "journal des envois", "courriels envoyés"),
    ),
]


def _texte_du_gabarit() -> str:
    """La politique du gabarit, en minuscules et sans balises.

    ⚠️ La **valeur** de la chaîne, jamais le texte du fichier. Une première
    version lisait le source entre deux ancres : le gabarit étant une
    concaténation de littéraux, la découpe y coupe les mots — « historique des
    envois » se retrouvait scindé entre deux littéraux, et le contrôle déclarait
    la mention absente alors qu'elle était là.

    C'est la même faute que celle du contrôle de `FAMILLES`, le même jour :
    **vérifier le comportement, jamais l'artefact.** Le texte servi est la
    valeur ; la façon dont le fichier la découpe ne regarde personne.
    """
    from app.seed.contenus_legaux import DEFAULT_LEGAL

    brut = DEFAULT_LEGAL["politique_confidentialite"]
    sans_balises = re.sub(r"<[^>]+>", " ", brut)
    return re.sub(r"\s+", " ", sans_balises).lower()


def _declencheur_present(fichier: str, motif: str) -> bool:
    chemin = _APP / fichier
    if not chemin.exists():
        return False
    return motif in chemin.read_text(encoding="utf-8")


def test_le_controle_lit_bien_le_gabarit():
    """Cas zéro de la portée : un texte vide se lirait comme « tout est nommé »…

    …non : il échouerait sur tout. Mais un texte introuvable, lui, ferait lever
    l'analyse — et c'est ce qu'on vérifie ici, plutôt que de laisser le contrôle
    se tromper de fichier en silence.
    """
    texte = _texte_du_gabarit()
    assert len(texte) > 1500, (
        f"le gabarit lu ne fait que {len(texte)} caractères : le contrôle ne lit "
        "probablement pas la bonne clé de `DEFAULT_LEGAL`"
    )
    assert "responsable du traitement" in texte, "le texte lu n'est pas la politique"


def test_chaque_capacite_du_code_est_nommee_dans_la_politique():
    """Le défaut exact : six capacités, zéro mention."""
    texte = _texte_du_gabarit()
    manquantes = []
    for libelle, (fichier, motif), mots in EXIGENCES:
        if not _declencheur_present(fichier, motif):
            continue
        if not any(mot.lower() in texte for mot in mots):
            manquantes.append(
                f"  {libelle}\n"
                f"      déclencheur : {fichier} contient « {motif} »\n"
                f"      attendu dans le texte, au moins un de : {', '.join(mots)}"
            )

    assert not manquantes, (
        "Le code porte des capacités que la politique de confidentialité ne "
        "nomme pas :\n" + "\n".join(manquantes) + "\n\n"
        "Un texte servi aux utilisateurs qui passe sous silence ce qui est "
        "collecté ou transmis est un défaut de RANG 1 (`standards/14`). Le "
        "gabarit (`seed/contenus_legaux.py`) doit le dire ; ce que l'instance "
        "doit renseigner elle-même s'écrit « À RENSEIGNER »."
    )


def test_la_politique_ne_pretend_plus_qu_aucune_donnee_ne_sort():
    """🔴 Le mensonge le plus net du texte d'origine.

    Il affirmait que les données ne sont « ni cédées à des tiers » — alors que
    le produit transmet un message et une photo à un groupe de messagerie, et le
    texte d'un contrat à un service de modèle de langage.

    La formule n'est pas fausse en soi (rien n'est *cédé*, au sens commercial),
    et c'est ce qui la rend trompeuse : elle répond à une question que le
    lecteur ne pose pas, et laisse croire qu'elle répond à celle qu'il pose.
    """
    texte = _texte_du_gabarit()
    if "ni cédées à des tiers" not in texte:
        return  # la formule a été retirée : rien à encadrer

    #  Si la formule reste, elle doit être accompagnée de ce qui SORT vraiment.
    assert any(mot in texte for mot in ("sous-traitant", "destinataire technique", "transmis")), (
        "Le texte affirme que les données ne sont « ni cédées à des tiers » sans "
        "nommer les services qui en reçoivent pourtant : groupe de messagerie, "
        "fournisseur de modèle de langage, acheminement des courriels. La phrase "
        "est vraie au sens commercial et trompeuse au sens du RGPD."
    )


def test_la_politique_ne_pretend_pas_que_rien_ne_part_automatiquement():
    """🔴 #1322 : la réponse du syndic reçue par courriel part au modèle SANS geste.

    La phrase « rien ne l'est automatiquement : la demande est toujours un geste
    explicite » était vraie jusqu'au 25/09/2026. Un texte juridique qui reste
    juste le jour où le code change ne l'est que si un contrôle le tient.
    """
    if not _declencheur_present("utils/reponse_courriel.py", "def mettre_en_forme"):
        return
    assert "rien ne l'est automatiquement" not in _texte_du_gabarit(), (
        "La politique affirme qu'aucune transmission à l'assistant n'est "
        "automatique, alors que la mise en forme des réponses par courriel l'est."
    )


def test_aucune_exigence_ne_survit_a_sa_capacite():
    """Une exigence dont le déclencheur a disparu ferait exiger un texte inutile.

    Le jour où une capacité est retirée du produit, la politique doit pouvoir
    cesser d'en parler — et ce test le dit, plutôt que de laisser le texte
    décrire une fonctionnalité morte.
    """
    orphelines = [
        f"  {libelle} — déclencheur absent : {fichier} / « {motif} »"
        for libelle, (fichier, motif), _ in EXIGENCES
        if not _declencheur_present(fichier, motif)
    ]
    assert not orphelines, (
        "Ces exigences ne correspondent plus à aucune capacité du code :\n"
        + "\n".join(orphelines)
        + "\n\nRetirer l'entrée d'EXIGENCES, **et** le paragraphe correspondant "
        "de la politique : un texte qui décrit une fonctionnalité disparue est "
        "faux lui aussi."
    )


def test_le_gabarit_et_la_migration_lisent_le_MEME_texte():
    """🔴 Une seule rédaction, deux usages.

    Les paragraphes ajoutés le 20/09/2026 sont exposés par le seed sous
    `AJOUTS_1034`, et la migration 0199 les **lit** au lieu de les recopier. Une
    migration qui les aurait recopiés aurait créé deux rédactions parallèles d'un
    texte juridique — et c'est alors le texte **servi** qui aurait divergé du
    gabarit, sans que rien ne le signale.

    Ce test tient le contrat dans les deux sens : chaque paragraphe exposé est
    bien dans le gabarit, et la migration ne contient aucun fragment de texte en
    dur.
    """
    import pathlib as _pathlib

    from app.seed.contenus_legaux import AJOUTS_1034, DEFAULT_LEGAL

    gabarit = DEFAULT_LEGAL["politique_confidentialite"]
    absents = [ajout[:60] for _ancre, ajout in AJOUTS_1034 if ajout not in gabarit]
    assert not absents, (
        "Ces paragraphes sont exposés à la migration mais ne figurent pas dans "
        "le gabarit : le texte servi par une nouvelle instance et celui servi "
        "après migration ont divergé.\n  " + "\n  ".join(absents)
    )

    migration = next((_APP.parent / "alembic" / "versions").glob("0199_*.py"), None)
    assert migration is not None, "la migration 0199 a disparu"
    source = migration.read_text(encoding="utf-8")
    assert "AJOUTS_1034" in source, (
        "la migration 0199 ne lit plus `AJOUTS_1034` : si elle recopie le texte, "
        "les deux rédactions divergeront au premier ajustement"
    )
    #  Un fragment de balisage dans la migration signerait une recopie. On
    #  cherche `<li><strong>` : présent dans les paragraphes, absent d'un code
    #  qui se contente de les lire.
    corps = source[source.index("def upgrade") :]
    assert "<li><strong>" not in corps, (
        "la migration 0199 porte du balisage en dur : elle recopie le texte au "
        "lieu de le lire dans le seed"
    )
    assert _pathlib.Path(migration).name.startswith("0199"), "numéro inattendu"


def test_la_duree_annoncee_des_courriels_est_celle_que_le_code_applique():
    """La politique a dit « aucune purge automatique » alors que l'historique des
    envois était purgé à 90 jours (#1073, 24/09/2026) : un texte faux dans
    l'autre sens. La durée se lit désormais dans le code, et le texte la répète.
    """
    from app.seed.contenus_legaux import CONSERVATION_COURRIELS, DEFAULT_LEGAL
    from app.utils.maintenance import CONSERVATION_COURRIELS_JOURS

    politique = DEFAULT_LEGAL["politique_confidentialite"]
    assert f"{CONSERVATION_COURRIELS_JOURS}\xa0jours" in CONSERVATION_COURRIELS, (
        "la politique n'annonce plus la durée que `purger()` applique"
    )
    assert CONSERVATION_COURRIELS in politique
    assert "Aucune purge automatique" not in politique
