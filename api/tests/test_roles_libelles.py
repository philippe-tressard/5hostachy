"""Un rôle et un statut s'écrivent d'UNE façon — des deux côtés de la frontière.

## Pourquoi ce test (#801, 06/09/2026)

La table des libellés existait **sept fois** : trois dans
`routers/admin/utilisateurs.py` (`ajouter_role`, `retirer_role`, `changer_role`),
une dans `utils/reponses.py`, et trois côté front (`admin`, `profil`,
`tableau-de-bord`). Elles avaient dérivé.

    ajouter_role       conseil_syndical → « Membre du Conseil Syndical »
    retirer_role       conseil_syndical → « Conseil Syndical »
    front/admin        copropriétaire_résident → « Copropriétaire Résident »
    front/tableau      copropriétaire_résident → « Copropriétaire résident »

Le même rôle s'annonçait autrement selon qu'on l'attribuait ou qu'on le retirait,
dans deux notifications que **la même personne** reçoit.

🔴 **Chaque table était cohérente avec elle-même** — c'est pourquoi rien ne l'a
vu. Deux copies d'accord entre elles ne prouvent rien (`standards/02` §3 bis) :
il faut une référence, et il n'y en avait pas.

## Ce que ce fichier vérifie, et pourquoi il lit le TypeScript

La duplication front ⇄ API est inévitable (contextes de build disjoints, mémoire
`project_partage_front_api_impossible`). Le seul motif viable est **copie +
concordance exécutée** — celui de `noms.py` / `noms.ts`.

Ce test lit donc `front/src/lib/roles.ts` **en tant que texte** et compare ses
tables aux tables Python. Il échoue si l'une des deux bouge sans l'autre.

⚠️ Il échoue aussi s'il n'arrive pas à lire assez d'entrées : un extracteur qui
ne trouve plus rien conclurait au vert sur zéro comparaison — c'est le « cas
zéro » de `standards/04` §2.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.models.core import RoleUtilisateur, StatutUtilisateur
from app.utils.roles_libelles import (
    LIBELLES_ROLE,
    LIBELLES_STATUT,
    libelle_role,
    libelle_statut,
    libelle_statut_court,
)

ROLES_TS = Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "roles.ts"

#  Les chaînes qui ne doivent apparaître QUE dans le module source. Écrites ici
#  une fois, et employées par le garde-fou comme par son cas zéro.
CHAINES_CANONIQUES = (
    "Conseil syndical",
    "Membre du Conseil Syndical",
    "Copropriétaire résident",
    "Copropriétaire bailleur",
)


def _motif_valeur(chaine: str) -> re.Pattern:
    """La chaîne SEULE entre guillemets — `"Conseil syndical"`, pas une phrase.

    C'est ce resserrement qui distingue un libellé posé comme valeur d'une prose
    qui contient les mêmes mots.
    """
    return re.compile("[\"']" + re.escape(chaine) + "[\"']")


def _table_ts(source: str, nom: str) -> dict[str, str]:
    """Extrait `export const <nom>: Record<string, string> = { … };` du fichier TS."""
    debut = source.index(f"export const {nom}")
    corps = source[source.index("{", debut) + 1 : source.index("};", debut)]
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r"^\t(\S+?):\s*'([^']*)',", corps, re.MULTILINE)
    }


def test_les_deux_tables_couvrent_TOUTE_l_enumeration():
    """Un rôle ou un statut sans libellé s'afficherait avec son identifiant brut."""
    for role in RoleUtilisateur:
        assert role.value in LIBELLES_ROLE, f"rôle sans libellé : {role.value}"
    for statut in StatutUtilisateur:
        assert statut.value in LIBELLES_STATUT, f"statut sans libellé : {statut.value}"


def test_une_cle_inconnue_est_rendue_TELLE_QUELLE_jamais_vide():
    """Un libellé manquant doit se voir dans l'interface, pas s'effacer.

    Rendre `""` ferait disparaître l'information au lieu de signaler l'oubli —
    c'est la version « affichage » du faux vert.
    """
    assert libelle_role("role_invente") == "role_invente"
    assert libelle_statut("statut_invente") == "statut_invente"
    assert libelle_role(RoleUtilisateur.conseil_syndical) == "Conseil syndical"
    assert libelle_statut(StatutUtilisateur.copropriétaire_résident) == "Copropriétaire résident"


