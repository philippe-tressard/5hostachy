"""Les actualités deviennent des affaires de catégorie « Actualité » (#1091, lot 4).

## Ce que l'utilisateur a tranché (22 et 23/09/2026)

Un seul objet, l'Affaire ; « Actualité » est une catégorie réservée au conseil,
sans cycle de vie (état `publie`). Les publications existantes **migrent en une
fois** ; la correspondance ancien → nouvel identifiant est tenue par
`ticket.promu_depuis_publication_id` (0202), que la redirection des liens
`#pub-N` lit déjà.

## La correspondance, colonne par colonne

| Publication | Affaire |
|---|---|
| `contenu` | `description` |
| `urgente` | `priorite = 'haute'` |
| `confidentiel` (réservé au périmètre) | `reserve_perimetre` |
| `brouillon` (réservé au conseil) | `public_cible = ["conseil_syndical"]` — arbitrage #1096 : la case disparaît, Destinataires = CS seul en tient lieu |
| `public_cible` = `["résidents"]` ou vide | `NULL` (tout le monde) |
| `archivee`, ou `statut = 'annule'` | `archive_manuel` |
| `statut` (publie, en_cours, resolu) | `publie` — l'actualité n'a plus de cycle |
| `envoyer_syndic` / `envoyer_cs` | `destinataire_syndic` / `destinataire_cs` |
| `statut_change_le` / `mis_a_jour_le` / `publiee_le` | `mis_a_jour_le`, dans cet ordre de repli |

Les évolutions suivent (`ticket_evolution`), les documents de la bibliothèque
passent à `ticket_id`, les affiches reçoivent leur `ticket_id` (0209), les
cartes masquées du fil passent de `pub_N` à `tk_M`.

## ⚠️ Ce que cette migration ne fait PAS : supprimer

Les lignes de `publication` et `publication_evolution` restent, **lues par rien**
sinon la redirection des anciens liens, qui cherche l'affaire d'abord. Leur
suppression est un geste à part, une fois la bascule constatée en production :
la prudence d'une migration de données se paie en place disque, pas en données.

Le numéro d'affaire d'une actualité, invisible à l'écran, est `TK-A<id>` : la
lettre ne peut pas entrer en collision avec les numéros tirés au sort (chiffres
seuls). Idempotente : une publication déjà migrée est sautée.
"""
import secrets
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0210"
down_revision = "0209"
branch_labels = None
depends_on = None

_STATUT_EVOLUTION = {"resolu": "résolu", "annule": "annulé"}
_PUBLIC_TOUS = (None, "", "[]", '["résidents"]')


def _public(public_cible, brouillon) -> str | None:
    if brouillon:
        return '["conseil_syndical"]'
    return None if public_cible in _PUBLIC_TOUS else public_cible


