"""Le document imprimé nomme les bâtiments comme l'application, ou il ne sert à rien.

Le document « Consignes de la copropriété » écrivait `Bât. {numero}` à la main
(#335). Deux conséquences, dont la seconde est la vraie :

1. aucune icône de périmètre, là où l'écran en montre une depuis la v2.57.0 ;
2. **le renommage d'un bâtiment depuis `/admin/patrimoine` ne l'atteignait pas.**

Le second défaut ne pouvait se voir nulle part : ce document ne passe par aucun
écran, personne ne compare son en-tête à celui du site. Le seed nommait d'ailleurs
les nœuds « Bât. {id} » quand la fiche écrivait « Bât. {numero} » — les deux ne
disaient déjà pas la même chose sur une base où l'un diffère de l'autre.

Le test qui compte ici est `test_un_batiment_renomme_apparait_renomme` : c'est le
seul qui prouve qu'on passe par l'arbre, et non par une convention recopiée qui
produirait par hasard le même texte.
"""
from __future__ import annotations

import re

from sqlmodel import Session, select

from app.database import engine
from app.models.perimetre import Perimetre
from app.utils import perimetres as P
from app.utils.fiche_arrivant import generer_fiche_arrivant
from app.utils.pdf_theme import icone_svg


def _fiche(membres: list[dict]) -> str:
    return generer_fiche_arrivant(
        cs_data={"membres": membres},
        syndic_data={"nom_syndic": "Syndic Test", "adresse": "1 rue Test", "membres": []},
        site_url="5hostachy.fr",
        whatsapp_url=None,
        annee=2026,
    )


def _membre(batiment_id: int | None, nom: str = "Dupont") -> dict:
    return {
        "genre": "M.", "prenom": "Jean", "nom": nom,
        "batiment_id": batiment_id, "batiment_nom": str(batiment_id or "?"),
        "etage": "2", "est_gestionnaire_site": False, "est_president": False,
        "photo_url": None,
    }


def _entetes(html: str) -> list[str]:
    """Le contenu des en-têtes de bâtiment, dans leur ordre d'apparition."""
    return re.findall(r'<div class="bat-label">(.*?)</div>', html, re.S)


# ── Le libellé vient de l'arbre ───────────────────────────────────────────────

def test_le_document_nomme_les_batiments_avec_le_libelle_de_l_arbre(batiments):
    entetes = _entetes(_fiche([_membre(batiments[0])]))
    assert len(entetes) == 1
    assert f"Bâtiment {batiments[0]}" in entetes[0]


def test_un_batiment_renomme_apparait_renomme(batiments):
    """LE test du ticket : renommer dans l'administration doit atteindre le PDF.

    Un document qui produirait « Bât. 1 » par sa propre convention passerait le
    test précédent sans passer celui-ci.
    """
    with Session(engine) as session:
        noeud = session.exec(
            select(Perimetre).where(Perimetre.code == f"bat:{batiments[0]}")
        ).one()
        noeud.libelle = "Villa des Tilleuls"
        session.add(noeud)
        session.commit()
    P.invalider_cache()

    entetes = _entetes(_fiche([_membre(batiments[0])]))
    assert "Villa des Tilleuls" in entetes[0], (
        "le document ne suit pas le renommage : il fabrique encore son propre libellé"
    )
    assert f"Bâtiment {batiments[0]}" not in entetes[0]


