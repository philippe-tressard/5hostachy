"""Un prompt SEMÉ ne suit pas le code — il faut une migration, et rien ne le disait.

## Ce qui est arrivé deux fois sans que personne le voie (#1059, 19/09/2026)

Le prompt de chaque usage de l'assistant est **semé** par la migration 0194 :
la valeur en base fait foi ensuite, et le code n'en est plus propriétaire
(`standards/06` §4). C'est voulu — l'administrateur relit et adapte ces
consignes depuis *Admin → Assistant IA*.

La conséquence, elle, ne l'était pas : **réécrire `prompt_defaut` dans le code
ne change plus rien à une installation en service.**

| Lot | Ce qu'il apportait | Effet en production |
|---|---|---|
| v1.44.0 (#1003) | « l'assistant peut mettre en valeur ce qui compte » | **aucun** |
| v1.44.4 (#1007) | « la mise en valeur était permise, elle n'était pas obtenue » | **aucun** |

Deux lots relus et déployés, sans effet sur l'assistant réellement employé. Le
code disait une chose, la base en servait une autre, et **aucun contrôle ne les
rapprochait** — c'est la définition d'un écart qui ne se découvre jamais.

## Ce que ce test fait, et ce qu'il ne fait pas

Il ne vérifie **pas** le contenu d'un prompt : ce contenu appartient à
l'administrateur, et le figer reviendrait à lui retirer ce que l'écran lui
donne. Il ne regarde pas non plus la base.

Il pose un **cliquet** sur la valeur d'ORIGINE : changer `prompt_defaut` sans
écrire la migration qui porte ce changement jusqu'aux installations existantes
fait échouer la CI, avec la marche à suivre. C'est le seul moment où quelqu'un
peut encore y penser.

⚠️ Un usage AJOUTÉ échoue ici aussi, et c'est voulu : il lui faut une migration
pour semer son prompt, sans quoi il démarrerait sur une clé absente.
"""

import hashlib
import re
from pathlib import Path

from app.utils.llm_usages import USAGES

#: Empreinte SHA-256 du prompt d'origine de chaque usage, telle qu'une migration
#: l'a portée en base. Mettre à jour une ligne ici est le DERNIER geste d'un lot
#: qui change un prompt — jamais le premier.
#:
#: | Usage | Migration qui a posé la valeur courante |
#: |---|---|
#: | `description` | 0197 (19/09/2026) — remplace les trois consignes antérieures |
#: | `synthese_contrat` | 0194 (17/09/2026) — ⚠️ voir l'écart connu ci-dessous |
EMPREINTES_SEMEES = {
    "description": "a6bca9c941ff52c7b5f90108eccf8c0d0a1dbe2ced37f9ca41d621953b84528e",
    "synthese_contrat": "35d2cc4c13b269dbfa80bb197fec7ade1b27278dc7152b4c3acbf21b2036f097",
}

#: 🔴 Écart connu, tracé et non corrigé ici.
#:
#: La consigne de `synthese_contrat` a changé en v1.43.0 (#993) après avoir été
#: semée par la 0194 : les installations en service portent donc la version
#: antérieure. Ce test verrouille l'empreinte du CODE pour que l'écart cesse de
#: grandir ; le rattrapage en base demande une migration à part, parce que cette
#: consigne est composée de fragments et que ses empreintes historiques ne se
#: relisent pas aussi sûrement que celles de `description`.
#:
#: Le déclarer ici plutôt que de le taire : une exception non écrite n'est pas
#: une exception, c'est un oubli qui ressemble à une décision.
ECART_CONNU = ("synthese_contrat",)


def _empreinte(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def test_chaque_usage_declare_l_empreinte_de_son_prompt_d_origine():
    """Un usage sans empreinte déclarée n'a pas de migration qui sème son prompt."""
    manquants = sorted(set(USAGES) - set(EMPREINTES_SEMEES))
    assert not manquants, (
        f"Usage(s) sans empreinte déclarée : {manquants}. Un prompt d'origine ne "
        "parvient à une installation que par une migration — en ajouter un ici sans "
        "elle laisserait l'usage démarrer sur une clé absente."
    )
    orphelines = sorted(set(EMPREINTES_SEMEES) - set(USAGES))
    assert not orphelines, (
        f"Empreinte(s) déclarée(s) pour un usage qui n'existe plus : {orphelines}."
    )


def test_un_prompt_d_origine_ne_change_pas_sans_migration():
    """🔴 Le cliquet. Ce test échoue EXPRÈS quand on améliore un prompt.

    Ce n'est pas un faux positif : c'est le rappel que l'amélioration s'arrête
    au code si personne ne la porte en base.
    """
    for code, attendue in EMPREINTES_SEMEES.items():
        obtenue = _empreinte(USAGES[code].prompt_defaut)
        assert obtenue == attendue, (
            f"Le prompt d'origine de l'usage « {code} » a changé.\n"
            "    Les installations en service gardent l'ancien EN BASE : sans "
            "migration, ce lot n'aura aucun effet en production (c'est arrivé deux "
            "fois, #1059).\n"
            "    Marche à suivre :\n"
            "      1. écrire une migration qui remplace la valeur stockée SI elle "
            "porte encore une empreinte écrite par le code (motif de la 0197) ;\n"
            "      2. ajouter l'empreinte précédente à la liste de cette migration ;\n"
            f'      3. mettre à jour cette ligne : "{code}": "{obtenue}".'
        )


def test_la_migration_0197_connait_l_empreinte_qu_elle_remplace():
    """La 0197 doit reconnaître les consignes que le code a écrites avant elle.

    Cas zéro de la migration : si sa liste ne portait pas l'empreinte réellement
    stockée en production, elle s'exécuterait sans rien remplacer — un vert qui
    ne mesure rien.
    """
    #  Lue en TEXTE, comme le reste de la suite lit les migrations : une
    #  migration s'importe dans un contexte alembic qu'un test n'a pas à monter.
    source = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0197_consigne_description_rappel.py"
    ).read_text(encoding="utf-8")
    empreintes = set(re.findall(r'"([0-9a-f]{64})"', source))

    assert len(empreintes) == 3, (
        "La 0197 remplace les trois consignes que le code a successivement écrites "
        f"(v1.41.0, v1.44.0, v1.44.4) — {len(empreintes)} empreinte(s) relevée(s)."
    )
    assert _empreinte(USAGES["description"].prompt_defaut) not in empreintes, (
        "La consigne COURANTE figure parmi celles que la 0197 remplace : elle "
        "remplacerait la valeur par elle-même, et masquerait le jour où la liste "
        "cesse d'être à jour."
    )
