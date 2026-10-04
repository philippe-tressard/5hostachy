"""Le `Caddyfile` versionné est dans la forme de `caddy fmt` (#1612, 04/10/2026).

## Pourquoi

Caddy relit son fichier à chaque démarrage et journalise, sinon :
« Caddyfile input is not formatted ». Le fichier était indenté par quatre
espaces : l'avertissement revenait à chaque redémarrage de `hostachy_caddy`,
et un avertissement permanent apprend à ne plus lire le journal où il
s'écrit.

## Ce que ce test juge — et ce qu'il ne juge pas

L'arbitre est `caddy fmt` lui-même. Le poste n'a ni Caddy ni Docker : une
étape de CI qui l'appellerait rendrait INCONNU à chaque rejeu local
(`scripts/poste/rejouer-ci.sh`), donc au point 16 de chaque pré-check — un
contrôle qui crie à chaque fois finit contourné.

Ce test tient donc la seule règle que le fichier ait jamais enfreinte : une
**tabulation par niveau d'accolade**, rien d'autre en tête de ligne, aucun
blanc en fin de ligne. Le 04/10/2026, la version ainsi indentée a été passée
au `caddy fmt --diff -` de production (v2.11.6, conteneur `hostachy_caddy`) :
code 0, aucun écart. Une autre règle de `caddy fmt` enfreinte un jour se
lirait de nouveau dans ce journal — c'est là qu'il faut regarder.
"""

from __future__ import annotations

from tests.aides_caddy import caddyfile


def _ecarts(texte: str) -> list[str]:
    """Les lignes dont l'indentation n'est pas celle de `caddy fmt`. (PURE)

    Un bloc s'ouvre par une ligne qui FINIT par `{` et se ferme par une ligne
    qui COMMENCE par `}` ; une accolade au milieu d'une ligne est un
    paramètre (`{client_ip}`), pas un bloc. Un commentaire s'indente comme
    son voisin et n'ouvre rien.
    """
    ecarts: list[str] = []
    profondeur = 0
    for numero, ligne in enumerate(texte.split("\n"), start=1):
        if "\r" in ligne:
            ecarts.append(f"ligne {numero} : fin de ligne CRLF (.editorconfig : LF)")
            ligne = ligne.rstrip("\r")
        nue = ligne.strip()
        if ligne != ligne.rstrip():
            ecarts.append(f"ligne {numero} : blanc en fin de ligne")
        if not nue:
            continue
        if nue.startswith("}"):
            profondeur -= 1
        attendue = "\t" * profondeur
        tete = ligne[: len(ligne) - len(ligne.lstrip())]
        if tete != attendue:
            ecarts.append(
                f"ligne {numero} : indentation {tete!r}, attendu {profondeur} tabulation(s)"
            )
        if not nue.startswith("#") and nue.endswith("{"):
            profondeur += 1
    if profondeur != 0:
        ecarts.append(f"accolades déséquilibrées en fin de fichier ({profondeur:+d})")
    return ecarts


def test_le_caddyfile_est_dans_la_forme_de_caddy_fmt():
    texte = caddyfile()
    #  Cas zéro : un fichier sans bloc passerait sans rien mesurer.
    assert texte.count("{\n") >= 5, "Caddyfile sans bloc — rien n'a été mesuré"
    ecarts = _ecarts(texte)
    assert not ecarts, (
        "Le Caddyfile n'est pas dans la forme de `caddy fmt` — Caddy le "
        "journalise à chaque démarrage :\n  " + "\n  ".join(ecarts[:10])
    )


def test_le_controle_refuse_ce_qu_il_doit_refuser():
    """Le défaut d'origine, et ses voisins : un contrôle vert qui ne refuse rien ment."""
    assert _ecarts("a {\n\tb\n}\n") == []
    assert _ecarts("a {\n\theader X {client_ip}\n\t# commentaire {\n}\n") == []
    assert _ecarts("a {\n    b\n}\n"), "quatre espaces : la forme d'avant #1612"
    assert _ecarts("a {\n\t\tb\n}\n"), "une tabulation de trop"
    assert _ecarts("a {\n\tb \n}\n"), "blanc en fin de ligne"
    assert _ecarts("a {\r\n\tb\r\n}\r\n"), "CRLF"
    assert _ecarts("a {\n\tb\n"), "bloc jamais fermé"
