"""Arborescence des périmètres — proposition de départ, entièrement remplaçable.

## Ce que ce module n'est pas

Ce n'est **pas** la liste des périmètres du produit. C'est une proposition initiale
pour la copropriété des Hostachy, que l'administration peut renommer, réordonner,
désactiver ou supprimer intégralement. Une autre copropriété n'a ni AFUL, ni quatre
bâtiments, ni forcément de caves — et aura peut-être une piscine, un local commercial
et trois entrées. Tout le code lit la table `perimetre` ; rien ne lit ce fichier.

## Les deux règles qui gouvernent ce qui est écrit ici

**1. Les libellés des périmètres déjà en service sont recopiés à l'identique.**
`résidence` → « Copropriété entière », `parking` → « Parking », `cave` → « Cave »,
`aful` → « AFUL », `bat:N` → « Bât. N ». Ces cinq libellés s'affichent aujourd'hui
sur des actualités, des tickets et des événements déjà publiés : les « améliorer »
au passage serait un changement visible, et ce lot n'en fait aucun. Ils se corrigent
depuis l'écran d'administration, un par un, en connaissance de cause.

C'est aussi pourquoi un bâtiment est libellé « Bât. {id} » et non « Bât. {numero} » :
la table de libellés supprimée produisait `Bât. 3` pour le code `bat:3`, où `3` est
l'**identifiant**. Sur l'installation de référence, `numero` vaut « 1 » à « 4 » et
les deux coïncident ; sur une copropriété dont les bâtiments seraient lettrés, afficher
« Bât. A » serait plus juste — mais ce serait un changement, et il appartient à
l'administrateur, pas à ce fichier. Le `numero` est rappelé dans la description pour
qu'il ait l'information sous les yeux.

**2. `cave` est conservé mais retiré de la saisie.** La cave relève d'un bâtiment :
la façon normale de la cibler devient `bat:N/caves`. Mais `cave` est aujourd'hui un
périmètre transverse visible de tous, et des contenus le citent déjà — le déplacer
sous les bâtiments changerait qui les voit. Il garde donc `portee_globale`, passe
`selectionnable = False`, et sa description dit par quoi il est remplacé. Personne ne
gagne ni ne perd un accès, et la pastille disparaît simplement du formulaire.

## Icônes

Volontairement absentes. `Icon.svelte` ne rend que les noms présents dans sa table ;
en inventer ici produirait des badges vides. Elles seront posées avec l'écran
d'administration, une fois la table d'icônes consultée.
"""
from sqlmodel import Session, select

from app.models.core import Batiment
from app.models.perimetre import Perimetre

#: Espaces posés sous chaque bâtiment. `(suffixe de code, libellé, description)`.
#: C'est le « gabarit » que l'écran d'administration proposera de réappliquer.
#: On s'arrête à l'espace : pas de niveau « élément » (porte, éclairage, canalisation),
#: la finesse utile pour localiser une demande s'arrête là.
GABARIT_BATIMENT: list[tuple[str, str, str]] = [
    ("hall", "Hall d'entrée",
     "Le hall du bâtiment : sas, boîtes aux lettres, interphone, affichage."),
    ("paliers", "Paliers",
     "Les paliers d'étage du bâtiment, du rez-de-chaussée au dernier niveau."),
    ("escaliers", "Escaliers",
     "La cage d'escalier du bâtiment, garde-corps et éclairage compris."),
    ("ascenseur", "Ascenseur",
     "L'ascenseur du bâtiment, sa cabine, sa gaine et sa machinerie."),
    ("caves", "Caves",
     "Les caves de ce bâtiment. Remplace l'ancien périmètre « Cave », "
     "qui désignait les caves de toute la copropriété sans distinction."),
    ("toit", "Toit",
     "Toiture et charpente du bâtiment, y compris les descentes d'eaux pluviales."),
    ("local-electrique", "Local électrique",
     "Le local électrique propre à ce bâtiment — à distinguer des locaux techniques "
     "partagés par toute la copropriété."),
    ("jardins-privatifs", "Jardins privatifs",
     "Les jardins attachés aux lots du rez-de-chaussée. Parties privatives : "
     "une demande qui les concerne relève de leur occupant."),
    ("autres", "Autres espaces",
     "Tout espace du bâtiment qui n'entre pas dans les catégories ci-dessus."),
]


