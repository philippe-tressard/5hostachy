"""Garde-fou — **l'écran annonce les variables que le modèle emploie** (#850).

## Le défaut, trouvé par Philippe en capture d'écran (08/09/2026)

`nouvel_arrivant_bal` venait de gagner trois variables — `role_destinataire`,
`lien_consignes`, `destinataire`. L'écran Admin → Emails en annonçait toujours
**trois**, celles posées par la migration 0066 : `nom_complet`, `batiment`,
`ancien_resident`.

La colonne `variables_disponibles` est une **copie**, écrite à la main par la
migration qui crée le modèle et jamais reprise. Elle avait six mois de retard.

🔴 **Rien ne pouvait le dire.** Le modèle et sa liste vivent dans la même ligne
de la même table : personne ne les compare. Et le contrat de variables du dépôt
(`test_email_templates.py`) ne lit que le **code** — jamais la base.

Ce n'était pas cosmétique : cet encart est ce qu'un membre du conseil lit **avant
de modifier un modèle**. Il y voyait trois variables sur six.

## Ce que ces tests verrouillent

1. la liste servie est **calculée** sur le texte du modèle, pas lue en base ;
2. elle **exclut** les variables du gabarit commun, qui ne sont propres à
   personne ;
3. un Jinja invalide **ne fait pas tomber l'écran** — il replie sur la colonne ;
4. 🔴 le **cas zéro** : sur `nouvel_arrivant_bal`, la liste calculée diffère de
   celle que la 0066 avait posée. Sans cet écart, ce fichier ne prouverait rien.
"""
from __future__ import annotations

import json

from app.routers.admin.communications import _variables_du_modele
from app.seed.emails import EMAIL_TEMPLATES

#: Ce que la migration 0066 avait posé pour `nouvel_arrivant_bal`, et que l'écran
#: affichait encore le 08/09/2026.
POSEES_EN_0066 = ["ancien_resident", "batiment", "nom_complet"]


class _Modele:
    """Une ligne `ModeleEmail`, réduite à ce que le calcul lit."""

    def __init__(self, sujet: str, corps: str, stockees: str = '["perime"]'):
        self.sujet = sujet
        self.corps_html = corps
        self.variables_disponibles = stockees


def _du_depot(code: str) -> _Modele:
    _c, _l, sujet, corps, _d = next(t for t in EMAIL_TEMPLATES if t[0] == code)
    return _Modele(sujet, corps)


def test_la_liste_est_CALCULEE_pas_lue_en_base():
    """🔴 Le défaut lui-même : la colonne stockée ne doit plus décider."""
    modele = _Modele("Bonjour {{ destinataire.prenom }}", "{{ lien }}", '["perime"]')
    assert json.loads(_variables_du_modele(modele)) == ["destinataire", "lien"], (
        "la liste servie vient encore de la colonne stockée — elle se périmera "
        "au premier enrichissement du modèle, comme en 0066."
    )


def test_les_variables_du_GABARIT_ne_sont_pas_annoncees():
    """`residence`, `app`, `annee`… sont injectées d'office pour TOUS les modèles.

    Les annoncer ici les ferait passer pour propres à celui qu'on édite, et le
    lecteur croirait qu'il peut les retirer.
    """
    modele = _Modele(
        "{{ prefixe_copro }}Chez {{ residence.nom }}",
        "{{ app.url }} — {{ annee }} — {{ nom_complet }}",
    )
    assert json.loads(_variables_du_modele(modele)) == ["nom_complet"]


def test_un_JINJA_INVALIDE_ne_fait_pas_tomber_l_ecran():
    """Le modèle échouera à l'envoi — c'est LÀ que le signal doit être.

    Faire échouer la liste des modèles priverait l'administrateur du seul écran
    depuis lequel il pourrait corriger le modèle fautif.
    """
    modele = _Modele("{% if %}", "", '["repli"]')
    assert json.loads(_variables_du_modele(modele)) == ["repli"]


def test_cas_zero_la_liste_calculee_DIFFERE_de_celle_de_2026_03():
    """🔴 La preuve que ce fichier mesure quelque chose.

    Si la liste calculée pour `nouvel_arrivant_bal` redevenait celle de la
    migration 0066, c'est que le modèle aurait perdu son adaptation aux trois
    publics — et les trois recevraient la version du syndic.
    """
    calculees = json.loads(_variables_du_modele(_du_depot("nouvel_arrivant_bal")))
    assert calculees != POSEES_EN_0066, (
        "le modèle n'emploie plus que les variables de mars 2026 : "
        "`role_destinataire` a disparu, et les trois publics reçoivent le même "
        "message."
    )
    for attendue in ("role_destinataire", "lien_consignes", "destinataire"):
        assert attendue in calculees, f"`{attendue}` n'est plus annoncée à l'écran"


def test_tous_les_modeles_du_depot_annoncent_au_moins_une_variable():
    """Cas zéro de la PORTÉE : un calcul cassé rendrait des listes vides partout.

    `standards/04` §40 — un relevé qui ne lit rien rend un vert parfait. Trois
    modèles n'ont légitimement aucune variable propre (ils ne parlent que du
    gabarit) : ils sont nommés, et la liste ne peut que décroître.
    """
    SANS_VARIABLE_PROPRE: set[str] = set()

    vides = []
    for code, _l, sujet, corps, _d in EMAIL_TEMPLATES:
        if not json.loads(_variables_du_modele(_Modele(sujet, corps, "[]"))):
            vides.append(code)

    inattendus = sorted(set(vides) - SANS_VARIABLE_PROPRE)
    assert not inattendus, (
        f"{len(inattendus)} modèle(s) n'annoncent AUCUNE variable : {inattendus}. "
        "Soit le calcul est cassé, soit ces modèles n'emploient réellement que le "
        "gabarit — dans ce cas, les déclarer dans `SANS_VARIABLE_PROPRE`."
    )
    assert len(EMAIL_TEMPLATES) > 20, (
        f"{len(EMAIL_TEMPLATES)} modèle(s) lus — la portée du relevé est cassée, "
        "et son vert ne veut rien dire (INCONNU, pas OK)."
    )
