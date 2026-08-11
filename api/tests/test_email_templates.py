"""Garde-fou préventif : contrat des variables des templates email.

Contexte (cf. point 9 du pré-check MEP) : les emails partent en BackgroundTask
et échouent silencieusement si un template Jinja2 référence une variable que le
contexte du point d'appel ne fournit pas. Ce bug s'est produit deux fois en
12 jours (reinitialisation_mdp le 03/06, ticket_statut_change le 15/06 — tous
deux `'destinataire' is undefined`).

Ce test verrouille, pour chaque template de `seed.EMAIL_TEMPLATES`, l'ensemble
exact des variables de premier niveau qu'il utilise (EXPECTED_VARS). Toute
modification d'un template qui ajoute/retire une variable casse ce test et
force une revue consciente :

    → si tu ajoutes `{{ ma_var.x }}` à un template, ajoute `ma_var` à
      EXPECTED_VARS ET vérifie que le `send_email(code=...)` correspondant
      passe bien `ma_var` dans son `context`.

Limite assumée : ce test garde le **côté template**. Le côté point d'appel
(une clé oubliée dans le `context`) reste couvert *a posteriori* par le point 9
(inspection de `historique_email`). Les deux forment une défense en profondeur.
"""
import pytest
from jinja2 import BaseLoader, meta
from jinja2.sandbox import SandboxedEnvironment

from app.seed import EMAIL_TEMPLATES

# Variables injectées d'office par send_email/_group (`_contexte_rendu` dans email.py)
#
# `reference_copro` et `prefixe_copro` les ont rejointes le 11/08/2026. Elles ne
# sont plus la responsabilité d'un point d'appel : cinq les lisaient chacun de
# leur côté et deux ne les fournissaient pas du tout, ce qui suffisait à faire
# partir un objet sans référence — Jinja évalue un indéfini à faux en silence.
# Elles sont désormais posées APRÈS le contexte de l'appelant, donc ni
# omissibles ni surchargeables.
BASE_CTX_VARS = {"annee", "app", "residence", "reference_copro", "prefixe_copro"}

# Contrat figé : variables de premier niveau requises par chaque template.
# Extrait de seed.EMAIL_TEMPLATES — à mettre à jour consciemment lors de toute
# modification d'un template (en alignant le point d'appel send_email).
EXPECTED_VARS: dict[str, set[str]] = {
    "reinitialisation_mdp": {"destinataire", "lien"},
    "compte_en_attente": {"utilisateur"},
    "compte_active": {"destinataire"},
    "compte_refuse": {"destinataire"},
    "ticket_bug_admin": {"auteur", "ticket"},
    "ticket_syndic": {
        "messages", "date_creation", "commentaire", "is_commentaire", "ticket",
        "fichiers", "date_commentaire", "historique", "auteur",
    },
    "ticket_statut_change": {"destinataire", "ticket"},
    "ticket_nouveau_message": {"ticket", "auteur_action", "message"},
    "reponse_communaute": {"reponse"},
    "idee_statut": {"idee"},
    "relance_syndic": {
        "tickets", "interlocuteurs", "anciennete",
    },
    "vigik_commande_recue": {"lot", "demandeur", "type"},
    "vigik_accepte": {"destinataire", "type"},
    "vigik_refuse": {"type", "destinataire", "motif"},
    "calendrier_evenement_cree": {"evenement"},
    "document_publie": {"document"},
    "publication_syndic": {
        "date_publication", "evolutions", "commentaire", "is_commentaire",
        "fichiers", "publication", "date_commentaire", "auteur",
    },
    # Remplace `sauvegarde_echec` et `alerte_espace_disque` : le contrôle
    # quotidien découvre les problèmes ensemble et n'envoie qu'un message.
    "alerte_systeme": {"problemes", "nb_problemes", "date_controle"},
    "verification_email": {"expire_heures", "lien", "prenom"},
    "annonce_hall": {"annonce", "auteur"},
    # Prévient le gestionnaire du site quand l'appariement a créé des accès
    # sans validation préalable. `resultat` porte aussi les accords en français,
    # calculés au point d'appel : un modèle n'a pas à porter la grammaire.
    "acces_apparies_auto": {"utilisateur", "resultat"},
    # Les trois modèles destinés à des destinataires EXTERNES (syndic, tiers),
    # longtemps déclarés en migration seulement et donc sans contrat ici.
    "nouvel_arrivant_bal": {"nom_complet", "batiment", "ancien_resident"},
    "publication_externe": {
        "date_publication", "evolutions", "commentaire", "is_commentaire",
        "fichiers", "publication", "date_commentaire", "auteur",
    },
    "ticket_externe": {
        "messages", "date_creation", "commentaire", "is_commentaire", "ticket",
        "fichiers", "date_commentaire", "auteur",
    },
}

