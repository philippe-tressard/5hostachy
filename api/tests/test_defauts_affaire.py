"""Les DESTINATAIRES d'une affaire SANS choix du conseil — la table de `defauts_affaire` (#1569).

Le module n'était nommé par aucun test (relevé du 02/10/2026, #1569) : son test
avait disparu au renommage de #1436. Sa lecture par statut est tenue ailleurs, contre
la pastille de l'écran (`test_lecture_pastille.py`) ; ce fichier tient CE QUE LE
MODULE DÉCIDE, objet en main, sans base :

1. chaque catégorie a son défaut, et le repli sur le conseil seul ne sert jamais ;
2. la Panne et l'Étude & travaux dépendent de leur catégorie ET de leur état ;
3. une actualité s'adresse à tous, jamais au repli fermé ;
4. « toute la résidence » ne vise que les copropriétaires — jamais les locataires ;
5. ce que `ticket_visible` / `reservee_au_conseil` en font : copropriétaire admis,
   locataire et mandataire refusés, affaire « Résident concerné » fermée à tous.
"""

from __future__ import annotations

import json

import pytest

from app.models.core import StatutUtilisateur, Ticket, Utilisateur
from app.models.tickets import STATUTS_ETUDE_OUVERTE, CategorieTicket, StatutTicket
from app.utils.visibility import reservee_au_conseil, ticket_visible
from app.utils.visibility.defauts_affaire import (
    CONCERNE,
    DEFAUT_INCONNU,
    DEFAUT_PAR_CATEGORIE,
    destinataires_par_defaut,
    lus_dans_toute_la_residence,
)

COPROPRIETAIRES = ["copropriétaires_occupants", "bailleurs"]


def _affaire(categorie: str, statut: str = "ouvert", **champs) -> Ticket:
    """Une affaire telle que la règle la lit — jamais enregistrée : seul le verdict compte."""
    champs.setdefault("perimetre_cible", json.dumps(["résidence"], ensure_ascii=False))
    return Ticket(
        numero="D-0001",
        titre="Défaut",
        description="…",
        categorie=categorie,
        statut=statut,
        auteur_id=-1,
        **champs,
    )


def _lecteur(statut: StatutUtilisateur, ident: int = 900) -> Utilisateur:
    """Un résident sans bâtiment ni base : suffit aux règles « toute la résidence »."""
    return Utilisateur(
        id=ident,
        email="lecteur@exemple.test",
        hashed_password="x",
        prenom="Sophie",
        nom="Morel",
        roles_json="résident",
        statut=statut,
        actif=True,
    )


# ── La table ────────────────────────────────────────────────────────────────


def test_chaque_categorie_d_affaire_a_son_defaut():
    """Le repli (conseil seul) est un filet : aucune catégorie réelle ne doit y tomber.

    La Panne (règle propre) et l'actualité (règle de l'actualité) sont les deux
    seules à ne pas figurer dans la table, et chacune a sa branche.
    """
    hors_table = {c.value for c in CategorieTicket if c.value not in DEFAUT_PAR_CATEGORIE} - {
        "panne",
        "actualite",
    }
    assert hors_table == set(), f"catégories sans défaut déclaré : {sorted(hors_table)}"


def test_la_table_n_est_pas_vide_et_ne_porte_que_des_categories_connues():
    assert DEFAUT_PAR_CATEGORIE, "cas zéro : une table vide ferait tout tomber sur le repli"
    inconnues = set(DEFAUT_PAR_CATEGORIE) - {c.value for c in CategorieTicket}
    assert inconnues == set(), f"entrées de la table sans catégorie : {sorted(inconnues)}"


@pytest.mark.parametrize(
    "categorie,attendu",
    [
        ("nuisance", [CONCERNE]),
        ("acces_accueil", [CONCERNE]),
        ("sinistre", [CONCERNE]),
        ("question", [CONCERNE]),
        ("bug", [CONCERNE]),
        ("espaces_verts", ["résidents"]),
        ("entretien", COPROPRIETAIRES),
    ],
)
def test_defaut_par_categorie(categorie, attendu):
    assert destinataires_par_defaut(_affaire(categorie)) == attendu


# ── Les deux catégories qui dépendent d'autre chose que d'elles-mêmes ───────


def test_une_panne_s_adresse_aux_coproprietaires_et_aux_locataires_du_perimetre():
    assert destinataires_par_defaut(_affaire("panne")) == [*COPROPRIETAIRES, "locataires"]


def test_une_etude_reste_au_conseil_tant_qu_elle_n_est_pas_ouverte():
    for statut in (StatutTicket.ouvert.value, StatutTicket.en_cours.value):
        assert statut not in STATUTS_ETUDE_OUVERTE
        assert destinataires_par_defaut(_affaire("etude_travaux", statut)) == ["conseil_syndical"]


