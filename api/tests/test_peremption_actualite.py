"""Une information datée sort du fil toute seule (#1093).

## Le besoin

« Coupure d'eau jeudi 9h-12h » n'a plus aucun intérêt vendredi ; « Nouveau
règlement de stationnement » n'en perd jamais. Rien ne les distinguait, et le
fil accumulait.

## 🔴 Dérivée à la lecture, JAMAIS recopiée à l'écriture

    perime_le =  fin de l'événement      si date d'événement
          sinon  jamais

⚠️ Il y avait un troisième champ en tête, `visible_jusqu_au`, saisi par
l'auteur pour une « durée de vie choisie ». Livré le matin du 22/09/2026,
retiré l'après-midi, arbitré à l'écran : *« cette date est à enlever, elle
est calculée par l'appli »*. Ce qui n'a pas de date d'événement ne périme
pas — l'archivage à trente jours couvre ce cas depuis le 19/08/2026, et le
champ faisait donc saisir ce que le produit savait déjà décider.

Calculer la péremption à la création laisserait un report d'événement
(jeudi → mardi) derrière lui : la date stockée dirait encore jeudi. C'est le
motif « deux copies qui divergent sur le cas limite », déjà vu trois fois dans
ce dépôt. Une source, une fonction.

## Périmée ≠ supprimée

Elle quitte le fil et le calendrier, elle **entre aux archives**, et son URL
directe continue d'ouvrir quelque chose — un lien envoyé il y a trois semaines
ne doit pas mener nulle part. C'est exactement ce que fait l'archivage : il
n'efface rien.

## ⚠️ La péremption DÉPINGLE

L'ordre des règles n'est pas cosmétique. L'épinglage interdit l'archivage
automatique — « garder en vue » — mais une information périmée n'a plus rien à
garder en vue. La péremption passe donc **avant** l'épinglage, et c'est la
seule règle qui le fasse après la décision humaine d'archiver.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.utils.archivage import est_archivable, perime_le


class _Pub:
    """Le strict nécessaire : l'archivage est PUR, il ne lit qu'un objet."""

    def __init__(self, **champs):
        self.statut = champs.get("statut", "publie")
        self.statut_change_le = champs.get("statut_change_le")
        self.publiee_le = champs.get("publiee_le")
        self.cree_le = champs.get("cree_le", datetime(2026, 9, 1))
        self.archivee = champs.get("archivee", False)
        self.epingle = champs.get("epingle", False)
        self.brouillon = champs.get("brouillon", False)
        self.debut = champs.get("debut")
        self.fin = champs.get("fin")


AUJOURDHUI = datetime(2026, 9, 22, 10, 0)
HIER = AUJOURDHUI - timedelta(days=1)
DEMAIN = AUJOURDHUI + timedelta(days=1)


# ══════════════════════════════════════════════════════════════════════════════
#  La dérivation — trois familles, une seule saisie
# ══════════════════════════════════════════════════════════════════════════════


def test_une_actualite_permanente_ne_perime_jamais():
    """Le cas par défaut, et le plus fréquent : on ne saisit rien."""
    assert perime_le(_Pub()) is None


def test_une_actualite_datee_perime_a_la_fin_de_l_evenement():
    """« Coupure d'eau jeudi 9h-12h » : rien de plus à saisir."""
    pub = _Pub(debut=datetime(2026, 9, 24, 9), fin=datetime(2026, 9, 24, 12))
    assert perime_le(pub) == date(2026, 9, 24)


def test_la_peremption_NE_SE_SAISIT_PAS():
    """🔴 Le garde-fou de l'arbitrage du 22/09/2026, pas de son effet.

    Le champ a existé une demi-journée. Sans ce test, il suffirait qu'on le
    juge « pratique » un jour pour qu'il revienne — et il reviendrait avec sa
    promesse : faire saisir une date que le produit sait déjà calculer.

    Il regarde les DEUX portes : la colonne, et ce que le serveur accepte en
    entrée. Verrouiller la première seule laisserait passer un schéma qui
    accepte le champ et le jette en silence.
    """
    from app.models.core import Publication
    from app.schemas_publications import PublicationCreate, PublicationUpdate

    assert "visible_jusqu_au" not in Publication.model_fields, (
        "La colonne est revenue : la péremption se déduit, elle ne se saisit pas (#1093)."
    )
    for schema in (PublicationCreate, PublicationUpdate):
        assert "visible_jusqu_au" not in schema.model_fields, (
            f"{schema.__name__} accepte de nouveau une date de validité en entrée."
        )


def test_un_debut_sans_fin_perime_au_debut():
    """Un événement ponctuel n'a qu'une date, et elle suffit à le dater."""
    assert perime_le(_Pub(debut=datetime(2026, 9, 24, 18))) == date(2026, 9, 24)


def test_la_derivation_ne_lit_QUE_l_objet():
    """Pure : pas de base, pas d'horloge. C'est ce qui la rend éprouvable."""
    pub = _Pub(fin=datetime(2026, 9, 30, 12))
    assert perime_le(pub) == perime_le(pub)


# ══════════════════════════════════════════════════════════════════════════════
#  L'effet : elle quitte les listes actives
# ══════════════════════════════════════════════════════════════════════════════


