"""Deux corrections sur l'accès des badges, signalées à l'écran les 14 et 15/09/2026.

## 1. Un accès n'ouvre pas n'importe quel périmètre

> « Télécommande n'est pas accessible à un bâtiment mais à "Parking résidence /
>   portail d'accès" + "AFUL / Portail public" »
>
> puis, correction du 15/09 : « pour les vigik : copropriété entière ou bâtiment
>   x **et Extérieurs / portillons** »

🔴 La migration 0190 déduisait le **bâtiment du lot** pour les DEUX types
d'accès, parce que c'est ce que la règle disait — et elle ne le disait que du
vigik. Une télécommande ouvre des **portails**, toujours les mêmes, et n'a rien à
voir avec le bâtiment où l'on habite.

Cette migration pose donc, pour chaque type, la liste de ses **accès fixes** —
ceux qui ne dépendent d'aucun lot :

| Clé de `config_site` | Ce qu'elle porte | Pour |
|---|---|---|
| `acces_fixes_vigik` | les portillons | s'ajoutent à la copropriété et aux bâtiments |
| `acces_fixes_telecommande` | les portails | c'est **tout** ce qu'une télécommande ouvre |

⚠️ **Les codes ne sont pas écrits ici.** « Parking », « AFUL » et « Extérieurs »
sont des nœuds de CETTE arborescence, administrés : les nommer dans le code
serait la faute déjà corrigée pour l'AFUL (0189) et pour le nom du site
(v1.36.7). La migration les **cherche** par ce qu'ils sont — un libellé qui parle
d'un portail, d'un portillon — et pose le résultat dans `config_site`, où
l'administration le corrige.

⚠️ Si un nœud manque, il n'est **pas** inventé : la clé porte ce qui existe, et
le conseil syndical complète l'accès à la main — ce qu'il peut faire depuis
v1.37.0. Mieux vaut une valeur incomplète et visible qu'un code inventé qui
s'afficherait brut.

## 2. « 4 SAISONS » est dans la colonne LOCATAIRE

> « Vigik dont le locataire (du fichier d'import) = 4 saisons est affecté à
>   "Copropriété entière" »

🔴 La 0190 lisait `batiment_raw` — la colonne A. La mention est en colonne **D**,
`nom_locataire` : ce sont les badges confiés au conseil syndical et à l'entreprise
de ménage, enregistrés au nom du lieu plutôt qu'au nom d'une personne.

⚠️ Cette correction **écrase** ce que la déduction avait posé : un badge « 4
SAISONS » avait pu recevoir le bâtiment de son propriétaire, ce qui est plus
étroit que la réalité. Restreindre un accès par erreur ne se voit pas — la porte
s'ouvre quand même, c'est l'écran qui ment.
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0191"
down_revision = "0190"
branch_labels = None
depends_on = None

#: Ce qu'on cherche dans les LIBELLÉS de l'arbre, par type d'accès — et le nom de
#: la clé qui reçoit le résultat.
#:
#: ⚠️ Un motif de libellé, pas un code de nœud : le code est arbitraire et propre
#: à cette copropriété, le mot « portail » désigne la chose. C'est la même
#: recherche qu'un humain ferait dans l'écran d'administration.
#:
#: ⚠️ La clé se compose comme dans `utils/acces_choix.cle_config` — recopié ici, et
#: c'est assumé : une migration ne doit pas importer le code de l'application, qui
#: change alors qu'elle non. `test_acces_choix.py` tient les deux ensemble.
FIXES_PAR_TYPE = {
    "vigik": "%portillon%",
    "telecommande": "%portail%",
}

#: La mention du classeur Vigik qui désigne un badge « toute la copropriété ».
#: Posée par 0190 dans `config_site` — relue ici, jamais redéfinie.
CLE_MENTION = "vigik_mention_tous_batiments"


def _normaliser(valeur) -> str:
    return " ".join(str(valeur or "").upper().split())


def _config(lien, cle: str):
    return lien.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :cle").bindparams(cle=cle)
    ).scalar()


def _poser_config(lien, cle: str, valeur: str) -> None:
    """N'écrit que si la clé n'existe pas : une valeur administrée n'est pas écrasée."""
    if _config(lien, cle) is None:
        lien.execute(
            sa.text("INSERT INTO config_site (cle, valeur) VALUES (:cle, :valeur)")
            .bindparams(cle=cle, valeur=valeur)
        )


def _noeuds_par_libelle(lien, motif: str) -> list[str]:
    """Les codes des nœuds actifs et sélectionnables dont le libellé correspond.

    C'est une recherche sur la DONNÉE, et elle rend ce qu'elle trouve : sur une
    arborescence qui ne porte pas ce mot, la liste est vide et le conseil syndical
    renseigne l'accès à la main.
    """
    lignes = lien.execute(sa.text("""
        SELECT code
          FROM perimetre
         WHERE actif = 1
           AND selectionnable = 1
           AND lower(libelle) LIKE :motif
         ORDER BY ordre, code
    """).bindparams(motif=motif)).all()
    return [ligne[0] for ligne in lignes]


def upgrade() -> None:
    lien = op.get_bind()

    #  ── 1. Les accès fixes de chaque type ───────────────────────────────────
    fixes: dict[str, list[str]] = {}
    for cle_type, motif in FIXES_PAR_TYPE.items():
        codes = _noeuds_par_libelle(lien, motif)
        fixes[cle_type] = codes
        _poser_config(
            lien, f"acces_fixes_{cle_type}",
            json.dumps(codes, ensure_ascii=False),
        )

    #  Les télécommandes que 0190 a rattachées à un bâtiment : c'est faux, et
    #  c'est le seul cas qu'on reprend. Une valeur posée à la main depuis
    #  v1.37.0 n'est pas un `bat:` et n'est donc pas touchée.
    if fixes["telecommande"]:
        lien.execute(
            sa.text(
                "UPDATE telecommande SET perimetre_cible = :valeur "
                "WHERE perimetre_cible IS NULL OR perimetre_cible LIKE '%\"bat:%'"
            ).bindparams(valeur=json.dumps(fixes["telecommande"], ensure_ascii=False))
        )

    #  ⚠️ Les vigiks ne sont PAS repris : un portillon est une faculté, pas un
    #  défaut. Le leur poser d'office attribuerait à tout le parc un accès que
    #  personne n'a décidé — et un accès élargi par erreur ne se voit pas.

    #  ── 2. La mention « toute la copropriété », colonne LOCATAIRE ───────────
    mention = _config(lien, CLE_MENTION)
    defaut = lien.execute(sa.text(
        "SELECT code FROM perimetre "
        "WHERE parent_id IS NULL AND portee_globale = 1 AND actif = 1 "
        "ORDER BY ordre LIMIT 1"
    )).scalar()
    if mention and defaut:
        cible = json.dumps([defaut], ensure_ascii=False)
        lignes = lien.execute(sa.text(
            "SELECT vigik_id, nom_locataire FROM vigik_import WHERE vigik_id IS NOT NULL"
        )).all()
        for vigik_id, nom_locataire in lignes:
            if _normaliser(nom_locataire) == _normaliser(mention):
                lien.execute(
                    sa.text("UPDATE vigik SET perimetre_cible = :cible WHERE id = :id")
                    .bindparams(cible=cible, id=vigik_id)
                )


def downgrade() -> None:
    #  ⚠️ Rien n'est défait : la 0190 avait posé des valeurs FAUSSES, et les
    #  restaurer n'aurait aucun sens. Une migration corrige une donnée ; elle ne
    #  promet pas de savoir remettre l'erreur.
    pass
