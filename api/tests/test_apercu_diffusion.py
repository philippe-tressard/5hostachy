"""L'aperçu montre **ce qui partira**, jamais une reconstitution (#498).

## Pourquoi ce garde-fou

Demandé le 19/08/2026 : *« avant la diffusion il faudrait voir le mail (aperçu)
avant de confirmer son envoi »*, étendu à WhatsApp.

🔴 **Un aperçu qui ment est pire que pas d'aperçu.** S'il recomposait le message
de son côté, il deviendrait faux à la première évolution d'un gabarit — et
personne ne s'en apercevrait, puisque c'est justement l'aperçu qu'on regarderait
pour le vérifier. C'est le faux-vert de `standards/04` §14 : observer la chose,
pas son enregistrement.

La seule protection qui tienne est structurelle : **une seule composition**, que
l'aperçu et l'envoi appellent tous deux. Ce fichier vérifie qu'elle le reste.

⚠️ Deux des trois tests sont de l'**analyse statique** — ils lisent le code, pas
son résultat. C'est délibéré : le défaut qu'on veut empêcher est *l'apparition
d'une seconde écriture*, et aucune exécution ne la révèle tant que les deux
copies sont d'accord. C'est exactement ce qui a laissé la clé `fichiers` absente
d'un des deux envois pendant des mois (`test_email_contexte_appel.py`).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from tests.aides_ast import corps_avec_delegations, corps_de

_RACINE = Path(__file__).resolve().parents[2]
_EMAIL = _RACINE / "api" / "app" / "utils" / "email" / "__init__.py"
_APERCU = _RACINE / "api" / "app" / "routers" / "tickets" / "apercu.py"
#  🔴 LA COMPOSITION A DÉMÉNAGÉ LE 31/08/2026, et ces tests l'ont refusée.
#
#  Ils lisaient `tickets/apercu.py` et y cherchaient `composer_email(` et
#  `construire_message(`. Le jour où ces deux appels sont passés dans un module
#  partagé — pour que les actualités et le calendrier aient enfin le même aperçu —
#  les tests ont échoué alors que le code venait de S'AMÉLIORER.
#
#  ⚠️ C'est le piège que ce dépôt connaît bien : *un contrôle qui ne voit pas la
#  factorisation mesure la forme, pas le fait* (self-test de `lib-volumes.sh`,
#  `check-formulaire-creation` aveugle aux formulaires extraits). La correction
#  n'est PAS d'assouplir : c'est de suivre la composition là où elle est, et
#  d'exiger EN PLUS que le routeur passe par elle.
_ASSEMBLEUR = _RACINE / "api" / "app" / "utils" / "apercu_diffusion.py"
_COURRIELS = _RACINE / "api" / "app" / "routers" / "tickets" / "courriels.py"
_WHATSAPP = _RACINE / "api" / "app" / "utils" / "whatsapp.py"


def test_le_routeur_ne_compose_RIEN_lui_meme():
    """Le routeur d'aperçu délègue aux assembleurs, il ne les recopie pas.

    C'est la moitié que le déménagement de la composition aurait pu faire perdre :
    sans elle, un routeur pourrait rappeler `composer_email` à sa façon, et
    l'assembleur partagé ne servirait plus qu'à ceux qui veulent bien s'en servir.
    """
    routeur = _APERCU.read_text(encoding="utf-8")
    for assembleur in ("apercu_email(", "apercu_whatsapp("):
        assert assembleur in routeur, (
            f"L'aperçu des tickets n'appelle plus `{assembleur}` : il compose de "
            "son côté, et les entités branchées sur l'assembleur divergeront de lui."
        )
    for interdit in ("composer_email(", "construire_message(", "_contexte_rendu("):
        assert interdit not in routeur, (
            f"Le routeur appelle `{interdit}` en direct : la composition doit "
            "rester dans `apercu_diffusion.py`, sinon il y en a de nouveau deux."
        )


def test_l_apercu_et_l_envoi_composent_l_email_au_meme_endroit():
    """`composer_email` est la seule composition, et l'aperçu passe par elle."""
    apercu = _ASSEMBLEUR.read_text(encoding="utf-8")
    assert "composer_email(" in apercu, (
        "L'aperçu ne passe plus par `composer_email` : il recompose le message de "
        "son côté, et montrera donc autre chose que ce qui partira."
    )
    #  Et il ne remet pas le gabarit lui-même : `_wrap_email` n'a rien à faire ici.
    assert "_wrap_email(" not in apercu, (
        "L'aperçu appelle `_wrap_email` directement : toute règle ajoutée dans "
        "`composer_email` lui échapperait, et les deux rendus divergeraient."
    )
    envoi = _EMAIL.read_text(encoding="utf-8")
    #  🔴 ON SUIT LA DÉLÉGATION (05/09/2026). Ce test exigeait l'appel DANS le
    #  corps de chaque fonction ; le jour où `send_email` et `send_email_group`
    #  ont été factorisées — elles étaient identiques à 68 % —, la composition
    #  est descendue d'un cran et les deux ont échoué, alors que la propriété
    #  surveillée n'avait pas bougé. `standards/04` §35 : un contrôle qui
    #  reconnaît son objet à un indice de forme devient d'autant plus aveugle
    #  que le code est bien factorisé.
    for fonction in ("send_email", "send_email_group"):
        assert "composer_email(" in corps_avec_delegations(_EMAIL, fonction), (
            f"`{fonction}` ne passe plus par `composer_email`, ni directement ni "
            "par une fonction du module : elle recomposerait le message de son "
            "côté, et l'aperçu montrerait autre chose que ce qui part."
        )
    #  Une seule définition, sinon « la seule composition » est un vœu.
    assert len(re.findall(r"^def composer_email\(", envoi, re.MULTILINE)) == 1


