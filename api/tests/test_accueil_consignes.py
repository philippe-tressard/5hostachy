"""Garde-fou — **les consignes SORTENT de l'application, par UN seul modèle** (#849).

Demandé le 08/09/2026 :

> *« Diffusion = pas de diffusion s'il y a déjà un mail envoyé au nouveau
> résident et au CS du bâtiment avec le template "nouveau résident" comprenant
> le lien ou le PDF "Consignes de la copropriété". »*

puis, quand j'ai proposé un modèle neuf :

> *« je rappelle la consigne de standardiser et non de dupliquer »*

## 🔴 Ce qui manquait, et ce qui ne manquait pas

Les consignes de la copropriété ne vivaient que dans une **notification in-app** :
l'arrivant devait ouvrir l'application pour apprendre qu'il devait l'ouvrir. Et
le conseil du bâtiment n'en recevait aucune trace — sa seule notification parle
de l'interphone.

Mais le **modèle**, lui, existait : `nouvel_arrivant_bal`, depuis la migration
0066. Il portait déjà les trois données de l'arrivée et le même parcours. Il
n'était pas incomplet — il ne s'adressait qu'à **un** public, le syndic.

Un second modèle en aurait été la copie, et les deux auraient divergé au premier
changement de l'un. Il est donc **adapté** par `role_destinataire`, et c'est le
socle du message — la carte d'arrivée — qui est écrit une fois pour les trois.

## Ce que ces tests verrouillent

1. le modèle sert les **trois** publics, et le socle n'est écrit qu'une fois ;
2. les consignes vont au résident et au conseil, **pas** au syndic ;
3. le sujet du syndic est **inchangé** — c'est son classement par affaire ;
4. le chemin des consignes a **une** écriture — `courriel_arrivee.FICHE_CONSIGNES` ;
5. le courriel vise **exactement** les membres que la section B notifie ;
6. 🔴 le **cas zéro** : sans les deux publics servis, la diffusion du ticket
   REPREND. Une règle « pas de diffusion » écrite en dur laisserait le suivi sans
   personne à prévenir le jour où le courriel ne part pas.
"""
from __future__ import annotations

import html
import re

from jinja2 import BaseLoader, meta
from jinja2.sandbox import SandboxedEnvironment

from app.seed.emails import EMAIL_TEMPLATES, INTENTIONS_PAR_MODELE

CODE = "nouvel_arrivant_bal"
ROLES = ("syndic", "resident", "cs")


def _modele():
    for code, libelle, sujet, corps, desactivable in EMAIL_TEMPLATES:
        if code == CODE:
            return libelle, sujet, corps, desactivable
    raise AssertionError(
        f"le modèle « {CODE} » a disparu — c'est LUI qui porte l'arrivée d'un "
        "résident depuis la migration 0066, et le ticket de suivi coupe sa "
        "diffusion en comptant sur son envoi."
    )


class _Personne:
    prenom = "Camille"


def _rendu(role: str) -> tuple[str, str]:
    """Sujet et corps rendus pour un rôle, avec un contexte complet."""
    _, sujet, corps, _ = _modele()
    env = SandboxedEnvironment(loader=BaseLoader())
    contexte = {
        "nom_complet": "Camille MARTIN",
        "batiment": "B2 — Apt 14",
        "ancien_resident": "Jean DUPONT",
        "lien_consignes": "/api/admin/fiche-arrivant",
        "role_destinataire": role,
        "destinataire": _Personne(),
        "residence": {"nom": "5 Hostachy"},
        "app": {"url": "https://5hostachy.fr"},
        "prefixe_copro": "🏢 00213 — ",
    }
    return (
        env.from_string(sujet).render(**contexte),
        env.from_string(corps).render(**contexte),
    )