@pytest.mark.parametrize("statut", sorted(STATUTS_ETUDE_OUVERTE))
def test_une_etude_s_ouvre_aux_coproprietaires_en_ag_chez_le_prestataire_ou_close(statut):
    assert destinataires_par_defaut(_affaire("etude_travaux", statut)) == COPROPRIETAIRES


def test_les_etats_d_ouverture_d_une_etude_sont_ceux_que_l_arbitrage_a_nommes():
    """Cas zéro et sens : si la liste se vidait, l'étude resterait au conseil à jamais."""
    assert {"en_ag", "chez_prestataire", "résolu", "annulé"} == set(STATUTS_ETUDE_OUVERTE)


def test_une_actualite_s_adresse_a_tous_et_ne_tombe_pas_sur_le_repli_ferme():
    defaut = destinataires_par_defaut(_affaire("actualite", "publie"))
    assert defaut == ["résidents"]
    assert defaut != DEFAUT_INCONNU


def test_une_categorie_inconnue_ne_peut_que_restreindre():
    assert destinataires_par_defaut(_affaire("categorie_de_demain")) == ["conseil_syndical"]
    assert DEFAUT_INCONNU == ["conseil_syndical"]


# ── « Toute la résidence » : les copropriétaires, et eux seuls ──────────────


def test_toute_la_residence_ne_vise_que_les_coproprietaires():
    #  La Panne a trois codes au défaut : le locataire n'en fait pas partie.
    assert lus_dans_toute_la_residence(_affaire("panne")) == COPROPRIETAIRES
    assert lus_dans_toute_la_residence(_affaire("entretien")) == COPROPRIETAIRES


@pytest.mark.parametrize("categorie", ["nuisance", "sinistre", "espaces_verts", "etude_travaux"])
def test_toute_la_residence_est_vide_sans_coproprietaire_vise(categorie):
    assert lus_dans_toute_la_residence(_affaire(categorie)) == []


def test_toute_la_residence_est_vide_pour_une_actualite():
    """Sa règle est ailleurs (`actualite_visible`) : ce n'est pas un défaut d'affaire."""
    assert lus_dans_toute_la_residence(_affaire("actualite", "publie")) == []


def test_une_etude_ouverte_se_lit_dans_toute_la_residence_une_etude_fermee_non():
    assert lus_dans_toute_la_residence(_affaire("etude_travaux", "en_ag")) == COPROPRIETAIRES
    assert lus_dans_toute_la_residence(_affaire("etude_travaux", "en_cours")) == []


# ── Ce que les règles de lecture en font ────────────────────────────────────


def test_un_coproprietaire_lit_un_entretien_sans_consulter_le_perimetre():
    """Occupant et bailleur lisent l'entretien de toute la résidence (standard du 30/09)."""
    entretien = _affaire("entretien", perimetre_cible=json.dumps(["bat:424242"]))
    for statut in (
        StatutUtilisateur.copropriétaire_résident,
        StatutUtilisateur.copropriétaire_bailleur,
    ):
        assert ticket_visible(entretien, _lecteur(statut)), statut


def test_ni_le_mandataire_ni_le_locataire_ne_lisent_un_entretien():
    entretien = _affaire("entretien", perimetre_cible=json.dumps(["bat:424242"]))
    for statut in (StatutUtilisateur.mandataire, StatutUtilisateur.locataire):
        assert not ticket_visible(entretien, _lecteur(statut)), statut


@pytest.mark.parametrize("categorie", ["nuisance", "sinistre", "question", "bug", "acces_accueil"])
def test_une_affaire_resident_concerne_est_fermee_aux_coproprietaires(categorie):
    assert not ticket_visible(
        _affaire(categorie), _lecteur(StatutUtilisateur.copropriétaire_résident)
    )


def test_l_auteur_lit_toujours_ce_qu_il_a_ecrit_meme_au_defaut_ferme():
    affaire = _affaire("nuisance")
    assert ticket_visible(affaire, _lecteur(StatutUtilisateur.locataire, ident=affaire.auteur_id))


def test_un_defaut_ferme_retient_l_affaire_du_hall_et_du_groupe():
    """`reservee_au_conseil` lit le défaut : rien ne sort d'une nuisance ni d'une étude au conseil."""
    assert reservee_au_conseil(_affaire("nuisance"))
    assert reservee_au_conseil(_affaire("etude_travaux", "ouvert"))
    assert not reservee_au_conseil(_affaire("entretien"))
    assert not reservee_au_conseil(_affaire("etude_travaux", "en_ag"))
    assert not reservee_au_conseil(_affaire("actualite", "publie"))


def test_un_choix_du_conseil_prime_sur_le_defaut_pour_la_diffusion():
    """Destinataires choisis : la nuisance n'est plus retenue par sa catégorie."""
    choisie = _affaire("nuisance", public_cible=json.dumps(["locataires"]))
    assert not reservee_au_conseil(choisie)
