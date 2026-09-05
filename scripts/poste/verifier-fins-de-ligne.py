#!/usr/bin/env python3
"""Refuse un commit qui convertit les fins de ligne d'un fichier sans le vouloir.

## Pourquoi (20/08/2026 — QUATRIÈME récidive)

`standards/10-encodage-et-fichiers.md` décrit cette faute avec l'appel exact qui
la produit, et se termine par : *« Ce qui manque n'est pas une phrase de plus,
c'est un contrôle. »* Ce fichier est ce contrôle.

Le 19-20/08, trois fichiers (`mon-lot`, `tickets`, `acces-securite`) sont passés
de CRLF à LF pendant des lots qui ne changeaient que quelques lignes. La pull
request annonçait **2 998 ajouts et 2 743 suppressions** pour quinze fichiers,
là où le changement réel tenait en une dizaine de lignes. C'est l'utilisateur
qui l'a vu, sur la page de comparaison de GitHub, juste avant de fusionner.

⚠️ **La parade prescrite existait déjà et n'a pas suffi.** `git diff --stat`
avant le commit était appliqué en début de soirée, puis a cessé de l'être au fil
des lots. Un contrôle manuel s'érode ; c'est exactement pourquoi le socle en
réclamait un automatique.

## Ce qu'il mesure — le FAIT, pas la forme

Pas « le fichier a-t-il changé de fins de ligne ? » : un lot de normalisation
assumé est légitime. Il compare deux nombres :

  - le changement **apparent**  : lignes que git verra comme modifiées ;
  - le changement **réel**      : lignes qui diffèrent une fois les deux versions
                                  normalisées en LF.

Quand l'apparent dépasse largement le réel, le diff est gonflé par des
terminaisons, et personne ne pourra plus le relire. C'est le seul critère qui
distingue « j'ai converti sans le vouloir » de « j'ai beaucoup modifié ».

Contournement pour un lot de normalisation voulu : ALLOW_EOL=1 git commit ...

Test : python scripts/poste/verifier-fins-de-ligne.py --selftest
"""
import os
import subprocess
import sys
from pathlib import Path

#  La console de ce poste est en cp1252 : le POURQUOI vit dans `lib_console`,
#  qui porte ces lignes pour tous les contrôles du poste (06/09/2026).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_console import console_utf8  # noqa: E402

console_utf8()

#  Un diff peut légitimement dépasser le réel de quelques lignes (une ligne
#  ajoutée en fin de fichier sans saut final, par exemple). En dessous de ce
#  seuil ABSOLU on ne dit rien : un contrôle qui crie sur trois lignes est
#  désarmé dans la semaine.
ECART_TOLERE = 20
#  … et il faut aussi que l'apparent soit disproportionné, pas seulement plus
#  grand : un lot qui change 400 lignes et en voit 425 n'a rien de suspect.
FACTEUR = 3


def lignes_differentes(avant: bytes, apres: bytes) -> int:
    """Nombre de lignes qui diffèrent entre deux contenus, sans rien normaliser."""
    import difflib

    a = avant.split(b"\n")
    b = apres.split(b"\n")
    n = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal":
            n += (i2 - i1) + (j2 - j1)
    return n


def normaliser(contenu: bytes) -> bytes:
    """CRLF et CR isolés ramenés à LF — la seule façon de comparer le FOND."""
    return contenu.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def verdict(avant: bytes, apres: bytes):
    """(suspect, apparent, reel). Fonction PURE : éprouvable sans dépôt."""
    if b"\x00" in avant or b"\x00" in apres:
        return False, 0, 0  # binaire : hors sujet
    apparent = lignes_differentes(avant, apres)
    reel = lignes_differentes(normaliser(avant), normaliser(apres))
    suspect = apparent - reel > ECART_TOLERE and apparent > FACTEUR * max(reel, 1)
    return suspect, apparent, reel


