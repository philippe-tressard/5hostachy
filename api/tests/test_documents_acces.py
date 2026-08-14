"""Garde-fou de sécurité : une pièce jointe ne fuit jamais au-delà de son actualité.

POURQUOI (28/07/2026) — `_user_can_read` traitait les pièces jointes d'actualité
comme un cas trivialement ouvert :

    if doc.publication_id and not doc.categorie_id:
        return True

Un document n'a pas de ciblage propre : ni `public_cible`, ni `perimetre_cible`. Sa
seule protection est celle de l'actualité qui le porte — et cette branche ne la
regardait pas. Concrètement, le PDF joint à une actualité réservée au conseil
syndical, ou ciblée sur un seul bâtiment, était :

  - listé par `GET /documents?publication_id=…`,
  - **téléchargeable** par `GET /documents/{id}/télécharger` pour tout compte
    authentifié, y compris un locataire,
  - et annoncé, titre compris, dans le fil d'activité du tableau de bord, qui
    s'appuie sur cette même fonction (`flux.py` → `_document_visible`).

Rien ne le signalait : les trois chemins partagent la fonction fautive, donc ils
étaient d'accord entre eux. Ce test fixe la règle dans les deux sens — ce qui doit
passer autant que ce qui doit être refusé — pour qu'un futur assouplissement de
`_user_can_read` échoue ici plutôt qu'en production.
"""
from app.models.core import (
    Document,
    Publication,
    RoleUtilisateur,
    StatutUtilisateur,
    Utilisateur,
)
from app.utils.visibility import document_visible


class _SessionSansBase:
    """`session.get(Publication, id)` — seul appel fait par la branche testée."""

    def __init__(self, publication: Publication | None):
        self._publication = publication

    def get(self, _modele, _id):
        return self._publication


def _utilisateur(role: str, statut: StatutUtilisateur, batiment_id=None) -> Utilisateur:
    return Utilisateur(
        email="x@example.test",
        mot_de_passe_hash="",
        prenom="X",
        nom="Y",
        role=role,
        roles_json=role,
        statut=statut,
        batiment_id=batiment_id,
    )


def _piece_jointe() -> Document:
    """Pièce jointe d'actualité : rattachée à une publication, sans catégorie."""
    return Document(
        id=42,
        titre="Compte rendu interne",
        fichier_nom="cr.pdf",
        fichier_chemin="/app/uploads/cr.pdf",
        publication_id=7,
        categorie_id=None,
    )


def _publication(**champs) -> Publication:
    base = dict(
        id=7,
        titre="Réunion",
        contenu="",
        auteur_id=1,
        brouillon=False,
        public_cible=None,
        perimetre_cible=None,
    )
    base.update(champs)
    return Publication(**base)


# ── Ce qui doit être REFUSÉ ──────────────────────────────────────────────────

def test_piece_jointe_d_actualite_reservee_au_cs_refusee_a_un_locataire():
    """Le cas d'origine : `public_cible=["conseil_syndical"]` ne protégeait que le texte."""
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    session = _SessionSansBase(_publication(public_cible='["conseil_syndical"]'))

    assert document_visible(locataire, _piece_jointe(), session) is False


def test_piece_jointe_d_actualite_ciblee_ailleurs_suit_l_actualite():
    """Le fichier suit l'actualité qui le porte — c'est le principe, et il tient.

    Ce test exigeait auparavant un refus. Il ne l'exige plus **parce que
    l'actualité elle-même a changé de verdict** (#339, 14/08/2026) : une actualité
    ciblée sur un autre bâtiment est désormais lisible, sauf si le lecteur a coché
    « n'afficher que mes bâtiments » dans son profil.

    Le principe que ce test protège n'a donc pas bougé d'un pouce — il est même
    vérifié dans les deux sens ici. Ce qui a bougé, c'est la visibilité de
    l'actualité, et le fichier la suit, comme il l'a toujours fait. La protection
    par le **public** (`public_cible`), elle, est inchangée : c'est le test
    juste au-dessus, et c'est lui qui empêche une agence ou un bailleur de gagner
    quoi que ce soit.
    """
    publication_ailleurs = _publication(perimetre_cible='["bat:1"]')

    ouvert = _utilisateur("locataire", StatutUtilisateur.locataire, batiment_id=2)
    assert document_visible(ouvert, _piece_jointe(), _SessionSansBase(publication_ailleurs)) is True

    restreint = _utilisateur("locataire", StatutUtilisateur.locataire, batiment_id=2)
    restreint.restreindre_a_mes_batiments = True
    assert document_visible(restreint, _piece_jointe(), _SessionSansBase(publication_ailleurs)) is False


def test_piece_jointe_de_brouillon_refusee():
    """Rien n'est publié tant que l'actualité est un brouillon — le fichier non plus."""
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    session = _SessionSansBase(_publication(brouillon=True))

    assert document_visible(locataire, _piece_jointe(), session) is False


def test_piece_jointe_orpheline_refusee():
    """Publication introuvable : aucune règle de visibilité à appliquer → on refuse."""
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)

    assert document_visible(locataire, _piece_jointe(), _SessionSansBase(None)) is False


# ── Ce qui doit rester AUTORISÉ ──────────────────────────────────────────────

def test_piece_jointe_d_actualite_tout_public_reste_lisible():
    """Le correctif ne doit pas fermer le cas courant : une actualité pour tous."""
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    session = _SessionSansBase(_publication(public_cible='["résidents"]'))

    assert document_visible(locataire, _piece_jointe(), session) is True


def test_piece_jointe_d_actualite_sans_ciblage_reste_lisible():
    """Absence de ciblage = tout le monde, comportement historique conservé."""
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    session = _SessionSansBase(_publication())

    assert document_visible(locataire, _piece_jointe(), session) is True


def test_le_conseil_syndical_garde_acces_a_tout():
    """CS et admin sortent avant toute autre règle — y compris sur un brouillon."""
    cs = _utilisateur(
        RoleUtilisateur.conseil_syndical.value, StatutUtilisateur.copropriétaire_bailleur
    )
    session = _SessionSansBase(_publication(brouillon=True, public_cible='["locataires"]'))

    assert document_visible(cs, _piece_jointe(), session) is True


# ── La règle elle-même, pour qu'on ne puisse pas la rouvrir par inadvertance ──

def test_la_branche_piece_jointe_consulte_bien_la_publication():
    """Si un jour la branche redevient un `return True` sec, ce test le dit.

    Il ne relit pas le code : il vérifie l'effet observable, à savoir que la
    fonction interroge la publication porteuse avant de se prononcer.
    """
    consultations = []

    class _SessionEspionne(_SessionSansBase):
        def get(self, modele, identifiant):
            consultations.append((modele, identifiant))
            return super().get(modele, identifiant)

    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    document_visible(locataire, _piece_jointe(), _SessionEspionne(_publication()))

    assert consultations == [(Publication, 7)], (
        "la pièce jointe a été autorisée (ou refusée) sans regarder son actualité"
    )
