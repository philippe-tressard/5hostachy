"""Les événements du calendrier deviennent des affaires (#1092, lot 5b2).

## Ce que l'utilisateur a tranché (23/09/2026)

Un seul objet, l'Affaire ; le Calendrier devient une vue (« une date est
définie »), son kanban un onglet d'Affaires. Les événements **migrent en une
fois**, selon leur suivi :

| Événement | Affaire |
|---|---|
| coupure, ou aucune colonne de kanban | **Actualité** datée (`publie`) |
| suivi, maintenance ou maintenance récurrente | **Entretien**, suivi au kanban |
| suivi, travaux · AG · autre | **Étude & travaux**, suivie au kanban |

| Colonne | État |
|---|---|
| `ag` · `cs` · `syndic` · `fournisseur` · `termine` · `annule` | `en_ag` · `ouvert` · `en_cours` · `chez_prestataire` · `résolu` · `annulé` |

- **Qui le voit** : règle de l'affaire. Une actualité garde ses destinataires —
  AG → Copropriétaires, maintenance récurrente → Conseil syndical, `reserve_cs`
  → Conseil syndical ; une affaire suivie réservée devient `confidentiel`.
- **Prestataire** → section Intervenant ; **fréquence** → la récurrence d'un
  Entretien (0211) ; **lieu** libre → en tête de la description.
- **Description** obligatoire : repli sur le titre quand l'événement n'en avait
  pas (deux cas en base au 23/09).
- **Aucune relance** du syndic : `non_relancable`, avec son motif — un dossier
  recopié n'a pas à déclencher, le mois suivant, un courriel que personne n'a
  décidé.

La correspondance ancien → nouvel identifiant est tenue par
`ticket.promu_depuis_evenement_id`, posée ici, que la redirection des anciens
liens `#ev-N` lira.

## ⚠️ Ce que cette migration ne fait PAS : supprimer

Comme la 0210 : les lignes d'`evenement` et d'`evenement_evolution` restent,
lues par rien. Leur suppression est un geste à part, une fois la bascule
constatée. Numéro d'affaire : `TK-E<id>`, la lettre excluant toute collision
avec les numéros tirés au sort. Idempotente : un événement déjà migré est sauté.
"""
import json
import secrets
from datetime import datetime
from html import escape

import sqlalchemy as sa
from alembic import op

revision = "0212"
down_revision = "0211"
branch_labels = None
depends_on = None

TABLE = "ticket"
COLONNE = "promu_depuis_evenement_id"  # identifiant de colonne : constante de ce fichier

_ETAT_PAR_COLONNE = {
    "ag": "en_ag", "cs": "ouvert", "syndic": "en_cours",
    "fournisseur": "chez_prestataire", "termine": "résolu", "annule": "annulé",
}
_CLOS = ("résolu", "annulé")
_MOTIF = "Issue du calendrier (#1092) : aucune relance automatique."


def categorie_de(type_: str | None, colonne: str | None) -> str:
    """La catégorie d'un événement — la règle arbitrée, écrite une fois."""
    if type_ == "coupure" or not colonne:
        return "actualite"
    if type_ in ("maintenance", "maintenance_recurrente"):
        return "entretien"
    return "etude_travaux"


def public_de(type_: str | None, reserve_cs: bool) -> str | None:
    """Le public visé d'une ACTUALITÉ issue d'un événement ; `None` : tout le monde."""
    if reserve_cs or type_ == "maintenance_recurrente":
        return '["conseil_syndical"]'
    if type_ == "ag":
        return '["copropriétaires"]'
    return None


def perimetre_de(csv: str | None) -> str:
    codes = [c.strip() for c in (csv or "").split(",") if c.strip()]
    return json.dumps(codes or ["résidence"], ensure_ascii=False)


