"""Le vocabulaire des rôles et des statuts n'est pas RÉÉCRIT dans un écran.

Trois garde-fous de même forme, nés de trois incidents, et séparés de
`test_roles_libelles.py` le 08/09/2026 quand le plafond de modularité a refusé
de le laisser grossir. Le refus disait vrai : ce fichier-ci regarde le **front**,
l'autre le **serveur**, et ils ne partagent que la mécanique de lecture — qui vit
désormais dans `roles_libelles_lecture.py`.

Les trois questions, dans l'ordre où on a appris à les poser :

1. chaque libellé a-t-il une TEINTE ? (#819)
2. une table de teintes est-elle réécrite dans un écran ? (#819)
3. une table de LIBELLÉS l'est-elle ? (#828)

⚠️ La troisième a existé un mois sans être vue, parce que les deux premières ne
pouvaient pas la voir : celle des libellés serveur cherche les chaînes
**canoniques**, et les copies fautives écrivaient des **abrégés**. Une copie qui
paraphrase devient invisible à un contrôle qui cherche le texte. D'où un contrôle
qui regarde la **forme** — les clés — et pas les valeurs.
"""
from __future__ import annotations

from tests.roles_libelles_lecture import (
    ROLES_TS,
    VALEUR_CHAINE,
    VALEUR_TEINTE,
    fichiers_du_front,
    table_ts,
    tables_par_cle,
)

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
    libelles_role = table_ts(ts, "LIBELLES_ROLE")
    libelles_statut = table_ts(ts, "LIBELLES_STATUT")
    badges_role = table_ts(ts, "BADGE_ROLE")
    badges_statut = table_ts(ts, "BADGE_STATUT")

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
    ts = ROLES_TS.read_text(encoding="utf-8")
    cles = set(table_ts(ts, "LIBELLES_ROLE")) | set(table_ts(ts, "LIBELLES_STATUT"))
    assert len(cles) >= 12, "extraction des clés cassée — le contrôle ne mesurerait rien"

    fautifs = []
    for relatif, source in fichiers_du_front(sauf=SOURCE_BADGES):
        for ligne, entrees in tables_par_cle(source, cles, VALEUR_TEINTE):
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
    assert len(tables_par_cle(copie, cles, VALEUR_TEINTE)) == 1

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
    assert len(tables_par_cle(homonymie, {"locataire", "conseil_syndical"}, VALEUR_TEINTE)) == 0

    ternaire = (
        "<span\n"
        "\tclass=\"badge {u.statut === 'locataire' ? 'badge-gray' : ''}\"\n"
        "></span>\n"
    )
    assert len(tables_par_cle(ternaire, cles, VALEUR_TEINTE)) == 0

    #  Un commentaire qui cite la forme ne la pose pas — `standards/04` §39, et
    #  deux contrôles s'y sont déjà pris eux-mêmes le 06/09/2026.
    commentaire = (
        "const x = {\n"
        "\t//  locataire: 'badge-gray' vivait ici avant #819\n"
        "\t//  conseil_syndical: 'badge-blue' aussi\n"
        "};\n"
    )
    assert len(tables_par_cle(commentaire, cles, VALEUR_TEINTE)) == 0


#  ══════════════════════════════════════════════════════════════════════════
#  LE LIBELLÉ ABRÉGÉ — le troisième demi, resté recopié jusqu'au 08/09/2026
#
#  🔴 `admin/+page.svelte` portait DEUX tables de libellés de statut, à trente
#  lignes d'écart et dans le même fichier : `statutLabels` et `statutLabelsAdmin`
#  (#828). Elles étaient identiques SAUF `admin_technique`, absent de la seconde
#  — si bien qu'une demande de profil émanant d'un compte technique affichait
#  `admin_technique`, la valeur brute de l'énumération. Un libellé manquant ne
#  lève pas, il s'imprime.
#
#  ⚠️ AUCUN des deux contrôles ci-dessus ne pouvait les voir, pour deux raisons
#  indépendantes — et la seconde est la leçon :
#
#    1. le premier ne scanne que `app/**.py`, côté serveur ;
#    2. surtout, il cherche les chaînes CANONIQUES (« Copropriétaire résident »),
#       et ces tables écrivaient des ABRÉGÉS (« Copro. résident »). Une copie qui
#       raccourcit le texte devient invisible à un contrôle qui cherche le texte.
#
#  D'où ce troisième contrôle, qui ne regarde pas les VALEURS mais la FORME : une
#  table dont plusieurs CLÉS sont des statuts, où qu'elle soit et quoi qu'elle
#  associe. C'est le seul angle sous lequel une paraphrase reste visible.
#  ══════════════════════════════════════════════════════════════════════════

#: Le seul fichier du front autorisé à déclarer une table indexée par des statuts.
SOURCE_LIBELLES = "src/lib/roles.ts"