def test_l_apercu_et_l_envoi_construisent_le_contexte_au_meme_endroit():
    """Le contexte du modèle vient de `contexte_ticket_syndic`, des deux côtés.

    C'est le point le plus fragile : le message peut être composé par la bonne
    fonction et rester faux si on lui donne un contexte fabriqué à la main.
    """
    apercu = _APERCU.read_text(encoding="utf-8")
    assert "contexte_ticket_syndic(" in apercu, (
        "L'aperçu construit son propre contexte : les variables du gabarit "
        "peuvent alors diverger de celles de l'envoi sans qu'aucun test ne le voie."
    )
    assert "contexte_ticket_syndic(" in corps_de(_COURRIELS, "envoyer_email_syndic_cs")


def test_l_apercu_whatsapp_ne_reecrit_pas_le_message():
    """`construire_message` est déjà pure — l'aperçu l'appelle, il ne la copie pas.

    Et il lit `message_sans_contenu` : c'est ce qui lui permet d'annoncer qu'un
    message partira **amputé** sur un périmètre restreint ou un contenu
    confidentiel. Rien à l'écran ne le disait avant, et c'est le meilleur apport
    de cet aperçu.
    """
    apercu = _ASSEMBLEUR.read_text(encoding="utf-8")
    assert "construire_message(" in apercu
    assert "message_sans_contenu(" in apercu, (
        "L'aperçu ne consulte pas `message_sans_contenu` : il montrerait le "
        "message complet alors que le groupe recevra un message amputé."
    )
    #  Les deux fonctions existent bien là où l'aperçu les prend.
    whatsapp = _WHATSAPP.read_text(encoding="utf-8")
    for nom in ("construire_message", "message_sans_contenu"):
        assert re.search(rf"^def {nom}\(", whatsapp, re.MULTILINE), (
            f"`{nom}` a disparu de `whatsapp.py` : l'aperçu importe une fonction "
            "qui n'existe plus, et l'erreur ne se verrait qu'à l'exécution."
        )


def test_l_apercu_whatsapp_transmet_TOUT_ce_que_l_envoi_transmet():
    """Les deux appels à `construire_message` doivent porter les mêmes arguments.

    🔴 POURQUOI (01/09/2026). `apercu_whatsapp` n'avait pas de paramètre `lien`,
    donc ne le transmettait pas — alors que `_envoyer_whatsapp` le passe. Aucun
    appelant ne s'en servait, et le défaut est resté invisible jusqu'à ce que
    l'annonce de hall envoie un lien vers l'actualité d'origine (#480). L'aperçu
    aurait alors montré un message **sans le lien** que le groupe reçoit.

    ⚠️ C'est l'angle mort propre aux aperçus : on regarde l'aperçu POUR vérifier
    ce qui part. Une omission y est indétectable à l'usage — seule la comparaison
    des deux appels la révèle, et seulement en lisant le code.

    Le test compare les **mots-clés** des deux appels. Les positionnels ne sont
    pas comparés : leur ordre est déjà verrouillé par la signature, et les nommer
    ici recopierait cette signature — une seconde liste qui divergerait.
    """
    def _mots_cles(source: str, dans: str) -> set[str]:
        """Les arguments NOMMÉS de l'appel à `construire_message` dans `dans`."""
        arbre = ast.parse(source)
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.FunctionDef) and noeud.name == dans):
                continue
            for appel in ast.walk(noeud):
                if (
                    isinstance(appel, ast.Call)
                    and getattr(appel.func, "id", None) == "construire_message"
                ):
                    return {kw.arg for kw in appel.keywords if kw.arg}
        raise AssertionError(
            f"aucun appel à `construire_message` dans `{dans}` — le test "
            "surveillait un appel qui n'existe plus, il ne surveillait donc rien."
        )

    cotes = _mots_cles(_ASSEMBLEUR.read_text(encoding="utf-8"), "apercu_whatsapp")
    envoi = _mots_cles(_WHATSAPP.read_text(encoding="utf-8"), "envoyer_whatsapp")

    manquants = envoi - cotes
    assert not manquants, (
        "`apercu_whatsapp` ne transmet pas à `construire_message` : "
        + ", ".join(sorted(manquants))
        + " — l'aperçu tairait ce que le message porte, et personne ne pourrait "
        "le voir : c'est l'aperçu qu'on regarde pour vérifier."
    )


def test_l_apercu_n_ecrit_rien_en_base():
    """Un aperçu qui persiste son brouillon laisserait des tickets fantômes.

    Le ticket prévisionnel est un objet en mémoire, jamais ajouté à la session.
    """
    corps = corps_de(_APERCU, "apercu_diffusion") + corps_de(_APERCU, "_ticket_previsionnel")
    for interdit in ("session.add(", "session.commit(", "session.delete("):
        assert interdit not in corps, (
            f"L'aperçu appelle `{interdit}` : il modifierait la base alors que "
            "l'utilisateur n'a encore rien confirmé."
        )
