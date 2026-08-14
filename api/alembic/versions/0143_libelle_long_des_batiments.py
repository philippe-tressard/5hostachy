"""Libellé LONG des bâtiments — « Bât. 1 » devient « Bâtiment 1 », sans écraser un renommage.

`perimetre` porte deux champs pour la même chose dite de deux façons : `libelle`
et `libelle_court`. Le seed les remplissait à l'identique (« Bât. {id} »), ce qui
rendait le second inutile et imposait l'abréviation **partout** — y compris sur le
document imprimé remis aux nouveaux arrivants, où la place ne manque pas et où
« Bât. 1 » se lit moins bien que « Bâtiment 1 » (demandé le 14/08/2026 après
relecture du PDF en production).

Le seed est corrigé pour les installations futures, mais il ne repassera **jamais**
sur celle en service : l'arbre n'est posé qu'une fois (marqueur `perimetres_semes`,
migration `0140`). D'où cette migration — même raison d'être que `0141` pour les
icônes, et même garantie.

**Elle ne touche que les libellés RESTÉS TELS QUE POSÉS**, c'est-à-dire ceux qui
valent encore exactement « Bât. {id} ». Un bâtiment renommé depuis
`/admin/patrimoine` — « Le Cèdre », « Bâtiment A » — n'est jamais réécrit : le
produit initialise, l'administrateur décide. C'est aussi ce qui la rend rejouable
sans dommage, et ce qui la rend sûre alors même qu'elle modifie une donnée déjà
affichée.

⚠️ Conséquence assumée, visible ailleurs que sur le document : `perimetre_label`
(API) et `perimetreLabel` (site) rendent le `libelle`, donc les badges du fil et
les e-mails diront « Bâtiment 1 ». Le calendrier et le sélecteur de périmètre,
eux, lisent `libelle_court` et gardent « Bât. 1 » — ce sont les deux endroits où
la place est réellement contrainte, et c'est précisément le partage que les deux
champs existent pour porter.
"""
from alembic import op
from sqlalchemy import text

revision = "0143"
down_revision = "0142"
branch_labels = None
depends_on = None


def _table_existe(nom: str) -> bool:
    return op.get_bind().execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:nom"),
        {"nom": nom},
    ).first() is not None


def decider(libelle: str, libelle_court: str | None, batiment_id: int):
    """Ce que devient un nœud de bâtiment, ou `None` s'il ne faut pas y toucher.

    Fonction **pure**, isolée pour être testable : contrairement à `0141` qui ne
    remplissait que des champs vides, celle-ci réécrit une donnée déjà affichée.
    La règle de non-écrasement est donc ce qu'il faut vérifier, et un test ne peut
    pas le faire à travers `op.get_bind()`.
    Voir `api/tests/test_migration_libelle_long.py`.
    """
    abrege = f"Bât. {batiment_id}"
    if libelle != abrege:
        return None                      # renommé depuis l'administration : intouchable
    return (
        f"Bâtiment {batiment_id}",
        #  L'abrégé n'est (re)posé que s'il était vide ou identique au long : un
        #  administrateur qui a saisi le sien le garde.
        abrege if not libelle_court or libelle_court == abrege else libelle_court,
    )


def upgrade() -> None:
    if not _table_existe("perimetre"):
        return

    bind = op.get_bind()
    #  Les seuls nœuds concernés : ceux qui SONT un bâtiment (`batiment_id` non
    #  nul — ses espaces ne portent pas le champ) et dont le libellé n'a jamais
    #  bougé. La comparaison se fait en Python plutôt qu'en SQL : construire
    #  « Bât. {id} » dans la requête demanderait une concaténation dépendante du
    #  moteur, et surtout aucune f-string ne doit entrer dans un `op.execute`.
    lignes = bind.execute(
        text("SELECT id, batiment_id, libelle, libelle_court FROM perimetre "
             "WHERE batiment_id IS NOT NULL")
    ).fetchall()

    for identifiant, batiment_id, libelle, libelle_court in lignes:
        decision = decider(libelle, libelle_court, batiment_id)
        if decision is None:
            continue
        long, court = decision
        bind.execute(
            text("UPDATE perimetre SET libelle = :long, libelle_court = :court "
                 "WHERE id = :id AND libelle = :attendu"),
            {"long": long, "court": court, "id": identifiant, "attendu": libelle},
        )


def downgrade() -> None:
    #  Symétrique et tout aussi prudente : on ne ramène à « Bât. {id} » que ce qui
    #  vaut exactement « Bâtiment {id} », donc ce que cette migration a posé.
    if not _table_existe("perimetre"):
        return

    bind = op.get_bind()
    lignes = bind.execute(
        text("SELECT id, batiment_id, libelle FROM perimetre WHERE batiment_id IS NOT NULL")
    ).fetchall()
    for identifiant, batiment_id, libelle in lignes:
        attendu = f"Bâtiment {batiment_id}"
        if libelle != attendu:
            continue
        bind.execute(
            text("UPDATE perimetre SET libelle = :abrege WHERE id = :id AND libelle = :attendu"),
            {"abrege": f"Bât. {batiment_id}", "id": identifiant, "attendu": attendu},
        )
