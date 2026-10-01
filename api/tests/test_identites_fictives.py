"""Aucun nom de personne réelle dans le dépôt PUBLIC (#1493, 01/10/2026).

## Le constat

L'audit de pertinence des tests (30/09/2026) a trouvé, dans ce dépôt public, les
noms du personnel du syndic, de résidents et de l'auteur, recopiés depuis l'écran
ou le fichier d'import qui avait motivé un test ou un commentaire : trente-trois
fichiers, code et tests. Une donnée personnelle publiée est un défaut de rang 1
(`standards/14`), et l'historique git la conserve.

Arbitré le 01/10/2026 : l'arbre courant est nettoyé, l'historique est accepté tel
quel — une réécriture serait incomplète, GitHub gardant les références des PR.

## Ce que ce contrôle tient

Une liste BLANCHE, jamais une liste noire : écrire les vrais noms dans un
contrôle les republierait, compilés cette fois. Tout nom de personne repéré dans
le code ou les tests doit figurer dans `FICTIFS` — l'y ajouter, c'est AFFIRMER
qu'il est inventé. Un mot repéré qui n'est pas un nom (« STOCK », « Témoin »)
va dans `PAS_DES_NOMS`. Une entrée qui ne sert plus fait échouer le contrôle.

Formes repérées :
- une civilité suivie d'un nom (« Mme DUPONT »), partout ;
- « Prénom NOM » ou « NOM Prénom » en littéral entier ou entre guillemets
  français, partout — et un prénom composé suivi d'un nom à casse mixte
  (« Jean-Hervé ForT »), qui avait échappé au premier passage ;
- la valeur d'un champ de nom (`nom=`, `prenom=`, `auteur_nom:`…), dans les
  tests et l'e2e — dans l'application, ces champs portent des libellés.

⚠️ Ce qu'il ne voit pas : un nom isolé hors de ces formes, ni ce qui est public
sans être du code — documents, messages de commit, tickets GitHub. La consigne
qui couvre le reste : `.claude/skills/security-audit`. L'attribution légale
(licences, SPDX, mentions légales des migrations) est hors de sa portée, et
c'est voulu : elle doit nommer l'auteur.
"""

from __future__ import annotations

import pathlib
import re
import unicodedata
from collections import defaultdict

from tests.aides_sources import modules_app

RACINE = pathlib.Path(__file__).resolve().parents[2]
CE_FICHIER = pathlib.Path(__file__).name
SUFFIXES = {".py", ".ts", ".svelte", ".mjs", ".js", ".sh"}

#: Où vivent les jeux de données : les champs de nom y portent des personnes.
DONNEES = ("api/tests", "front/e2e")
#: Le code hors `app/` (lu par `modules_app`) : seuls les noms en clair comptent.
CODE = ("front/src", "front/scripts", "scripts")

#: Les noms inventés. En ajouter un, c'est affirmer qu'il ne désigne personne
#: de la résidence, du syndic ni de ses prestataires.
FICTIFS = frozenset(
    """
    ADELE ALAIN ALEX ALICE ALIX ANNE BERNARD BLONDEL BRUNO CAMILLE CARON CATHERINE
    CHRISTINE CHRISTOPHE CLAIRE COLLARD DELMAS DUPONT DUPRE DURAND DURANDAL ELISE
    ELODIE FAURE FORT HELENE INES ITO JEAN JEAN-BAPTISTE JEAN-HERVE JEANNE KERBRAT
    LAMBERT LEROY LUC LYON MARC MARCEL MARCO MARTIN MARTIN-LEROY MARTINEAU MERCIER
    MOREL MORIN-LEGRAND NADIA ODILE PAUL PERRIN PHILIPPE PIERRE REINE RENARD RENEE
    ROBIN ROSSI ROUSSEL ROY SIDENTE SOPHIE SOREL SYLVIE VERDIERE ZELLER ZOE
    """.split()
)

#: Les mots que les formes ci-dessus attrapent sans qu'ils nomment quelqu'un :
#: entreprises, lieux, rôles, mots d'interface.
PAS_DES_NOMS = frozenset(
    """
    ADMIN ANCIEN ASCENSEURS ASSUREUR AULNAY AUTRE BAILLEUR BEARER BONJOUR CAS CLE
    COMPTEURS CONSEIL CONSTATE COPRO COTE CRAYON CSS DEGAT DEJA DEMANDEUR DUREE
    ENTREE ESSAI EXTERNE FAQ GEST HTML INCONNU LIE LOC LOCATAIRE MIS MIXTE MME NOM
    NOUVEAU NOUVEL NOUVELLE NOYAU ORPHELINE OTIS PARC PARTI PDF PLANS PLOMBERIE
    PRENOM PROPRIO REGLEMENT REJEU RESIDENCE RESIDENT SANS SANSBAT SCAN SERIE
    SERVICES SICLI SITE SONDAGE SOURCE STOCK SYNDIC TEMOIN TEST UNUSED
    """.split()
)

_MAJ = "A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜ"
_MIN = "a-zàâäçéèêëîïôöùûü"
_PRENOM = rf"[{_MAJ}][{_MIN}]+(?:-[{_MAJ}][{_MIN}]+)?"
_NOM = rf"[{_MAJ}][{_MAJ}'-]+[{_MAJ}]"
#: Un prénom COMPOSÉ annonce une personne même quand le nom suit à casse mixte
#: (« Jean-Hervé ForT ») : la forme exacte d'une saisie signalée à l'écran.
_PRENOM_COMPOSE = rf"[{_MAJ}][{_MIN}]+-[{_MAJ}][{_MIN}]+"
_PERSONNE = (
    rf"(?:{_PRENOM}\**\s+{_NOM})|(?:{_NOM}\s+{_PRENOM})"
    rf"|(?:{_PRENOM_COMPOSE}\s+[{_MAJ}][{_MAJ}{_MIN}'-]+)"
)