def _selftest() -> int:
    st = 0

    def t(libelle, attendu, avant, apres):
        nonlocal st
        obtenu = verdict(avant, apres)[0]
        if obtenu == attendu:
            print(f"PASS  {libelle}")
        else:
            print(f"FAIL  {libelle}  attendu={attendu} obtenu={obtenu}")
            st = 1

    gros_crlf = b"\r\n".join(b"ligne %d" % i for i in range(200))
    gros_lf = gros_crlf.replace(b"\r\n", b"\n")

    #  Le cas du 20/08 : conversion massive, une seule ligne changée au fond.
    modifie = gros_lf.replace(b"ligne 5", b"ligne CINQ")
    t("CRLF -> LF sur tout le fichier, 1 ligne changée", True, gros_crlf, modifie)
    #  … et le sens inverse, tout aussi illisible.
    t("LF -> CRLF sur tout le fichier", True, gros_lf, gros_crlf.replace(b"ligne 5", b"ligne CINQ"))
    #  Un vrai changement, même gros, ne doit RIEN déclencher.
    autre = b"\r\n".join(b"autre %d" % i for i in range(200))
    t("gros changement de fond, fins de ligne intactes", False, gros_crlf, autre)
    #  Un petit changement ordinaire.
    t("petit changement ordinaire", False, gros_crlf, gros_crlf.replace(b"ligne 5", b"ligne CINQ"))
    #  Fichier identique.
    t("aucun changement", False, gros_crlf, gros_crlf)
    #  Fichier court : sous le seuil absolu, on se tait (pas de faux positif).
    court_crlf = b"a\r\nb\r\nc\r\n"
    t("fichier de 3 lignes converti (sous le seuil)", False, court_crlf, b"a\nb\nc\n")
    #  Binaire : hors sujet, jamais d'alerte.
    t("contenu binaire", False, b"\x00\x01\x02", b"\x00\x03\x04")
    #  Nouveau fichier (avant vide) : rien à comparer.
    t("nouveau fichier", False, b"", gros_lf)

    print("\n✓ Autotest : la conversion massive est refusée dans les deux sens,"
          if st == 0 else "\n✗ Autotest en échec")
    if st == 0:
        print("  et un vrai changement, même gros, passe.")
    return st


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    if os.environ.get("ALLOW_EOL"):
        return 0

    #  Seuls les fichiers MODIFIÉS : un fichier neuf n'a pas de « avant ».
    sortie = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=M"],
        capture_output=True, text=True,
    ).stdout
    coupables = []
    for chemin in [c for c in sortie.split("\n") if c.strip()]:
        avant = subprocess.run(["git", "show", f"HEAD:{chemin}"], capture_output=True).stdout
        apres = subprocess.run(["git", "show", f":{chemin}"], capture_output=True).stdout
        if not avant:
            continue
        suspect, apparent, reel = verdict(avant, apres)
        if suspect:
            coupables.append((chemin, apparent, reel))

    if not coupables:
        return 0

    print("", file=sys.stderr)
    print("✗ Commit refusé : des fins de ligne ont été converties sans que le", file=sys.stderr)
    print("  contenu le justifie.", file=sys.stderr)
    print("", file=sys.stderr)
    for chemin, apparent, reel in coupables:
        print(f"  {chemin}", file=sys.stderr)
        print(f"      le diff montrera ~{apparent} lignes, alors que {reel} seulement", file=sys.stderr)
        print("      changent vraiment.", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Un diff gonflé par des terminaisons n'est plus relisible : la revue", file=sys.stderr)
    print("  passe à côté du changement réel. Vu QUATRE fois sur ce dépôt.", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Réparer : relire et réécrire le fichier en OCTETS", file=sys.stderr)
    print("  (`read_bytes()` / `write_bytes()`), jamais en texte —", file=sys.stderr)
    print("  `standards/10-encodage-et-fichiers.md`.", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Si la normalisation est VOULUE : ALLOW_EOL=1 git commit ...", file=sys.stderr)
    print("", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
