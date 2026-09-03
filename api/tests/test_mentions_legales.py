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


def _module_migration():
    spec = importlib.util.spec_from_file_location("mig0170", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    """Ce que la migration pose doit répondre aux questions, pas les reformuler."""
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
