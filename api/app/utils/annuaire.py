"""L'annuaire du conseil et du syndic — la composition, écrite UNE fois.

## 🔴 Elle l'était deux fois, et elle avait déjà divergé (09/09/2026)

`routers/admin/annuaire.py` (l'écran) et `routers/admin/arrivants.py` (la fiche
d'accueil remise aux nouveaux résidents) construisaient **la même liste**, avec le
même tri, les mêmes caches et les mêmes clés. Le second l'annonçait lui-même —
*« même logique que GET /admin/annuaire »* — ce qui est la signature d'une copie
qui se sait copie et que personne ne rapproche.

Trente et une lignes identiques au caractère près, et **deux divergences déjà
installées** :

1. `est_gestionnaire_site` s'écrivait `site_manager_user_id is not None and …`
   d'un côté, `site_manager_user_id and …` de l'autre. Les deux ne disent pas la
   même chose pour l'identifiant `0` — latent aujourd'hui, faux le jour où un
   identifiant vaut zéro, et alors sur **un** des deux rendus seulement ;
2. l'écran rendait `id`, la fiche rendait `batiment_id`. Chacun avait ajouté ce
   dont il avait besoin, sans savoir que l'autre existait.

C'est la forme la plus coûteuse de la duplication d'un **rendu** : les deux
sorties décrivent le même objet — le conseil syndical — et personne ne les compare
jamais, parce qu'elles vivent sur deux écrans différents (`standards/11` §14).

## Ce que ce module rend, et pourquoi c'est un sur-ensemble

Les deux clés qui manquaient à l'un ou à l'autre sont rendues à tout le monde :
`id` **et** `batiment_id`. Retenir la version la plus disante est la règle quand
on fusionne deux copies (`standards/02` §4 bis) — une clé en trop est ignorée par
qui ne la lit pas, une clé en moins est une fonctionnalité perdue.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from app.models.core import Batiment, MembreCS, MembreSyndic, Utilisateur
from app.utils.destinataires import site_manager_user_id as _site_manager_user_id


def _ordre_genre(genre: str) -> int:
    """« Mme » et « Mlle » avant « M. », à bâtiment égal."""
    return 0 if genre in ("Mme", "Mlle") else 1


class _Caches:
    """Les deux lectures répétées d'une composition : le bâtiment et la photo.

    Elles étaient écrites en fermetures dans chacun des deux appelants, avec leur
    dictionnaire de cache. Un objet plutôt que deux fonctions libres : le cache et
    la lecture qui s'en sert ne se séparent pas.
    """

    def __init__(self, session: Session):
        self._session = session
        self._batiments: dict[int, str] = {}
        self._photos: dict[int, Optional[str]] = {}

    def batiment_nom(self, bid: Optional[int]) -> Optional[str]:
        """Le NUMÉRO du bâtiment (« A »), pas son libellé (« Bât. A »).

        ⚠️ Ce n'est volontairement pas `libelle_batiment` : les deux appelants
        rendent ici le numéro nu, que la fiche et l'écran préfixent eux-mêmes.
        Le repli sur `str(bid)` quand le bâtiment a disparu vient des deux copies
        d'origine — il vaut mieux un identifiant qu'un trou.
        """
        if bid is None:
            return None
        if bid not in self._batiments:
            bat = self._session.get(Batiment, bid)
            self._batiments[bid] = bat.numero if bat else str(bid)
        return self._batiments[bid]

    def photo(self, uid: Optional[int]) -> Optional[str]:
        if uid is None:
            return None
        if uid not in self._photos:
            u = self._session.get(Utilisateur, uid)
            self._photos[uid] = u.photo_url if u else None
        return self._photos[uid]


def membres_du_conseil(session: Session) -> list[dict]:
    """Le conseil syndical, trié par bâtiment puis genre puis nom."""
    caches = _Caches(session)
    gestionnaire = _site_manager_user_id(session)
    membres = sorted(
        session.exec(select(MembreCS)).all(),
        key=lambda m: (m.batiment_id or 9999, _ordre_genre(m.genre), m.nom.lower()),
    )
    return [
        {
            "id": m.id,
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            #  L'identifiant EN PLUS du nom : la fiche d'accueil nomme le bâtiment
            #  d'après l'arbre des périmètres, qui s'interroge par `batiment_id`.
            #  `batiment_nom` reste son dernier repli, quand l'arbre est vide.
            "batiment_id": m.batiment_id,
            "batiment_nom": caches.batiment_nom(m.batiment_id),
            "etage": m.etage,
            #  `is not None` et non la valeur de vérité : les deux copies ne
            #  disaient déjà pas la même chose pour l'identifiant 0.
            "est_gestionnaire_site": bool(
                m.est_gestionnaire_site
                or (gestionnaire is not None and m.user_id == gestionnaire)
            ),
            "est_president": m.est_president,
            "photo_url": caches.photo(m.user_id),
        }
        for m in membres
    ]


def membres_du_syndic(session: Session) -> list[dict]:
    """Les interlocuteurs du syndic, dans l'ordre que l'administration a fixé."""
    caches = _Caches(session)
    return [
        {
            "id": m.id,
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            "fonction": m.fonction,
            "email": m.email,
            "telephone": m.telephone,
            "est_principal": m.est_principal,
            "photo_url": caches.photo(m.user_id),
        }
        for m in sorted(session.exec(select(MembreSyndic)).all(), key=lambda m: m.ordre)
    ]


__all__ = ["membres_du_conseil", "membres_du_syndic"]
