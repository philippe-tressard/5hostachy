"""Aucune colonne de `Utilisateur` ne doit être ÉCRITE sans être jamais LUE.

## L'incident (10/09/2026, #873)

`consentement_communications` est posé à l'inscription — l'utilisateur coche
« J'accepte de recevoir les notifications de l'application par e-mail » — puis
**plus rien** ne le lit. Ni la décision d'envoi (`mail_autorise` consulte
`preferences_notifications`, jamais ce champ), ni un écran, ni un administrateur.

Deux conséquences, dont une de conformité :

1. **la promesse est fausse** : décocher la case ne coupe aucun e-mail, le défaut
   des préférences valant « mon bâtiment : oui » ;
2. **le consentement n'est pas retirable** — RGPD art. 7.3, *aussi simple à
   retirer qu'à donner*. Il ne s'affiche nulle part, donc il ne se retire nulle
   part.

## Pourquoi un contrôle, et pas une relecture

Le défaut ne se voit **d'aucun point d'observation** : la case s'affiche
normalement, la ligne s'écrit en base, l'inscription réussit, aucun journal ne dit
rien. Il n'apparaît qu'en croisant quatre fichiers qu'on n'a aucune raison
d'ouvrir ensemble. C'est `standards/11` §17 dans sa forme la plus muette — une
donnée qu'on demande à quelqu'un et qu'on ne rend ni à lui, ni à personne.

## Ce que « lue » veut dire ici — et pourquoi chercher le NOM ne suffisait pas

Première version de ce contrôle : chercher le nom de la colonne hors du modèle.
Elle déclarait `consentement_communications` **corrigé**, alors qu'il est le
défaut qui l'a fait écrire — parce que son nom apparaît bien deux fois, dans
`Utilisateur(consentement_communications=…)` et dans `UserCreate`. Ce sont des
**écritures**, exactement le geste dont on cherche l'absence de contrepartie.

Un contrôle qui compte l'écriture comme une lecture déclare toujours vert le
défaut qu'il cherche. Il raisonne donc sur l'arbre syntaxique :

* **lecture** = `X.mon_champ` en contexte `Load` (`ast.Attribute`), n'importe où
  dans `app/` hors du modèle ;
* **lecture aussi** = champ déclaré dans un schéma de **sortie** (classe dont le
  nom finit par `Read`) — c'est le front qui le lit ;
* tout le reste — `Champ(mon_champ=…)`, `user.mon_champ = …`, un champ de
  `*Create` ou `*Update` — est une **écriture**, et ne compte pas.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
MODELE = APP / "models" / "core.py"

#: Les colonnes écrites et jamais lues, avec leur ticket. Ce sont des DETTES, pas
#: des dérogations : chacune est une donnée qu'on demande à quelqu'un sans s'en
#: servir. Le second test échoue si l'une d'elles se met à être lue — une dette
#: qui ne sert plus fait croire que la règle est plus poreuse qu'elle ne l'est.
#:
#: 🔴 **Ce dictionnaire est VIDE depuis le 10/09/2026, et c'est le but.** Il en a
#: porté exactement une, `consentement_communications`, le temps que l'arbitrage
#: soit rendu (#873) : la case a été retirée de l'inscription, la colonne
#: supprimée par la migration 0187, et son refus enfin honoré pour les comptes
#: existants. Une dette déclarée est une dette datée — celle-ci a vécu douze
#: heures.
DETTES: dict[str, str] = {}

#: Colonnes dont l'absence de lecture est NORMALE et le restera.
#:
#: ⚠️ Ce ne sont pas des dettes : une clé primaire n'a pas à être « lue » par un
#: nom d'attribut pour servir, et un mot de passe haché se lit par la fonction de
#: vérification, qui le reçoit en argument.
HORS_SUJET = {"id", "hashed_password"}


def _colonnes_utilisateur() -> list[str]:
    """Les noms de colonnes déclarés dans `class Utilisateur`."""
    source = MODELE.read_text(encoding="utf-8")
    debut = source.index("class Utilisateur(")
    #  La classe s'arrête à la déclaration suivante au niveau du module.
    suite = re.search(r"\nclass \w+\(", source[debut + 10:])
    corps = source[debut: debut + 10 + suite.start()] if suite else source[debut:]
    noms = re.findall(r"^    ([a-z][a-z0-9_]*)\s*:", corps, re.MULTILINE)
    #  Les `Relationship` ne sont pas des colonnes : elles se lisent par
    #  navigation, et leur absence de mention littérale ne prouve rien.
    return [n for n in noms if f"{n}:" in corps and "Relationship(" not in corps.split(f"\n    {n}:")[1].split("\n")[0]]


def _transports(arbre: ast.AST) -> set[int]:
    """Les `X.champ` qui ne font que RECOPIER l'entrée vers la colonne homonyme.

    🔴 C'est la correction qui a fait passer ce contrôle du faux vert au rouge.
    `Utilisateur(consentement_communications=body.consentement_communications)`
    contient un `Attribute` en `Load` — et pourtant rien n'y *lit* la donnée : la
    ligne transporte l'entrée de la requête vers la base, ce qui est justement le
    geste dont on cherche la contrepartie manquante.

    Un argument nommé dont la valeur est un attribut **du même nom** est donc
    écarté. Le motif est étroit à dessein : `statut=body.statut_souhaite` ou
    `actif=body.consentement_rgpd` restent des lectures, parce qu'ils décident de
    quelque chose au lieu de recopier.

    Rend les `id()` des nœuds à ignorer — l'AST n'étant pas hachable par valeur.
    """
    a_ignorer: set[int] = set()
    for noeud in ast.walk(arbre):
        for mot_cle in getattr(noeud, "keywords", []):
            valeur = mot_cle.value
            if (
                mot_cle.arg
                and isinstance(valeur, ast.Attribute)
                and valeur.attr == mot_cle.arg
            ):
                a_ignorer.add(id(valeur))
    return a_ignorer


def _noms_lus() -> set[str]:
    """Les attributs LUS quelque part dans `app/`, hors déclaration du modèle.

    Deux sources, et rien d'autre :

    1. `ast.Attribute` en contexte `Load` — `if user.actif`, `select(...).where(
       Utilisateur.email == …)`, `f"{u.prenom}"`. L'écriture (`Store`) et
       l'argument nommé (`Champ(x=…)`, qui est un `keyword`, pas un `Attribute`)
       n'y figurent pas ;
    2. les champs déclarés dans une classe dont le nom finit par `Read` : le
       schéma de sortie est le chemin par lequel le front lit la donnée.
    """
    lus: set[str] = set()
    for fichier in APP.rglob("*.py"):
        if fichier == MODELE:
            continue
        try:
            arbre = ast.parse(fichier.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:  # pragma: no cover — un fichier cassé se voit ailleurs
            continue
        transports = _transports(arbre)
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Attribute) and isinstance(noeud.ctx, ast.Load):
                if id(noeud) not in transports:
                    lus.add(noeud.attr)
            elif isinstance(noeud, ast.ClassDef) and noeud.name.endswith("Read"):
                for element in noeud.body:
                    if isinstance(element, ast.AnnAssign) and isinstance(element.target, ast.Name):
                        lus.add(element.target.id)
    return lus


def _jamais_lues() -> set[str]:
    lus = _noms_lus()
    return {
        colonne
        for colonne in _colonnes_utilisateur()
        if colonne not in HORS_SUJET and colonne not in lus
    }


def test_aucune_colonne_ecrite_puis_oubliee():
    """Une donnée qu'on demande à quelqu'un doit servir à quelque chose."""
    orphelines = _jamais_lues() - set(DETTES)
    assert not orphelines, (
        "Colonne(s) de `Utilisateur` écrite(s) et jamais lue(s) : "
        f"{sorted(orphelines)}.\n"
        "  Une donnée recueillie et inutilisée est au mieux du bruit, au pire un\n"
        "  consentement qu'on ne peut pas retirer (RGPD art. 7.3, `standards/14`).\n"
        "  La brancher, la retirer — ou la déclarer dans DETTES avec son ticket."
    )


def test_aucune_dette_ne_survit_a_son_objet():
    """Une dette qui ne sert plus fait croire la règle plus poreuse qu'elle ne l'est."""
    inutiles = sorted(set(DETTES) - _jamais_lues())
    assert not inutiles, (
        f"Dette(s) devenue(s) inutile(s), à retirer de DETTES : {inutiles}.\n"
        "  Ces colonnes sont désormais lues : le défaut est corrigé, la\n"
        "  déclaration doit partir avec lui."
    )


def test_le_controle_regarde_bien_quelque_chose():
    """Cas zéro — `standards/04` §2 : un relevé vide n'est pas un vert.

    Si l'extraction des colonnes échouait, les deux tests ci-dessus passeraient
    en ne mesurant rien.
    """
    colonnes = _colonnes_utilisateur()
    assert len(colonnes) > 20, f"seulement {len(colonnes)} colonne(s) trouvée(s) — extraction cassée"
    #  Deux colonnes témoins, choisies parce qu'elles ne disparaîtront pas : le
    #  cas zéro doit échouer si l'extraction casse, et il ne peut pas s'appuyer
    #  sur une colonne qu'un lot supprimera — c'est ce qui vient d'arriver à
    #  `consentement_communications`, qui servait ici de témoin (10/09/2026).
    assert "email" in colonnes
    assert "etage" in colonnes


def test_le_controle_sait_REFUSER():
    """Cas zéro, seconde moitié : un contrôle qui ne peut pas échouer ne mesure rien.

    Si `_noms_lus()` rendait tout — un `walk` trop large, une exception avalée —
    aucune colonne ne serait jamais orpheline et les deux tests ci-dessus
    passeraient éternellement. On vérifie donc les deux bords :

    * un nom qui n'existe nulle part **n'est pas** compté comme lu ;
    * des colonnes manifestement lues **le sont**.
    """
    lus = _noms_lus()
    assert "colonne_qui_n_existe_pas_dans_ce_depot" not in lus
    for temoin in ("actif", "email", "statut", "photo_url"):
        assert temoin in lus, f"`{temoin}` est lu partout et le contrôle ne le voit pas"
