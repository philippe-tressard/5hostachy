"""L'actualité qui accueille un nouvel arrivant (#821).

Demandé le 07/09/2026, capture à l'appui :

> *« Quand un nouvel utilisateur coche "nouvel arrivant", créer une actualité
> pour informer d'un nouvel arrivant dans la copropriété. Tu peux t'inspirer de
> cet exemple, magnifie-le, et mets des infos que tu pourrais avoir à
> disposition : bâtiment, étage… Par contre sois vigilant de ne pas communiquer
> des infos personnelles comme l'email. »*

L'exemple montrait : « Bienvenue à Mme Mr ITMI-VÉRITÉ nouveaux arrivants au
Bâtiment 1 », corps « Remplace Mme BERNAERT ». Deux civilités collées, et trois
mots de contenu.

## 🔴 Ce qui NE sort jamais d'ici — et pourquoi c'est une liste, pas une intention

`CHAMPS_INTERDITS` nomme les données qui ne doivent apparaître ni dans le titre
ni dans le corps : **e-mail, téléphone, numéro de lot, mot de passe**. Elle
n'est pas décorative — `test_annonce_arrivee.py` construit une annonce à partir
d'un compte dont tous ces champs sont remplis de valeurs reconnaissables, et
vérifie qu'aucune ne s'y trouve.

Une intention (« faire attention aux données personnelles ») ne survit pas au
premier enrichissement du gabarit. Un contrôle, oui.

## Ce qui EST publié, et le raisonnement

| Donnée | Publiée | Pourquoi |
|---|---|---|
| nom et prénom | oui | déjà lisibles sur l'interphone et la boîte aux lettres |
| bâtiment | oui | c'est le périmètre de l'annonce, il est nécessairement dit |
| étage | **si renseigné** | facultatif à la saisie : le donner vaut consentement à le situer |
| ancien résident | si renseigné | saisi par l'arrivant lui-même, dans ce but |
| e-mail, téléphone, lot | **jamais** | rien dans une annonce de voisinage n'en a besoin |

⚠️ L'étage est le cas limite : couplé au bâtiment, il approche l'identification
du logement. Il n'est publié que si la personne l'a renseigné — et le champ est
facultatif partout, précisément pour que ce soit un choix.

## L'arrivant est l'AUTEUR de sa propre annonce

`auteur_id = user.id`. Ce n'est pas un détail de plomberie : c'est ce qui lui
permet de la **voir et de la corriger**. Une annonce sur quelqu'un que
l'intéressé ne pourrait ni lire ni modifier serait exactement le défaut de
`project_auteur_toujours_visible`, appliqué à sa propre présentation.
"""
from __future__ import annotations

from html import escape

from sqlmodel import Session, select

from app.models.core import Batiment, Publication, Utilisateur

#: Le titre est stable : c'est lui qui sert de garde contre le doublon.
PREFIXE_TITRE = "Bienvenue à "

#: 🔴 Les attributs d'un compte qui ne doivent JAMAIS entrer dans l'annonce.
#: Éprouvée par `test_annonce_arrivee.py` sur un compte dont tous sont remplis.
CHAMPS_INTERDITS = ("email", "telephone", "hashed_password", "nom_proprietaire")


def libelle_etage(etage: int | None) -> str:
    """« 2ᵉ étage », « rez-de-chaussée », « sous-sol ». Vide si non renseigné.

    ⚠️ Le vide est une valeur normale, pas une erreur : l'étage est facultatif,
    et l'annonce doit se lire aussi bien sans lui. Écrire « étage non
    renseigné » exposerait le fait que la question a été posée.
    """
    if etage is None:
        return ""
    if etage < 0:
        return "sous-sol"
    if etage == 0:
        return "rez-de-chaussée"
    if etage == 1:
        return "1ᵉʳ étage"
    return f"{etage}ᵉ étage"


def _nom_batiment(session: Session, batiment_id: int | None) -> str:
    if not batiment_id:
        return ""
    bat = session.get(Batiment, batiment_id)
    return f"Bâtiment {bat.numero}" if bat and bat.numero else ""


