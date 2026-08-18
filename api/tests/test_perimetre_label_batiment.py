"""Un espace de bâtiment se lit avec son bâtiment — des DEUX côtés.

## Pourquoi ce garde-fou (18/08/2026)

Le gabarit du patrimoine pose les **mêmes neuf espaces** sous chaque bâtiment —
Hall, Paliers, Escaliers, Ascenseur, Caves, Toit, Local électrique… Un ticket
visant les toits de deux bâtiments s'affichait donc :

    Toit · Toit

Deux mentions identiques, et rien pour dire de quel bâtiment il s'agit. Signalé à
l'écran, sur une carte de ticket puis, **une seconde fois**, sur le fil d'activité.

## 🔴 Ce que la seconde fois enseigne, et qui est l'objet de ce test

La règle a d'abord été corrigée **côté front** (`front/src/lib/perimetres.ts`).
Le fil d'activité a continué d'afficher « Toit · Toit » — parce que ses libellés
sont calculés **côté serveur** (`app/utils/perimetres.py`) et transportés déjà mis
en forme.

Une même règle, deux implémentations, une seule corrigée : c'est très exactement
ce que la mémoire `project_partage_front_api_impossible` décrit — les contextes de
build sont `./api` et `./front`, rien de la racine n'entre dans les images, et
**le seul pattern viable est la copie plus un test**. Sans ce test, la troisième
occurrence est une question de temps.

⚠️ Ce fichier ne peut pas vérifier le front (il ne s'exécute pas en Python). Il
verrouille la forme **serveur** et **nomme** son jumeau, pour qu'une correction
d'un côté rappelle l'autre.
"""
from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel, delete

from app.database import engine
from app.models.perimetre import Perimetre
#  Importé pour ses tables : `create_all` ne peut pas résoudre la clé étrangère
#  `perimetre.modifie_par_id` sans le modèle `Utilisateur` en mémoire.
from app.models.core import Utilisateur  # noqa: F401
from app.utils import perimetres as P


@pytest.fixture()
def arbre_deux_batiments():
    """Deux bâtiments, chacun avec un « Toit » — le cas qui a produit le défaut."""
    SQLModel.metadata.create_all(engine)
    suffixe = uuid.uuid4().hex[:6]
    codes = []
    with Session(engine) as session:
        session.exec(delete(Perimetre))
        session.commit()
        for numero in (3, 4):
            bat = f"bat{suffixe}:{numero}"
            noeud_bat = Perimetre(
                code=bat, libelle=f"Bâtiment {numero}",
                libelle_court=f"Bât. {numero}", description="", batiment_id=numero,
                profondeur=0, ordre=numero, actif=True, selectionnable=True,
            )
            session.add(noeud_bat)
            #  ⚠️ Le lien de parenté est `parent_id`, un ENTIER — pas un code. Mon
            #  premier jet posait `parent="bat:3"` : SQLModel ignore en silence un
            #  champ qui n'existe pas, l'arbre voyait donc un toit SANS parent, et
            #  le test accusait le code de production d'un défaut qui était le sien.
            #  Il faut donc committer le bâtiment AVANT, pour disposer de son id.
            session.commit()
            session.refresh(noeud_bat)
            toit = f"{bat}/toit"
            session.add(Perimetre(
                code=toit, parent_id=noeud_bat.id, libelle="Toit",
                libelle_court="Toit", description="", batiment_id=numero,
                profondeur=1, ordre=1, actif=True, selectionnable=True,
            ))
            codes.append((bat, toit))
        session.commit()
    P.invalider_cache()
    yield codes
    with Session(engine) as session:
        session.exec(delete(Perimetre))
        session.commit()
    P.invalider_cache()


def test_deux_toits_ne_se_lisent_plus_pareil(arbre_deux_batiments):
    """« Toit · Toit » devient « Bât. 3 › Toit · Bât. 4 › Toit »."""
    (_, toit3), (_, toit4) = arbre_deux_batiments

    rendu = P.perimetre_label([toit3, toit4])

    assert rendu == "Bât. 3 › Toit · Bât. 4 › Toit", rendu
    #  Le fait, pas le symptôme : les deux mentions doivent être DISTINCTES.
    #  Un test qui n'affirmerait que « ça contient Toit » serait passé au vert sur
    #  le défaut qu'il est censé attraper.
    gauche, droite = rendu.split(" · ")
    assert gauche != droite


def test_un_batiment_entier_garde_son_libelle(arbre_deux_batiments):
    """Seuls les ESPACES sont qualifiés — un bâtiment ne se préfixe pas lui-même."""
    (bat3, _), _ = arbre_deux_batiments

    assert P.perimetre_label_un(bat3) == "Bâtiment 3"


def test_le_front_porte_la_meme_regle():
    """Le jumeau TypeScript existe et qualifie, lui aussi, par le parent.

    ⚠️ Contrôle de PRÉSENCE, pas d'exécution : ce test ne peut pas lancer le
    module front. Il vérifie que la règle y est écrite et signale son absence —
    ce qui est déjà plus que rien, puisque c'est justement l'oubli d'un des deux
    côtés qui a produit le défaut deux fois.

    Un contrôle qui ne peut pas mesurer doit le DIRE : si le fichier est
    introuvable, ce test échoue au lieu de conclure au vert (`standards/04` §2).
    """
    from pathlib import Path

    jumeau = Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "perimetres.ts"
    assert jumeau.exists(), (
        f"{jumeau} est introuvable : ce contrôle ne peut plus rien établir. "
        "Ne pas lire son silence comme un succès."
    )
    source = jumeau.read_text(encoding="utf-8")
    assert "batiment_id" in source and "›" in source, (
        "La qualification d'un espace par son bâtiment a disparu du front. "
        "Les deux implémentations doivent rester d'accord — la copie est le seul "
        "pattern viable entre `./api` et `./front`, et elle se vérifie ici."
    )
