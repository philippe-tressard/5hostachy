"""Les mentions légales identifient quelqu'un — et le gabarit ne peut pas revenir.

## 🔴 Le défaut, et pourquoi il n'avait aucun symptôme (03/09/2026)

`/mentions-legales` est une page **publique** : lisible sans compte, indexable.
Elle servait le gabarit générique du produit, qui disait en toutes lettres :

> « L'identité de l'éditeur correspond à la copropriété ou au syndic bénévole qui
>   gère cette instance. »

Ce n'est pas une mention, c'est une **instruction pour en rédiger une**. Elle
décrit ce qu'il faudrait écrire au lieu de l'écrire. Aucun lecteur ne pouvait
identifier l'éditeur, le directeur de la publication ni l'hébergeur — les trois
que la LCEN impose de pouvoir identifier.

Et rien ne le signalait : la page s'affiche, elle a l'air complète, personne ne
la lit jusqu'à ce que quelqu'un ait une raison de chercher qui contacter. C'est
un lecteur qui l'a vu, pas un contrôle.

## Ce que ce fichier tient

1. **Le gabarit se déclare comme tel.** `DEFAULT_LEGAL` reste générique — le seed
   porte le PRODUIT, réutilisable sous licence MIT, et y écrire un nom d'éditeur
   l'imposerait à tout autre déploiement. Mais il doit dire « À RENSEIGNER »,
   jamais faire semblant.

2. 🔴 **Les deux listes de marqueurs sont d'accord.** La migration 0170 ne
   remplace le texte que s'il porte encore un marqueur de gabarit — c'est ce qui
   l'empêche d'écraser une rédaction faite à la main. Si le seed changeait de
   formulation sans que la migration suive, celle-ci deviendrait **inerte sans
   rien dire** : exactement le piège que `test_migration_0162` a déjà attrapé
   ailleurs.

3. **Les mentions écrites nomment vraiment quelqu'un** — un nom, un moyen de
   contact, une réponse sur l'hébergement.

## Ce qu'il ne peut pas vérifier

Que la page servie en PRODUCTION porte ces mentions : la base n'est pas
accessible depuis les tests, et une migration peut avoir été suivie d'une
retouche en administration. Le relevé se fait à la main :

    curl -s https://5hostachy.fr/api/config/legal

Une limite nommée vaut mieux qu'une limite tue — sans ce paragraphe, un vert ici
se lirait « le site est conforme », ce qu'il ne dit pas.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from app.seed.contenus_legaux import DEFAULT_LEGAL

_RACINE = Path(__file__).resolve().parents[1]
_MIGRATION = _RACINE / "alembic" / "versions" / "0170_mentions_legales_reelles.py"
_MIGRATION_POLITIQUE = (
    _RACINE / "alembic" / "versions" / "0171_politique_confidentialite_exacte.py"
)


def _charger(chemin: Path, nom: str):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_migration():
    return _charger(_MIGRATION, "mig0170")


def _texte_nu(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def test_le_gabarit_du_seed_se_declare_comme_gabarit():
    """Il a le droit d'être vide, pas celui de faire semblant.

    Les trois rubriques que la LCEN impose doivent porter la marque, sans quoi la
    page publique paraîtrait complète en n'identifiant personne.
    """
    texte = _texte_nu(DEFAULT_LEGAL["mentions_legales"])
    assert texte.count("À RENSEIGNER") >= 3, (
        "le gabarit ne se signale pas sur les trois rubriques obligatoires "
        "(éditeur, directeur de la publication, hébergeur) :\n" + texte[:400]
    )


def test_le_gabarit_ne_pretend_plus_identifier_quelqu_un():
    """La formulation d'origine, mot pour mot, ne doit pas revenir."""
    texte = DEFAULT_LEGAL["mentions_legales"]
    for tournure in (
        "correspond à la copropriété ou au syndic bénévole",
        "l'organisation ou la personne physique",
        "l'administrateur désigné de l'instance",
    ):
        assert tournure not in texte, (
            f"le gabarit décrit à nouveau ce qu'il faudrait écrire : « {tournure} »"
        )


