"""Un constat propre à UN nœud nomme ce nœud — sinon il disparaît de sa carte.

## Pourquoi (27/09/2026, #1396)

Chaque nœud audite les deux, et l'écran « Contrôles de fiabilité » range chaque
constat une seule fois (`portee_constat`, `scripts/lib/lib-notification.sh`) :

- un constat qui nomme **un seul** nœud s'affiche sous ce nœud ;
- un constat qui n'en nomme **aucun** est dit « commun » — site, split-brain,
  tunnel — et seul l'**actif** le porte.

Arbitrage de Philippe : *un constat propre à un RPi reste affiché sous ce RPi*.
La règle tient tant que le message NOMME son nœud. Un contrôle par nœud qui
écrirait « Disque à 81 % » au lieu de « Disque $n à 81 % » serait lu comme
commun : sur le standby, il ne serait plus affiché nulle part, sans un mot.

## Ce que ce test vérifie

Dans chaque boucle qui parcourt les deux nœuds — `for n in "$SELF" "$PEER"` ou
`for pair in "$SELF:…" "$PEER:…"` suivi de `n=${pair%%:*}` —, chaque `warn` et
chaque `fail` cite la variable du nœud. Il n'a rien à dire des constats hors
boucle : ceux-là portent sur les deux nœuds, ou nomment le leur explicitement.
"""

import re

from tests.conftest import scripts_shell_versionnes

FICHIERS = scripts_shell_versionnes()

_BOUCLE_NOEUDS = re.compile(r'^\s*for\s+(\w+)\s+in\s+"\$SELF[":].*"\$PEER[":]')
_EXTRAIT_NOEUD = re.compile(r"(\w+)=\$\{(\w+)%%?:\*\}")
_OUVRE = re.compile(r"^\s*(for|while|until)\b.*;\s*do\b|^\s*(for|while|until)\b[^#]*$")
_FERME = re.compile(r"^\s*done\b")
_CONSTAT = re.compile(r'\b(warn|fail)\s+"')


def constats_anonymes(texte: str, nom: str = "?") -> tuple[int, list[str]]:
    """→ (nombre de boucles par nœud lues, lignes `warn`/`fail` qui ne nomment pas le nœud)."""
    lignes = texte.splitlines()
    boucles, fautes = 0, []
    i = 0
    while i < len(lignes):
        m = _BOUCLE_NOEUDS.match(lignes[i])
        if not m:
            i += 1
            continue
        boucles += 1
        variables = {m.group(1)}
        profondeur, j = 1, i + 1
        while j < len(lignes) and profondeur:
            ligne = lignes[j]
            if _FERME.match(ligne):
                profondeur -= 1
            elif _OUVRE.match(ligne):
                profondeur += 1
            for extrait in _EXTRAIT_NOEUD.finditer(ligne):
                if extrait.group(2) in variables:
                    variables.add(extrait.group(1))
            if _CONSTAT.search(ligne) and not any(
                re.search(r"\$\{?" + v + r"\b", ligne) for v in variables
            ):
                fautes.append(f"{nom}:{j + 1}: {ligne.strip()[:120]}")
            j += 1
        i = j
    return boucles, fautes


def test_chaque_constat_par_noeud_nomme_son_noeud():
    total, fautes = 0, []
    for chemin in FICHIERS:
        n, f = constats_anonymes(chemin.read_text(encoding="utf-8"), chemin.name)
        total += n
        fautes += f
    # Cas zéro : un motif qui ne trouverait plus aucune boucle rendrait ce test
    # vert sans rien avoir lu (standards/04 §2). Il y en a une dizaine le 27/09.
    assert total >= 8, (
        f"seulement {total} boucle(s) par nœud trouvée(s) — le motif ne lit plus les scripts"
    )
    assert not fautes, (
        "Constat par nœud qui ne nomme pas son nœud — il serait lu comme commun, "
        "et disparaîtrait de la carte du standby (#1396) :\n" + "\n".join(fautes)
    )


def test_le_controle_refuse_un_constat_anonyme():
    """La faute injectée est vue — sinon le test ci-dessus ne prouverait rien."""
    fautif = (
        'for pair in "$SELF:${S_disk:-0}" "$PEER:${P_disk:-0}"; do\n'
        "  n=${pair%:*}; d=${pair#*:}\n"
        '  if [ "$d" -ge 90 ]; then fail "Disque $n à ${d}%"\n'
        '  else warn "Disque à ${d}%"; fi\n'
        "done\n"
        'warn "Site public KO"\n'
    )
    boucles, fautes = constats_anonymes(fautif)
    assert boucles == 1
    assert len(fautes) == 1 and 'warn "Disque à' in fautes[0]

    direct = 'for n in "$SELF" "$PEER"; do\n  warn "Noyau INCONNU"\n  ok "rien"\ndone\n'
    assert len(constats_anonymes(direct)[1]) == 1