def test_la_forme_COURTE_ne_dit_pas_si_le_coproprietaire_habite_ou_loue():
    """La divergence assumée de `LIBELLES_STATUT_COURT`, verrouillée.

    Elle n'est pas un oubli : à côté d'une réponse dans un fil, préciser
    « résident » ou « bailleur » révélerait si la personne habite son lot ou le
    loue — sans rapport avec le message. Si quelqu'un « corrige » un jour la
    table courte pour l'aligner sur la longue, ce test le dit.
    """
    assert libelle_statut_court(StatutUtilisateur.copropriétaire_résident) == "Copropriétaire"
    assert libelle_statut_court(StatutUtilisateur.copropriétaire_bailleur) == "Copropriétaire"
    assert libelle_statut(StatutUtilisateur.copropriétaire_résident) != libelle_statut_court(
        StatutUtilisateur.copropriétaire_résident
    )


def test_le_front_ecrit_EXACTEMENT_les_memes_chaines():
    """La moitié qui tient les deux implémentations ensemble."""
    assert ROLES_TS.exists(), f"jumeau front introuvable : {ROLES_TS}"
    source = ROLES_TS.read_text(encoding="utf-8")

    ts_roles = _table_ts(source, "LIBELLES_ROLE")
    ts_statuts = _table_ts(source, "LIBELLES_STATUT")

    #  🔴 Cas zéro : sans ce garde, un extracteur cassé rendrait deux dictionnaires
    #  vides et le test passerait au vert en ne comparant rien.
    assert len(ts_roles) >= 5, f"extraction des rôles incomplète : {ts_roles}"
    assert len(ts_statuts) >= 7, f"extraction des statuts incomplète : {ts_statuts}"

    assert ts_roles == LIBELLES_ROLE, (
        "les libellés de RÔLES divergent entre le front et l'API :\n"
        f"  front : {ts_roles}\n  api   : {LIBELLES_ROLE}"
    )
    assert ts_statuts == LIBELLES_STATUT, (
        "les libellés de STATUTS divergent entre le front et l'API :\n"
        f"  front : {ts_statuts}\n  api   : {LIBELLES_STATUT}"
    )


def test_aucun_libelle_de_role_n_est_REECRIT_ailleurs():
    """Le garde-fou contre la huitième écriture.

    ⚠️ **La portée fait partie du contrôle** (`standards/05` §9). Ce test ne
    cherche pas « une table de libellés » en général : il cherche la chaîne
    canonique **posée comme une valeur**, c'est-à-dire seule entre guillemets.

    Sans ce resserrement, il criait sur quatre PHRASES qui contiennent les mêmes
    mots — « Conseil syndical, syndic et admin uniquement » (une description de
    profil), « À la demande du Conseil syndical… » (un texte de la fiche
    arrivant). Un contrôle qui crie sur de la prose finit désarmé, et il aurait
    fallu quatre dérogations pour zéro défaut réel.
    """
    racine = Path(__file__).resolve().parents[1] / "app"
    source_unique = racine / "utils" / "roles_libelles.py"
    motifs = [_motif_valeur(c) for c in CHAINES_CANONIQUES]

    fautifs = []
    for fichier in racine.rglob("*.py"):
        if fichier == source_unique:
            continue
        for numero, ligne in enumerate(fichier.read_text(encoding="utf-8").splitlines(), 1):
            nue = ligne.strip()
            #  Un commentaire ne pose pas de libellé — celui qui explique la
            #  suppression de `changer-role` cite justement l'ancienne chaîne.
            if nue.startswith("#") or nue.startswith('"""') or nue.startswith("*"):
                continue
            if any(m.search(ligne) for m in motifs):
                fautifs.append(f"{fichier.relative_to(racine)}:{numero} — {nue[:80]}")

    assert not fautifs, (
        "un libellé de rôle est réécrit hors de `app/utils/roles_libelles.py` :\n  "
        + "\n  ".join(fautifs)
        + "\n  → employer `libelle_role()` / `libelle_statut()`."
    )


def test_le_garde_fou_REFUSE_bien_une_reecriture():
    """Cas zéro : sans lui, un motif cassé rendrait un vert parfait.

    Les deux sens sont vérifiés — la valeur seule est refusée, la prose qui
    contient les mêmes mots passe.
    """
    motif = _motif_valeur("Conseil syndical")
    assert motif.search('    role = "Conseil syndical"')
    assert motif.search("    badge = 'Conseil syndical'")
    assert not motif.search('    "description": "Conseil syndical, syndic et admin uniquement",')
    assert not motif.search("    À la demande du Conseil syndical, il est rappelé")