#:  Les clés que `StatutUtilisateur` PARTAGE avec `TypeLien` — deux énumérations
#:  distinctes du produit, dont deux valeurs portent le même mot.
#:
#:  ⚠️ Elles sont retirées du jeu de recherche, et c'est nécessaire : `TypeLien`
#:  dit comment une personne est liée à un LOT (propriétaire, bailleur,
#:  locataire, mandataire), `StatutUtilisateur` ce qu'elle EST dans la
#:  copropriété. `TYPE_LIEN_LABEL` (`OngletImportLots.svelte`) est une table
#:  légitime de la première, et le seuil de deux ne suffisait pas à la
#:  distinguer puisque DEUX de ses clés sont homonymes.
#:
#:  🔴 Rien n'est perdu : une vraie table de statuts porte forcément l'un des
#:  cinq mots restants — `copropriétaire_résident`, `copropriétaire_bailleur`,
#:  `syndic`, `aidant`, `admin_technique`. Les deux copies trouvées le 08/09 en
#:  portaient chacune au moins trois. Exclure ces clés par NOM plutôt que
#:  d'excuser un FICHIER laisse le contrôle actif partout, y compris dans le
#:  fichier où l'homonymie vit.
_CLES_PARTAGEES_AVEC_TYPE_LIEN = {"locataire", "mandataire"}

def test_la_table_ABREGEE_couvre_tout_ce_que_la_table_complete_couvre():
    """Une clé absente s'imprime en brut — c'est le défaut exact de #828.

    Même contrat que `BADGE_ROLE` et `BADGE_STATUT` : une clé par entrée de
    `LIBELLES_STATUT`, sans exception.
    """
    ts = ROLES_TS.read_text(encoding="utf-8")
    complets = table_ts(ts, "LIBELLES_STATUT")
    abreges = table_ts(ts, "LIBELLES_STATUT_ABREGE")

    #  Cas zéro : un extracteur cassé conclurait au vert sur zéro comparaison.
    assert len(complets) >= 7 and len(abreges) >= 7, "extraction cassée"

    assert set(abreges) == set(complets), (
        "LIBELLES_STATUT_ABREGE et LIBELLES_STATUT ne couvrent pas les mêmes "
        f"statuts : {set(complets) ^ set(abreges)}. Une clé manquante n'est pas "
        "rendue vide — elle s'affiche en brut (`admin_technique`)."
    )


def test_aucun_LIBELLE_de_statut_n_est_REECRIT_dans_un_ecran():
    """Le garde-fou contre la quatrième table de libellés de statut."""
    ts = ROLES_TS.read_text(encoding="utf-8")
    cles = set(table_ts(ts, "LIBELLES_STATUT")) - _CLES_PARTAGEES_AVEC_TYPE_LIEN
    assert len(cles) >= 5, "extraction des clés cassée — le contrôle ne mesurerait rien"

    fautifs = []
    for relatif, source in fichiers_du_front(sauf=SOURCE_LIBELLES):
        for ligne, entrees in tables_par_cle(source, cles, VALEUR_CHAINE):
            fautifs.append(f"{relatif}:{ligne} — {len(entrees)} clés : {entrees[0]}…")

    assert not fautifs, (
        "une table indexée par des statuts est réécrite hors de `$lib/roles.ts` :\n  "
        + "\n  ".join(fautifs)
        + "\n  → employer `libelleStatut()` ou `LIBELLES_STATUT_ABREGE`."
    )


def test_le_garde_fou_des_LIBELLES_ABREGES_refuse_bien_une_reecriture():
    """Cas zéro, dans les deux sens — dont la PARAPHRASE, que rien d'autre ne voit.

    La deuxième copie est celle qui a échappé aux deux contrôles existants
    pendant un mois : mêmes clés, texte raccourci. Elle doit être refusée ici
    **sans** que le contrôle sache à quoi ressemble le texte canonique.
    """
    cles = {"copropriétaire_résident", "copropriétaire_bailleur", "syndic", "aidant"}

    canonique = (
        "const labels: Record<string, string> = {\n"
        "\tcopropriétaire_résident: 'Copropriétaire résident',\n"
        "\tsyndic: 'Syndic',\n"
        "};\n"
    )
    paraphrase = (
        "const statutLabelsAdmin: Record<string, string> = {\n"
        "\tcopropriétaire_résident: 'Copro. résident',\n"
        "\tcopropriétaire_bailleur: 'Copro. bailleur',\n"
        "};\n"
    )
    #  🔴 L'homonymie RÉELLE, celle qui a fait échouer ma première version :
    #  `TYPE_LIEN_LABEL` est une table de `TypeLien`, dont DEUX valeurs portent
    #  le même mot qu'un statut. Un seuil de deux ne la distinguait pas — c'est
    #  l'exclusion par NOM DE CLÉ qui la sauve.
    homonymie = (
        "const TYPE_LIEN_LABEL: Record<string, string> = {\n"
        "\tpropriétaire: 'Propriétaire',\n"
        "\tbailleur: 'Bailleur',\n"
        "\tlocataire: 'Locataire',\n"
        "\tmandataire: 'Mandataire',\n"
        "};\n"
    )

    assert len(tables_par_cle(canonique, cles, VALEUR_CHAINE)) == 1
    assert len(tables_par_cle(paraphrase, cles, VALEUR_CHAINE)) == 1, (
        "une copie qui RACCOURCIT le texte doit rester visible : c'est "
        "précisément ce qui a échappé aux deux contrôles existants."
    )
    assert len(tables_par_cle(homonymie, cles, VALEUR_CHAINE)) == 0, (
        "une table de `TypeLien` n'est pas une table de statuts — les deux mots "
        "communs ne doivent pas suffire à la condamner."
    )

