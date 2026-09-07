"""La sauvegarde est quotidienne, et il n'y a plus de choix à faire.

`ConfigSauvegarde.frequence` proposait `quotidienne` | `hebdomadaire` |
`mensuelle`, et l'écran y ajoutait une option « Désactivée » qui **n'existe pas
dans l'enum**. Ces valeurs sont EXCLUSIVES : choisir « hebdomadaire » ne s'ajoute
pas au quotidien, il le remplace. Sur une base de quelques mégaoctets, espacer les
sauvegardes n'apporte rien et coûte des jours de données en cas de perte — la
question a été posée en ces termes le 13/08/2026, et elle n'a pas de bonne réponse
autre que « tous les jours ».

Cette migration ramène les installations existantes au quotidien et réactive la
tâche si elle avait été coupée. Elle est **idempotente** et ne crée rien : elle
normalise une ligne de configuration.

L'énumération et la colonne restent en place. Les supprimer imposerait de recréer
la table sous SQLite pour un gain nul, et une valeur ancienne qui ressurgirait
serait de toute façon interprétée comme quotidienne par `utils/backup.py`.

⚠️ Ce qui est corrigé ailleurs, dans le même lot, et qui explique pourquoi
personne n'avait vu le problème : `PUT /admin/sauvegardes/config` applique
`if hasattr(cfg, k)`, et l'écran envoyait `heure` et `nb_versions` là où le modèle
porte `heure_execution` et `nb_versions_conservees`. **Les deux réglages étaient
ignorés en silence depuis toujours** — le formulaire affichait ses propres valeurs
par défaut, jamais celles du serveur.
"""
from alembic import op
from sqlalchemy import text

revision = "0139"
down_revision = "0138"
branch_labels = None
depends_on = None


def _table_existe(nom: str) -> bool:
    return op.get_bind().execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:nom"),
        {"nom": nom},
    ).first() is not None


def upgrade() -> None:
    if not _table_existe("config_sauvegarde"):
        return
    #  Jamais de f-string dans `op.execute` — paramètres liés, comme partout.
    op.get_bind().execute(
        text(
            "UPDATE config_sauvegarde SET frequence = :quotidienne, active = 1 "
            "WHERE frequence IS NULL OR frequence <> :quotidienne OR active = 0"
        ),
        {"quotidienne": "quotidienne"},
    )


def downgrade() -> None:
    #  Rien à défaire : on ne sait pas quelle fréquence était réglée avant, et la
    #  rétablir au hasard serait pire que de la laisser quotidienne.
    pass
