"""La 0259 remet au vocabulaire de l'écran deux réponses de la FAQ servie (#1594).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte les deux réponses telles que la production les a gardées.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.seed.faq import FAQ_COMPLEMENTAIRE
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0259_faq_vocabulaire_suivi")


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(MIGRATION, sens)()


def _moteur(reponses: dict[str, str]):
    m = moteur_memoire()
    with m.begin() as conn:
        for ordre, (question, reponse) in enumerate(reponses.items()):
            conn.execute(
                text(
                    "INSERT INTO faq_item (categorie, question, reponse, ordre, actif, "
                    "cree_le, mis_a_jour_le) VALUES ('📱 Application 5Hostachy', :q, :r, "
                    ":o, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"q": question, "r": reponse, "o": ordre},
            )
    return m


def _reponses(moteur) -> dict[str, str]:
    with moteur.connect() as conn:
        return dict(conn.execute(text("SELECT question, reponse FROM faq_item")).all())


def _avant() -> dict[str, str]:
    return {question: avant for question, avant, _ in MIGRATION.ENTREES}


def _apres() -> dict[str, str]:
    return {question: apres for question, _, apres in MIGRATION.ENTREES}


def test_le_texte_d_apres_est_celui_du_seed():
    """Une base neuve et une base migrée servent la même réponse, au caractère près."""
    seed = {question: reponse for _, question, reponse, _ in FAQ_COMPLEMENTAIRE}
    for question, apres in _apres().items():
        assert seed.get(question) == apres, f"« {question} » : la migration et le seed divergent"


def test_les_deux_reponses_sont_corrigees_une_seule_fois():
    moteur = _moteur(_avant())
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    assert _reponses(moteur) == _apres()
    servi = " ".join(_reponses(moteur).values())
    assert "commentaire de suivi" not in servi
    assert "<strong>Saisi pour</strong>" not in servi


def test_une_reponse_retouchee_a_la_main_n_est_pas_touchee():
    question = "Pourquoi mon nom apparaît-il sur une demande que je n'ai pas saisie ?"
    retouchee = "Réponse réécrite par l'administrateur, qui parle encore de la section Saisi pour."
    reponses = {**_avant(), question: retouchee}
    moteur = _moteur(reponses)
    _jouer(moteur)
    lu = _reponses(moteur)
    assert lu[question] == retouchee
    autre = "Que voit le conseil syndical lorsqu'il traite mon affaire ?"
    assert lu[autre] == _apres()[autre], "la réponse intacte doit, elle, être corrigée"


def test_le_retour_arriere_remet_l_ancien_texte():
    moteur = _moteur(_avant())
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _reponses(moteur) == _avant()