# Modèles dont un exemplaire au moins part vers le syndic.
#
# La référence de copropriété y est obligatoire **sans exception** (règle du
# 11/08/2026) : c'est l'identifiant du dossier chez lui, et un message qui ne la
# porte pas sort de son tri par affaire. L'état de départ montre pourquoi une
# règle « sans exception » ne se tient pas à la main : deux modèles ne
# l'affichaient que sur une branche — un commentaire sur un ticket déjà transmis
# arrivait sans —, deux ne l'avaient nulle part, et `relance_syndic` l'écrivait
# sous une forme à lui (« [🏢 00213] – » au lieu de « 🏢 00213 — »).
#
# Les deux canaux « externes » en font partie bien que leur destinataire soit
# une adresse saisie à la main : rien ne dit que ce n'est pas le syndic, et une
# règle sans exception ne peut pas dépendre de ce que le code ignore.
MODELES_VERS_LE_SYNDIC = frozenset({
    "ticket_syndic", "publication_syndic", "relance_syndic",
    "nouvel_arrivant_bal", "ticket_externe", "publication_externe",
})

# Modèles dont l'objet doit NOMMER ce dont il parle, et l'expression qui le fait.
#
# « Ticket #TK-427648 — 5Hostachy » n'apprenait rien : deux tickets de la même
# copropriété avaient des objets interchangeables, et il fallait ouvrir pour
# savoir de quoi il s'agissait (11/08/2026). Le titre a été ajouté aux cinq
# modèles qui en manquaient ; les cinq autres l'avaient déjà.
#
# Ce contrat est ici parce que rien d'autre ne le porte : les modèles vivent en
# base, `EXPECTED_VARS` ne regarde que le premier niveau (`ticket` suffit à le
# satisfaire, que le titre soit dans l'objet ou seulement dans le corps), et une
# migration qui réécrit un objet le ferait disparaître sans un test rouge.
SUJETS_QUI_NOMMENT_L_OBJET: dict[str, str] = {
    "ticket_syndic": "{{ ticket.titre }}",
    "ticket_statut_change": "{{ ticket.titre }}",
    "ticket_nouveau_message": "{{ ticket.titre }}",
    "ticket_bug_admin": "{{ ticket.titre }}",
    "ticket_externe": "{{ ticket.titre }}",
    "publication_syndic": "{{ publication.titre }}",
    "publication_externe": "{{ publication.titre }}",
    "calendrier_evenement_cree": "{{ evenement.titre }}",
    "idee_statut": "{{ idee.titre }}",
    "annonce_hall": "{{ annonce.titre }}",
}

_env = SandboxedEnvironment(loader=BaseLoader())


def _required_vars(sujet: str | None, corps_html: str | None) -> set[str]:
    """Variables de premier niveau référencées par le template (hors base_ctx)."""
    source = f"{sujet or ''} {corps_html or ''}"
    ast = _env.parse(source)  # lève TemplateSyntaxError si le template est cassé
    return meta.find_undeclared_variables(ast) - BASE_CTX_VARS


def test_chaque_modele_declare_son_intention():
    """Tout modèle doit dire ce qu'il attend du destinataire.

    Le bandeau d'intention ne vaut que s'il est là partout : un seul e-mail qui
    n'annonce pas la couleur ramène le lecteur au tri à l'aveugle, et comme
    l'absence d'intention ne rend simplement aucun bandeau, rien ne le
    signalerait. C'est le genre d'oubli qui arrive au modèle suivant, pas à
    ceux d'aujourd'hui.
    """
    from app.seed import INTENTIONS_PAR_MODELE
    from app.utils.email import INTENTIONS

    codes = {row[0] for row in EMAIL_TEMPLATES}
    sans_intention = codes - set(INTENTIONS_PAR_MODELE)
    assert not sans_intention, (
        f"Modèles sans intention déclarée : {sorted(sans_intention)}. Ajoute-les "
        "à `seed.INTENTIONS_PAR_MODELE` — information, action_requise, "
        "reponse_attendue ou archive."
    )

    inconnues = {
        code: valeur
        for code, valeur in INTENTIONS_PAR_MODELE.items()
        if valeur not in INTENTIONS
    }
    assert not inconnues, (
        f"Intentions non reconnues par le gabarit : {inconnues}. Elles ne "
        "rendraient aucun bandeau, en silence."
    )

    orphelines = set(INTENTIONS_PAR_MODELE) - codes
    assert not orphelines, (
        f"Intentions déclarées pour des modèles inexistants : {sorted(orphelines)}."
    )


