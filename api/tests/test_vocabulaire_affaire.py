"""Le mot que l'utilisateur lit est « affaire », plus jamais « ticket ».

## La décision (#1094, chantier v2.0.0)

« Ticket » dit l'**outil**, pas la chose. Le chantier v2.0.0 ramène trois objets à
deux — **Actualité** et **Affaire** —, et le mot d'écran suit : une affaire est
une information qu'on suit jusqu'à sa résolution.

Le renommage porte sur ce que l'utilisateur **lit**, et sur rien d'autre.

## 🔴 Ce qui ne bouge PAS, et pourquoi

| | Raison |
|---|---|
| la route `/tickets` | elle est dans des courriels **déjà envoyés**, et un lien mort est pire qu'un mot vieilli |
| les identifiants `TK-xxxx` | dans des boîtes mail depuis des mois ; `courriel_entrant.py` s'en sert pour rattacher les réponses du syndic |
| les noms de code (`Ticket`, `ticket_syndic`, `{{ ticket.id }}`) | ce sont des identifiants, pas des libellés — les renommer ferait un lot de 7 000 lignes sans rien changer à ce qui se lit |

C'est la même distinction que pour `TicketEvolution` / « Suite » : le modèle garde
son nom, l'écran parle français.

## Ce que ce contrôle lit

Les **sources de texte servi** — ce qu'un résident a sous les yeux :

- `front/src/lib/pages.ts` — nom, titre, libellé de navigation, descriptif ;
- `api/app/seed/faq.py` — les questions et les réponses ;
- `api/app/seed/emails/` — les sujets et les corps des courriels ;
- `README.md` et `docs/manuel-utilisateur.html`.

⚠️ Il ne lit PAS les écrans `.svelte` : le mot y apparaît des deux façons, en
libellé et en identifiant, sur la même ligne (`{#each tickets as ticket}` sous un
titre « Mes tickets »), et aucun motif ne les sépare sans se tromper
(`standards/04` §12 — un contrôle borné dit ce qu'il ne couvre pas). Ce qui
protège ces fichiers-là, c'est `lint:etats` et la relecture, pas ce test.
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

#: Les fichiers dont chaque mot est lu par un résident.
SOURCES = (
    "front/src/lib/pages.ts",
    "api/app/seed/faq.py",
    "README.md",
    "docs/manuel-utilisateur.html",
    #  🔴 Les MODÈLES D'E-MAIL (#1101, 22/09/2026). Ils sont lus par les
    #  résidents comme le reste, et ils étaient restés au mot du modèle — le
    #  lot de renommage s'était arrêté aux écrans, à la FAQ et à la
    #  documentation, parce que les courriels sont un circuit à part.
    "api/app/seed/emails/tickets.py",
    "api/app/seed/emails/__init__.py",
    "api/app/seed/emails/fragments.py",
    "api/app/seed/emails/vie_collective.py",
    "api/app/seed/emails/exploitation.py",
)

#: Ce qui porte le mot sans que personne ne le lise — un identifiant, un chemin,
#: une variable de gabarit. Éprouvé sur le dépôt le 21/09/2026.
#:
#: 🔴 `(?-i: … )` sur les noms de types, et ce n'est pas un détail : sous
#: `re.IGNORECASE`, la classe `[A-Z]` accepte aussi les minuscules, et
#: `Ticket[A-Z]` avalait donc « Tickets » — le libellé du menu, celui que
#: l'utilisateur voit. Le contrôle passait au vert sans avoir rien lu de
#: `pages.ts` (mesuré le 21/09/2026, `standards/04` §2).
IDENTIFIANTS = re.compile(
    r"""
      /tickets                 # la route, figée : elle est dans des courriels envoyés
    | tickets\+                # l'adresse à jeton
    | ticket[_.]               # ticket_syndic, ticket.id, ticket_id…
    | _ticket                  # _bouton_ticket, meta_ticket…
    | (?-i:Ticket[A-Z])        # TicketCreate, TicketEvolution — casse EXACTE
    | \bTK-                    # les identifiants d'affaires
    | --c-ticket               # une variable CSS du manuel
    | data-section="tickets"   # un sélecteur CSS du manuel
    | CHIPS\ \(tickets\)       # le commentaire qui nomme ce sélecteur
    | in\ tickets             # la variable de boucle Jinja de la relance
    | emails\.tickets         # le MODULE des modèles de courriel
    | _TICKETS                # la constante qu'il exporte
    """,
    re.VERBOSE | re.IGNORECASE,
)

MOT = re.compile(r"[Tt]ickets?\b")


def _sans_commentaires(source: str) -> str:
    """Le code SERVI, sans ce qui n'en sort jamais (#1101, 22/09/2026).

    🔴 Les modèles d'e-mail parlent du « circuit des tickets » dans leurs
    docstrings, nomment `_bouton_ticket`, et documentent `ticket.id`. Rien de
    tout cela n'est lu par un résident : ce sont des commentaires de code, et
    le mot du modèle y est à sa place — le fichier s'appelle `tickets.py`, la
    table `ticket`, le code de modèle `ticket_syndic`.

    Sans cette neutralisation, le contrôle criait sur dix-huit commentaires
    parfaitement légitimes. Un contrôle qui crie sur du légitime finit
    désarmé (leçon de C16, déjà écrite dans ce dépôt).

    ⚠️ Les docstrings partent aussi : elles sont du commentaire pour qui lit
    le code, jamais du texte servi. Ce qui reste est ce qu'un gabarit peut
    rendre.
    """
    sortie = []
    dans_docstring = None
    for ligne in source.splitlines():
        reste = ligne
        if dans_docstring:
            if dans_docstring in reste:
                reste = reste.split(dans_docstring, 1)[1]
                dans_docstring = None
            else:
                sortie.append("")
                continue
        #  Une docstring qui s'ouvre et ne se referme pas sur la même ligne.
        for guillemets in ('"""', "'''"):
            if reste.count(guillemets) % 2 == 1:
                reste = reste.split(guillemets, 1)[0]
                dans_docstring = guillemets
                break
        #  Un `#` hors chaîne : la heuristique suffit ici — les chaînes de ces
        #  fichiers sont du HTML, et un `#` y est toujours précédé d'un `"` ou
        #  d'une couleur (`#c0392b`), jamais seul en début de mot.
        if "#" in reste:
            avant, _, apres = reste.partition("#")
            if avant.count('"') % 2 == 0 and avant.count("'") % 2 == 0 and not apres[:1].isalnum():
                reste = avant
        sortie.append(reste)
    return chr(10).join(sortie)