def _racines() -> list[dict]:
    """Les nœuds de premier niveau et leurs enfants directs.

    `parent_id = NULL` sur tous : « Copropriété entière » n'est **pas** le parent
    des autres. S'il l'était, sa portée globale serait héritée par l'arbre entier
    et tout deviendrait visible de tous — y compris les espaces d'un bâtiment.
    """
    return [
        {
            "code": "résidence",
            "libelle": "Copropriété entière",
            "libelle_court": "Copropriété",
            "description":
                "Toute la copropriété. C'est le périmètre le plus large : le contenu "
                "est visible de tous les résidents et notifie l'ensemble du conseil "
                "syndical. C'est aussi le périmètre retenu par défaut quand aucun "
                "autre n'est précisé.",
            "portee_globale": True,
            "selectionnable": True,
            "ordre": 0,
        },
        {
            "code": "batiments",
            "libelle": "Bâtiments",
            "libelle_court": "Bâtiments",
            "description":
                "Regroupement des bâtiments. Ce nœud ne se cible pas lui-même : on "
                "choisit un bâtiment, ou l'un de ses espaces.",
            "portee_globale": False,
            "selectionnable": False,
            "ordre": 10,
        },
        {
            "code": "parking",
            "libelle": "Parking",
            "libelle_court": "Parking",
            "description":
                "Le parking privé de la copropriété, au niveau −2. On y accède par le "
                "portail depuis le parking public de l'AFUL, au niveau −1. Concerne "
                "tous les résidents.",
            "portee_globale": True,
            "selectionnable": True,
            "ordre": 20,
            "enfants": [
                ("places", "Places", "Les places de stationnement et leur marquage."),
                ("voies", "Voies de circulation",
                 "Les voies de circulation et de manœuvre du parking."),
                ("portail", "Portail d'accès",
                 "Le portail qui sépare le parking privé de la copropriété (−2) du "
                 "parking public de l'AFUL (−1). Il protège le parking privé : son "
                 "entretien revient à la copropriété."),
                ("eclairage", "Éclairage",
                 "L'éclairage du parking, éclairage de sécurité compris."),
            ],
        },
        {
            "code": "cave",
            "libelle": "Cave",
            "libelle_court": "Cave",
            "description":
                "Ancien périmètre désignant les caves de toute la copropriété sans "
                "distinction de bâtiment. Conservé pour que les contenus déjà publiés "
                "gardent leur libellé et leur visibilité, mais **plus proposé à la "
                "saisie** : une cave relève d'un bâtiment, il faut désormais choisir "
                "les caves du bâtiment concerné.",
            "portee_globale": True,
            "selectionnable": False,
            "ordre": 30,
        },
        {
            "code": "aful",
            "libelle": "AFUL",
            "libelle_court": "AFUL",
            "description":
                "Le parking public géré par l'association foncière urbaine libre, au "
                "niveau −1 : celui que l'on traverse pour rejoindre le parking de la "
                "copropriété. Il n'appartient pas à la copropriété, mais celle-ci "
                "participe à son assemblée générale. Concerne tous les résidents.",
            "portee_globale": True,
            "selectionnable": True,
            "ordre": 40,
        },
        {
            "code": "espaces-verts",
            "libelle": "Espaces verts",
            "libelle_court": "Espaces verts",
            "description":
                "Les espaces verts communs de la copropriété. Concerne tous les "
                "résidents.",
            "portee_globale": True,
            "selectionnable": True,
            "ordre": 50,
            "enfants": [
                ("pelouses", "Pelouses", "Les surfaces engazonnées et leur tonte."),
                ("massifs", "Massifs", "Les massifs plantés et leur entretien."),
                ("arbres", "Arbres", "Les arbres de la copropriété, élagage compris."),
                ("jardins", "Jardins", "Les jardins communs, hors jardins privatifs."),
            ],
        },
        {
            "code": "cheminements",
            "libelle": "Cheminements",
            "libelle_court": "Cheminements",
            "description":
                "Les circulations extérieures de la copropriété, hors bâtiment et hors "
                "parking. Concerne tous les résidents.",
            "portee_globale": True,
            "selectionnable": True,
            "ordre": 60,
            "enfants": [
                ("chemin-pietonne", "Chemin piétonné",
                 "Le chemin piétonné traversant la copropriété : revêtement, bordures, "
                 "signalisation."),
                ("escalier-exterieur", "Escalier extérieur",
                 "Les escaliers extérieurs et leurs garde-corps."),
                ("acces-batiments", "Accès aux bâtiments",
                 "Les allées et rampes desservant les entrées des bâtiments."),
                ("eclairage-exterieur", "Éclairage extérieur",
                 "L'éclairage des cheminements et des abords."),
            ],
        },
        {
            "code": "locaux-techniques",
            "libelle": "Locaux techniques",
            "libelle_court": "Locaux tech.",
            "description":
                "Les locaux techniques **partagés** par toute la copropriété. Ceux qui "
                "appartiennent à un bâtiment donné — son local électrique, par exemple "
                "— sont rangés sous ce bâtiment.",
            "portee_globale": True,
            "selectionnable": True,
            "ordre": 70,
            "enfants": [
                ("chaufferie", "Chaufferie",
                 "La chaufferie commune et la production d'eau chaude collective."),
                ("local-eau", "Local eau",
                 "Le local d'arrivée d'eau et le comptage général."),
                ("autres", "Autres locaux techniques",
                 "Tout local technique partagé qui n'entre pas dans les catégories "
                 "ci-dessus."),
            ],
        },
    ]