def titre_annonce(nom_complet: str, nom_batiment: str) -> str:
    """« Bienvenue à Alix RIVANT — Bâtiment 3 ».

    ⚠️ UN seul nom, et pas de civilité accolée : l'exemple d'origine affichait
    « Mme Mr ITMI-VÉRITÉ », deux civilités que rien ne séparait. `Utilisateur`
    n'en porte d'ailleurs pas — le nom d'affichage suffit, et il est le même
    partout ailleurs dans le produit (`nom_affiche`).
    """
    return PREFIXE_TITRE + nom_complet + (f" — {nom_batiment}" if nom_batiment else "")


def corps_annonce(nom_complet: str, nom_batiment: str, etage: int | None, ancien: str) -> str:
    """Le corps de l'annonce — accueillant, situé, et sans rien de personnel.

    ⚠️ Aucun pronom de genre. `Utilisateur` ne porte pas de civilité, et
    « il ou elle » alourdit une phrase de trois mots. Les tournures sont donc
    construites sans sujet animé — c'est plus court ET plus juste.
    """
    ou = ", ".join(x for x in (nom_batiment, libelle_etage(etage)) if x)
    situe = f" au <strong>{escape(ou)}</strong>" if ou else " dans la résidence"

    #  « Ne sait pas » est la valeur que pose le formulaire quand l'arrivant coche
    #  « Je ne sais pas ». La publier telle quelle dirait « succède à Ne sait pas ».
    succede = ""
    if ancien and ancien.strip().lower() not in {"ne sait pas", "inconnu"}:
        succede = f", et succède à <strong>{escape(ancien.strip())}</strong>"

    return (
        f"<p><strong>{escape(nom_complet)}</strong> vient d'emménager{situe}{succede}.</p>"
        "<p>Un mot de bienvenue dans le hall ou l'ascenseur est toujours "
        "apprécié — c'est ce qui fait la différence entre un immeuble et un "
        "voisinage.</p>"
        "<p>📋 Les consignes de la résidence — tri, accès, stationnement — sont "
        'réunies dans la <a href="/api/admin/fiche-arrivant" target="_blank" '
        'rel="noopener">fiche d\'accueil</a>.</p>'
    )


def annonce_existante(session: Session, user_id: int) -> Publication | None:
    """L'annonce déjà publiée pour cette personne, s'il y en a une.

    Même raison que pour le ticket : `accueil-arrivant` est rejouable par un
    membre du conseil, et un second passage publierait une seconde annonce sans
    que rien ne le dise.
    """
    return session.exec(
        select(Publication).where(
            Publication.auteur_id == user_id,
            Publication.titre.like(PREFIXE_TITRE + "%"),
        )
    ).first()


def creer_annonce_arrivee(
    session: Session,
    user: Utilisateur,
    *,
    nom_complet: str,
    ancien: str,
) -> Publication | None:
    """Publie l'actualité de bienvenue. Rend `None` si elle existe déjà.

    ⚠️ Aucun `commit` : l'appelant en fait un seul à la fin de l'accueil. Une
    annonce committée au milieu resterait publiée si la suite échouait — un
    voisinage informé d'une arrivée qui n'a pas été enregistrée.
    """
    if annonce_existante(session, user.id):
        return None

    nom_batiment = _nom_batiment(session, user.batiment_id)
    #  Le périmètre suit le bâtiment quand il est connu : une arrivée intéresse
    #  d'abord les voisins de palier. Sans bâtiment, la résidence entière — mieux
    #  vaut une annonce large qu'une annonce que personne ne voit.
    perimetre_cible = f'["bat:{user.batiment_id}"]' if user.batiment_id else '["résidence"]'

    pub = Publication(
        titre=titre_annonce(nom_complet, nom_batiment),
        contenu=corps_annonce(nom_complet, nom_batiment, user.etage, ancien),
        perimetre="bâtiment" if user.batiment_id else "résidence",
        batiment_id=user.batiment_id,
        perimetre_cible=perimetre_cible,
        public_cible='["résidents"]',
        #  🔴 L'arrivant est l'auteur de sa propre annonce : c'est ce qui lui
        #  permet de la voir et de la corriger. Une présentation de soi qu'on ne
        #  peut ni lire ni modifier serait le défaut de
        #  `project_auteur_toujours_visible` appliqué à sa propre arrivée.
        auteur_id=user.id,
        statut="publie",
        #  Jamais sur le groupe WhatsApp : une annonce nominative n'a pas à
        #  quitter l'application, où la lecture est déjà restreinte au périmètre.
        partager_whatsapp=False,
        envoyer_syndic=False,
    )
    session.add(pub)
    return pub
