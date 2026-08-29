"""Un PV d'AG est visible de TOUS les copropriétaires, quel que soit leur bâtiment.

Règle tranchée par l'utilisateur le 29/08/2026. Deux écarts mesurés sur la
fonction réelle avant d'écrire cette migration :

                                  AG copropriété    AG bâtiment 1    AG bât. 1+2
    Membre du CS                        voit             voit            voit
    Copropriétaire du bâtiment 1        voit             voit            voit
    Copropriétaire du bâtiment 3        voit           REFUSÉ          REFUSÉ

## Le périmètre d'un PV d'AG est DESCRIPTIF, jamais restrictif

L'écran des comptes-rendus écrivait `perimetre='bâtiment'` quand un seul bâtiment
était coché — ce qui restreint la lecture aux détenteurs d'un lot dans ce
bâtiment — et `'résidence'` dès qu'il y en avait deux, la seconde forme ne
restreignant rien. **Deux régimes d'accès pour un même geste**, invisibles à
l'écran : cocher un bâtiment de plus ouvrait le document.

Le ciblage dit **de quoi parle** le compte-rendu, pas qui a le droit de le lire.
Les documents existants sont donc reversés en `perimetre='résidence'`, leur
bâtiment passant dans `batiments_ids_json` — la forme qui n'a jamais restreint.

⚠️ **Sans cette conversion, la règle ne vaudrait que pour les AG à venir** : le
code applicatif change de comportement, les lignes déjà en base gardent leur
`perimetre='bâtiment'` et resteraient invisibles aux copropriétaires des autres
bâtiments. Un correctif qui ne traite que le futur laisse le défaut où il est.

## Ce que cette migration NE fait pas — et c'est arbitré, pas oublié

🔴 **Elle n'ouvre PAS les PV d'AG au syndic.** Une première version le faisait,
en ajoutant le statut `syndic` au profil `résidence_tous` : le syndic ne voit en
effet aucun de ses quatre documents (règlement, PV d'AG, fiche synthétique,
plan). La question a été posée explicitement à l'utilisateur, qui a tranché — les
comptes-rendus d'assemblée sont une affaire de copropriétaires. L'absence du
syndic dans ce profil est donc **une décision**, pas un défaut à corriger.

Elle ne touche **que** la catégorie `pv_ag`. Le mécanisme `perimetre='bâtiment'`
reste entier pour les diagnostics, les contrats et les attestations de lot, où la
restriction géographique est le comportement voulu.

Elle ne retire rien aux locataires : le profil les autorise toujours (rôle
`résident`), et l'écran leur masque déjà la section. Le changer serait un retrait
d'accès, qui se décide et s'annonce.

Revision ID: 0159
Revises: 0158
"""
import json

from alembic import op
from sqlalchemy import text

revision = "0159"
down_revision = "0158"
branch_labels = None
depends_on = None

_CATEGORIE = "pv_ag"


def upgrade() -> None:
    conn = op.get_bind()

    #  Les PV d'AG déjà en base cessent de restreindre par bâtiment.
    #
    #  Le `batiment_id` n'est PAS effacé : il reste la trace de ce que le CS
    #  avait choisi, et le jour où l'on voudra rejouer cette décision, l'avoir
    #  perdu coûterait plus cher que de le garder. Seul `perimetre` change, et
    #  c'est lui seul que `document_visible` consulte pour restreindre.
    lignes = conn.execute(
        text(
            "SELECT d.id, d.batiment_id, d.batiments_ids_json "
            "FROM document d JOIN categorie_document c ON c.id = d.categorie_id "
            "WHERE c.code = :cat AND d.perimetre = 'bâtiment' AND d.batiment_id IS NOT NULL"
        ),
        {"cat": _CATEGORIE},
    ).fetchall()

    for doc_id, batiment_id, multi in lignes:
        #  Une liste déjà présente prime : elle est plus riche que le champ
        #  simple, et l'écraser perdrait les autres bâtiments visés.
        cible = multi if multi else json.dumps([batiment_id])
        conn.execute(
            text(
                "UPDATE document SET perimetre = 'résidence', batiments_ids_json = :m "
                "WHERE id = :i"
            ),
            {"m": cible, "i": doc_id},
        )


def downgrade() -> None:
    """Ne défait rien, et c'est délibéré.

    Reconvertir un PV d'AG vers `perimetre='bâtiment'` exigerait de savoir
    lesquels l'étaient AVANT — information que la montée n'efface pas
    (`batiment_id` est conservé) mais qui ne distingue plus les documents
    convertis de ceux qui portaient déjà un ciblage descriptif. Une descente
    approximative refermerait des accès au hasard : mieux vaut ne rien défaire
    que défaire mal.
    """