def _poser(session: Session, connus: dict[str, int], entree: dict,
           parent_id: int | None) -> int:
    """Pose un nœud s'il est absent, et renvoie son identifiant dans tous les cas.

    Le `flush` est nécessaire et non décoratif : les enfants ont besoin de l'`id`
    du parent, que SQLite n'attribue qu'à l'écriture.
    """
    code = entree["code"]
    if code in connus:
        return connus[code]
    noeud = Perimetre(
        code=code,
        parent_id=parent_id,
        libelle=entree["libelle"],
        libelle_court=entree.get("libelle_court"),
        description=entree.get("description", ""),
        batiment_id=entree.get("batiment_id"),
        portee_globale=entree.get("portee_globale", False),
        selectionnable=entree.get("selectionnable", True),
        ordre=entree.get("ordre", 0),
    )
    session.add(noeud)
    session.flush()
    connus[code] = noeud.id
    return noeud.id


def poser_arborescence(session: Session) -> int:
    """Pose les nœuds absents de l'arborescence. N'écrase jamais un nœud existant.

    Suit la règle du paquet `seed` : ce qui est déjà là est laissé tel quel,
    personnalisations comprises. Un administrateur qui a renommé « AFUL » ou
    supprimé « Cheminements » ne les verra pas revenir — sauf pour la suppression,
    qu'un seed ne peut pas distinguer d'une absence initiale ; c'est la raison
    pour laquelle l'écran propose de **désactiver** plutôt que de supprimer.

    Renvoie le nombre de nœuds posés.
    """
    connus = {
        code: identifiant
        for identifiant, code in session.exec(
            select(Perimetre.id, Perimetre.code)
        ).all()
    }
    avant = len(connus)

    for racine in _racines():
        racine_id = _poser(session, connus, racine, None)
        for rang, (suffixe, libelle, description) in enumerate(racine.get("enfants", [])):
            _poser(session, connus, {
                "code": f"{racine['code']}/{suffixe}",
                "libelle": libelle,
                "description": description,
                #  Pas de `portee_globale` sur les enfants : ils l'héritent de leur
                #  parent au moment de la lecture. La poser deux fois, c'est
                #  autoriser les deux valeurs à diverger.
                #
                #  `ordre` suit l'ordre de déclaration : sans lui, tous les enfants
                #  valaient 0 et se rangeaient alphabétiquement — « Éclairage »
                #  arrivait avant « Places » sous Parking.
                "ordre": rang,
            }, racine_id)

    _poser_les_batiments(session, connus)
    return len(connus) - avant


def _poser_les_batiments(session: Session, connus: dict[str, int]) -> None:
    """Un nœud par bâtiment réel, avec le gabarit d'espaces en dessous.

    Les bâtiments sont **lus dans la table `batiment`**, jamais énumérés en dur.
    L'implémentation précédente générait `bat:1` à `bat:9` par une boucle sur une
    constante `_BATIMENTS = 9` sans rapport avec le contenu de la base, tandis que
    le front s'arrêtait à `bat:4` : un cinquième bâtiment s'affichait « Bât. 5 »
    côté API et `bat:5` brut à l'écran.
    """
    parent_id = connus.get("batiments")
    if parent_id is None:
        return

    batiments = session.exec(select(Batiment).order_by(Batiment.id)).all()
    for rang, batiment in enumerate(batiments):
        code = f"bat:{batiment.id}"
        bat_id = _poser(session, connus, {
            "code": code,
            #  « Bât. {id} » et non « Bât. {numero} » : voir la règle 1 du
            #  docstring du module. Le numéro figure dans la description.
            "libelle": f"Bât. {batiment.id}",
            "libelle_court": f"Bât. {batiment.id}",
            "description":
                f"Le bâtiment {batiment.numero} et ses parties communes. "
                "Un contenu ciblé sur ce bâtiment, ou sur l'un de ses espaces, "
                "n'est visible que de ses résidents.",
            "batiment_id": batiment.id,
            "portee_globale": False,
            "selectionnable": True,
            "ordre": rang,
        }, parent_id)

        for rang_espace, (suffixe, libelle, description) in enumerate(GABARIT_BATIMENT):
            _poser(session, connus, {
                "code": f"{code}/{suffixe}",
                "libelle": libelle,
                "description": description,
                #  `batiment_id` non répété : il est hérité de l'ancêtre bâtiment.
                "ordre": rang_espace,
            }, bat_id)