def test_le_bandeau_dintention_est_rendu_dans_le_gabarit():
    """Cas zéro : le bandeau doit réellement apparaître dans le HTML envoyé."""
    from app.utils.email import INTENTIONS, _wrap_email

    html = _wrap_email(
        "<p>corps</p>", "Résidence", "https://exemple.fr", "", 2026,
        intention="action_requise",
    )
    assert INTENTIONS["action_requise"][0] in html, (
        "Le bandeau d'intention n'apparaît pas dans le gabarit : les modèles "
        "déclarent une intention que personne n'affiche."
    )
    # Une intention absente ou inconnue ne doit rien ajouter, jamais une
    # étiquette fausse.
    for valeur in ("", None, "inconnue"):
        neutre = _wrap_email(
            "<p>corps</p>", "Résidence", "https://exemple.fr", "", 2026, intention=valeur
        )
        assert all(lib not in neutre for lib, _, _ in INTENTIONS.values()), (
            f"Une intention {valeur!r} affiche pourtant un bandeau."
        )


def test_tous_les_templates_ont_un_contrat():
    """EXPECTED_VARS et EMAIL_TEMPLATES doivent lister exactement les mêmes codes.

    La vérification est **bidirectionnelle**, et le second sens est le plus
    important depuis que les modèles vivent dans quatre modules assemblés par
    `seed/emails/__init__.py` (05/08/2026) : une famille oubliée à l'assemblage
    ferait disparaître cinq ou six modèles d'un coup.

    Rien ne l'aurait vu. Les contrôles qui comparent la base à `EMAIL_TEMPLATES`
    comparent alors une liste amputée à elle-même et restent verts — vérifié en
    retirant une famille, ils passaient tous. EXPECTED_VARS est la seule liste de
    codes maintenue **indépendamment** de l'assemblage : c'est elle qui sert
    d'ancre, et c'est ce qui rend ce test non circulaire (`standards/04` §16).
    """
    codes = {row[0] for row in EMAIL_TEMPLATES}
    sans_contrat = codes - set(EXPECTED_VARS)
    assert not sans_contrat, (
        f"Templates sans contrat déclaré dans EXPECTED_VARS : {sorted(sans_contrat)}. "
        "Ajoute leur jeu de variables et vérifie le point d'appel send_email."
    )

    disparus = set(EXPECTED_VARS) - codes
    assert not disparus, (
        f"Modèles déclarés dans EXPECTED_VARS mais absents de EMAIL_TEMPLATES : "
        f"{sorted(disparus)}. Soit une famille manque à l'assemblage de "
        "`seed/emails/__init__.py` — et ces e-mails ne partiront plus du tout —, "
        "soit la suppression est voulue et EXPECTED_VARS doit suivre, avec la "
        "migration qui retire les modèles de la base."
    )


@pytest.mark.parametrize("row", EMAIL_TEMPLATES, ids=lambda r: r[0])
def test_template_respecte_son_contrat(row):
    """Le template ne référence ni plus ni moins que les variables déclarées."""
    code, _libelle, sujet, corps_html, _desactivable = row
    if code not in EXPECTED_VARS:
        pytest.skip("contrat absent — couvert par test_tous_les_templates_ont_un_contrat")
    needs = _required_vars(sujet, corps_html)
    assert needs == EXPECTED_VARS[code], (
        f"{code}: variables utilisées {sorted(needs)} ≠ contrat {sorted(EXPECTED_VARS[code])}.\n"
        f"Si la modification est voulue : mets à jour EXPECTED_VARS ET assure-toi que "
        f"le send_email(code={code!r}) fournit exactement ces variables dans son context."
    )


@pytest.mark.parametrize("code,expression", sorted(SUJETS_QUI_NOMMENT_L_OBJET.items()))
def test_lobjet_nomme_ce_dont_il_parle(code, expression):
    """L'objet doit désigner l'élément, pas seulement son numéro.

    Ce test garde la **source**. Une installation en service tient ses modèles en
    base : c'est la migration 0135 qui les y met à jour, et le test suivant
    vérifie qu'elle dit exactement la même chose que cette source-ci.
    """
    sujets = {row[0]: row[2] for row in EMAIL_TEMPLATES}
    assert code in sujets, f"{code} a disparu de EMAIL_TEMPLATES."
    assert expression in sujets[code], (
        f"L'objet de {code} ne nomme plus l'élément : {sujets[code]!r} ne contient "
        f"pas {expression}. Le destinataire retrouve un objet interchangeable avec "
        "celui du ticket ou de la publication d'à côté."
    )


