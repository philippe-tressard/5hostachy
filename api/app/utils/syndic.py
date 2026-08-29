"""Le nom du syndic — une seule source, celle du contrat (#535).

## Le doublon (relevé le 29/08/2026)

Le nom du syndic existait **deux fois**, et rien ne disait que c'était le même :

| Source | Chemin | Qui la lisait |
|---|---|---|
| Texte libre | `SyndicInfo.nom_syndic` | annuaire, fiche arrivant |
| Entité | `Copropriete.syndic_contrat_id` → `ContratEntretien` → `Prestataire.nom` | écran Prestataires |

C'est mot pour mot ce que #535 décrit : *« la même chose existe deux fois »*,
*« ce qui est attaché à l'entité — documents, échéances, relances — ne l'est pas
au texte »*, *« une correction sur l'un ne touche pas l'autre »*.

🔴 **Conséquence concrète** : changer de syndic dans Prestataires ne mettait à
jour ni l'annuaire ni la **fiche arrivant remise aux nouveaux résidents**. Le
contrat porte l'échéance, le préavis et les documents ; le texte ne portait rien.

⚠️ Et c'est le même défaut que #490 a corrigé pour l'assurance, **sur la ligne
d'à côté du même modèle**. La conversion s'était arrêtée à mi-chemin.

## La règle, arbitrée le 29/08/2026 (option 1)

Le contrat FAIT FOI dès qu'il existe. `SyndicInfo.nom_syndic` devient un
**repli** — il sert encore aux copropriétés qui n'ont pas désigné de contrat, et
c'est ce qui permet de ne casser aucune installation.

⚠️ Le repli n'est pas une seconde vérité : il ne s'applique que là où la première
est absente. Deux sources qui répondent *en même temps* seraient le doublon
qu'on ferme ici.
"""
from typing import Optional

from sqlmodel import Session, select

from app.models.copropriete import Copropriete
from app.models.core import Prestataire, SyndicInfo


def nom_du_syndic(session: Session) -> str:
    """Le nom du syndic : celui du contrat désigné, sinon le texte saisi.

    Rend une chaîne vide si ni l'un ni l'autre n'est renseigné — jamais `None` :
    les appelants l'insèrent dans un e-mail et dans un PDF, où `None` s'écrirait
    « None » sur le document remis au résident.
    """
    #  Import différé : `routers.copropriete` importe des schémas qui importent
    #  ce module. Le faire en tête créerait un cycle à l'import de l'application.
    from app.routers.copropriete import contrat_de_reference

    copro = session.exec(select(Copropriete)).first()
    if copro:
        contrat = contrat_de_reference(session, copro, "syndic")
        if contrat and contrat.prestataire_id:
            presta: Optional[Prestataire] = session.get(Prestataire, contrat.prestataire_id)
            if presta and presta.nom:
                return presta.nom

    #  Repli : la saisie libre, pour les copropriétés sans contrat désigné.
    info = session.exec(select(SyndicInfo)).first()
    return (info.nom_syndic if info else "") or ""


def source_du_nom(session: Session) -> str:
    """D'où vient le nom rendu : `"contrat"`, `"saisie"` ou `"aucune"`.

    🔴 Sert à l'ÉCRAN, pas à la logique. Un champ de saisie qui n'a plus d'effet
    doit le dire : sans cela, l'administrateur corrige un texte que personne ne
    lit, et croit avoir changé le nom du syndic. C'est la moitié qui manque à
    beaucoup de dérivations — on remplace la source, on oublie de retirer le
    formulaire qui alimentait l'ancienne.
    """
    from app.routers.copropriete import contrat_de_reference

    copro = session.exec(select(Copropriete)).first()
    if copro:
        contrat = contrat_de_reference(session, copro, "syndic")
        if contrat and contrat.prestataire_id:
            presta = session.get(Prestataire, contrat.prestataire_id)
            if presta and presta.nom:
                return "contrat"
    info = session.exec(select(SyndicInfo)).first()
    return "saisie" if (info and info.nom_syndic) else "aucune"