def _fautes(chemin: str) -> list[str]:
    fichier = RACINE / chemin
    if not fichier.exists():
        return [f"{chemin} : fichier introuvable — le contrôle ne mesure plus rien"]
    fautes = []
    lisible = _sans_commentaires(fichier.read_text(encoding="utf-8"))
    for n, ligne in enumerate(lisible.splitlines(), 1):
        #  On retire d'abord tout ce qui est un identifiant, PUIS on cherche le
        #  mot : l'inverse ferait passer « /tickets » pour un libellé.
        reste = IDENTIFIANTS.sub("", ligne)
        if MOT.search(reste):
            fautes.append(f"{chemin}:{n} — {ligne.strip()[:110]}")
    return fautes


def test_aucun_ticket_dans_les_textes_servis():
    fautes = [f for chemin in SOURCES for f in _fautes(chemin)]
    assert not fautes, (
        f"{len(fautes)} occurrence(s) de « ticket » dans un texte lu par un résident :\n"
        + "\n".join(f"  {f}" for f in fautes)
        + "\n\nLe mot d'écran est **affaire** (#1094). Les identifiants, les routes "
        "et les numéros TK ne bougent pas — le motif `IDENTIFIANTS` les laisse passer."
    )


def test_le_controle_lit_bien_quelque_chose():
    """Cas zéro : un chemin faux rendrait le test précédent vert sans rien lire.

    C'est arrivé ailleurs dans ce dépôt — un contrôle dont la portée n'incluait
    pas le bon répertoire, et qui affichait OK (`standards/04` §2).
    """
    for chemin in SOURCES:
        fichier = RACINE / chemin
        assert fichier.exists(), f"{chemin} introuvable : le contrôle ne lit rien"
        assert fichier.stat().st_size > 200, f"{chemin} est quasi vide"


def test_les_identifiants_sont_bien_epargnes():
    """Le motif d'exception doit laisser passer ce qui ne se lit pas.

    Sans ce test, on pourrait durcir `IDENTIFIANTS` jusqu'à ce qu'il n'épargne
    plus rien, et le contrôle exigerait alors de renommer la route `/tickets` —
    ce qui casserait les liens des courriels déjà partis.
    """
    epargnes = [
        "{{ app.url }}/tickets/{{ ticket.id }}",
        "tickets+{{ jeton }}@5hostachy.fr",
        "def _bouton_ticket(libelle: str) -> str:",
        "class TicketEvolution(EvolutionMixin, table=True):",
        "L'affaire TK-417640 est close.",
    ]
    for ligne in epargnes:
        assert not MOT.search(IDENTIFIANTS.sub("", ligne)), (
            f"« {ligne} » est refusé alors qu'aucun résident ne lit ce mot-là."
        )


def test_le_motif_ne_mange_pas_les_libelles():
    """L'autre sens, et c'est celui qui a mordu.

    `Ticket[A-Z]` sous `re.IGNORECASE` acceptait « Tickets » : le libellé du
    menu passait pour un nom de type, et `pages.ts` n'était pas lu du tout. Un
    motif d'exception trop large ne fait pas de bruit — il rend muet.
    """
    lus_par_un_resident = [
        "\t\tnom: 'Tickets',",
        "\t\ttitre: 'Mes Tickets',",
        "Suivez l'avancement de vos tickets.",
        "Les tickets résolus passent dans les Archives.",
    ]
    for ligne in lus_par_un_resident:
        assert MOT.search(IDENTIFIANTS.sub("", ligne)), (
            f"« {ligne} » passe au travers : le motif d'exception est trop large, "
            f"et le contrôle est muet là où il devrait parler."
        )