def upgrade() -> None:
    conn = op.get_bind()
    pubs = conn.execute(sa.text(
        "SELECT id, titre, contenu, perimetre_cible, public_cible, batiment_id, epingle, urgente, "
        "auteur_id, cree_le, publiee_le, mis_a_jour_le, statut, statut_change_le, brouillon, "
        "archivee, envoyer_syndic, envoyer_cs, confidentiel, photos_urls, debut, fin, "
        "saisi_pour_user_id, saisi_pour_nom, saisi_pour_email, assiste_ia "
        "FROM publication ORDER BY id"
    )).mappings().all()

    for p in pubs:
        deja = conn.execute(sa.text(
            "SELECT id FROM ticket WHERE promu_depuis_publication_id = :pid"
        ).bindparams(pid=p["id"])).scalar()
        if deja is not None:
            continue
        maj = p["statut_change_le"] or p["mis_a_jour_le"] or p["publiee_le"] or p["cree_le"] or datetime.utcnow()
        conn.execute(sa.text(
            "INSERT INTO ticket (numero, jeton_courriel, promu_depuis_publication_id, titre, description, "
            "categorie, statut, priorite, auteur_id, batiment_id, perimetre_cible, public_cible, "
            "photos_urls, fichiers_urls, destinataire_syndic, destinataire_cs, debut, fin, "
            "cree_le, mis_a_jour_le, confidentiel, epingle, suivi_kanban, reserve_perimetre, "
            "archive_manuel, non_relancable, saisi_pour_user_id, saisi_pour_nom, saisi_pour_email, assiste_ia) "
            "VALUES (:numero, :jeton, :pid, :titre, :description, 'actualite', 'publie', :priorite, "
            ":auteur_id, :batiment_id, :perimetre_cible, :public_cible, :photos_urls, '[]', "
            ":syndic, :cs, :debut, :fin, :cree_le, :maj, 0, :epingle, 0, :reserve, :archive, 0, "
            ":sp_id, :sp_nom, :sp_email, :assiste_ia)"
        ).bindparams(
            numero=f"TK-A{p['id']:05d}",
            jeton=secrets.token_hex(16),
            pid=p["id"],
            titre=p["titre"],
            description=p["contenu"] or "",
            priorite="haute" if p["urgente"] else "normale",
            auteur_id=p["auteur_id"],
            batiment_id=p["batiment_id"],
            perimetre_cible=p["perimetre_cible"] or '["résidence"]',
            public_cible=_public(p["public_cible"], p["brouillon"]),
            photos_urls=p["photos_urls"],
            syndic=bool(p["envoyer_syndic"]),
            cs=bool(p["envoyer_cs"]),
            debut=p["debut"],
            fin=p["fin"],
            cree_le=p["cree_le"],
            maj=maj,
            epingle=bool(p["epingle"]),
            reserve=bool(p["confidentiel"]),
            archive=bool(p["archivee"]) or p["statut"] == "annule",
            sp_id=p["saisi_pour_user_id"],
            sp_nom=p["saisi_pour_nom"],
            sp_email=p["saisi_pour_email"],
            assiste_ia=bool(p["assiste_ia"]),
        ))
        tid = conn.execute(sa.text(
            "SELECT id FROM ticket WHERE promu_depuis_publication_id = :pid"
        ).bindparams(pid=p["id"])).scalar()

        for e in conn.execute(sa.text(
            "SELECT type, contenu, ancien_statut, nouveau_statut, auteur_id, cree_le, fichiers_urls, assiste_ia "
            "FROM publication_evolution WHERE publication_id = :pid ORDER BY id"
        ).bindparams(pid=p["id"])).mappings().all():
            conn.execute(sa.text(
                "INSERT INTO ticket_evolution (ticket_id, type, contenu, ancien_statut, nouveau_statut, "
                "auteur_id, cree_le, fichiers_urls, assiste_ia) "
                "VALUES (:tid, :type, :contenu, :ancien, :nouveau, :auteur, :cree, :fichiers, :ia)"
            ).bindparams(
                tid=tid, type=e["type"], contenu=e["contenu"],
                ancien=_STATUT_EVOLUTION.get(e["ancien_statut"], e["ancien_statut"]),
                nouveau=_STATUT_EVOLUTION.get(e["nouveau_statut"], e["nouveau_statut"]),
                auteur=e["auteur_id"], cree=e["cree_le"], fichiers=e["fichiers_urls"] or "[]",
                ia=bool(e["assiste_ia"]),
            ))

        conn.execute(sa.text(
            "UPDATE document SET ticket_id = :tid, publication_id = NULL WHERE publication_id = :pid"
        ).bindparams(tid=tid, pid=p["id"]))
        conn.execute(sa.text(
            "UPDATE annonce_hall SET ticket_id = :tid WHERE publication_id = :pid"
        ).bindparams(tid=tid, pid=p["id"]))
        conn.execute(sa.text(
            "UPDATE flux_masque SET item_id = :neuf WHERE item_id = :ancien"
        ).bindparams(neuf=f"tk_{tid}", ancien=f"pub_{p['id']}"))


def downgrade() -> None:
    """Défait la recopie : les publications n'ont pas été supprimées."""
    conn = op.get_bind()
    migrees = conn.execute(sa.text(
        "SELECT id, promu_depuis_publication_id AS pid FROM ticket "
        "WHERE categorie = 'actualite' AND numero LIKE 'TK-A%' AND promu_depuis_publication_id IS NOT NULL"
    )).mappings().all()
    for t in migrees:
        conn.execute(sa.text(
            "UPDATE document SET publication_id = :pid, ticket_id = NULL WHERE ticket_id = :tid"
        ).bindparams(pid=t["pid"], tid=t["id"]))
        conn.execute(sa.text(
            "UPDATE annonce_hall SET ticket_id = NULL WHERE ticket_id = :tid"
        ).bindparams(tid=t["id"]))
        conn.execute(sa.text(
            "UPDATE flux_masque SET item_id = :ancien WHERE item_id = :neuf"
        ).bindparams(ancien=f"pub_{t['pid']}", neuf=f"tk_{t['id']}"))
        conn.execute(sa.text("DELETE FROM ticket_evolution WHERE ticket_id = :tid").bindparams(tid=t["id"]))
        conn.execute(sa.text("DELETE FROM ticket WHERE id = :tid").bindparams(tid=t["id"]))