def test_le_jour_meme_elle_est_encore_la():
    """🔴 La péremption est au SOIR du jour dit, pas à son matin.

    Une coupure d'eau qui finit aujourd'hui à midi reste lisible ce soir : la
    date dit la fin de l'événement, pas l'heure à laquelle on l'efface.
    """
    pub = _Pub(fin=AUJOURDHUI)
    assert est_archivable("publication", pub, maintenant=AUJOURDHUI) is False


def test_le_lendemain_elle_sort():
    pub = _Pub(fin=HIER)
    assert est_archivable("publication", pub, maintenant=AUJOURDHUI) is True


def test_une_date_a_venir_ne_change_rien():
    pub = _Pub(fin=DEMAIN)
    assert est_archivable("publication", pub, maintenant=AUJOURDHUI) is False


def test_la_peremption_DEPINGLE():
    """⚠️ L'épinglage interdit l'archivage automatique — mais pas celui-ci.

    « Garder en vue » n'a plus de sens pour une information qui n'est plus
    valable. Sans cette règle, une coupure d'eau épinglée resterait en tête du
    fil indéfiniment, et c'est le seul cas où l'épinglage nuit.
    """
    pub = _Pub(fin=HIER, epingle=True)
    assert est_archivable("publication", pub, maintenant=AUJOURDHUI) is True


def test_un_brouillon_perime_ne_sort_pas_puisqu_il_n_est_pas_entre():
    """Il n'a rien à quitter : il n'a jamais été publié."""
    pub = _Pub(fin=HIER, brouillon=True)
    assert est_archivable("publication", pub, maintenant=AUJOURDHUI) is False


def test_l_archivage_manuel_prime_toujours():
    """Une décision humaine ne se discute pas, périmée ou non."""
    pub = _Pub(archivee=True)
    assert est_archivable("publication", pub, maintenant=AUJOURDHUI) is True


@pytest.mark.parametrize("type_objet", ["ticket", "evenement", "annonce"])
def test_les_autres_objets_ne_periment_pas(type_objet):
    """🔴 Une AFFAIRE ne périme jamais — elle se clôt.

    Une fuite d'eau ne cesse pas d'exister parce que personne n'a écrit depuis
    trois mois. L'équivalent est un signalement au conseil (« 4 affaires sans
    suite depuis 60 jours ») : c'est un manque de suivi, et le remède est qu'on
    s'en occupe, pas qu'elle disparaisse.

    Ce test vérifie que la règle de péremption ne s'est pas répandue aux autres
    types par un `getattr` trop large.
    """
    from app.utils.archivage import REGLES

    regle = REGLES.get(type_objet)
    if regle is None:
        pytest.skip(f"{type_objet} n'est pas déclaré")
    assert regle.champs_peremption == (), (
        f"{type_objet} périmerait tout seul : seule une ACTUALITÉ le fait."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Le chemin réel vers l'écran : modèle → schéma
# ══════════════════════════════════════════════════════════════════════════════


def test_la_derivation_traverse_le_schema_de_lecture():
    """🔴 Une règle juste que personne ne lit ne change rien à l'écran.

    `perime_le` est une propriété du modèle, que `PublicationRead` lit par
    `from_attributes`. Sans ce test, la fonction pourrait être parfaite et la
    date ne jamais arriver au navigateur — c'est exactement ce qui est arrivé
    à `debut`/`fin`, saisissables depuis #1092 et **jamais rendus**.
    """
    from app.models.core import Publication
    from app.schemas_publications import PublicationRead

    pub = Publication(
        id=1, titre="Assemblée générale", contenu="…", auteur_id=1,
        debut=datetime(2026, 9, 30, 18), fin=datetime(2026, 9, 30, 21),
    )
    lu = PublicationRead.model_validate(pub)
    assert lu.fin == datetime(2026, 9, 30, 21)
    assert lu.perime_le == date(2026, 9, 30)


def test_une_actualite_datee_rend_sa_peremption_sans_rien_saisir():
    """La deuxième famille : `debut`/`fin` suffisent, l'auteur n'ajoute rien."""
    from app.models.core import Publication
    from app.schemas_publications import PublicationRead

    pub = Publication(
        id=2, titre="Coupure d'eau", contenu="…", auteur_id=1,
        debut=datetime(2026, 9, 24, 9), fin=datetime(2026, 9, 24, 12),
    )
    lu = PublicationRead.model_validate(pub)
    assert lu.perime_le == date(2026, 9, 24)


def test_la_peremption_ne_se_STOCKE_nulle_part():
    """⚠️ Le garde-fou de la décision, pas de son effet.

    Une colonne `perime_le` survivrait à un report d'événement : jeudi devient
    mardi, la colonne dit encore jeudi, et l'actualité quitte le fil le jour où
    elle redevient utile. Ce test refuse qu'on l'ajoute un jour « pour
    accélérer une requête ».
    """
    from app.models.core import Publication

    assert "perime_le" not in Publication.model_fields, (
        "`perime_le` est devenue une COLONNE : elle se dérive à la lecture, "
        "sinon elle diverge au premier report de date (#1093)."
    )


def test_le_report_d_un_evenement_deplace_la_peremption():
    """La conséquence concrète de la dérivation : rien à resynchroniser."""
    from app.models.core import Publication

    pub = Publication(
        id=3, titre="Réunion", contenu="…", auteur_id=1,
        fin=datetime(2026, 9, 24, 12),
    )
    assert perime_le(pub) == date(2026, 9, 24)
    pub.fin = datetime(2026, 9, 29, 12)  # reportée
    assert perime_le(pub) == date(2026, 9, 29)