#  ══════════════════════════════════════════════════════════════════════════
#  LA TEINTE — le second demi du vocabulaire, resté recopié jusqu'au 07/09/2026
#
#  #801 a fait de `roles.ts` la source unique des LIBELLÉS. La COULEUR, elle,
#  est restée écrite dans les écrans : `/admin` et `/profil` importaient tous
#  deux `libelleRole`, puis recopiaient la table des badges trois lignes plus
#  bas. Le contrôle ci-dessus ne pouvait pas le voir — il cherche des chaînes de
#  LIBELLÉ, et `badge-teal` n'en est pas une.
#
#  🔴 Ce que la copie coûtait déjà : `/profil` ne connaissait ni `propriétaire`
#  ni `externe`. Un compte portant l'un de ces rôles s'affichait en **gris** sur
#  son propre profil et en **teal** ou **jaune** dans l'administration. Le repli
#  `?? 'badge-gray'` rend un badge parfaitement normal : rien ne signalait
#  l'oubli, et c'est ce qui le rendait durable.
#  ══════════════════════════════════════════════════════════════════════════

#  Les fichiers du front autorisés à écrire `badge-<teinte>` en face d'une clé
#  de rôle ou de statut. Un seul, et c'est le sujet.
SOURCE_BADGES = "src/lib/roles.ts"


def test_chaque_libelle_de_role_ou_statut_a_une_TEINTE():
    """Un rôle libellé mais sans teinte s'affiche en gris — ce qui se lit comme
    une décision, alors que c'est un oubli.

    C'est exactement ce qui était arrivé à `/profil` : deux rôles absents de sa
    copie, rendus gris par le repli, sans que rien ne le dise.
    """
    ts = ROLES_TS.read_text(encoding="utf-8")
    libelles_role = _table_ts(ts, "LIBELLES_ROLE")
    libelles_statut = _table_ts(ts, "LIBELLES_STATUT")
    badges_role = _table_ts(ts, "BADGE_ROLE")
    badges_statut = _table_ts(ts, "BADGE_STATUT")

    #  Cas zéro : un extracteur qui ne trouve plus rien conclurait au vert sur
    #  zéro comparaison (`standards/04` §2).
    assert len(libelles_role) >= 5 and len(badges_role) >= 5, "extraction des rôles cassée"
    assert len(libelles_statut) >= 7 and len(badges_statut) >= 7, "extraction des statuts cassée"

    assert set(badges_role) == set(libelles_role), (
        "BADGE_ROLE et LIBELLES_ROLE ne couvrent pas les mêmes rôles : "
        f"{set(libelles_role) ^ set(badges_role)}"
    )
    assert set(badges_statut) == set(libelles_statut), (
        "BADGE_STATUT et LIBELLES_STATUT ne couvrent pas les mêmes statuts : "
        f"{set(libelles_statut) ^ set(badges_statut)}"
    )


#  Le SEUIL qui distingue une table recopiée d'une homonymie, et le pourquoi de
#  sa valeur — voir `_teintes_par_table`.
SEUIL_TABLE = 2


def _teintes_par_table(source: str, cles: set[str]) -> list[tuple[int, list[str]]]:
    """Les tables de ce fichier qui associent PLUSIEURS clés de rôle à une teinte.

    ⚠️ Le comptage se fait par TABLE et non par ligne, et c'est tout le contrôle.

    🔴 Ma première version signalait chaque ligne isolément. Elle a trouvé
    `KANBAN_COLORS` dans `reporting.ts` — où `syndic: 'badge-orange'` désigne la
    **colonne du kanban** qui traite le sujet, pas un rôle d'utilisateur. Le mot
    est le même, la notion non.

    Une table recopiée en porte cinq à onze ; une homonymie en porte une. Deux
    est donc le seuil qui les sépare, et il est mesuré sur le relevé réel — pas
    choisi pour faire passer le contrôle. Une dérogation nominative pour
    `reporting.ts` aurait, elle, laissé passer une vraie table de rôles dans ce
    même fichier.
    """
    lignes = source.splitlines()
    motif = re.compile(r"^\s*(" + "|".join(re.escape(c) for c in cles) + r")\s*:\s*'badge-")
    tables: list[tuple[int, list[str]]] = []
    debut, trouvees = None, []
    for numero, ligne in enumerate(lignes, 1):
        nue = ligne.strip()
        if nue.startswith(("//", "*", "/*", "<!--")):
            continue
        if re.search(r"=\s*\{\s*$", ligne):
            debut, trouvees = numero, []
            continue
        if debut is not None and re.match(r"^\s*\}", ligne):
            if len(trouvees) >= SEUIL_TABLE:
                tables.append((debut, trouvees))
            debut, trouvees = None, []
            continue
        if debut is not None and motif.search(ligne):
            trouvees.append(nue[:60])
    return tables


