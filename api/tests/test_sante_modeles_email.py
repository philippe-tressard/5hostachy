"""Garde-fou — **le contrôle qui compare la BASE au code** (#850).

## Pourquoi ce contrôle existe

Une migration qui enrichit un modèle d'e-mail porte une clause `WHERE` sur le
texte attendu, pour ne pas écraser une installation retouchée depuis
Admin → Emails. Si ce `WHERE` ne correspond à rien, **il ne se passe rien** : la
migration réussit en ayant modifié zéro ligne, sans erreur ni trace. Le code
porte la nouvelle version, tous les tests passent — ils lisent le dépôt — et
l'installation continue d'envoyer l'ancienne.

Ces tests éprouvent le contrôle lui-même : **un contrôle qui ne refuse rien est
un contrôle absent.**

## Ce qui est verrouillé

1. il **détecte** une variable du code absente du modèle servi (migration
   silencieusement sans effet) ;
2. il **détecte** une variable servie que personne ne fournit (Jinja rend vide) ;
3. il **se tait** sur une simple reformulation — sinon il crierait à chaque
   édition légitime, et serait ignoré dans la semaine ;
4. il **se tait** sur une intention différente de celle du code — l'écran permet
   de la changer, et c'est elle qui décide depuis le 08/09/2026 ;
5. 🔴 le **cas zéro** : une base sans aucun modèle rend INCONNU, pas OK.
"""
from __future__ import annotations

from app.utils.sante_modeles_email import controler, variables_de


class _Ligne:
    """Une ligne `ModeleEmail`, réduite à ce que le contrôle lit."""

    def __init__(self, code: str, sujet: str, corps: str, intention: str = "information"):
        self.code = code
        self.sujet = sujet
        self.corps_html = corps
        self.intention = intention


class _Session:
    """Une session qui ne rend que les lignes qu'on lui donne."""

    def __init__(self, lignes):
        self._lignes = lignes

    def exec(self, _requete):
        session = self

        class _Resultat:
            def all(self):
                return session._lignes

        return _Resultat()


def _du_depot(code: str) -> tuple[str, str]:
    from app.seed import EMAIL_TEMPLATES

    _c, _l, sujet, corps, _d = next(t for t in EMAIL_TEMPLATES if t[0] == code)
    return sujet, corps


def test_il_DETECTE_une_migration_restee_sans_effet():
    """🔴 Le cas de `nouvel_arrivant_bal` s'il n'avait pas basculé.

    La ligne porte le texte de mars 2026 ; le code, celui de septembre. Le
    contrôle doit nommer les trois variables perdues — sans quoi l'arrivant et le
    conseil recevraient la version du syndic, et personne ne le saurait.
    """
    ancien = (
        "{{ prefixe_copro }}Nouvel arrivant",
        "<p>{{ nom_complet }} — {{ batiment }} — {{ ancien_resident }}</p>",
    )
    ecarts = controler(_Session([_Ligne("nouvel_arrivant_bal", *ancien)]))

    assert len(ecarts) == 1, f"écart non détecté : {ecarts}"
    for perdue in ("role_destinataire", "lien_consignes", "destinataire"):
        assert perdue in ecarts[0], f"`{perdue}` n'est pas nommée dans l'alerte"
    assert "WHERE" in ecarts[0], "l'alerte ne dit pas où chercher la cause"


def test_il_DETECTE_une_variable_que_personne_ne_fournit():
    """La famille `'destinataire' is undefined` — Jinja rend vide, en silence.

    Quelqu'un ajoute `{{ civilite }}` depuis Admin → Emails. Aucun point d'appel
    ne la fournit : le message part avec un trou, et rien ne le signale. C'est le
    seul cas que `test_email_templates.py` ne peut pas voir — il lit le dépôt.
    """
    sujet, corps = _du_depot("compte_active")
    ecarts = controler(_Session([_Ligne("compte_active", sujet, corps + "{{ civilite }}")]))

    assert len(ecarts) == 1
    assert "civilite" in ecarts[0]
    assert "VIDES" in ecarts[0], "l'alerte ne dit pas ce qui arrivera au lecteur"


def test_il_SE_TAIT_sur_une_simple_reformulation():
    """Le conseil a le droit de réécrire un modèle — les migrations le protègent.

    ⚠️ C'est la moitié qui décide si ce contrôle survivra : un contrôle qui crie
    à chaque édition légitime est désactivé dans la semaine, et ne protège alors
    plus du cas grave.
    """
    sujet, corps = _du_depot("compte_active")
    reformule = corps.replace("Bonjour", "Bonjour à vous").replace("<p>", "<p >")
    assert controler(_Session([_Ligne("compte_active", sujet, reformule)])) == [], (
        "le contrôle a crié sur une reformulation : il sera ignoré, puis retiré."
    )


def test_il_SE_TAIT_sur_une_intention_CHANGEE_a_l_ecran():
    """L'écran permet de la changer, et c'est elle qui décide de l'expéditeur.

    La signaler ferait crier le contrôle sur une décision d'administrateur.
    """
    sujet, corps = _du_depot("compte_active")
    ligne = _Ligne("compte_active", sujet, corps, intention="action_requise")
    assert controler(_Session([ligne])) == []


def test_il_SIGNALE_une_intention_ABSENTE():
    """Une ligne muette : bandeau vide, et l'expéditeur retombe sur le code.

    C'est différent d'une intention changée — ce n'est pas un choix, c'est une
    ligne posée avant la migration 0130.
    """
    sujet, corps = _du_depot("compte_active")
    ecarts = controler(_Session([_Ligne("compte_active", sujet, corps, intention="")]))
    assert len(ecarts) == 1
    assert "aucune intention" in ecarts[0].lower()


def test_un_modele_INCONNU_du_code_n_est_pas_un_ecart():
    """Ancien, ou créé à la main : il n'a pas de version de référence."""
    assert controler(_Session([_Ligne("modele_maison", "Objet", "{{ truc }}")])) == []


def test_cas_zero_une_base_SANS_modele_rend_INCONNU_pas_OK():
    """🔴 La forme d'échec la plus coûteuse : le vert qui a cessé de voir.

    Sans ce cas, une base vide — seed non exécuté, table tronquée — produirait
    « aucun écart ». Or dans cet état plus **aucun** message ne part : ni alerte
    système, ni réinitialisation de mot de passe.
    """
    ecarts = controler(_Session([]))
    assert len(ecarts) == 1
    assert "ne peut pas conclure" in ecarts[0]
    assert "seed" in ecarts[0]


def test_variables_de_ecarte_le_gabarit_commun():
    """`residence`, `app`, `annee`… valent pour tous : hors du contrat de chacun."""
    assert variables_de("{{ residence.nom }}", "{{ app.url }}{{ mien }}") == {"mien"}


def test_variables_de_ne_crie_pas_sur_un_JINJA_invalide():
    """Il échouera à l'envoi — c'est là que le signal doit être, pas ici."""
    assert variables_de("{% if %}", "") == set()