def test_les_marqueurs_de_la_migration_reconnaissent_le_gabarit():
    """🔴 Le cœur du fichier — deux listes qui doivent rester d'accord.

    La migration n'écrit que si elle RECONNAÎT un gabarit. Si le seed changeait de
    formulation sans qu'elle suive, elle ne reconnaîtrait plus rien : un
    déploiement neuf garderait le gabarit, et la migration passerait au vert en
    n'ayant rien fait.
    """
    marqueurs = _module_migration()._MARQUEURS_GABARIT
    assert marqueurs, "la migration ne reconnaît plus aucun gabarit"
    gabarit = DEFAULT_LEGAL["mentions_legales"]
    assert any(m in gabarit for m in marqueurs), (
        "AUCUN marqueur de la migration 0170 ne correspond au gabarit du seed :\n"
        f"  marqueurs : {marqueurs}\n"
        "La migration ne remplacerait donc jamais un déploiement neuf, sans que "
        "rien ne le signale."
    )


def test_les_mentions_ecrites_nomment_vraiment_quelqu_un():
    """Ce que la migration pose doit répondre aux questions, pas les reformuler.

    ⚠️ Ce test lit la migration 0170, qui reste telle qu'elle a été appliquée —
    on ne réécrit pas une migration. Le texte SERVI aujourd'hui est celui de
    0173, qui a remplacé le nom par l'entité : voir le test suivant.
    """
    texte = _texte_nu(_module_migration().MENTIONS)
    for quoi, motif in (
        ("un nom d'éditeur", r"Philippe Tressard"),
        ("un moyen de contact", r"contact@5hostachy\.fr"),
        ("une réponse sur l'hébergement", r"auto-héberg"),
        ("l'intermédiaire technique", r"Cloudflare"),
    ):
        assert re.search(motif, texte), f"les mentions ne donnent pas {quoi}"
    #  Et elles ne doivent surtout pas retomber dans le gabarit.
    assert "À RENSEIGNER" not in texte


def test_la_migration_n_ecrase_PAS_une_redaction_a_la_main():
    """La garde d'idempotence, vérifiée sur la forme.

    Sans elle, chaque déploiement remettrait le texte de la migration par-dessus
    ce que l'administration a saisi — le défaut du seed des périmètres, qui
    reposait son arborescence à chaque démarrage et annulait les suppressions
    (13/08/2026).
    """
    source = _MIGRATION.read_text(encoding="utf-8")
    assert "_MARQUEURS_GABARIT" in source
    assert "if not any(marqueur in actuel" in source, (
        "la migration ne teste plus la présence d'un marqueur avant d'écrire : "
        "elle écraserait une rédaction faite depuis Admin → Légal"
    )


# ── La politique de confidentialité (migration 0171) ─────────────────────────

def test_le_seed_n_affirme_plus_qu_aucune_donnee_ne_sort_de_l_UE():
    """🔴 L'affirmation était FAUSSE, et deux pages du site se contredisaient.

    Les mentions légales déclarent Cloudflare, Inc. (États-Unis) comme
    intermédiaire technique. La politique disait « Aucun transfert hors UE ». Le
    fait n'avait pas changé — seulement le moment où on l'a écrit quelque part.

    ⚠️ Le texte DÉCRIT le relais, il ne le QUALIFIE pas : savoir si cela
    constitue un transfert au sens du chapitre V est une question de droit, et
    `standards/14` interdit de l'improviser.
    """
    assert "Aucun transfert hors UE" not in DEFAULT_LEGAL["politique_confidentialite"]


def test_la_politique_du_seed_reste_un_gabarit_declare():
    """Le seed porte le PRODUIT : il ne nomme aucun responsable, et le dit."""
    politique = DEFAULT_LEGAL["politique_confidentialite"]
    assert politique.count("À RENSEIGNER") >= 3, (
        "le gabarit de la politique ne se signale pas sur le responsable du "
        "traitement, l'hébergement et l'acheminement"
    )
    assert "Philippe Tressard" not in politique, (
        "le seed nomme un éditeur : tout autre déploiement publierait des "
        "mentions FAUSSES — le seed porte le produit, la base porte l'instance"
    )