def test_aucune_TEINTE_de_role_n_est_REECRITE_dans_un_ecran():
    """Le garde-fou contre la troisième table de badges.

    ⚠️ La portée fait partie du contrôle, comme au-dessus : ce test ne cherche
    pas « badge- » en général — la classe est employée partout, légitimement. Il
    cherche une TABLE qui associe plusieurs clés de rôle ou de statut à une
    teinte, c'est-à-dire la forme exacte d'une copie :

        copropriétaire_bailleur: 'badge-purple',
        locataire: 'badge-gray',

    Une clé qui reçoit un badge dans un ternaire (`x === 'actif' ? 'badge-green'
    : …`) n'est pas visée : c'est une condition sur une valeur, pas une table.
    """
    front = Path(__file__).resolve().parents[2] / "front" / "src"
    ts = ROLES_TS.read_text(encoding="utf-8")
    cles = set(_table_ts(ts, "LIBELLES_ROLE")) | set(_table_ts(ts, "LIBELLES_STATUT"))
    assert len(cles) >= 12, "extraction des clés cassée — le contrôle ne mesurerait rien"

    fautifs = []
    for fichier in front.rglob("*"):
        if fichier.suffix not in (".svelte", ".ts") or not fichier.is_file():
            continue
        relatif = fichier.relative_to(front.parent).as_posix()
        if relatif == SOURCE_BADGES:
            continue
        for ligne, entrees in _teintes_par_table(
            fichier.read_text(encoding="utf-8"), cles
        ):
            fautifs.append(f"{relatif}:{ligne} — {len(entrees)} clés : {entrees[0]}…")

    assert not fautifs, (
        "une table de teintes de rôle ou de statut est réécrite hors de "
        "`$lib/roles.ts` :\n  "
        + "\n  ".join(fautifs)
        + "\n  → employer `badgeRole()` / `badgeStatut()`."
    )


def test_le_garde_fou_des_TEINTES_refuse_bien_une_reecriture():
    """Cas zéro : les deux sens, et surtout l'homonymie.

    Le troisième cas est celui que la première version du contrôle a signalé à
    tort : une table du reporting dont UNE clé porte le nom d'un rôle. Sans lui,
    le resserrement serait invérifiable — et un seuil qu'on ne peut pas éprouver
    est un seuil qu'on rabotera au prochain faux positif.
    """
    cles = {"locataire", "conseil_syndical", "copropriétaire_bailleur", "syndic", "ag"}

    copie = (
        "const roleBadge: Record<string, string> = {\n"
        "\tlocataire: 'badge-gray',\n"
        "\tconseil_syndical: 'badge-blue',\n"
        "\tcopropriétaire_bailleur: 'badge-purple',\n"
        "};\n"
    )
    assert len(_teintes_par_table(copie, cles)) == 1

    homonymie = (
        "export const KANBAN_COLORS: Record<string, string> = {\n"
        "\tag: 'badge-purple',\n"
        "\tsyndic: 'badge-orange',\n"
        "\tfournisseur: 'badge-yellow',\n"
        "};\n"
    )
    #  `ag` et `syndic` sont ici des colonnes de kanban. Deux clés du jeu, mais
    #  la notion n'est pas la même — c'est la limite assumée du contrôle, et
    #  c'est pourquoi le cas zéro l'écrit noir sur blanc.
    assert len(_teintes_par_table(homonymie, {"locataire", "conseil_syndical"})) == 0

    ternaire = (
        "<span\n"
        "\tclass=\"badge {u.statut === 'locataire' ? 'badge-gray' : ''}\"\n"
        "></span>\n"
    )
    assert len(_teintes_par_table(ternaire, cles)) == 0

    #  Un commentaire qui cite la forme ne la pose pas — `standards/04` §39, et
    #  deux contrôles s'y sont déjà pris eux-mêmes le 06/09/2026.
    commentaire = (
        "const x = {\n"
        "\t//  locataire: 'badge-gray' vivait ici avant #819\n"
        "\t//  conseil_syndical: 'badge-blue' aussi\n"
        "};\n"
    )
    assert len(_teintes_par_table(commentaire, cles)) == 0