def test_le_libelle_venu_de_la_base_est_echappe(batiments):
    """Un nom de bâtiment est une donnée : il ne doit pas pouvoir injecter de balise."""
    with Session(engine) as session:
        noeud = session.exec(
            select(Perimetre).where(Perimetre.code == f"bat:{batiments[0]}")
        ).one()
        noeud.libelle = '<script>alert(1)</script>'
        session.add(noeud)
        session.commit()
    P.invalider_cache()

    html = _fiche([_membre(batiments[0])])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_l_ordre_est_celui_de_l_administration(batiments):
    """`Noeud.ordre`, et non l'ordre alphabétique — « Bât. 10 » précédait « Bât. 2 »."""
    with Session(engine) as session:
        for rang, bid in enumerate(reversed(batiments[:3])):
            noeud = session.exec(
                select(Perimetre).where(Perimetre.code == f"bat:{bid}")
            ).one()
            noeud.ordre = rang
            session.add(noeud)
        session.commit()
    P.invalider_cache()

    entetes = _entetes(_fiche([_membre(b) for b in batiments[:3]]))
    lus = [int(re.search(r"Bâtiment (\d+)", e).group(1)) for e in entetes]
    assert lus == list(reversed(batiments[:3])), f"ordre ignoré : {lus}"


# ── L'icône ───────────────────────────────────────────────────────────────────

def test_le_document_porte_l_icone_du_perimetre(batiments):
    """Un bâtiment semé porte `building-2` : le document doit la dessiner."""
    entete = _entetes(_fiche([_membre(batiments[0])]))[0]
    assert "<svg" in entete, "aucune icône dans l'en-tête de bâtiment"
    assert "stroke=" in entete, (
        "l'icône n'a pas de couleur explicite — WeasyPrint n'hérite pas currentColor"
    )


def test_un_noeud_sans_icone_ne_produit_ni_carre_vide_ni_point_d_interrogation(batiments):
    """Cas zéro : `icone` est facultatif, et son absence est un état normal."""
    with Session(engine) as session:
        noeud = session.exec(
            select(Perimetre).where(Perimetre.code == f"bat:{batiments[0]}")
        ).one()
        noeud.icone = None
        session.add(noeud)
        session.commit()
    P.invalider_cache()

    entete = _entetes(_fiche([_membre(batiments[0])]))[0]
    assert "<svg" not in entete, "une icône est dessinée alors qu'aucune n'est définie"
    assert f"Bâtiment {batiments[0]}" in entete, "le libellé a disparu avec l'icône"


def test_icone_svg_rend_vide_sur_un_nom_absent_ou_inconnu():
    """Les trois entrées qui ne doivent rien produire, plutôt que quelque chose de faux."""
    assert icone_svg(None) == ""
    assert icone_svg("") == ""
    assert icone_svg("icone-qui-n-existe-pas") == ""
    assert icone_svg("building-2").startswith("<svg")


# ── Les replis ────────────────────────────────────────────────────────────────

def test_sans_arbre_le_document_se_produit_quand_meme(arbre_vide):
    """Une copropriété qui n'a pas configuré ses périmètres reçoit son document.

    Le repli passe par `perimetre_label_un`, qui porte déjà la convention
    `bat:{id}` — elle n'est pas réécrite dans le générateur du document.
    """
    entetes = _entetes(_fiche([_membre(7)]))
    assert entetes == [] or "Bât. 7" in entetes[0]  # repli hors arbre : la convention du code
    assert "<svg" not in (entetes[0] if entetes else "<svg")


def test_un_membre_sans_batiment_reste_affiche_sous_un_entete_lisible(batiments):
    """Le faire disparaître serait pire — mais « ? » n'est pas lisible non plus.

    Ce document est imprimé et remis à un nouvel arrivant : il n'a aucun moyen
    d'interpréter le « Bât. ? » que produisait la version précédente.
    """
    html = _fiche([_membre(None, nom="Sansbat")])
    assert "SANSBAT" in html, "un membre non rattaché a disparu du document"
    entetes = _entetes(html)
    assert entetes == ["Bâtiment non précisé"], entetes


def test_l_entete_neutre_passe_en_dernier(batiments):
    """Les bâtiments réels d'abord ; l'en-tête neutre ne s'intercale pas."""
    entetes = _entetes(_fiche([_membre(None), _membre(batiments[0])]))
    assert entetes[-1] == "Bâtiment non précisé", entetes