def test_les_corrections_de_0171_sont_bien_formees():
    """🔴 CE TEST A ÉTÉ RÉÉCRIT DANS SON PROPRE LOT, et c'est la leçon.

    La première version comparait les fragments cherchés par la migration au seed
    tel que `git show HEAD:` le portait — pour vérifier qu'ils correspondaient
    bien au texte présent en base. L'intention était juste. Le mécanisme ne
    l'était pas : **`HEAD` avance**. Dès le commit du lot, HEAD portait le seed
    CORRIGÉ, les fragments n'y étaient plus, et le test échouait sur son propre
    succès.

    Un contrôle dont le verdict dépend de l'endroit où l'on se trouve dans
    l'historique n'est pas un contrôle, c'est une coïncidence.

    ⚠️ CE QUI RESTE INVÉRIFIABLE EN CI, ET QU'IL FAUT DONC DIRE : que les
    fragments correspondent au texte réellement EN BASE. Une espace, une
    insécable ou un accent mal recopié rendrait la migration inerte — au vert,
    sans rien changer, et la page resterait fausse. Cela se constate en
    production, et nulle part ailleurs :

        curl -s https://5hostachy.fr/api/config/legal

    Ce que ce test tient, lui : les corrections sont bien formées, et elles
    changent quelque chose.
    """
    corrections = _charger(_MIGRATION_POLITIQUE, "mig0171").CORRECTIONS
    assert corrections, "la migration ne corrige plus rien"
    for avant, apres in corrections:
        assert avant.strip(), "un fragment cherché est vide : il correspondrait partout"
        assert avant != apres, "une correction qui ne change rien est une migration inerte"
        assert len(avant) > 40, (
            f"fragment trop court pour être sûr de sa cible : {avant!r}"
        )
    #  Et le défaut nommé par le lot doit bien être celui qu'on corrige.
    assert any("Aucun transfert hors UE" in avant for avant, _ in corrections)
    assert not any("Aucun transfert hors UE" in apres for _, apres in corrections)


# ── Aucune personne physique nommée sur une page publique (0173) ─────────────

_MIGRATION_ANONYME = (
    _RACINE / "alembic" / "versions" / "0173_editeur_sans_nom_de_personne.py"
)


def test_l_editeur_publie_n_est_plus_une_personne_nommee():
    """🔴 Demandé le 03/09/2026 : *« peux-tu enlever mon nom des mentions »*.

    La page est **publique et indexable**. Y publier le nom d'une personne
    physique, pour un outil interne de copropriété ni commercial ni destiné au
    public, c'est publier une donnée personnelle sans nécessité — la
    minimisation (RGPD art. 5-1-c) dit exactement cela.

    ⚠️ Retirer le nom sans rien mettre à la place recréerait le défaut corrigé la
    veille : une page qui n'identifie personne. L'éditeur devient donc une
    ENTITÉ — le conseil syndical —, identifiable et joignable.
    """
    substitutions = _charger(_MIGRATION_ANONYME, "mig0173").SUBSTITUTIONS
    assert substitutions, "la migration ne remplace plus rien"
    for avant, apres in substitutions:
        assert "Philippe Tressard" in avant, (
            "un remplacement de 0173 ne vise pas le nom qu'il doit retirer"
        )
        assert "Philippe Tressard" not in apres, (
            "le nom d'une personne réapparaît dans le texte de remplacement"
        )
        assert "conseil syndical" in apres, (
            "le nom est retiré sans qu'aucune entité prenne sa place : la page "
            "n'identifierait plus d'éditeur"
        )


def test_les_remplacements_de_0173_visent_bien_le_texte_pose_par_0170_et_0171():
    """🔴 Une migration de texte qui rate sa cible est inerte, EN SILENCE.

    Contrairement au test que j'avais écrit puis retiré pour 0171, celui-ci ne
    dépend pas de `HEAD` : les textes de 0170 et 0171 sont figés dans leurs
    propres fichiers — une migration ne se réécrit pas. La comparaison est donc
    stable, aujourd'hui comme dans un an.
    """
    mentions = _module_migration().MENTIONS
    politique_apres = "".join(
        apres for _, apres in _charger(_MIGRATION_POLITIQUE, "mig0171").CORRECTIONS
    )
    cible = mentions + politique_apres

    introuvables = [
        avant[:60]
        for avant, _ in _charger(_MIGRATION_ANONYME, "mig0173").SUBSTITUTIONS
        if avant not in cible
    ]
    assert not introuvables, (
        "fragment(s) que 0173 ne trouvera jamais — le nom resterait publié :\n  "
        + "\n  ".join(introuvables)
    )