def test_lobjet_rendu_tient_sur_une_ligne_et_reste_court():
    """Un titre est saisi librement : il ne doit ni couper l'en-tête, ni s'étaler.

    Le cas du saut de ligne n'est pas cosmétique — il permettrait à l'auteur d'un
    ticket d'ajouter un `Bcc:` à l'en-tête du message envoyé au syndic. Python
    encode aujourd'hui nos objets en RFC 2047 et neutraliserait la coupure, mais
    cette protection tient à la présence d'un caractère non-ASCII : elle
    disparaîtrait en silence le jour où un objet devient purement ASCII.
    """
    from app.utils.email import _SUJET_MAX, _sujet_sur_une_ligne

    injecte = _sujet_sur_une_ligne("Fuite parking\r\nBcc: tiers@exemple.fr\n\nsuite")
    assert "\n" not in injecte and "\r" not in injecte, (
        "Un titre à retours à la ligne passe tel quel dans l'objet : l'en-tête "
        "Subject peut être coupée et un Bcc ajouté."
    )
    assert injecte == "Fuite parking Bcc: tiers@exemple.fr suite"

    assert _sujet_sur_une_ligne("Réunion\tdu\x00mardi") == "Réunion du mardi", (
        "Les caractères de contrôle doivent être neutralisés, NUL compris — "
        "`\\s` ne le couvre pas et la bibliothèque `email` lèverait dessus."
    )

    long = _sujet_sur_une_ligne("Ticket — " + "a" * 400)
    assert len(long) == _SUJET_MAX, f"Objet non borné : {len(long)} caractères."
    assert long.endswith("…"), "La troncature doit se voir."

    #  Cas zéro : un objet normal ne doit surtout pas être retouché.
    intact = "🏢 00213 — Ticket #TK-427648 — Fuite au parking — 5Hostachy"
    assert _sujet_sur_une_ligne(intact) == intact


class _Quelconque:
    """Répond à n'importe quel attribut : rend un objet sans monter un contexte réel."""

    def __getattr__(self, nom):
        return f"<{nom}>"

    def __getitem__(self, cle):
        return f"<{cle}>"

    def __str__(self):
        return "<valeur>"

    def __bool__(self):
        return True


@pytest.mark.parametrize("code", sorted(MODELES_VERS_LE_SYNDIC))
def test_lobjet_au_syndic_porte_toujours_la_reference(code):
    """La référence doit survivre à TOUTES les branches de l'objet, pas à une seule.

    C'est le défaut que ce test verrouille : `reference_copro` figurait dans
    `EXPECTED_VARS` de `ticket_syndic` et de `publication_syndic`, et les deux
    modèles la mentionnaient bien — mais uniquement dans la branche de la
    création. Un commentaire sur un ticket déjà transmis partait sans elle, et
    aucun contrôle ne pouvait le voir : chercher la variable dans la source d'un
    modèle répond « présente » quel que soit le `{% if %}` qui l'entoure.

    On rend donc l'objet, dans les deux états de `is_commentaire`, et on regarde
    le texte produit. Le préfixe vient de `_prefixe_copro`, la fonction réellement
    utilisée à l'envoi : le test traverse la même chaîne que la production, du
    code jusqu'au modèle.
    """
    from app.utils.email import _prefixe_copro

    sujets = {row[0]: row[2] for row in EMAIL_TEMPLATES}
    assert code in sujets, f"{code} a disparu de EMAIL_TEMPLATES."
    prefixe = _prefixe_copro("00213")

    for is_commentaire in (False, True):
        ctx = {nom: _Quelconque() for nom in EXPECTED_VARS[code]}
        ctx.update({
            "reference_copro": "00213",
            "prefixe_copro": prefixe,
            "is_commentaire": is_commentaire,
            "residence": _Quelconque(),
            "app": _Quelconque(),
            "annee": 2026,
        })
        rendu = _env.from_string(sujets[code]).render(**ctx)
        assert prefixe in rendu, (
            f"L'objet de {code} n'affiche pas la référence de copropriété quand "
            f"is_commentaire={is_commentaire} : {rendu!r}.\n"
            "Elle est obligatoire, sans exception, dans tout message adressé au "
            "syndic — c'est l'identifiant sous lequel il classe le dossier."
        )
        #  Sous la forme commune, et une seule : `relance_syndic` écrivait
        #  « [🏢 00213] – », les autres « 🏢 00213 — ». Deux copies d'une même
        #  notion divergent, et celles-ci l'avaient déjà fait.
        assert rendu.count("00213") == 1, (
            f"L'objet de {code} affiche la référence plusieurs fois ou sous une "
            f"forme parallèle : {rendu!r}. Elle se compose dans `_prefixe_copro`, "
            "nulle part ailleurs."
        )


