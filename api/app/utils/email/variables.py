"""Les variables d'un modèle d'e-mail — **une** lecture, pour les trois lecteurs.

Trois endroits posaient la même question (« quelles variables ce modèle
emploie-t-il ? ») et y répondaient chacun avec son propre code :

* `routers/admin/communications._variables_du_modele` — ce que l'écran annonce à
  qui va modifier un modèle ;
* `utils/sante_modeles_email.variables_de` — ce que le contrôle quotidien compare
  entre la base et le code ;
* `tests/test_email_templates._required_vars` — le contrat de variables du dépôt.

Trois copies d'une même notion divergent, et celles-ci l'avaient déjà fait sur
les deux points qui comptent :

1. **la liste du gabarit** était écrite deux fois (`VARIABLES_DU_GABARIT` d'un
   côté, un `DU_GABARIT` local de l'autre). La prochaine variable injectée
   d'office par `_contexte_rendu` aurait été ajoutée à l'une des deux, et le
   contrôle aurait crié sur tous les modèles à la fois ;
2. **le séparateur** : deux lecteurs concaténaient `sujet + corps`, le troisième
   glissait une espace entre les deux. Or ni l'un ni l'autre n'est juste — voir
   ci-dessous.

## Chaque champ est analysé SÉPARÉMENT, comme il sera rendu

`email._render` est appelé deux fois : une fois sur `sujet`, une fois sur
`corps_html`. Ce sont deux gabarits indépendants. Les concaténer pour l'analyse
crée un couplage qui n'existe pas à l'envoi : un `{% if %}` déséquilibré dans
l'objet pouvait être « refermé » par un `{% endif %}` du corps, et l'analyse
réussissait sur un modèle qui échoue à l'envoi. Le contraire est possible aussi.

## Un modèle illisible se DIT, il ne se tait pas

`ModeleIllisible` est levée quand Jinja refuse le texte. Chaque appelant décide
quoi en faire, mais aucun ne peut plus l'ignorer par accident : rendre un
ensemble vide faisait passer « ce modèle ne peut pas partir » pour « ce modèle
n'emploie aucune variable » — c'est-à-dire, pour le contrôle quotidien, pour
« toutes les variables du code lui manquent », avec une cause affirmée qui
n'était pas la bonne (`standards/04` : vérifier le fait, pas le symptôme
attendu).

C'est le seul défaut que rien ne rattrape en aval : `send_email` capture toute
exception et n'enregistre l'échec que dans `historique_email` (#850).
"""
from __future__ import annotations

#: Injectées d'office par `email._contexte_rendu` — communes à tous les modèles,
#: donc hors du contrat de chacun. Source unique : les trois lecteurs l'importent.
VARIABLES_DU_GABARIT = frozenset(
    {"annee", "app", "residence", "reference_copro", "prefixe_copro"}
)


class ModeleIllisible(Exception):
    """Jinja refuse ce texte : le modèle ne peut pas être rendu, donc pas envoyé.

    Porte le champ fautif (`sujet` ou `corps_html`) et le message de Jinja : sans
    eux, celui qui lit l'alerte doit rouvrir les deux champs pour trouver lequel
    est cassé.
    """

    def __init__(self, champ: str, cause: Exception):
        self.champ = champ
        self.cause = cause
        super().__init__(f"{champ} : {cause}")


def _variables_dun_champ(texte: str | None, champ: str) -> set[str]:
    from jinja2 import BaseLoader, meta
    from jinja2.sandbox import SandboxedEnvironment

    env = SandboxedEnvironment(loader=BaseLoader())
    try:
        arbre = env.parse(texte or "")
    except Exception as exc:  # TemplateSyntaxError et tout ce que Jinja lève
        raise ModeleIllisible(champ, exc) from exc
    return set(meta.find_undeclared_variables(arbre))


def variables_de(sujet: str | None, corps_html: str | None) -> set[str]:
    """Les variables de premier niveau d'un modèle, gabarit exclu.

    Lève `ModeleIllisible` si l'un des deux champs ne se parse pas — c'est-à-dire
    si ce modèle échouerait à l'envoi.
    """
    return (
        _variables_dun_champ(sujet, "sujet")
        | _variables_dun_champ(corps_html, "corps_html")
    ) - VARIABLES_DU_GABARIT


__all__ = ["ModeleIllisible", "VARIABLES_DU_GABARIT", "variables_de"]
