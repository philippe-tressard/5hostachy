"""Le manuel ne promet pas autre chose que ce que l'application fait.

## Le vrai sujet de #651

Le manuel **recopie des tables que le code fait évoluer**, et rien ne les
rapproche. Le lot du 30/08/2026 a corrigé quatre écarts d'un coup :

| Le manuel disait | La réalité |
|---|---|
| « 5 photos / 5 documents » | `MAX_FICHIERS = 10` depuis le 16/08 — deux semaines |
| « 15 Mo maximum par fichier » | 5 Mo pour une photo, 15 Mo pour un document |
| « PDF, Word ou Excel » | le texte (`.txt`) est accepté aussi |
| cinq descriptions de catégories | les cinq avaient divergé de `CATEGORIES_TICKET` |

C'est le motif que ce dépôt a déjà traité **quatre fois** — périmètres (#316),
canaux de notification, libellés de tâches, table des pages (#401). À chaque
fois la même conclusion : *une table recopiée finit par diverger, et deux listes
d'accord entre elles ne prouvent rien.*

⚠️ `npm run lint:pages` existe déjà et refuse qu'une table de pages soit
recopiée — mais **sa portée est le code**. Le manuel cite les mêmes valeurs en
prose, hors de portée : le contrôle est vert et le manuel dérive. C'est la
portée qui manquait, pas le contrôle (`standards/05` §9).

## Ce que ce test peut, et ce qu'il ne peut pas

Il vérifie les **chiffres et les listes**, qui ont une source unique et qui se
lisent mécaniquement. Il ne dit rien des **captures d'écran** ni de la prose :
elles restent le gros morceau de #651, et aucun test ne les tiendra.

🔴 Il regarde **les deux copies** du manuel — `docs/` et `front/static/`. La
synchronisation est vérifiée ailleurs, mais un contrôle qui ne lirait que la
source croirait sur parole que la copie lui ressemble ; et c'est la copie que
les résidents ouvrent.
"""
from __future__ import annotations

import re
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
_MANUELS = [
    _RACINE / "docs" / "manuel-utilisateur.html",
    _RACINE / "front" / "static" / "manuel-utilisateur.html",
]


def _valeur_js(fichier: Path, nom: str) -> int:
    """La constante `export const <nom> = <n>;` d'un module TypeScript."""
    m = re.search(rf"\b{nom}\s*=\s*(\d+)", fichier.read_text(encoding="utf-8"))
    assert m, f"{nom} est introuvable dans {fichier.name} — la source a bougé."
    return int(m.group(1))


def _valeur_py(fichier: Path, nom: str) -> int:
    m = re.search(rf"^{nom}\s*=\s*(\d+)", fichier.read_text(encoding="utf-8"), re.M)
    assert m, f"{nom} est introuvable dans {fichier.name} — la source a bougé."
    return int(m.group(1))


def _textes() -> list[tuple[str, str]]:
    """Le texte VISIBLE de chaque manuel — balises retirées, accents gardés."""
    sortie = []
    for chemin in _MANUELS:
        brut = chemin.read_text(encoding="utf-8")
        #  Le `<style>` et le `<script>` ne sont pas lus par un résident : y
        #  chercher des chiffres ferait crier sur des tailles de police.
        sans_tete = re.sub(r"<(style|script)\b.*?</\1>", " ", brut, flags=re.S | re.I)
        sortie.append((chemin.name, re.sub(r"<[^>]+>", " ", sans_tete)))
    return sortie


def test_les_deux_manuels_sont_lisibles():
    """Cas zéro : sans texte, tous les tests plus bas passeraient à vide."""
    for nom, texte in _textes():
        assert len(texte) > 5000, (
            f"{nom} rend {len(texte)} caractère(s) de texte visible — le "
            "retrait des balises ne mord plus. Ne pas lire ceci comme un succès."
        )


