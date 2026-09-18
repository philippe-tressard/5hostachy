"""Un **accès** — vigik ou télécommande — décrit une fois, par un objet.

## 🔴 Pourquoi (14/09/2026, #779)

`routers/acces/resident.py` portait **quatre paires de fonctions jumelles** :
lister les miens, signaler une perte, supprimer, déclarer. Chaque paire disait
la même chose deux fois, à trois mots près — le modèle, sa table de liaison, et
le nom du champ qui porte la référence (``code`` pour le vigik, ``reference``
pour la télécommande).

Le dépôt savait déjà que c'était un défaut : ``_acces_admin_out`` porte, écrit à
la main, *« les deux ont les mêmes champs utiles, et deux fonctions jumelles
auraient divergé au premier ajout »*. Et ``detacher_acces`` avait été factorisé
pour la même raison (#546) — au prix de **six paramètres** que chaque appelant
devait rappeler dans le bon ordre.

🔴 **Elles avaient bel et bien divergé**, et personne ne l'avait vu : à la
déclaration d'un badge, la branche vigik recopiait le ``lot_id`` de la ligne
d'import sur l'objet créé, la branche télécommande non. Une télécommande
déclarée par son porteur restait donc **sans lot** dans la vue du conseil
syndical, alors que l'import connaissait le lot. La factorisation corrige ce
défaut en passant — c'est ce qu'elle a de mieux à offrir.

## Ce que cet objet est, et ce qu'il n'est pas

Il ne remplace pas les deux modèles : ``Vigik`` et ``Telecommande`` restent deux
tables, parce que ce sont deux objets physiques distincts que l'on compte
séparément. Il décrit **ce qui, dans le code, change de l'un à l'autre** — et
rien d'autre. Tout ce qui n'est pas ici est commun, donc s'écrit une fois.

⚠️ Un troisième accès (une clé, un bip de portail) s'ajoute en déclarant une
entrée ici. S'il fallait en plus recopier quatre fonctions, il serait ajouté à
moitié — c'est précisément ce qui est arrivé au ``lot_id``.
"""
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.core import (
    Telecommande,
    TelecommandeImport,
    UserTelecommande,
    UserVigik,
    Vigik,
    VigikImport,
)


