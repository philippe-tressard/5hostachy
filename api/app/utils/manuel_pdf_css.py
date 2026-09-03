"""Feuille de style du manuel imprimable — extraite au fil de l'eau.

Même geste que `fiche_arrivant_css.py`, et pour la même raison : `manuel_pdf.py`
a franchi les 500 lignes du plafond de modularité (rang 1 §4) en gagnant les deux
colonnes et le sommaire paginé.

La feuille de style est ce qui s'en détache le plus proprement — elle n'a aucune
logique, et elle change pour des raisons qui ne sont pas celles du document : une
retouche de charte n'est pas un changement de contenu.

⚠️ Elle reprend la feuille de l'ÉCRAN et n'en redéfinit que ce que l'impression
impose. Redessiner ici les cartes et les couleurs du manuel créerait une seconde
charte, qui dériverait à la première retouche de l'écran.
"""
from __future__ import annotations

from app.utils.pdf_theme import FONT_SANS, FONT_SERIF, PALETTE_CSS


def css_du_pdf(styles_manuel: str) -> str:
    """Le CSS du PDF : celui du manuel, plus ce que l'impression exige."""
    return f"""
{PALETTE_CSS}
{styles_manuel}

@page {{
  size: A4;
  /*  Marges resserrées (03/09/2026) : l'objectif annoncé est de réduire le
      nombre de pages. 12 mm reste au-delà de la zone non imprimable d'une
      imprimante de bureau (5 mm) et laisse le pied respirer. */
  margin: 12mm 12mm 14mm;
  @bottom-center {{
    content: counter(page) " / " counter(pages);
    font-family: {FONT_SANS};
    font-size: 8pt;
    color: var(--light-muted);
  }}
}}
/*  La page de garde n'a ni marge ni numéro : elle est une affiche. */
@page garde {{ margin: 0; @bottom-center {{ content: none; }} }}

body {{
  font-family: {FONT_SANS};
  color: var(--ink);
  background: #fff;
  font-size: 9pt;
  line-height: 1.42;
}}

/*  🔴 CE QUE L'IMPRESSION IMPOSE, et que l'écran n'a pas. La barre latérale et
    les boutons d'action sont des gestes d'écran : sur le papier, ils ne mènent
    nulle part. Le repli des blocs, lui, est levé À LA COMPOSITION (voir
    `corps_du_manuel`) — pas ici : ce qui suit habille le résultat. */
.sidebar, .hero-actions, .aide-liens {{ display: none !important; }}
.ecran-detail {{ margin-top: 2mm; border-top: 1px dashed var(--border); padding-top: 2mm; }}
.ecran-detail-titre {{
  font-size: 8.5pt;
  font-weight: 700;
  color: var(--gold);
  text-transform: uppercase;
  letter-spacing: .08em;
  margin: 0 0 1.5mm;
}}
.ecran-detail-corps {{ margin-top: 0; }}

/*  🔴 DEUX COLONNES sur les trois grilles — demandé le 03/09/2026.
    Ce sont des listes de blocs courts : sur une pleine largeur A4, chacun tient
    trois mots suivis de vingt centimètres de blanc, et le document double de
    pages pour rien.

    `column-count` et non un `display: grid` : la coupure en colonnes est ce que
    l'impression sait faire, et elle continue d'une page à l'autre. Un grid CSS
    poserait des lignes fixes que la pagination casserait au milieu.

    ⚠️ `break-inside: avoid` sur chaque carte est indispensable : sans lui, une
    carte se couperait entre deux colonnes — la moitié en bas à gauche, la moitié
    en haut à droite. */
.ecran-grid, .quick-grid, .persona-grid, .profils-grid {{
  display: block;
  column-count: 2;
  column-gap: 7mm;
}}
.ecran-card, .quick-card, .persona-card, .profil-card {{
  break-inside: avoid;
  page-break-inside: avoid;
  display: inline-block;
  width: 100%;
  margin-bottom: 2.5mm;
  border: 1px solid var(--border);
  border-left: 1mm solid var(--navy);
  border-radius: 0 2mm 2mm 0;
  padding: 2.5mm 3mm;
  background: #fff;
}}
/*  Les trois étapes du démarrage se distinguent des quinze écrans : c'est un
    parcours, pas un catalogue. Liseré doré et pastille numérotée, en écho aux
    titres de section. */
.quick-card {{ border-left-color: var(--gold); }}
.quick-step {{
  display: inline-block;
  width: 5.5mm;
  height: 5.5mm;
  line-height: 5.5mm;
  text-align: center;
  border-radius: 50%;
  background: var(--gold);
  color: #fff;
  font-weight: 700;
  font-size: 8.5pt;
  margin-bottom: 1.5mm;
}}
.persona-card {{ border-left-color: var(--green); }}
/*  Les six profils : la porte d'entrée du document — « est-ce que ça
    me concerne ? ». Ils se distinguent des écrans par leur liseré. */
.profil-card {{ border-left-color: #2563eb; }}
.profil-card strong {{ display: block; margin-bottom: .6mm; }}
.apropos {{ margin-bottom: 5mm; }}
.ecran-acces {{
  display: inline-block;
  font-size: 7pt;
  font-weight: 700;
  border-radius: 999px;
  padding: .4mm 1.8mm;
  border: 1px solid var(--border);
  color: var(--muted);
  background: var(--bg);
}}
.ecran-icone {{ width: 6mm; height: 6mm; color: var(--navy); }}
/*  ⚠️ PAS de `column-span: all` sur les cartes dépliées, contrairement à ma
    première idée : l'aperçu montre qu'elles tiennent dans leur colonne, et leur
    donner toute la largeur aurait coûté le blanc qu'on cherche justement à
    supprimer. La règle est partie avant d'être livrée. */
.chapter, .quick-start, .hero {{
  page-break-inside: auto;
  background: none;
  color: var(--ink);
  padding: 0;
  margin-bottom: 5mm;
}}
/*  Le manuel aère beaucoup pour l'écran ; sur le papier, chaque respiration
    coûte une fraction de page. On resserre sans coller. */
.chapter-header {{ margin-bottom: 3mm; }}
.chapter-icon {{ display: none; }}
p {{ margin-bottom: 1.6mm; }}
ul, ol {{ margin: 1.5mm 0 1.5mm 4mm; }}
li {{ margin-bottom: .8mm; }}
.divider {{ display: none; }}
.hero h1 {{ color: var(--navy); font-family: {FONT_SERIF}; }}
.hero p, .hero-note {{ color: var(--muted); }}
/*  🔴 LES SUR-TITRES SONT MASQUÉS, et c'est une correction de MON fait.
    « Bienvenue sur votre extranet de résidence », « Guide express » : à l'écran
    ce sont des accroches, posées au-dessus du vrai titre. Je les avais repeints
    en doré — ils devenaient alors les éléments les plus voyants de la page,
    alors qu'ils ne figurent pas au sommaire. Signalé à l'écran : *« bref c'est
    pas cohérent »*.

    Un document imprimé se lit par sa structure : ce qui saute aux yeux doit être
    ce que le sommaire annonce, et rien d'autre. Trois titres au sommaire, trois
    titres dans le corps. */
.hero-kicker, .quick-badge {{ display: none !important; }}
/*  Les pastilles du bandeau d'accueil sont blanches sur fond bleu à l'écran :
    sur le papier, le fond disparaît et elles deviennent invisibles. Repeintes
    plutôt que masquées — elles portent trois phrases utiles. */
.hero-cards {{ display: block; margin-top: 4mm; }}
.hero-card {{
  display: inline-block;
  margin: 0 2mm 2mm 0;
  padding: 1.5mm 3mm;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  font-size: 8.5pt;
}}
/*  🔴 LES TITRES DE SECTION SONT NUMÉROTÉS ET COLORÉS (03/09/2026).
    « Pas très joli », et c'était juste : trois titres perdus dans le gris, alors
    que le sommaire les annonce numérotés. Le compteur est le MÊME que celui du
    sommaire — un lecteur qui cherche « 2. » le retrouve tel qu'il l'a lu.

    Le numéro est en pastille dorée, le titre en marine sur un aplat très clair :
    la section s'ouvre par un bloc qu'on repère en feuilletant, ce que trois mots
    en gras ne font pas. */
body {{ counter-reset: sect; }}
h2 {{
  counter-increment: sect;
  font-family: {FONT_SERIF};
  color: var(--navy);
  font-size: 15pt;
  margin: 0 0 3mm;
  padding: 2.5mm 3mm 2.5mm 14mm;
  background: linear-gradient(90deg, var(--bg) 0%, #fff 82%);
  border-left: 1.6mm solid var(--gold);
  border-radius: 0 2mm 2mm 0;
  position: relative;
  page-break-after: avoid;
}}
h2::before {{
  content: counter(sect);
  position: absolute;
  left: 3.5mm;
  top: 50%;
  transform: translateY(-50%);
  width: 7mm;
  height: 7mm;
  line-height: 7mm;
  text-align: center;
  border-radius: 50%;
  background: var(--gold);
  color: #fff;
  font-family: {FONT_SANS};
  font-size: 10pt;
  font-weight: 700;
}}
/*  Le titre du sommaire et celui des mentions ne sont pas des sections du
    manuel : ils gardent le style, sans le numéro qui décalerait le compteur. */
.sommaire h2, .mentions h2 {{ counter-increment: none; padding-left: 3mm; }}
.sommaire h2::before, .mentions h2::before {{ content: none; }}
h3 {{
  font-family: {FONT_SERIF};
  color: var(--navy);
  font-size: 10.5pt;
  margin-bottom: 1mm;
  page-break-after: avoid;
}}
/*  Le titre d'accueil est l'INTRODUCTION du document, pas une de ses trois
    sections : il n'est donc pas numéroté au sommaire, et il se distingue des
    `h2` par sa taille plutôt que par une couleur de plus. */
/*  L'introduction : un chapeau, pas une section. Filet doré court sous le titre
    — le même geste que la page de garde, pour que les deux se répondent. */
.hero h1 {{
  font-size: 20pt;
  margin-bottom: 2mm;
  padding-bottom: 2mm;
  border-bottom: 2px solid var(--gold);
  display: inline-block;
}}
a {{ color: var(--navy); text-decoration: none; }}

/* ── Page de garde ────────────────────────────────────────────────────── */
.garde {{
  page: garde;
  page-break-after: always;
  height: 297mm;
  position: relative;
  background: var(--navy);
  color: #fff;
  text-align: center;
}}
/*  Le bandeau doré : la seule ligne de couleur chaude de la charte, employée
    ici comme sur les affiches de hall — un rappel, pas une décoration. */
.garde::after {{
  content: "";
  position: absolute; left: 0; right: 0; bottom: 0;
  height: 14mm;
  background: var(--gold);
}}
/*  Un liseré doré en haut répond à celui du pied : la page est tenue par ses
    deux bords, pas posée sur un fond. */
.garde::before {{
  content: "";
  position: absolute; left: 0; right: 0; top: 0;
  height: 4mm;
  background: var(--gold);
}}
.garde-logo {{ padding-top: 34mm; }}
/*  Médaillon : le logo est blanc sur bleu, il se perdrait sans un fond clair. */
.garde-medaillon {{
  width: 30mm; height: 30mm;
  margin: 0 auto;
  border-radius: 50%;
  background: rgba(255, 255, 255, .08);
  border: 1px solid rgba(255, 255, 255, .18);
  display: flex;
  align-items: center;
  justify-content: center;
}}
.garde-surtitre {{
  font-size: 9.5pt;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--gold);
  margin-top: 10mm;
}}
.garde-titre {{
  font-family: {FONT_SERIF};
  font-size: 34pt;
  line-height: 1.1;
  margin: 4mm 22mm 0;
  letter-spacing: .01em;
}}
.garde-sous {{
  font-size: 12pt;
  color: #C7D2E0;
  margin: 6mm 28mm 0;
  line-height: 1.6;
}}
.garde-filet {{
  width: 26mm; height: 2px;
  background: var(--gold);
  margin: 10mm auto;
}}
.garde-qr {{ margin-top: 12mm; }}
.garde-qr img {{
  width: 34mm; height: 34mm;
  background: #fff;
  padding: 3mm;
  border-radius: 3mm;
}}
.garde-qr p {{
  font-size: 9.5pt;
  color: #C7D2E0;
  margin-top: 4mm;
}}
.garde-qr strong {{ color: #fff; }}
.garde-pied {{
  position: absolute;
  left: 0; right: 0; bottom: 20mm;
  font-size: 9pt;
  color: #A8B6C8;
}}

/* ── Sommaire ─────────────────────────────────────────────────────────── */
.sommaire {{ page-break-after: always; }}
.sommaire h2 {{ margin-bottom: 6mm; }}
.sommaire ol {{ list-style: none; padding: 0; counter-reset: som; }}
.sommaire li {{ padding: 1.2mm 0; }}
.sommaire a {{
  display: block;
  color: var(--ink);
  text-decoration: none;
}}
/*  🔴 Le numéro de page est RÉSOLU À LA MISE EN PAGE (`target-counter`), jamais
    écrit : on ne sait pas encore combien de pages fera le document, et un
    numéro saisi serait faux dès la première phrase ajoutée au manuel. */
.sommaire a::after {{
  content: target-counter(attr(href), page);
  float: right;
  color: var(--gold);
  font-weight: 700;
}}
/*  Les points de conduite : c'est ce qui rend une ligne de sommaire lisible
    quand le titre est court et le numéro loin. */
.sommaire a::before {{
  content: "";
  float: right;
  width: 0;
}}
.sommaire .som-n2 {{
  counter-increment: som;
  border-bottom: 1px solid var(--border);
  margin-top: 3mm;
}}
.sommaire .som-n2 a {{
  font-family: {FONT_SERIF};
  font-size: 12pt;
  color: var(--navy);
}}
.sommaire .som-n2 a::before {{
  content: counter(som) ". ";
  float: none;
  color: var(--gold);
  font-weight: 700;
}}
/*  Les quinze écrans sont des sous-entrées : décalées, plus discrètes, mais
    présentes — c'est par elles qu'on cherche « Accès & badges ». */
.sommaire .som-n3 {{
  padding: .8mm 0 .8mm 7mm;
  font-size: 9.5pt;
  border-bottom: 1px dotted var(--border);
}}
.sommaire .som-n3 a {{ color: var(--muted); }}

/* ── Mentions ─────────────────────────────────────────────────────────── */
.mentions {{
  page-break-before: always;
  border-top: 3px solid var(--gold);
  padding-top: 6mm;
  font-size: 9pt;
  color: var(--muted);
}}
.mentions h2 {{ font-size: 13pt; }}
.mentions dt {{ font-weight: 700; color: var(--ink); margin-top: 3mm; }}
.mentions dd {{ margin: 0 0 1mm; }}
.mentions .avert {{
  margin-top: 6mm;
  padding: 3mm 4mm;
  background: var(--bg);
  border-left: 3px solid var(--gold);
}}
"""


