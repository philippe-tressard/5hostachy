"""**« Saisi pour »** — au nom de qui une entrée est ouverte, et par qui.

## La notion

Le conseil syndical enregistre ce qu'un résident a signalé par téléphone, ou ce
qu'un intervenant extérieur a rapporté. L'**auteur** est alors celui qui a tapé ;
le **propriétaire** est celui que ça concerne.

Trois champs, et ils vont **toujours ensemble** :

| champ | ce qu'il porte |
|---|---|
| `saisi_pour_user_id` | un résident **inscrit** — nom et adresse à jour |
| `saisi_pour_nom` | une personne **extérieure** — ce que le rédacteur a saisi |
| `saisi_pour_email` | son adresse, **facultative** |

## 🔴 Pourquoi ce module (15/09/2026)

La notion vivait dans le seul circuit des tickets, écrite en quatre endroits —
le modèle, la création, la correction, la lecture. La demande de l'étendre aux
**actualités** et aux **événements** en aurait fait douze.

> « As-tu réalisé l'évolution d'ajout de la section “SAISI POUR” aux actualités
>   et Événements ? »

⚠️ Et la logique n'a rien d'évident : elle porte deux distinctions que trois
copies auraient perdues à des moments différents.

1. **Les trois champs voyagent ensemble, y compris à `null`.** C'est leur
   *présence* dans la charge utile qui dit d'écrire (`model_fields_set`), et
   c'est ce qui permet de revenir à « En mon nom » : sans elles, un `None`
   serait indistinguable d'un champ non transmis, et le choix resterait sans
   effet — en silence.
2. **La PRÉSENCE décide d'écrire, la COMPARAISON décide d'annoncer**
   (18/08/2026). Les deux étaient confondues : le formulaire envoyant toujours
   les trois champs, « Saisi pour modifié » apparaissait à chaque
   enregistrement, même quand personne n'y avait touché.

## Ce que ce module ne porte pas

**Qui est le propriétaire** — `utils/copie_auteur.proprietaire()`, déjà
générique : elle lit `saisi_pour_*` par `getattr` et retombe sur l'auteur pour
les objets qui n'en ont pas. Elle n'avait pas besoin de changer, et c'est le
signe qu'elle était juste.

**Qui a le droit** — `auth/deps`. Le filtre `est_cs` ci-dessous n'est pas une
autorisation : c'est la traduction d'une règle métier déjà tranchée par la
dépendance qui protège la route. Un résident qui enverrait ces champs les voit
simplement ignorés.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from sqlmodel import Field, Session, SQLModel


#: Les trois champs, nommés une fois — les parcourir plutôt que les énumérer.
CHAMPS = ("saisi_pour_user_id", "saisi_pour_nom", "saisi_pour_email")


class SaisiPourMixin(SQLModel):
    """Les trois colonnes, héritées plutôt que recopiées.

    ⚠️ **`saisi_pour_user_id` ne déclare PAS `foreign_key` ici**, et c'est une
    contrainte de SQLite, pas un oubli : une migration ne peut pas ajouter une
    colonne *avec* sa contrainte (`ALTER TABLE` la refuse, la migration crashe
    après avoir posé la colonne — c'est arrivé deux fois, 0117 et 0165). Si le
    modèle la déclarait quand même, une base **neuve** (`create_all`) et une base
    **migrée** porteraient deux schémas différents, et rien ne le dirait.
    `api/tests/test_migrations.py` refuse les deux.

    `Ticket` **redéclare** ce champ avec sa clé étrangère : sa colonne existe en
    base depuis l'origine, avec la contrainte. Le mixin décrit donc le socle, et
    l'entité qui en sait plus l'enrichit — sans que les trois autres aient à
    connaître ce détail.
    """

    saisi_pour_user_id: Optional[int] = Field(default=None)
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None


def valeurs(body, *, autorise: bool) -> dict:
    """Ce qu'il faut poser à la CRÉATION — les trois champs, ou trois `None`.

    :param autorise: le rédacteur a-t-il le droit de saisir pour autrui (le
        conseil syndical, l'administration) ? Sinon les trois valeurs sont
        ignorées — ce n'est pas le contrôle d'accès, qui vit dans `auth/deps`,
        mais sa traduction sur ces trois champs.
    """
    return {c: (getattr(body, c, None) if autorise else None) for c in CHAMPS}


def corriger(objet, body, envoye) -> list[str]:
    """Applique une CORRECTION, et dit s'il y a lieu de l'annoncer.

    :param envoye: `lambda body, champ: …` — le prédicat de l'appelant qui dit
        si un champ figure dans la charge utile reçue. Il reste chez lui : la
        façon de lire `model_fields_set` dépend du schéma, pas de cette notion.
    :returns: la liste des évolutions à tracer — vide si rien n'a changé.

    🔴 Les deux règles de l'en-tête sont ICI, et nulle part ailleurs : la
    présence décide d'écrire, la comparaison décide d'annoncer.
    """
    if not any(envoye(body, c) for c in CHAMPS):
        return []
    avant = tuple(getattr(objet, c) for c in CHAMPS)
    apres = tuple(getattr(body, c, None) for c in CHAMPS)
    for champ, valeur in zip(CHAMPS, apres):
        setattr(objet, champ, valeur)
    return ["Saisi pour modifié"] if avant != apres else []


def affichage(session: Session, objet) -> Optional[str]:
    """Le nom à afficher — `None` quand personne n'est nommé.

    ⚠️ Ce n'est PAS le propriétaire, et la nuance porte tout l'usage : le
    propriétaire retombe sur l'auteur, celui-ci reste **vide**. L'écran s'en sert
    pour n'afficher « Saisi pour X » que lorsqu'il y a un X — sans quoi chaque
    entrée porterait la mention, y compris celles que leur auteur a écrites pour
    lui-même.
    """
    #  🔴 Import DIFFÉRÉ, et c'est un cycle réel : `copie_auteur` a besoin
    #  des modèles, et les modèles ont besoin du mixin de ce fichier. Le
    #  poser en tête ferait échouer le DÉMARRAGE de l'API, pas un test.
    from app.utils.copie_auteur import proprietaire

    if not (objet.saisi_pour_user_id or objet.saisi_pour_nom):
        return None
    nom, _ = proprietaire(session, objet)
    return nom


class SaisiPourEntree(BaseModel):
    """Ce qu'un formulaire ENVOIE — hérité par les schémas de création et de
    correction des trois entités.

    ⚠️ **Les trois champs sont `Optional` et sans valeur par défaut autre que
    `None`**, y compris à la création : c'est leur PRÉSENCE dans la charge utile
    qui dit d'écrire (`model_fields_set`), et c'est ce qui permet de revenir à
    « En mon nom ». Un défaut « intelligent » ici rendrait ce retour impossible.
    """

    saisi_pour_user_id: Optional[int] = None
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None


class SaisiPourSortie(BaseModel):
    """Ce qu'un écran REÇOIT — les trois champs, plus le nom déjà composé.

    ⚠️ `saisi_pour_affichage` n'est pas une redite des deux autres : il vaut
    `None` quand personne n'est nommé, là où `proprietaire()` retombe sur
    l'auteur. C'est lui qui décide si l'écran affiche « Saisi pour X » — le
    composer côté client demanderait de relire la règle des trois cas dans
    chaque écran.
    """

    saisi_pour_user_id: Optional[int] = None
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None
    saisi_pour_affichage: Optional[str] = None
