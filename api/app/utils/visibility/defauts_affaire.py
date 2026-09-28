"""Les DESTINATAIRES d'une affaire SANS choix du conseil — ce que sa catégorie décide.

Extrait de `objets.py` le 28/09/2026 (#1436), qui touchait les 500 lignes en
recevant la table des défauts par catégorie. C'est une notion à part : QUI une
affaire regarde quand personne n'a choisi, que `ticket_visible` applique et que
`reservee_au_conseil` lit pour ne rien laisser sortir. Son miroir à l'écran est
`front/src/lib/lecture.ts`, et `tests/donnees/lecture_pastille.json` les tient
d'accord — un cas par catégorie.
"""

from __future__ import annotations

from app.models.core import Ticket
from app.utils.perimetres import batiments_cibles
from app.utils.valeurs import valeur

from .socle import _codes_json_pour_acces


#: Ce que lit une Panne sans choix du conseil, dans un bâtiment : ceux qui Y
#: VIVENT — occupants et locataires —, pas les bailleurs (#1343).
_DESTINATAIRES_PANNE_BATIMENT = ["copropriétaires_occupants", "locataires"]

#: « Résident concerné » : l'auteur, la personne pour qui l'affaire a été
#: saisie, et le conseil — ce que `confidentiel` veut dire sur une affaire.
#: Un DÉFAUT, jamais un code que l'écran envoie : le conseil qui le choisit
#: coche le drapeau. Inconnu de `public_cible_visible`, il ne ferait lire
#: personne — mais `ticket_visible` le traite avant, en toutes lettres.
CONCERNE = "concerné"

#: Ce qu'une affaire lit SANS choix du conseil, selon sa catégorie (#1436,
#: arbitré le 28/09/2026). Absente : les copropriétaires, la règle historique
#: de `ticket_visible` — Étude & travaux. La Panne a sa règle (le bâtiment).
#:
#: Une nuisance nomme souvent un voisin, un sinistre touche un lot, une
#: question est personnelle : les lire à tout un bâtiment exposait des données
#: personnelles. Un Entretien — contrats, fournisseurs, pièces — revient au
#: conseil, comme les maintenances migrées par 0232 (#1428).
#:
#: ⚠️ Miroir : `DEFAUT_PAR_CATEGORIE` (`front/src/lib/lecture.ts`), tenus
#: d'accord par `tests/donnees/lecture_pastille.json` — un cas par catégorie.
DEFAUT_PAR_CATEGORIE: dict[str, list[str]] = {
    "nuisance": [CONCERNE],
    "acces_accueil": [CONCERNE],
    "espaces_verts": ["résidents"],
    "sinistre": [CONCERNE],
    "entretien": ["conseil_syndical"],
    "question": [CONCERNE],
    "bug": [CONCERNE],
}

#: Les défauts qui ne laissent lire que le conseil — et l'auteur : rien ne sort.
_DEFAUTS_FERMES = ([CONCERNE], ["conseil_syndical"])


def destinataires_par_defaut(ticket: Ticket) -> list[str] | None:
    """Les Destinataires qu'une affaire a SANS choix du conseil, quand sa
    catégorie en décide (#1343, 26/09/2026 ; toutes depuis #1436) — `None` :
    la règle historique (les copropriétaires), écrite dans `ticket_visible`.

    Arbitré à l'écran : *« pour une catégorie Panne, tout le périmètre (sauf
    bailleurs) concernés, si le périmètre est un bâtiment ; hors bâtiments =
    tout le monde »*. Une panne d'ascenseur concerne qui prend l'ascenseur.

    « Dans un bâtiment » : CHAQUE code du périmètre descend d'un bâtiment
    (`batiments_cibles`) ; un seul espace commun — parking, espaces verts, la
    copropriété entière — et la panne concerne tout le monde.

    ⚠️ Miroir : `destinatairesParDefaut` (`front/src/lib/lecture.ts`), tenus
    d'accord par `tests/donnees/lecture_pastille.json`.
    """
    categorie = valeur(ticket.categorie)
    if categorie != "panne":
        return DEFAUT_PAR_CATEGORIE.get(categorie)
    #  Illisible : `cible_visible` refusera de toute façon, la valeur importe peu.
    codes = _codes_json_pour_acces(ticket.perimetre_cible) or []
    if codes and all(batiments_cibles([c]) for c in codes):
        return _DESTINATAIRES_PANNE_BATIMENT
    return ["résidents"]
