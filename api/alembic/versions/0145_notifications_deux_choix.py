"""Notifications : huit cases deviennent deux, sans consentement inventé.

Le réglage comptait **huit** drapeaux — quatre rubriques (tickets, actualités,
documents, communauté) × deux canaux (application, e-mail). Le résident devait
comprendre une matrice pour dire une chose simple : « je veux les e-mails de chez
moi, pas ceux d'à côté ». Deux clés désormais (#339) :

- `mon_batiment_mail` ;
- `autres_batiments_mail`.

## La conversion, et pourquoi elle est asymétrique

- `mon_batiment_mail` = vrai si **au moins un** des anciens `*_mail` valait vrai.
  Quelqu'un qui recevait des e-mails continue d'en recevoir ; quelqu'un qui les
  avait tous coupés reste au silence. C'est la lecture la plus fidèle de ce qu'il
  avait demandé, à défaut de pouvoir conserver le détail par rubrique.
- `autres_batiments_mail` = **faux pour tout le monde**, sans exception. Personne
  n'a jamais consenti à recevoir les autres bâtiments : la question ne lui a
  jamais été posée. Déduire un « oui » d'un réglage qui portait sur autre chose
  reviendrait à inventer un consentement — et c'est un e-mail non sollicité de
  plus pour chaque résident (`standards/14`).

Les quatre drapeaux `*_app` sont perdus, et c'est assumé : les notifications dans
l'application ne se règlent plus, elles restent actives. Leur valeur par défaut
était déjà vraie pour les quatre rubriques ; seuls les comptes en ayant décoché
une verront un changement.

## Précautions

Elle est **idempotente** : un enregistrement déjà converti (les deux clés
présentes, aucune ancienne) est laissé tel quel, donc un second passage ne fait
rien. Un JSON illisible est remplacé par les défauts plutôt que laissé en l'état
— le champ n'est plus lisible par personne, le conserver ne protège rien.

Revision ID: 0145
Revises: 0144
Create Date: 2026-08-14
"""
import json

from alembic import op
from sqlalchemy import text

revision = "0145"
down_revision = "0144"
branch_labels = None
depends_on = None

ANCIENNES_MAIL = ("ticket_mail", "actu_mail", "doc_mail", "communaute_mail")
MON_BATIMENT = "mon_batiment_mail"
AUTRES_BATIMENTS = "autres_batiments_mail"


def convertir(brut: str | None) -> str | None:
    """Le nouveau JSON, ou `None` s'il n'y a rien à changer.

    Fonction **pure**, isolée pour être testable : elle décide de ce que devient
    le consentement de chaque résident, et une erreur ici se traduirait soit par
    des e-mails non sollicités, soit par un silence que personne n'a demandé.
    Voir `api/tests/test_migration_notifications.py`.
    """
    try:
        prefs = json.loads(brut or "{}")
        if not isinstance(prefs, dict):
            prefs = {}
    except (json.JSONDecodeError, TypeError):
        prefs = {}

    deja_converti = MON_BATIMENT in prefs and not any(c in prefs for c in ANCIENNES_MAIL)
    if deja_converti:
        return None

    recevait = any(bool(prefs.get(cle, True)) for cle in ANCIENNES_MAIL) if prefs else True
    return json.dumps({MON_BATIMENT: recevait, AUTRES_BATIMENTS: False})


def _table_existe(nom: str) -> bool:
    return op.get_bind().execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:nom"),
        {"nom": nom},
    ).first() is not None


def upgrade() -> None:
    if not _table_existe("utilisateur"):
        return

    bind = op.get_bind()
    lignes = bind.execute(
        text("SELECT id, preferences_notifications FROM utilisateur")
    ).fetchall()

    for identifiant, brut in lignes:
        nouveau = convertir(brut)
        if nouveau is None:
            continue
        bind.execute(
            text("UPDATE utilisateur SET preferences_notifications = :val WHERE id = :id"),
            {"val": nouveau, "id": identifiant},
        )


def downgrade() -> None:
    #  Aucun retour en arrière : le détail par rubrique n'existe plus nulle part,
    #  et le reconstituer demanderait d'inventer quatre réponses à partir d'une.
    #  Mieux vaut ne rien faire que rendre un consentement fabriqué.
    pass