def description_de(titre: str, description: str | None, lieu: str | None) -> str:
    corps = (description or "").strip() or f"<p>{escape(titre)}</p>"
    if lieu and lieu.strip():
        corps = f"<p>Lieu : {escape(lieu.strip())}</p>" + corps
    return corps


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade() -> None:
    conn = op.get_bind()
    if COLONNE not in _colonnes(conn):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer(), nullable=True))
        op.create_index(f"ix_{TABLE}_{COLONNE}", TABLE, [COLONNE])

    evs = conn.execute(sa.text(
        "SELECT id, titre, description, type, lieu, debut, fin, perimetre, batiment_id, auteur_id, "
        "cree_le, mis_a_jour_le, archivee, statut_kanban, prestataire_id, frequence_type, "
        "frequence_valeur, photos_urls, fichiers_urls, epingle, reserve_cs, envoyer_syndic, "
        "envoyer_cs, saisi_pour_user_id, saisi_pour_nom, saisi_pour_email, assiste_ia "
        "FROM evenement ORDER BY id"
    )).mappings().all()
    for e in evs:
        deja = conn.execute(sa.text(
            "SELECT id FROM ticket WHERE promu_depuis_evenement_id = :eid"
        ).bindparams(eid=e["id"])).scalar()
        if deja is not None:
            continue
        colonne = e["statut_kanban"] or None
        categorie = categorie_de(e["type"], colonne)
        actualite = categorie == "actualite"
        statut = "publie" if actualite else _ETAT_PAR_COLONNE.get(colonne, "ouvert")
        maj = e["mis_a_jour_le"] or e["cree_le"] or datetime.utcnow()
        entretien = categorie == "entretien"
        conn.execute(sa.text(
            "INSERT INTO ticket (numero, jeton_courriel, promu_depuis_evenement_id, titre, description, "
            "categorie, statut, priorite, auteur_id, batiment_id, perimetre_cible, public_cible, "
            "photos_urls, fichiers_urls, destinataire_syndic, destinataire_cs, debut, fin, "
            "cree_le, mis_a_jour_le, ferme_le, confidentiel, epingle, suivi_kanban, reserve_perimetre, "
            "archive_manuel, non_relancable, non_relancable_motif, prestataire_id, frequence_type, "
            "frequence_valeur, saisi_pour_user_id, saisi_pour_nom, saisi_pour_email, assiste_ia) "
            "VALUES (:numero, :jeton, :eid, :titre, :description, :categorie, :statut, :priorite, "
            ":auteur_id, :batiment_id, :perimetre, :public, :photos, :fichiers, :syndic, :cs, "
            ":debut, :fin, :cree_le, :maj, :ferme, :confidentiel, :epingle, :suivi, 0, :archive, 1, "
            ":motif, :prestataire, :ftype, :fvaleur, :sp_id, :sp_nom, :sp_email, :ia)"
        ).bindparams(
            numero=f"TK-E{e['id']:05d}",
            jeton=secrets.token_hex(16),
            eid=e["id"],
            titre=e["titre"],
            description=description_de(e["titre"], e["description"], e["lieu"]),
            categorie=categorie,
            statut=statut,
            priorite="haute" if e["type"] == "coupure" else "normale",
            auteur_id=e["auteur_id"],
            batiment_id=e["batiment_id"],
            perimetre=perimetre_de(e["perimetre"]),
            public=public_de(e["type"], bool(e["reserve_cs"])) if actualite else None,
            photos=e["photos_urls"],
            fichiers=e["fichiers_urls"] or "[]",
            syndic=bool(e["envoyer_syndic"]),
            cs=bool(e["envoyer_cs"]),
            debut=e["debut"],
            fin=e["fin"],
            cree_le=e["cree_le"],
            maj=maj,
            ferme=maj if statut in _CLOS else None,
            confidentiel=bool(e["reserve_cs"]) and not actualite,
            epingle=bool(e["epingle"]),
            suivi=not actualite,
            archive=bool(e["archivee"]),
            motif=_MOTIF,
            #  L'intervenant ne vaut que pour le bâti, la récurrence que pour un
            #  Entretien (`utils/intervenant`) : la migration suit la même règle.
            prestataire=None if actualite else e["prestataire_id"],
            ftype=e["frequence_type"] if entretien else None,
            fvaleur=e["frequence_valeur"] if entretien else None,
            sp_id=e["saisi_pour_user_id"],
            sp_nom=e["saisi_pour_nom"],
            sp_email=e["saisi_pour_email"],
            ia=bool(e["assiste_ia"]),
        ))
        tid = conn.execute(sa.text(
            "SELECT id FROM ticket WHERE promu_depuis_evenement_id = :eid"
        ).bindparams(eid=e["id"])).scalar()
        for v in conn.execute(sa.text(
            "SELECT type, contenu, ancien_statut, nouveau_statut, auteur_id, cree_le, fichiers_urls, "
            "assiste_ia FROM evenement_evolution WHERE evenement_id = :eid ORDER BY id"
        ).bindparams(eid=e["id"])).mappings().all():
            conn.execute(sa.text(
                "INSERT INTO ticket_evolution (ticket_id, type, contenu, ancien_statut, nouveau_statut, "
                "auteur_id, cree_le, fichiers_urls, assiste_ia) "
                "VALUES (:tid, :type, :contenu, :ancien, :nouveau, :auteur, :cree, :fichiers, :ia)"
            ).bindparams(
                tid=tid, type=v["type"], contenu=v["contenu"],
                ancien=_ETAT_PAR_COLONNE.get(v["ancien_statut"], v["ancien_statut"]),
                nouveau=_ETAT_PAR_COLONNE.get(v["nouveau_statut"], v["nouveau_statut"]),
                auteur=v["auteur_id"], cree=v["cree_le"], fichiers=v["fichiers_urls"] or "[]",
                ia=bool(v["assiste_ia"]),
            ))
        conn.execute(sa.text(
            "UPDATE document SET ticket_id = :tid, evenement_id = NULL WHERE evenement_id = :eid"
        ).bindparams(tid=tid, eid=e["id"]))
        conn.execute(sa.text(
            "UPDATE flux_masque SET item_id = :neuf WHERE item_id = :ancien"
        ).bindparams(neuf=f"tk_{tid}", ancien=f"ev_{e['id']}"))


def downgrade() -> None:
    """Défait la recopie : les événements n'ont pas été supprimés."""
    conn = op.get_bind()
    if COLONNE not in _colonnes(conn):
        return
    migrees = conn.execute(sa.text(
        "SELECT id, promu_depuis_evenement_id AS eid FROM ticket "
        "WHERE numero LIKE 'TK-E%' AND promu_depuis_evenement_id IS NOT NULL"
    )).mappings().all()
    for t in migrees:
        conn.execute(sa.text(
            "UPDATE document SET evenement_id = :eid, ticket_id = NULL WHERE ticket_id = :tid"
        ).bindparams(eid=t["eid"], tid=t["id"]))
        conn.execute(sa.text(
            "UPDATE flux_masque SET item_id = :ancien WHERE item_id = :neuf"
        ).bindparams(ancien=f"ev_{t['eid']}", neuf=f"tk_{t['id']}"))
        conn.execute(sa.text("DELETE FROM ticket_evolution WHERE ticket_id = :tid").bindparams(tid=t["id"]))
        conn.execute(sa.text("DELETE FROM ticket WHERE id = :tid").bindparams(tid=t["id"]))
    op.drop_index(f"ix_{TABLE}_{COLONNE}", TABLE)
    with op.batch_alter_table(TABLE) as lot:
        lot.drop_column(COLONNE)
