"""Un secret de configuration ne sort JAMAIS de l'API, pas même pour un admin.

## Le défaut, trouvé le 03/09/2026

`GET /config/admin` renvoyait `smtp_password` **en clair**. L'écran ne l'affichait
pas — il s'en servait pour savoir si un mot de passe était posé — mais la valeur
était bien dans la réponse HTTP : lisible dans l'onglet réseau du navigateur,
dans un cache, dans une capture d'écran de débogage, dans un journal de proxy.

🔴 **Un secret qu'un écran n'affiche pas mais que l'API transmet est un secret
exposé.** La protection était alors dans le rendu, c'est-à-dire nulle part : elle
tombait au premier `console.log`, au premier outil de développement ouvert, au
premier collègue à qui l'on montre son écran.

Le compte admin est le seul concerné, et c'est justement ce qui rendait le défaut
discret : on se dit qu'un administrateur « a le droit ». Il a le droit de
CHANGER le mot de passe de la boîte mail, pas celui de le LIRE — ce sont deux
pouvoirs différents, et le second n'a jamais été nécessaire.

## Ce que le remède préserve

L'écran a besoin de savoir si une valeur existe, pour afficher « Mot de passe
masqué » et le bouton « Changer » plutôt qu'un champ vide. Le marqueur le lui
dit, sans transmettre laquelle — c'est pourquoi ce n'est pas une chaîne vide.
"""
from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import ConfigSite, Utilisateur
from app.routers.config import MARQUEUR_SECRET, _SECRETS, get_config, get_config_admin


_SECRET_EN_CLAIR = "s3cr3t-de-la-boite-" + uuid.uuid4().hex[:8]


@pytest.fixture()
def base():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        poses = []
        for cle in sorted(_SECRETS):
            ligne = session.exec(select(ConfigSite).where(ConfigSite.cle == cle)).first()
            if ligne is None:
                ligne = ConfigSite(cle=cle, valeur=_SECRET_EN_CLAIR)
                session.add(ligne)
                poses.append(cle)
            else:
                ligne.valeur = _SECRET_EN_CLAIR
                session.add(ligne)
        session.commit()
        admin = Utilisateur(
            email=f"admin-{uuid.uuid4().hex[:8]}@exemple.test", mot_de_passe_hash="x",
            prenom="A", nom="D", roles_json="admin", actif=True,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        yield session, admin
        #  `ConfigSite` a `cle` pour clé primaire, pas `id` : `purger_ligne` ne
        #  sait pas la supprimer. La ligne part par son propre identifiant.
        for cle in poses:
            ligne = session.exec(select(ConfigSite).where(ConfigSite.cle == cle)).first()
            if ligne:
                session.delete(ligne)
        session.delete(admin)
        session.commit()


def test_aucun_secret_ne_sort_de_config_admin(base):
    """🔴 Le coeur du fichier — sur TOUS les secrets, pas seulement le SMTP."""
    session, admin = base
    rendu = get_config_admin(user=admin, session=session)
    for cle in _SECRETS:
        assert rendu.get(cle) != _SECRET_EN_CLAIR, (
            f"« {cle} » sort en clair de /config/admin : un secret que l'API "
            "transmet est un secret exposé, quel que soit ce que l'écran affiche."
        )
    #  Et la valeur ne doit apparaître nulle part, même sous une autre clé.
    assert _SECRET_EN_CLAIR not in "".join(str(v) for v in rendu.values())


def test_l_ecran_sait_quand_meme_qu_un_secret_EXISTE(base):
    """Le marqueur n'est pas une chaîne vide, et c'est ce qui le rend utile.

    Sans lui, l'écran afficherait un champ vide sur une boîte pourtant
    configurée — et l'administrateur ressaisirait un mot de passe qu'il n'a pas.
    """
    session, admin = base
    rendu = get_config_admin(user=admin, session=session)
    for cle in _SECRETS:
        assert rendu.get(cle) == MARQUEUR_SECRET
        assert bool(rendu.get(cle)) is True, "l'écran teste la PRÉSENCE de la valeur"


def test_les_secrets_ne_sont_pas_non_plus_publics(base):
    """La liste blanche publique ne doit évidemment pas les porter.

    Ce test paraît redondant avec `test_autorisation` — il ne l'est pas : il
    éprouve la MÊME donnée par les DEUX portes, et c'est la seule façon de voir
    qu'on n'a pas refermé l'une en oubliant l'autre.
    """
    session, _admin = base
    public = get_config(session=session)
    for cle in _SECRETS:
        assert cle not in public
    assert _SECRET_EN_CLAIR not in "".join(str(v) for v in public.values())


def test_la_liste_des_secrets_n_est_pas_vide():
    """Cas zéro. Un `_SECRETS` vidé rendrait les trois tests ci-dessus verts en
    ne vérifiant plus rien — chacun itère dessus.
    """
    assert len(_SECRETS) >= 3, f"seulement {len(_SECRETS)} secret(s) déclaré(s)"
    assert "smtp_password" in _SECRETS
    assert "imap_password" in _SECRETS