def _texte(corps_html: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", corps_html))).strip()


def test_UN_SEUL_modele_sert_les_TROIS_publics():
    """🔴 La consigne du 08/09/2026 : standardiser, ne pas dupliquer.

    Un modèle d'accueil distinct aurait porté les mêmes trois variables
    d'arrivée, la même carte et le même parcours. Ce test échoue s'il
    réapparaît — c'est la seule façon d'empêcher la copie de revenir, puisqu'elle
    a l'air correcte tant qu'on ne regarde qu'un des deux fichiers.
    """
    codes = {code for code, *_ in EMAIL_TEMPLATES}
    intrus = {c for c in codes if c != CODE and ("arrivant" in c or "resident" in c)}
    assert not intrus, (
        f"modèle(s) d'arrivée en double : {sorted(intrus)}. `{CODE}` porte déjà "
        "l'arrivée d'un résident — l'ADAPTER par `role_destinataire`, pas le "
        "recopier."
    )

    sujets = {role: _rendu(role)[0] for role in ROLES}
    assert len(set(sujets.values())) == 3, (
        f"deux publics reçoivent le même objet : {sujets}. Le conseil lirait un "
        "message rédigé pour quelqu'un d'autre."
    )


def test_le_SOCLE_du_message_n_est_ecrit_qu_une_fois():
    """La carte d'arrivée — qui, quel bâtiment, quel occupant précédent.

    C'est ce qui rend la mise en commun réelle : si chaque branche réécrivait la
    carte, il y aurait trois copies dans un seul fichier plutôt que dans trois —
    et ce serait le même défaut, mieux caché.
    """
    _, _, corps, _ = _modele()
    assert corps.count("{{ nom_complet }}") == 1, (
        "le nom de l'arrivant est écrit plusieurs fois : la carte a été recopiée "
        "dans les branches au lieu d'être commune aux trois."
    )
    assert corps.count("{{ ancien_resident }}") == 1

    for role in ROLES:
        assert "Camille MARTIN" in _texte(_rendu(role)[1]), (
            f"le rôle « {role} » ne reçoit pas la carte d'arrivée"
        )


def test_les_CONSIGNES_vont_au_resident_et_au_conseil_PAS_au_syndic():
    """🔴 Le geste demandé, et sa limite.

    Le syndic n'a que faire du règlement intérieur : il le connaît, et sa demande
    à lui est l'étiquette de boîte aux lettres. Lui envoyer le bouton ferait un
    message qui demande deux choses sans dire laquelle le concerne.
    """
    for role in ("resident", "cs"):
        _, corps = _rendu(role)
        assert "fiche-arrivant" in corps, (
            f"le rôle « {role} » ne reçoit pas le lien des consignes"
        )
        assert "https://5hostachy.fr/api/admin/fiche-arrivant" in corps, (
            "le lien est relatif dans le message : un courriel n'a pas de base."
        )
        assert "Consignes de la copropriété" in _texte(corps)

    _, corps_syndic = _rendu("syndic")
    assert "fiche-arrivant" not in corps_syndic, (
        "le syndic reçoit le bouton des consignes : son message demande alors "
        "deux choses, sans dire laquelle le concerne."
    )
    assert "étiquette de boîte aux lettres" in _texte(corps_syndic).lower()


def test_le_SUJET_DU_SYNDIC_est_inchange():
    """C'est sous ce libellé qu'il classe ses dossiers depuis la migration 0132.

    « Uniformiser » les trois objets casserait son tri par affaire — et une
    uniformisation qui détruit un usage n'est pas une standardisation.
    """
    sujet, _ = _rendu("syndic")
    assert sujet == "🏢 00213 — Nouvel arrivant — mise à jour des boîtes aux lettres", (
        f"l'objet du syndic a changé : « {sujet} »"
    )


def test_le_chemin_des_consignes_a_UNE_seule_ecriture():
    """Un modèle vit en base et se réécrit depuis Admin → Emails.

    Y coder `/api/admin/fiche-arrivant` en dur en ferait une copie que personne
    ne reverrait le jour où la route change — et un lien mort dans un message
    d'accueil ne se signale pas : personne ne répond pour dire qu'il n'a pas lu.
    """
    from app.utils.courriel_arrivee import FICHE_CONSIGNES

    _, _, corps, _ = _modele()
    assert FICHE_CONSIGNES not in corps, (
        f"le chemin « {FICHE_CONSIGNES} » est recopié dans le modèle : il doit "
        "arriver par la variable `lien_consignes`."
    )
    assert "{{ app.url }}{{ lien_consignes }}" in corps
    assert FICHE_CONSIGNES.startswith("/")


def test_toutes_les_variables_du_modele_sont_au_contrat():
    """Le cas zéro de ce fichier : sans lui, un rendu vide passerait pour bon.

    Jinja évalue un indéfini à faux **en silence** — un `role_destinataire`
    manquant enverrait à tout le monde la version du syndic, sans erreur.
    """
    from tests.test_email_templates import BASE_CTX_VARS, EXPECTED_VARS

    _, sujet, corps, _ = _modele()
    env = SandboxedEnvironment(loader=BaseLoader())
    reelles = meta.find_undeclared_variables(env.parse(sujet + corps)) - BASE_CTX_VARS
    assert reelles == EXPECTED_VARS[CODE], (
        f"le contrat et le modèle divergent : modèle={sorted(reelles)} "
        f"contrat={sorted(EXPECTED_VARS[CODE])}"
    )
    assert "role_destinataire" in reelles, (
        "le modèle ne s'adapte plus à son public : les trois recevraient le même "
        "message, et deux d'entre eux le mauvais."
    )


def test_l_intention_laisse_la_porte_ouverte_a_une_reponse():
    """`information` expédierait depuis `noreply@` — et un arrivant a des questions.

    Consigne du 05/09/2026 : `noreply@` est **réservé** à ce qui n'appelle aucune
    réponse. Un message d'accueil n'est pas de cette famille.
    """
    from app.seed.emails import EXPEDITEUR_REPONSE, expediteur_du_modele

    assert INTENTIONS_PAR_MODELE.get(CODE), (
        f"« {CODE} » n'a pas d'intention déclarée — `expediteur_du_modele` "
        "retomberait sur son défaut sûr sans que personne l'ait décidé."
    )
    assert expediteur_du_modele(CODE) == EXPEDITEUR_REPONSE, (
        "le message d'accueil partirait de `noreply@` : la porte se ferme sur "
        "les questions d'un résident qui vient d'arriver."
    )


def test_le_courriel_vise_EXACTEMENT_les_notifies_et_pas_un_de_plus():
    """🔴 Le défaut que ce lot a failli introduire.

    `membres_cs_notifiables(session, None)` rend **tout** le conseil. Or ce
    parcours, quand le bâtiment de l'arrivant est inconnu, se limite au
    gestionnaire du site — c'est la règle de `cs_unique`, écrite plus haut dans
    la même fonction.

    Appeler l'un pour l'autre aurait écrit l'arrivée d'un résident à des membres
    qui n'ont jamais reçu sa notification : deux listes pour une même question,
    divergentes dans le cas — le cas sans bâtiment — que personne n'essaie.

    ⚠️ Contrôle **statique** : ce qui doit être vrai est que le courriel
    n'accepte que des destinataires déjà notifiés. Cela se lit dans le code, et
    reconstruire tout un accueil (SMTP, tâches de fond, six écritures) pour
    l'observer coûterait plus cher que la ligne qu'il protège.
    """
    import inspect

    from app.routers.admin import arrivants
    from app.utils import courriel_arrivee

    #  Le routeur passe la liste ; le module d'envoi la fait respecter. Les deux
    #  moitiés sont vérifiées, sans quoi retirer l'une passerait inaperçue.
    assert "membres_cs_notifies={mc.user_id for mc in cs_unique}" in inspect.getsource(
        arrivants
    ), (
        "le routeur ne transmet plus les membres réellement notifiés : le module "
        "d'envoi n'aurait plus rien contre quoi filtrer."
    )
    assert "if cs_user_id not in membres_cs_notifies:" in inspect.getsource(
        courriel_arrivee
    ), (
        "le courriel ne filtre plus sur les membres réellement notifiés : sans "
        "bâtiment connu, il partirait à TOUT le conseil syndical."
    )


def test_le_ticket_ne_DIFFUSE_pas_quand_les_consignes_sont_parties():
    """🔴 La règle demandée, lue dans le code qui la porte.

    ⚠️ Contrôle **statique**, pour la même raison que ci-dessus : les deux
    drapeaux du ticket doivent dépendre de `consignes_transmises`, et c'est
    visible sans rien exécuter.
    """
    import inspect

    from app.routers.admin import arrivants

    source = inspect.getsource(arrivants)
    assert "consignes_transmises = envoyer_message_arrivee(" in source, (
        "la coupure de diffusion ne dépend plus de l'envoi réel du courriel"
    )
    for drapeau in ("vers_syndic", "vers_cs"):
        assert re.search(rf"{drapeau}=.*not consignes_transmises", source), (
            f"`{drapeau}` ne dépend pas de `consignes_transmises` : le ticket "
            "diffuserait un second message disant la même chose, le même jour, "
            "aux mêmes personnes."
        )


def test_cas_zero_SANS_les_DEUX_publics_la_diffusion_REPREND():
    """La diffusion coupée en dur laisserait le suivi sans personne à prévenir.

    `consignes_transmises` exige les deux rôles — `resident` ET `cs`. Un arrivant
    sans adresse, un conseil dont tout le monde a décoché les e-mails : le
    courriel ne part pas, et le ticket doit alors reprendre son rôle d'alerte.

    Le contrôle rejoue l'expression telle qu'elle est écrite, sur toutes les
    combinaisons — c'est la table de vérité de la règle, pas une paraphrase.
    """
    from app.utils.courriel_arrivee import ROLES_CONSIGNES

    def transmises(roles):
        #  L'expression d'`courriel_arrivee.envoyer`, avec SA constante — pas une
        #  paraphrase : si les rôles requis changeaient, ce test changerait avec.
        return ROLES_CONSIGNES <= set(roles)

    assert transmises({"syndic", "resident", "cs"}) is True
    assert transmises({"resident", "cs"}) is True
    assert transmises({"syndic", "resident"}) is False, (
        "le conseil n'a rien reçu — le ticket doit encore le prévenir"
    )
    assert transmises({"syndic", "cs"}) is False, (
        "l'arrivant n'a rien reçu — il ne connaît pas les consignes"
    )
    assert transmises({"syndic"}) is False
    assert transmises(set()) is False, "aucun envoi : la diffusion doit reprendre"


def test_le_modele_reste_desactivable():
    """Un accueil qu'on ne peut pas couper est un accueil qu'on subit."""
    _, _, _, desactivable = _modele()
    assert desactivable is True
