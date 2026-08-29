"""Un PV d'AG est visible de tous les copropriétaires, du syndic et du CS.

Règle tranchée par l'utilisateur le 29/08/2026. Deux écarts mesurés sur la
fonction réelle avant d'écrire cette migration :

                                  AG copropriété    AG bâtiment 1    AG bât. 1+2
    Membre du CS                        voit             voit            voit
    SYNDIC                            REFUSÉ           REFUSÉ          REFUSÉ
    Copropriétaire du bâtiment 1        voit             voit            voit
    Copropriétaire du bâtiment 3        voit           REFUSÉ          REFUSÉ

## 1. Le syndic ne voyait AUCUN PV d'AG — pas même celui qu'il rédige

La catégorie `pv_ag` pointe sur le profil `résidence_tous`, dont les rôles
autorisés sont `["propriétaire", "résident"]`. Le syndic n'a ni l'un ni l'autre :
son STATUT vaut `syndic`, et `document_visible` compare `roles ∪ {statut}` à
cette liste. Il tombait au premier filtre — sur les **quatre** catégories de ce
profil : règlement de copropriété, PV d'AG, fiche synthétique, plan.

🔴 **La question a été posée, tranchée dans un sens, puis retranchée dans
l'autre** — et c'est le second argument qui emporte : *le syndic réalise le PV
d'AG, il a donc le droit de le voir*. Un rédacteur qui ne peut pas relire son
propre document est un défaut, pas une règle. Le raisonnement vaut de la même
façon pour les trois autres catégories, qu'il gère aussi.

## 2. Le périmètre d'un PV d'AG est DESCRIPTIF, jamais restrictif

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

## Ce que cette migration NE fait pas

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

#  Le statut du syndic, ajouté aux rôles autorisés du profil « Tous les
#  résidents ». `document_visible` compare `roles ∪ {statut}` à cette liste :
#  y placer le STATUT est le seul moyen d'y faire entrer le syndic, qui ne porte
#  aucun rôle de copropriétaire — c'est déjà ainsi que fonctionne le profil
#  `cs_syndic_uniquement`.
_STATUT_SYNDIC = "syndic"
_PROFIL = "résidence_tous"


def _roles(connexion, code: str):
    """Les rôles autorisés d'un profil, ou `None` s'il est introuvable/illisible."""
    ligne = connexion.execute(
        text("SELECT roles_autorises FROM profil_acces_document WHERE code = :c"),
        {"c": code},
    ).fetchone()
    if not ligne or not ligne[0]:
        return None
    try:
        valeur = json.loads(ligne[0])
    except (ValueError, TypeError):
        return None
    return valeur if isinstance(valeur, list) else None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Le syndic entre dans le profil « Tous les résidents » ─────────────
    #  ⚠️ On LIT la valeur avant d'écrire, plutôt que de poser une liste en dur :
    #  ce profil est modifiable depuis l'administration, et l'écraser effacerait
    #  silencieusement une personnalisation.
    roles = _roles(conn, _PROFIL)
    if roles is not None and _STATUT_SYNDIC not in roles:
        conn.execute(
            text("UPDATE profil_acces_document SET roles_autorises = :r WHERE code = :c"),
            {"r": json.dumps(roles + [_STATUT_SYNDIC], ensure_ascii=False), "c": _PROFIL},
        )

    # ── 2. Les PV d'AG déjà en base cessent de restreindre par bâtiment.
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
    """Rétablit le profil sans le syndic. **Ne défait pas** la conversion.

    Reconvertir un PV d'AG vers `perimetre='bâtiment'` exigerait de savoir
    lesquels l'étaient AVANT — information que la montée n'efface pas
    (`batiment_id` est conservé) mais qui ne distingue plus les documents
    convertis de ceux qui portaient déjà un ciblage descriptif. Une descente
    approximative refermerait des accès au hasard : mieux vaut ne rien défaire
    que défaire mal.
    """
    conn = op.get_bind()
    roles = _roles(conn, _PROFIL)
    if roles is not None and _STATUT_SYNDIC in roles:
        conn.execute(
            text("UPDATE profil_acces_document SET roles_autorises = :r WHERE code = :c"),
            {
                "r": json.dumps(
                    [r for r in roles if r != _STATUT_SYNDIC], ensure_ascii=False
                ),
                "c": _PROFIL,
            },
        )