def test_les_migrations_disent_la_meme_chose_que_le_seed():
    """Toute migration exposant `REMPLACEMENTS` doit produire l'objet du seed.

    C'est le défaut propre à ce projet : le seed n'insère que ce qui est absent,
    donc en service, l'objet réellement envoyé est celui qu'a écrit la migration —
    pas celui qu'on lit dans `seed/emails/`. Les deux peuvent diverger sans que
    rien ne le signale, et c'est alors le code source qui ment, pas la production.

    Le balayage est volontairement générique plutôt que nominatif : la migration
    suivante qui retouchera un objet sera couverte sans que personne n'ait à
    penser à l'ajouter ici.

    Trois propriétés, dont la dernière est la plus facile à casser :

    1. le fragment **voulu** par la migration est bien celui du seed ;
    2. le fragment **remplacé** n'y est plus — sinon la migration serait sans effet
       sur une base qui vient d'être semée ;
    3. aucun fragment de remplacement ne contient celui qu'il remplace, faute de
       quoi rejouer `upgrade` appliquerait l'ajout une seconde fois.

    Si deux migrations retouchent le même objet en cascade, la seconde peut
    invalider le fragment de la première et faire échouer ce test : c'est voulu —
    la revue doit être consciente, pas automatique.
    """
    import importlib.util
    from pathlib import Path

    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    sujets = {row[0]: row[2] for row in EMAIL_TEMPLATES}
    vues = 0

    for chemin in sorted(versions.glob("*.py")):
        if "REMPLACEMENTS" not in chemin.read_text(encoding="utf-8"):
            continue
        spec = importlib.util.spec_from_file_location(f"migration_{chemin.stem}", chemin)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        remplacements = getattr(migration, "REMPLACEMENTS", None)
        if not remplacements:
            continue
        vues += 1
        for code, ancien, nouveau in remplacements:
            assert code in sujets, (
                f"{chemin.name} met à jour « {code} », absent de EMAIL_TEMPLATES."
            )
            assert nouveau in sujets[code], (
                f"{chemin.name} écrit {nouveau!r} dans l'objet de {code}, mais le "
                f"seed porte {sujets[code]!r}. Les bases existantes et les bases "
                "neuves n'enverraient pas le même objet."
            )
            assert ancien not in sujets[code], (
                f"Le seed de {code} contient encore {ancien!r}, que {chemin.name} "
                "remplace : une base neuve partirait avec l'ancien objet."
            )
            assert ancien not in nouveau, (
                f"{chemin.name} remplace {ancien!r} par un fragment qui le contient "
                f"({code}) : rejouer la migration l'appliquerait une fois de plus."
            )

    #  Cas zéro : si le balayage ne trouve plus rien, il ne vérifie plus rien —
    #  et resterait vert (`standards/04` §2).
    assert vues >= 2, (
        f"Seulement {vues} migration(s) à REMPLACEMENTS trouvée(s) : le balayage "
        "ne vérifie plus la correspondance seed ↔ migration."
    )


def test_aucun_objet_ne_recompose_la_reference_a_la_main():
    """La forme du préambule vit dans `_prefixe_copro`, et nulle part ailleurs.

    Elle était recopiée dans sept objets, sous deux formes déjà divergentes. Un
    huitième modèle écrit demain la recopierait sans que rien ne s'y oppose — et
    c'est exactement ainsi que les deux formes actuelles sont apparues.

    Le test lit les objets, pas les corps : ceux-ci mentionnent légitimement la
    référence en toutes lettres (« — réf. 00213 »), ce qui n'est pas un préambule
    d'objet mais une phrase.
    """
    fautifs = []
    for code, _libelle, sujet, _corps, _desactivable in EMAIL_TEMPLATES:
        if "reference_copro" in (sujet or ""):
            fautifs.append(f"{code} : {sujet}")

    assert not fautifs, (
        "Ces objets composent la référence eux-mêmes au lieu d'utiliser "
        "`{{ prefixe_copro }}` :\n  " + "\n  ".join(fautifs)
        + "\nLa forme est écrite une seule fois, dans `email._prefixe_copro` — "
        "et un modèle se réécrit depuis Admin → Emails, donc une règle qui y "
        "serait recopiée pourrait être retirée par un formulaire."
    )
