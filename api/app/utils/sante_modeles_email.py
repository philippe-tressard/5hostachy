"""Ce qui est SERVI diffère-t-il de ce que le code dit ? (#850)

## Le trou que ce contrôle bouche

Un modèle d'e-mail vit **en base**. `_poser_les_absents` ne pose que ce qui
manque : une ligne existante n'est **jamais** reprise par le seed. Enrichir un
modèle demande donc une migration, et cette migration porte une clause `WHERE`
sur le texte attendu — pour ne pas écraser une installation qui l'aurait retouché
depuis Admin → Emails.

🔴 **Si ce `WHERE` ne correspond à rien, il ne se passe RIEN.** Pas d'erreur, pas
de trace, aucune ligne de journal : la migration réussit en ayant modifié zéro
ligne. Le code contient la nouvelle version, tous les tests passent —
`test_email_templates.py` lit le dépôt — et l'installation continue d'envoyer
l'ancienne.

C'est ce qui serait arrivé à `nouvel_arrivant_bal` le 08/09/2026 : l'arrivant et
le conseil auraient reçu la version rédigée pour le syndic, sans le lien vers les
consignes, et personne n'aurait pu le savoir sans ouvrir l'écran. C'est d'ailleurs
en l'ouvrant que Philippe a trouvé les deux colonnes restées en arrière.

C'est le raisonnement de `health_monitor._check_reference_copro` : la règle est
vérifiable sur les modèles, elle reste fausse sur l'installation, et le seul
endroit d'où l'écart se voit est un contrôle qui regarde **la base réelle**.

## Deux axes, et pourquoi pas le texte

Comparer le **texte** alerterait à chaque reformulation faite depuis
Admin → Emails — un droit que le conseil a, et que les migrations protègent
exprès. L'alerte deviendrait du bruit, puis serait ignorée : un contrôle qu'on
ignore est un contrôle absent (`standards/04`).

Sont donc comparés les deux axes qui ne changent **pas** quand on reformule :

1. **les variables**. Un écart signifie l'une de deux choses, toutes deux graves :

   * le modèle servi n'a **pas** reçu un enrichissement que le code fournit — il
     rend une version incomplète, ou identique pour des publics qui devraient
     différer ;
   * le modèle servi lit une variable que **personne ne fournit** — Jinja
     l'évalue à vide, en silence. C'est la famille `'destinataire' is undefined`,
     survenue trois fois en deux mois, et le seul cas que
     `test_email_templates.py` ne peut pas voir : il n'inspecte que le dépôt.

2. **l'intention**, quand la ligne n'en porte aucune. Elle décide du bandeau
   **et** de l'adresse d'expédition : une ligne muette repart sur le choix du
   code, ce qui est le repli voulu, mais mérite d'être signalé — c'est le signe
   d'une ligne posée avant la migration 0130.

   ⚠️ Une intention **différente** de celle du code n'est PAS un écart : l'écran
   permet de la changer, et depuis le 08/09/2026 c'est bien celle de la ligne qui
   décide de l'expéditeur. La signaler ferait crier le contrôle sur une décision
   d'administrateur.
"""
from __future__ import annotations

from sqlmodel import Session, select

#: Injectées d'office par `email._contexte_rendu` — communes à tous les modèles,
#: donc hors du contrat de chacun.
VARIABLES_DU_GABARIT = {"annee", "app", "residence", "reference_copro", "prefixe_copro"}


def variables_de(sujet: str | None, corps: str | None) -> set[str]:
    """Les variables de premier niveau d'un modèle, gabarit exclu.

    Même lecture que `tests/test_email_templates.py`, appliquée au texte **réel**
    d'une installation plutôt qu'à celui du dépôt. C'est toute la différence : le
    test garde le code, ce contrôle garde ce qui est servi.
    """
    from jinja2 import BaseLoader, meta
    from jinja2.sandbox import SandboxedEnvironment

    env = SandboxedEnvironment(loader=BaseLoader())
    try:
        arbre = env.parse(f"{sujet or ''}{corps or ''}")
    except Exception:
        #  Un Jinja invalide échouera à l'envoi, et c'est là que le signal doit
        #  être. Rendre un ensemble vide ferait crier CE contrôle sur un défaut
        #  qui n'est pas le sien.
        return set()
    return meta.find_undeclared_variables(arbre) - VARIABLES_DU_GABARIT


def controler(session: Session) -> list[str]:
    """Les écarts entre les modèles servis et ceux du code, en clair."""
    from app.models.core import ModeleEmail
    from app.seed import EMAIL_TEMPLATES
    from app.seed.emails import INTENTIONS_PAR_MODELE

    attendus = {code: (sujet, corps) for code, _l, sujet, corps, _d in EMAIL_TEMPLATES}
    lignes = session.exec(select(ModeleEmail)).all()

    #  🔴 Cas zéro : une base sans aucun modèle rendrait « aucun écart », donc un
    #  vert — alors que plus rien ne partirait, ni alerte ni réinitialisation de
    #  mot de passe. Un contrôle qui ne peut pas s'exécuter rend INCONNU, jamais
    #  OK (`standards/04` §1).
    if not lignes:
        return [
            "Aucun modèle d'e-mail en base : le contrôle ne peut pas conclure.\n"
            "Aucun message ne peut partir dans cet état — ni alerte système, ni "
            "réinitialisation de mot de passe.\n"
            "Vérifier que le seed s'est exécuté au démarrage de l'API."
        ]

    ecarts: list[str] = []
    for modele in lignes:
        if modele.code not in attendus:
            #  Un modèle en base que le code ignore : ancien, ou créé à la main.
            #  Il n'a pas de version de référence — ce n'est pas un écart.
            continue

        sujet_code, corps_code = attendus[modele.code]
        du_code = variables_de(sujet_code, corps_code)
        servies = variables_de(modele.sujet, modele.corps_html)

        if du_code != servies:
            detail = []
            manquantes = sorted(du_code - servies)
            en_trop = sorted(servies - du_code)
            if manquantes:
                detail.append(
                    "Variables du code absentes du modèle servi : "
                    + ", ".join(manquantes)
                    + " — une migration d'enrichissement n'a probablement rien "
                    "touché : sa clause WHERE ne correspondait plus au texte en base."
                )
            if en_trop:
                detail.append(
                    "Variables lues par le modèle servi et fournies par personne : "
                    + ", ".join(en_trop)
                    + " — Jinja les rend VIDES, en silence."
                )
            ecarts.append(
                f"Modèle d'e-mail « {modele.code} » : ce qui part diffère du code.\n"
                + "\n".join(detail)
                + "\nÀ comparer dans Admin → Emails, puis réappliquer la migration "
                "concernée ou corriger le texte à la main."
            )

        if not (modele.intention or "").strip() and INTENTIONS_PAR_MODELE.get(modele.code):
            ecarts.append(
                f"Modèle d'e-mail « {modele.code} » : aucune intention en base.\n"
                "Le bandeau du message est vide, et l'adresse d'expédition retombe "
                f"sur le choix du code (« {INTENTIONS_PAR_MODELE[modele.code]} »).\n"
                "À choisir dans Admin → Emails → Intention."
            )

    return ecarts


__all__ = ["VARIABLES_DU_GABARIT", "controler", "variables_de"]