@dataclass(frozen=True)
class TypeAcces:
    """Ce qui distingue un vigik d'une télécommande — la liste complète."""

    #: La valeur employée dans les URL et les corps de requête : `vigik`…
    cle: str
    #: Ce qu'un humain lit dans un message d'erreur.
    libelle: str
    #: La table de l'objet remis au porteur.
    modele: type
    #: La table d'attribution à plusieurs copropriétaires.
    modele_attribution: type
    #: La colonne de cette table qui pointe l'objet.
    colonne_attribution: str
    #: La table de staging de l'import Excel.
    modele_import: type
    #: La colonne de l'import qui pointe l'objet une fois résolu.
    colonne_import: str
    #: 🔴 La SEULE divergence de vocabulaire : le classeur des vigiks nomme sa
    #: référence `code`, celui des télécommandes `reference`. C'est cette
    #: différence-là qui rendait les deux branches « pas tout à fait pareilles »,
    #: et donc impossibles à relire ensemble.
    colonne_code_import: str
    #: 🔹 L'accès de cet objet se DÉDUIT-il du lot de son porteur ?
    #:
    #: 🔴 Vrai pour un vigik, faux pour une télécommande — corrigé le 14/09/2026,
    #: signalé à l'écran : *« Télécommande n'est pas accessible à un bâtiment mais
    #: à Parking résidence / portail d'accès + AFUL / portail public »*.
    #:
    #: La première version déduisait le bâtiment pour les DEUX, parce que la règle
    #: écrite ne parlait que du vigik. Une télécommande ouvre des portails,
    #: toujours les mêmes, et n'a rien à voir avec le bâtiment où l'on habite.
    #:
    #: ⚠️ C'est ici — et pas dans un `if` au fil des appels — parce que c'est la
    #: huitième différence entre ces deux objets, et que les sept autres sont déjà
    #: là. Ce qui les sépare se lit d'un seul endroit, ou se dérive.
    acces_suit_le_lot: bool
    #: 🏠 Les natures de lot que cet accès concerne — `TypeLot`, par leur valeur.
    #:
    #: 🔴 Corrigé le 15/09/2026, signalé à l'écran : *« la colonne lot correspond,
    #: pour les vigik à celui ou ceux de(s) l'appartement(s), pour les
    #: télécommandes à ceux des garages »*.
    #:
    #: La colonne montrait le lot ENREGISTRÉ, quel qu'il soit — et l'import des
    #: télécommandes, comme le formulaire, y posait volontiers l'appartement du
    #: copropriétaire. On lisait donc « Appartement 314 » en face d'une
    #: télécommande de parking, ce qui ne désigne aucune porte.
    #:
    #: ⚠️ Un tuple, pas une valeur : rien ne dit qu'un troisième accès ne
    #: concernera pas deux natures à la fois. Une valeur unique se serait
    #: transformée en liste au premier cas, et les appelants avec elle.
    types_lot: tuple[str, ...]

    @property
    def champ_code_import(self):
        """La colonne de l'import, prête pour un `where`."""
        return getattr(self.modele_import, self.colonne_code_import)

    def attribuer(self, session: Session, *, user_id: int, acces_id: int) -> bool:
        """Attribue cet accès à cet utilisateur, sans doublon. Vrai si créé.

        ## 🔴 Ce geste était écrit QUATRE fois (18/09/2026, #779)

        `utils/auto_match_service.py` portait deux paires de jumelles —
        `_create_user_telecommandes`/`_create_user_vigiks`, puis
        `_assoc_tc`/`_assoc_vigik`. Les quatre disaient la même phrase : *« cet
        accès appartient aussi à cette personne, et pas deux fois »*. Ce qui les
        distinguait — la table d'attribution et le nom de sa colonne — est décrit
        ici depuis le 14/09/2026, et par cet objet seul.

        ⚠️ La leçon de ce module vaut pour ce geste-là aussi : les jumelles du
        téléversement **avaient divergé** sans que personne ne le voie (le
        `lot_id` recopié d'un côté, pas de l'autre). Une cinquième copie ne
        ferait pas exception.

        Le doublon n'est pas une erreur de l'appelant : l'appariement automatique
        repasse par les mêmes accès depuis trois vecteurs différents (le lot, le
        copropriétaire, la table de liaison). Répondre « déjà fait » est donc la
        réponse normale, et c'est ce que le booléen sert à compter.
        """
        deja = session.exec(
            select(self.modele_attribution).where(
                self.modele_attribution.user_id == user_id,
                getattr(self.modele_attribution, self.colonne_attribution) == acces_id,
            )
        ).first()
        if deja:
            return False
        session.add(
            self.modele_attribution(user_id=user_id, **{self.colonne_attribution: acces_id})
        )
        return True

    def attribuer_aux_coproprietaires(self, acces, session: Session) -> None:
        """Attribue cet accès à son porteur et aux copropriétaires concernés.

        Le geste vit dans `utils/acces_attribution` — il lit des lots, ce que
        ce descripteur n'a pas à savoir faire. La méthode existe pour que les
        appelants n'aient pas à nommer les deux ensemble : le socle des imports
        recevait autrefois cette fonction en PARAMÈTRE, à travers un second
        descripteur qui n'existait que pour la transporter.
        """
        from app.utils.acces_attribution import attribuer_aux_coproprietaires

        attribuer_aux_coproprietaires(acces, self, session)


VIGIK = TypeAcces(
    cle="vigik",
    libelle="Vigik",
    modele=Vigik,
    modele_attribution=UserVigik,
    colonne_attribution="vigik_id",
    modele_import=VigikImport,
    colonne_import="vigik_id",
    colonne_code_import="code",
    acces_suit_le_lot=True,
    types_lot=("appartement",),
)

TELECOMMANDE = TypeAcces(
    cle="telecommande",
    libelle="Télécommande",
    modele=Telecommande,
    modele_attribution=UserTelecommande,
    colonne_attribution="telecommande_id",
    modele_import=TelecommandeImport,
    colonne_import="telecommande_id",
    colonne_code_import="reference",
    acces_suit_le_lot=False,
    types_lot=("parking",),
)

#: Les accès connus, par leur clé d'URL — la source unique de « quels types
#: existent ». Un écran ou un routeur qui énumérerait « vigik ou telecommande »
#: à la main serait une seconde liste, libre de diverger.
TYPES_ACCES = {t.cle: t for t in (VIGIK, TELECOMMANDE)}