def test_le_nombre_de_pieces_jointes_annonce_est_le_bon():
    """« 10 photos », « 10 documents » — et jamais un autre chiffre.

    Le manuel a promis 5 pendant deux semaines là où l'application en acceptait
    10 : un résident renonçait à joindre ce qu'il avait le droit de joindre.
    """
    maxi = _valeur_js(_RACINE / "front" / "src" / "lib" / "fichiers.ts", "MAX_FICHIERS")
    #  ⚠️ SEULE la formule qui énonce un PLAFOND est regardée — « jusqu'à N ».
    #  Le premier jet cherchait tout nombre suivi de « photos », et il criait sur
    #  « vous pouvez y ajouter 1 ou 2 photos », qui est un conseil de rédaction.
    #  Un contrôle qui crie sur du légitime finit désarmé (leçon de C16).
    plafond = re.compile(r"jusqu'à\s+(\d+)\s+(photos|documents)\b")
    for nom, texte in _textes():
        cites = plafond.findall(texte)
        assert cites, (
            f"{nom} n'énonce plus aucun plafond de pièces jointes (« jusqu'à N "
            "photos »). Soit la rubrique a disparu, soit le motif ne correspond "
            "plus — ne pas lire ceci comme un succès."
        )
        mauvais = [(n, mot) for n, mot in cites if n != str(maxi)]
        assert not mauvais, (
            f"{nom} annonce « jusqu'à {mauvais[0][0]} {mauvais[0][1]} » alors que "
            f"MAX_FICHIERS vaut {maxi}. Le manuel promet autre chose que "
            "l'application."
        )


def test_les_tailles_annoncees_sont_celles_du_serveur():
    """5 Mo pour une photo, 15 Mo pour un document — et rien d'autre.

    ⚠️ Les deux plafonds sont DIFFÉRENTS, et c'est ce qui rend l'écart discret :
    « 15 Mo maximum par fichier » est vrai d'un document et faux d'une photo. Le
    test n'exige donc pas un chiffre unique — il refuse tout chiffre qui ne soit
    ni l'un ni l'autre.
    """
    uploads = _RACINE / "api" / "app" / "routers" / "uploads.py"
    admis = {str(_valeur_py(uploads, "MAX_SIZE_MB")), str(_valeur_py(uploads, "MAX_DOC_SIZE_MB"))}
    for nom, texte in _textes():
        cites = set(re.findall(r"(\d+)\s*Mo\b", texte, re.I))
        etrangers = cites - admis
        assert not etrangers, (
            f"{nom} cite {sorted(etrangers)} Mo, alors que le serveur applique "
            f"{sorted(admis)} Mo. Un résident se verra refuser ce que le manuel "
            "lui promet."
        )
        #  Cas zéro : si plus aucune taille n'est citée, le test ne mesure rien.
        assert cites, (
            f"{nom} ne cite plus aucune taille en Mo — soit la rubrique a "
            "disparu, soit le motif ne correspond plus."
        )


def test_les_categories_de_ticket_sont_celles_du_code():
    """Les cinq libellés de `CATEGORIES_TICKET`, mot pour mot.

    Ils avaient divergé tous les cinq. La copie la plus consultée est celle qui
    trompe le plus longtemps.
    """
    source = (_RACINE / "front" / "src" / "lib" / "tickets.ts").read_text(encoding="utf-8")
    debut = source.index("export const CATEGORIES_TICKET")
    bloc = source[debut : source.index("];", debut)]
    libelles = re.findall(r"label:\s*'([^']+)'", bloc)
    assert len(libelles) >= 5, (
        f"{len(libelles)} catégorie(s) lue(s) dans tickets.ts — le motif ne "
        "correspond plus à la table. Ne pas lire ceci comme un succès."
    )
    for nom, texte in _textes():
        manquants = [lib for lib in libelles if lib not in texte]
        assert not manquants, (
            f"{nom} ne cite pas les catégories {manquants}, qui existent dans "
            "l'application. Le manuel décrit un écran qui n'est plus celui-là."
        )
