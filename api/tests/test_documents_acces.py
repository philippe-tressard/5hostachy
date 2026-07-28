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


def test_piece_jointe_d_actualite_ciblee_sur_un_autre_batiment_refusee():
    """Le ciblage géographique de l'actualité vaut aussi pour ses fichiers."""
    resident_bat2 = _utilisateur(
        "locataire", StatutUtilisateur.locataire, batiment_id=2
    )
    session = _SessionSansBase(_publication(perimetre_cible='["bat:1"]'))

    assert document_visible(resident_bat2, _piece_jointe(), session) is False


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