CIVILITE = re.compile(
    rf"\b(?:M\.|Mme|Madame|Monsieur)\s+((?:{_PRENOM}\s+)?(?:{_NOM}|[{_MAJ}][{_MIN}]+))"
)
LITTERAL = re.compile(rf"[\"']({_PERSONNE})[\"']")
GUILLEMETS = re.compile(rf"«\s*\**({_PERSONNE})")
CHAMP = re.compile(
    r"\b(?:nom|prenom|nom_complet|nom_proprietaire|nom_locataire|nom_coproprietaire"
    r"|auteur_nom|porteur_nom)\s*[=:]\s*[\"']([^\"'{}\n]+)[\"']"
)
_MOT = re.compile(rf"[{_MAJ}{_MIN}][{_MAJ}{_MIN}'-]{{2,}}")

#: Occurrences repérées sur l'arbre du 01/10/2026 : environ 330. Sous ce
#: plancher, une portée ou un motif a cassé, et le contrôle ne lit plus rien.
PLANCHER = 200


def _normaliser(mot: str) -> str:
    sans_accent = unicodedata.normalize("NFD", mot)
    return "".join(c for c in sans_accent if unicodedata.category(c) != "Mn").upper()


def noms_dans(source: str, *, donnees: bool) -> list[str]:
    """Les mots repérés comme des noms de personne, normalisés, avec répétitions."""
    motifs = (CIVILITE, LITTERAL, GUILLEMETS) + ((CHAMP,) if donnees else ())
    return [
        _normaliser(mot)
        for motif in motifs
        for trouve in motif.finditer(source)
        for mot in _MOT.findall(trouve.group(1))
    ]


def _sources() -> list[tuple[str, str, bool]]:
    """(chemin relatif, texte, est-ce un jeu de données) pour toute la portée."""
    lus = [(f"api/app/{m.rel}", m.source, False) for m in modules_app()]
    for dossier, donnees in [(d, True) for d in DONNEES] + [(d, False) for d in CODE]:
        racine = RACINE / dossier
        assert racine.is_dir(), f"`{dossier}/` introuvable : la portée du contrôle a bougé."
        lus += [
            (p.relative_to(RACINE).as_posix(), p.read_text(encoding="utf-8"), donnees)
            for p in sorted(racine.rglob("*"))
            if p.suffix in SUFFIXES and p.name != CE_FICHIER and "node_modules" not in p.parts
        ]
    return lus


def _releve() -> dict[str, set[str]]:
    vus: dict[str, set[str]] = defaultdict(set)
    total = 0
    for rel, source, donnees in _sources():
        for nom in noms_dans(source, donnees=donnees):
            vus[nom].add(rel)
            total += 1
    assert total >= PLANCHER, (
        f"{total} nom(s) repéré(s), plancher {PLANCHER} : un motif ou une portée a "
        "cassé, et le contrôle est vert sur rien."
    )
    return vus


def test_chaque_forme_est_reperee():
    """🔴 Le cas fautif d'abord : chaque forme attrape un nom inventé pour l'occasion."""
    assert noms_dans('nom="ZORGLUB"', donnees=True) == ["ZORGLUB"]
    assert noms_dans('nom="ZORGLUB"', donnees=False) == [], "un libellé d'écran n'est pas un nom"
    assert noms_dans("« Remplace Mme ZORGLUB »", donnees=False) == ["ZORGLUB"]
    assert noms_dans("Monsieur Zorglub,", donnees=False) == ["ZORGLUB"]
    assert noms_dans("const A = 'Hélène ZORGLUB';", donnees=False) == ["HELENE", "ZORGLUB"]
    assert noms_dans("« ZORGLUB Hélène » à la lettre Z", donnees=False) == ["ZORGLUB", "HELENE"]
    #  Prénom composé + nom à casse mixte : la forme d'un signalement à l'écran,
    #  « Prénom NomMalSaisi » — elle avait échappé au premier passage (01/10/2026).
    assert noms_dans("« Jean-Hervé ZorgluB », signalé", donnees=False) == ["JEAN-HERVE", "ZORGLUB"]


def test_aucun_nom_reel_dans_le_code_ni_les_tests():
    vus = _releve()
    inconnus = sorted(n for n in vus if n not in FICTIFS | PAS_DES_NOMS)
    assert not inconnus, (
        "Nom(s) de personne non déclaré(s) fictif(s) — le dépôt est PUBLIC (#1493) :\n"
        + "\n".join(f"  • {n} — {', '.join(sorted(vus[n]))}" for n in inconnus)
        + "\nUn nom tiré d'un écran, d'un import ou d'un courriel est une donnée "
        "personnelle : le remplacer par un nom inventé de même forme. Un nom déjà "
        "inventé s'ajoute à `FICTIFS` ; un mot qui n'est pas un nom, à `PAS_DES_NOMS`."
    )


def test_chaque_entree_declaree_sert_encore():
    vus = _releve()
    morts = sorted((FICTIFS | PAS_DES_NOMS) - set(vus))
    assert not morts, (
        f"Entrée(s) qui ne servent plus : {morts}. Les retirer — une liste blanche qui "
        "ne décroît pas finit par couvrir le prochain vrai nom."
    )
    assert not FICTIFS & PAS_DES_NOMS, "un mot est à la fois un nom et pas un nom"
