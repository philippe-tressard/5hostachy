---
name: ux-patterns
description: "Apply and enforce 5Hostachy UX patterns: expand cards, tabs, pills, badges, photo thumbnails and galleries, kanban column visibility, pagination, accessibility, archiving, perimeter display, urgency, pinned items, form field conventions. Use when: implementing a new UI feature, reviewing UX consistency, checking if a pattern is correctly applied across all pages."
argument-hint: "Describe the UX element to implement or review (e.g. 'add tabs to page fournisseurs', 'review badge consistency')"
---

# UX Patterns — 5Hostachy

Guide de référence des patterns UX établis. Tout pattern utilisé ≥ 2 fois doit être uniforme sur **toutes** les occurrences du site.

## Règle d'uniformisation

> 📖 **La règle générale est dans `standards/11-interface-et-ux.md` §1 et §1 bis** —
> regarder les autres écrans **avant** d'écrire, y compris pour ce qui n'a pas de
> nom (en-tête, titre, section, bloc, pied de page, espacement, ordre des boutons) ;
> corriger l'écart trouvé s'il est simple, ouvrir un ticket sinon ; et se méfier de
> l'**héritage partiel** quand on redéfinit localement une règle globale.
> Ne pas la recopier ici : cette skill ne porte que son instanciation 5Hostachy.

1. **Avant** d'implémenter, vérifier si un pattern similaire existe déjà (grep / semantic search)
2. Si le pattern existe ≥ 2 fois → c'est un **pattern établi** → l'appliquer à l'identique
3. Si la demande contredit un pattern → **signaler le conflit** et demander confirmation
4. Après implémentation → mettre à jour **cette skill** si le pattern a évolué

**Où chercher, ici** : `front/src/app.css` porte les règles globales (`.carte-liste`,
`.page-header`, `.form-actions`, `.clamp-5`, `.chevron`, `.largeur-saisie`…) —
c'est le premier endroit à lire, avant toute règle locale. Les composants partagés
sont dans `front/src/lib/components/`.

⚠️ **Deux fois déjà, une page a réécrit chez elle une règle qu'`app.css` portait
déjà** : `.form-actions` (identique, donc inerte, supprimée le 15/08) et
`.page-header` (réécrite dans six pages et surchargée en ligne dans six autres —
issue #363, qui a projeté le titre de *Nouveau ticket* à droite de l'écran). Le
réflexe n'est pas « qu'est-ce que j'ajoute ? » mais « de quoi est-ce que j'hérite ? ».

## 🔴 CE QUI EST TRANCHÉ — à appliquer sans rediscuter

Onze arbitrages en deux jours (17–18/08/2026), tous **constatés à l'écran** avant
d'être écrits ici. Trois d'entre eux **contredisent** une version antérieure de
cette skill : c'est normal, et c'est même le mécanisme — *une règle d'interface
se vérifie sur un écran, pas sur du papier*.

Ce bloc n'énonce que les décisions et renvoie à la section qui les développe.
**Il ne recopie rien** : deux versions d'une même règle divergent au premier lot.

| # | Ce qui est tranché | Développé en |
|---|---|---|
| 1 | **Le geste de dépliage est asymétrique** — carte repliée : clic n'importe où ; carte dépliée : **seul le titre** replie | §3 |
| 2 | **Le survol colore le TITRE**, jamais le fond du bloc, et **sans soulignement** | §3 |
| 3 | **Le liseré gauche** de `.carte-liste` qui passe au bleu est **la référence** — sauf sur le fil, où il porte déjà la couleur du type | §3 |
| 4 | **L'en-tête de carte** : titre sur sa ligne, puis tags à gauche / date + actions + chevron à droite, **sur une seule ligne** | §3 |
| 5 | **Ordre des icônes : 🔄 ✏️ 🗑️**, dans l'en-tête et jamais dans le corps | §3 |
| 6 | **Le mode se lit sur l'icône** qui a ouvert le formulaire (`aria-pressed`), jamais sur un titre au-dessus | §13 bis |
| 7 | **Section 1 = le titre SEUL** ; ce qui qualifie l'objet est en section 2 | §0 |
| 8 | **Un workflow se déclare, le tracer est une AUTRE décision** — cinq états sur une annonce, aucun fil | §16 |
| 9 | **L'archivage se calcule, il ne se choisit pas** : 30 j après un état terminal, sur `statut_change_le`, jamais de bouton 📦 | §16 |
| 10 | **Deux droits** : éditer = auteur · saisi_pour · admin ; commenter = les mêmes **+ CS** | §15 |
| 11 | **L'écran dit ce que le serveur fait**, ni plus ni moins | §15 |

### ⚠️ Les trois pièges que ces onze arbitrages ont révélés

**1. Une objection juste dans l'absolu peut être hors sujet ici.** J'ai refusé la
carte entière comme cible de clic — « elle intercepte la sélection de texte ».
L'argument est réel et ne s'appliquait pas : le corps déplié arrête déjà la
propagation, et la zone repliée n'a rien à sélectionner. **Trois allers-retours**
ont été perdus à défendre une objection valide au mauvais endroit.

**2. Quand un écran sert de référence, il est le premier à devoir suivre la règle
qu'on en tire.** Le fil d'activité a été désigné comme modèle du geste — et c'est
lui qui a gardé l'ancien comportement le plus longtemps, parce que la règle a été
appliquée à ses imitateurs sans être remontée au modèle.

**3. Un garde-fou qui refuse dit souvent que le code est au MAUVAIS ENDROIT, pas
qu'il est trop long.** Le contrôle de modularité a refusé cinq ajouts de deux
lignes le 18/08 ; quatre fois j'ai raboté (#453), la cinquième la bonne réponse
était de **remonter la règle dans `app.css`** — et les deux pages y ont perdu des
lignes. Trois réponses possibles, une seule mauvaise :

| Réponse | Quand |
|---|---|
| découper le fichier | l'ajout est propre à cet écran |
| **remonter la règle d'un cran** | l'ajout dit quelque chose de **global** |
| raboter pour passer sous le seuil | ❌ jamais |

### Ce qui n'a PAS bougé

Le cadre lui-même — **les 9 sections, les 4 rendus, les 3 motifs de divergence** —
n'a pas changé d'une ligne en deux jours. Ce sont les **entités** qui ont appris,
pas la grammaire. C'est le signe que la grammaire est la bonne.


## 0. LE CADRE — une entité, quatre rendus (décidé le 17/08/2026)

**C'est la règle qui gouverne toutes les suivantes.** Les sections §9, §10, §13 et
§14 de cette skill en sont les instanciations ; en cas de désaccord, le cadre tranche.

> 📐 **Le cadre et sa maquette** : https://claude.ai/code/artifact/ed8e5dd8-67f0-4fd3-a0bc-e80653bac686
> 📊 **Le relevé des 42 couples menu/entité qui le fonde** : https://claude.ai/code/artifact/88087a21-8fe3-4463-8a35-a39f3032e5f3
> 🧠 **Le pourquoi, avec ses contre-exemples chiffrés** : mémoire projet
> `project_cadre_quatre_rendus` · 🎫 **#430**, lots #431 → #433 → #432

### Les quatre états

**Affichage** · **Création** · **Édition** · **Évolution** (une entrée de
**l'Historique**). « Commentaire » est abandonné : trop étroit, l'entrée pouvant
porter un changement d'état, des pièces jointes et une diffusion. C'est déjà le
vocabulaire du code (`TicketEvolution`, `EvolForm`).
⚠️ Le cadre parle d'évolutions ; **l'écran parle de gestes** (« Commenter »,
« Changer l'état »).

### Les neuf sections, dans cet ordre — il ne se discute pas

1. **Titre** *(et lui seul)* · 2. **Champs spécifiques** (Catégorie, Saisi
pour…) · 3. **Workflow** *(quand l'entité en a un — voir ci-dessous)* · 4.
**Périmètre** · 5.
**Destinataires** *(qui est concerné dans l'application)* · 6. **Description** ·
7. **Photos** · 8. **Documents** · 9. **Diffusion** *(par quels canaux on prévient
à l'extérieur)*.

🔴 **Une section ne se fusionne JAMAIS avec une autre, dans aucun rendu.** Neuf
déclarées, neuf rendues — même voisines, même courtes, même héritées. Fusionner
« Photos · Documents » parce qu'elles tiennent sur une ligne crée une dixième
section que rien ne déclare.

### Un champ n'est pas un geste — d'où la seule différence création/édition

Les sections **1 à 8 décrivent l'entité** ; la **9 est un acte**.

| État | Contenu |
|---|---|
| Affichage | 1→8 en lecture · 9 absente |
| Création | 1→9 en saisie |
| **Édition** | **1→9 identiques à la création** — la Diffusion y est **rouverte** (18/08), mais **seule la transition décoché → coché envoie** |
| **Évolution** | **création sans le titre** (hérité) · workflow **tracé** · périmètre et destinataires hérités · **9 rejouable** |

**L'édition corrige** — une erreur, un oubli, un complément. Le `PATCH` écrit une
**correction**, jamais une transition.

🔴 **La Diffusion a rouvert à l'édition le 18/08/2026**, sur arbitrage : *le CS
doit pouvoir décider d'envoyer au syndic un objet déjà saisi*. Ce qui rend la
réouverture sûre n'est **pas** l'interface mais le **serveur** — seule la
transition *décoché → coché* envoie. Un canal déjà coché ne repart pas à chaque
enregistrement, donc corriger une faute de frappe reste silencieux.

⚠️ **Sans ce mécanisme, rouvrir est PIRE que fermer** : le `PATCH` stockerait le
drapeau sans rien envoyer, et la case promettrait un envoi qui n'a pas lieu.
**Avant de rouvrir un champ dans l'interface, vérifier que le serveur le
CONSOMME.**

### Les six règles

- **R1** squelette de page immuable (titre + action primaire en haut · corps ·
  soumission en bas à droite) — **et c'est LUI qui porte la responsivité**, une
  seule fois pour toutes les pages.
- **R2** ordre des 9 sections immuable, **et valable pour l'affichage**.
- **R3** un champ est un **objet** à trois rendus, qui se rend **toujours pareil**,
  avec **le même libellé partout**, le requis marqué par **`*` et rien d'autre**
  (jamais « (optionnel) »), **le fond de saisie** s'il est éditable — le mode se lit
  alors sans lire un badge — et **toute sélection en pastilles arrondies, jamais un
  `<select>` nu**. Une pastille qui se déplie porte un **chevron `›`**, seule marque
  du second niveau, *qui annonce sans imposer*. **La hiérarchie est une DONNÉE**
  (`parent` + `selectionnable`), administrée dans Admin → Patrimoine :
  *« sans inventer de niveau dans les données »*.
- **R3 bis** une **rubrique** groupe des objets et porte leur ordre, agencement et
  allure — variantes **limitées et justifiées**. *Une variante ajoutée pour
  accueillir un écart existant ne factorise pas : elle entérine.*
- 🔴 **R4** toute divergence entre états **se déclare avec son motif** :
  **`geste`** · **`hérité`** · **`api`** ⚠️ *motif de dette, qui doit citer un
  ticket*. **Une divergence sans motif est refusée par la CI** (`lint:etats`).
- 🔴 **R5** l'**enrichissement se propage** (squelette → toutes les pages ; rubrique
  → toutes les pages hôtes ; objet → toutes les sections). **Donc il se propose sur
  UN écran, se fait constater, puis se généralise.** Jamais l'inverse.

### Où le cadre VIT dans le code (depuis #431, 17/08/2026)

| Quoi | Où | À faire avant d'écrire un écran |
|---|---|---|
| Les 9 sections, leur ordre, leurs libellés, les 4 états, les 3 motifs | `front/src/lib/entites/types.ts` | ne jamais recopier cette table |
| La déclaration d'une entité et **ses divergences motivées** | `front/src/lib/entites/<entite>.ts` | la lire ; si elle n'existe pas, l'écrire |
| Le squelette de **lecture** (R1 pour l'affichage) | `FicheLecture.svelte` | l'affichage passe par lui, il tient l'ordre |
| Le squelette de **saisie** | `FormulaireCreation.svelte` + `ChampsCommuns.svelte` | sections 4→9, jamais réécrites |
| La rubrique **Historique** (le fil) | `RubriqueHistorique.svelte` | **6 recopies sur 6 remplacées** |
| L'**en-tête d'une carte de liste** | `EnteteCarte.svelte` | titre / tags · date · actions — voir §3 |
| La rangée d'**états en pastilles** | `WorkflowPastilles.svelte` | jamais un `<select>` nu (R3) |
| **Toute** pastille de sélection | `Pastille.svelte` | jamais un `<button class="pill">` — voir le seuil ci-dessous |
| Le garde-fou R4 | `npm run lint:etats` | il refuse une divergence sans motif, un motif `api` sans ticket, et **une section rendue hors déclaration** |

### Le seuil des listes courtes : **6** (arbitré le 29/08/2026, #491)

Une liste de **6 entrées ou moins** qui fait CHOISIR se rend en pastilles
(`Pastille.svelte`). Au-delà, elle reste ce qu'elle est.

Le chiffre n'est pas arbitraire : les usages existants allaient de 2 à 6, et deux
cas se posaient juste au-dessus — `CATEGORIES_ANNONCE` (9) et les statuts
utilisateur (7). Le seuil les exclut, et il est **écrit ici pour que la question
ne se repose pas à chaque écran** : c'est en y répondant au cas par cas qu'on a
obtenu sept pastilles réécrites à la main.

⚠️ **Le seuil décide d'une CONVERSION, il n'impose pas de revenir en arrière.**
Les douze filtres d'équipement de `prestataires` restent des pastilles : ils
l'étaient déjà en substance, et les défaire n'apporterait rien.

**Une pastille peut porter un SOUS-TEXTE** (`<span slot="detail">`), et c'est ce
qui a débloqué la conversion des listes qui portaient une description. Sans lui,
elles restaient en cartes maison — ou perdaient l'information.

🔴 Le cas qui l'a rendu nécessaire : les six types de prestataire portaient leur
description dans un `title`, donc **invisible au tactile** — un survol n'existe
pas sur téléphone, et c'est là que ces types sont le plus difficiles à
distinguer.

⚠️ **Ce qui NE se convertit PAS** : un vrai `radiogroup` avec des
`<input type="radio">`, comme les catégories de ticket. `Pastille` rend un
`<button>` : la navigation par flèches et l'annonce par le lecteur d'écran y
seraient perdues. L'uniformité ne se paie pas en accessibilité
(`standards/11` §2).

🔴 **La section 1 ne porte QUE le titre** (arbitré le 18/08/2026, sur les
Tickets où la catégorie était rendue *avant* lui). Ce qui qualifie l'objet —
catégorie, « Saisi pour » — est en **section 2**. Une section peut donc porter
**plusieurs champs nommés** : `titreEcran` accepte une liste, et `lint:etats`
continue de refuser un intitulé inventé sur place.

⚠️ **Limite connue de R4, trouvée le 18/08/2026** : elle ne déclare qu'une
divergence de **section**, pas de **champ**. Sur le ticket, la catégorie reste
ouverte en édition quand « Saisi pour » y est fermé (motif `api`, #431) — ce
motif ne peut pas s'écrire dans `absente` et vit en commentaire, **invisible au
contrôle**. Premier écart que le cadre ne tient pas.

🔴 **La présence d'une section ne se décide plus dans l'écran.** `avecPhotos`,
`avecDiffusion`… se gouvernent par `sectionPresente(ENTITE, etat, 'photos')` et
par rien d'autre. Une condition en dur (`{!modeEdition}`) rouvre exactement la
divergence silencieuse que le cadre supprime — et `lint:etats` la refuse.

⚠️ **`EvolForm` n'est pas encore gouverné par la déclaration** : il sert quatre
écrans, l'y brancher les changerait tous les quatre (R5). L'état `evolution` est
donc déclaré, pas encore confronté à son rendu. Sujet de **#433**.

### Ce que le cadre ne couvre pas

**Document** (1 champ commun sur 5 entre création et édition, *et c'est juste*),
**Utilisateur** (zéro champ commun), et **le moment du téléversement** — trois
régimes, dont un existe **pour raison de sécurité**, et qui **ne se voit pas à
l'écran**.

> ⚠️ Cette skill fait plus de 500 lignes. Le cadre y est **résumé, pas recopié** —
> le détail vit dans l'artefact et la mémoire. Prochaine évolution notable : la
> découper (§9 « Champs de formulaire » fait à lui seul 230 lignes).

## 1. Icônes de contexte

| Icône | Signification | Usage |
|-------|--------------|-------|
| 📍 | Lieu physique (adresse, salle) | Texte inline, pas de badge |
| 🔹 | Périmètre logique (Parking, Bât.) | Badge `.badge-gray` ou `.badge-blue` |

**Ne JAMAIS utiliser** 📍 pour un périmètre logique.

## 2. Affichage du périmètre

**Il n'y a plus de table de libellés, ni ici ni dans le code.** L'arborescence vit
en base (table `perimetre`) et s'édite depuis `/admin/patrimoine` : le produit doit
servir une autre copropriété, qui n'a ni AFUL, ni quatre bâtiments, ni forcément de
caves.

> ⚠️ Cette section portait la table en dur — et elle en **omettait AFUL**, si bien
> qu'un développeur qui la suivait recopiait un défaut. C'est exactement ce que
> `standards/02` §2 décrit : une table recopiée finit par diverger, et la copie la
> plus consultée est celle qui trompe le plus longtemps.

**Écrire un code de périmètre est interdit** — `npm run lint:perimetres` échoue
dessus. Utiliser, depuis `$lib/perimetres` :

| Besoin | Fonction |
|---|---|
| libellé affichable | `perimetreLabel(items)` — accepte tableau **ou** chaîne CSV |
| « c'est le périmètre par défaut ? » | `estPerimetreParDefaut(items)` — **remplace** `=== 'résidence'` |
| valeur initiale d'un formulaire | `perimetreDefautListe()` |
| périmètre d'un bâtiment | `perimetreDuBatiment(batimentId)` |
| « concerne tout le monde ? » | `concerneTous(items)` |
| bâtiments visés | `batimentsCibles(items)` |

**Condition d'affichage** : ne jamais afficher le badge si `estPerimetreParDefaut()`
est vrai (c'est le défaut, le redire n'apprend rien).

### Comment un périmètre S'ÉCRIT — trois règles, portées par `perimetreLabel()`

1. **Un espace est qualifié par son parent** — « Bât. 3 › Toit », « AFUL › Voie
   d'accès ». Sans cela, le gabarit posant les mêmes neuf espaces sous chaque
   bâtiment, un ticket visant deux toits affichait « Toit · Toit » (18/08/2026).
   ⚠️ La qualification s'est arrêtée aux **bâtiments** pendant neuf jours, au motif
   que les enfants du parking ou des locaux techniques « portent déjà des libellés
   distincts ». C'était vrai du **seed**, pas de l'administration : une « Voie
   d'accès » créée sous AFUL s'affichait nue (27/08/2026). La condition porte
   désormais sur ce que le parent EST — une cible, ou un simple **regroupement**
   (« Bâtiments », `selectionnable = false`), qui lui ne préfixe jamais.
2. **Deux séparateurs, deux sens.** ` · ` sépare deux éléments ; ` — ` borne un
   groupe qui en contient plusieurs, et n'apparaît que là — sinon le « · » d'un
   groupe se confond avec celui qui sépare les groupes :
   `Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès`.
   Les deux constantes sont exportées (`SEPARATEUR_ELEMENT`, `SEPARATEUR_GROUPE`) —
   **les importer, jamais les retaper**, le sélecteur le fait.
3. **L'ordre affiché est celui de l'arbre, jamais celui des clics.** Le sélecteur
   stocke l'ordre de sélection ; `perimetreLabel()` trie et regroupe. Un rendu qui
   dépend du chemin de saisie n'est pas un rendu, c'est un hasard.

🔒 **Deux garde-fous en CI, tenus par la MÊME chaîne attendue** : la règle est
écrite deux fois (front et API — les contextes de build interdisent le partage), et
le 18/08 elle n'a été corrigée que d'un côté. `api/tests/test_perimetre_label_batiment.py`
exécute la forme serveur ; `npm run lint:libelle-perimetre` transpile et exécute la
forme front, puis vérifie que le test Python attend la même chaîne.

**Sélecteur** : `PerimetrePicker.svelte`, alimenté par le store — premier niveau de
pastilles, second niveau facultatif quand un bâtiment est choisi, et la
**description** du nœud affichée sous la sélection.

Rendus par page — l'icône du périmètre est **🔹**, jamais 📍 (cf. §1) :
- Actualités : `<span class="badge badge-gray">&#x1F539; {label}</span>`
- Calendrier : `<span class="badge badge-blue">&#x1F539; {label}</span>`
- Tickets : `<p style="font-size:.8rem;color:var(--color-text-muted)">🔹 {label}</p>`

Le label vient de `perimetreLabel()` (`$lib/utils`) — ne pas réimplémenter la table
de correspondance dans une page.

## 3. Carte expansible (Expand Card)

**Le pattern principal** pour les listes (tickets, publications, événements, prestataires).

### 🔴 La structure d'en-tête — `EnteteCarte.svelte`, et elle vaut pour TOUT le site

Posée le **18/08/2026**, après un constat à l'écran : le titre partageait sa ligne
avec les tags, la date et les icônes, et **sur téléphone il disparaissait** — la
ligne étant en `flex` avec `text-overflow: ellipsis`, les badges de largeur fixe
gagnaient et le titre se réduisait à trois points. On lisait une liste sans savoir
de quoi elle parlait.

```
┌──────────────────────────────────────────────┐
│ Titre — sur 1 ou 2 lignes si nécessaire      │
│ tags ················· date  actions  ›      │
│ quatre lignes d'aperçu                       │
└──────────────────────────────────────────────┘
```

- le **titre** occupe sa ou ses propres lignes (2 au maximum, puis coupé) ;
- en dessous, **une seule ligne** : **tags à gauche** (workflow, périmètre,
  confidentiel, auteur), **date puis actions puis chevron à droite** ;
- puis l'aperçu.

**Ne JAMAIS recomposer cet en-tête dans une page** : `EnteteCarte` le porte, avec
son style et son repli. C'est **R1** au sens propre — la responsivité appartient
au squelette, une seule fois pour toutes les pages ; chaque carte qui recomposait
son en-tête avait sa propre façon de mal se replier.

**L'ORDRE DES ICÔNES est celui de la carte de ticket**, désignée comme référence :
**🔄 commenter · ✏️ modifier · 🗑️ supprimer**, puis le chevron. Il était inversé
sur les actualités, et deux cartes du même site ne se lisaient pas pareil.

### La source unique : `.carte-liste` (app.css) — depuis le 15/08/2026

Le conteneur, son espacement, son survol et son état d'urgence vivent **une seule
fois**, dans `front/src/app.css`. Actualités et tickets les redéfinissaient chacun
de leur côté, avec les mêmes valeurs et un simple préfixe qui change — rien
n'empêchait la troisième copie.

```svelte
<div class="carte-liste pub-expand" class:expanded class:urgent={item.urgente}>
```

La page ne garde chez elle que ses **différences** (`.pub-expand.brouillon`,
`.tk-cat`…). Ne jamais y redéfinir marge, bordure gauche, rayon, fond ou ombre.

**Espacement** : `.75rem` entre deux cartes (`.6rem` sous 640 px). Il était de
`.3rem`, et l'aperçu tronqué **net** au ras du bord : deux cartes voisines
formaient un pavé continu où l'œil ne trouvait plus la limite. Signalé par
l'utilisateur, pas par un contrôle — aucun test ne dit qu'une liste est confuse.

**Fin d'aperçu** : `ApercuCarte.svelte` estompe la dernière ligne par un
dégradé, **et seulement si le texte déborde vraiment**. ⚠️ Appliqué sans
condition, il efface la dernière ligne d'un aperçu court et annonce une suite qui
n'existe pas — constaté à l'écran. Aucun sélecteur CSS ne sait dire « ce texte
déborde » : la mesure se fait après rendu (`scrollHeight > clientHeight`).

### Règles
- **Une seule** carte ouverte à la fois
- Chargement lazy des détails au premier clic
- Prévisualisation `.clamp-5` (5 lignes max)
- Border-left, urgence, espacement et ombre : **portés par `.carte-liste`** (voir
  ci-dessus). Ne pas les redéfinir dans une page.
- Urgence : bord gauche rouge — **pas de badge texte 🚨**
- **Le corps déplié ne referme pas la carte** : `on:click|stopPropagation` dessus.
  On referme par l'en-tête. Sans cela, impossible de sélectionner du texte, et un
  clic sur une photo ou un formulaire referme ce qu'on lisait. Le fil des
  actualités était le seul à ne pas l'appliquer (corrigé le 15/08/2026, signalé
  par l'utilisateur — qui croyait l'anomalie du côté des tickets, alors que
  c'étaient eux qui avaient raison).
- **Aperçu replié : vignette dès que l'élément porte une photo**, via
  `ApercuCarte.svelte` (ou `FluxVignette` quand la carte n'a pas d'aperçu texte).
  Vaut pour **les six écrans dépliables**, vérifié un par un le 15/08/2026 : fil
  d'activité, actualités, tickets, espace CS, calendrier, prestataires. Les trois
  derniers ne l'appliquaient pas — et le **calendrier** laissait joindre des photos
  à un événement sans jamais les montrer, ni repliées ni dépliées.

  ⚠️ Deux architectures donnent le bon comportement de refermeture : conteneur
  cliquable **+** corps en `stopPropagation` (actualités, tickets, calendrier), ou
  en-tête cliquable **+** corps *frère* (prestataires). Ne pas « corriger » une
  absence de `stopPropagation` sans regarder la structure : on casserait ce qui
  marche.
- Accessibilité : `role="button"` + `tabindex="0"` + `on:keydown`

### Préfixes par page
| Page | Préfixe CSS | Référence |
|------|------------|-----------|
| Actualités | `.pub-` | **`CarteActualite.svelte`** — la page ne rend plus la carte |
| Tickets | `.tk-` | `tickets/+page.svelte` |
| Calendrier | `.ev-` | `calendrier/+page.svelte` |
| Tableau de bord | `.pub-`, `.ev-`, `.tk-` | `tableau-de-bord/+page.svelte` |

⚠️ **La carte des actualités est un composant depuis le 15/08/2026** (#356) :
`CarteActualite.svelte` sert le fil **et** l'Historique, qui rendaient jusque-là
le même balisage deux fois — le lot #351 avait dû y appliquer quatre
modifications au lieu de deux. Toute évolution de la carte se fait là, une fois.

Le balisage part **avec ses règles CSS** : Svelte scope les styles au composant.
Ce qui reste dans la page (formulaires, fil d'évolutions) y est passé en **slots**
— écrit dans la page, donc stylé par la page. Le signal qui dit que le découpage
est correct est `svelte-check` : **aucun** « Unused CSS selector » nouveau.

### Le GESTE de dépliage — il est ASYMÉTRIQUE (18/08/2026)

```
carte REPLIÉE  → toute la zone déplie · le fond change au survol
carte DÉPLIÉE  → SEUL le titre replie · le corps se lit et se sélectionne
```

Formulé ainsi : *« applique partout la logique du fil d'actualité : cliquable
sur toute la zone pour déplier, avec changement de couleur au survol »* puis
*« clic sur le titre seul pour le repliement — pour permettre de sélectionner le
texte sans le replier »*.

🔴 **L'asymétrie résout le conflit**, elle ne l'arbitre pas : une grande cible
pour ouvrir (au doigt, sur téléphone), aucune cible parasite une fois ouvert
(pour lire, sélectionner, copier). Les deux exigences ne se contredisent pas —
elles ne portent pas sur le même état.

⚠️ **Trois allers-retours dans la même journée** avant d'y arriver, parce que je
lisais chaque moitié de la règle sans l'autre : d'abord « le titre et lui seul »,
puis « toute la carte », enfin les deux à leur moment. La leçon n'est pas qu'il
fallait deviner — c'est qu'une objection juste dans l'absolu (« la carte entière
intercepte la sélection ») peut être **hors sujet** ici : le corps déplié arrête
déjà la propagation, et la zone repliée n'a rien à sélectionner.

**Mise en œuvre**, une seule fois :

| Où | Quoi |
|---|---|
| conteneur de la carte | `role="presentation"` + `on:click={() => { if (!expanded) basculer(); }}` |
| `EnteteCarte` | `basculable` → le titre devient un `<button>` qui bascule, avec `stopPropagation` |
| `app.css` | `.carte-liste:not(.expanded)` porte le curseur **et** le fond au survol |
| corps déplié | `.carte-corps` + `role="presentation"` + `on:click\|stopPropagation` |

⚠️ Le titre est un **vrai `<button>`** : il porte le clavier dans les deux sens.
Le conteneur n'est donc pas interactif, et rien n'est imbriqué.

⚠️ `:not(.expanded)` porte toute la règle de survol. Sans lui, le curseur
promettrait partout un clic qui ne fait rien, et le fond se surlignerait sous un
formulaire ouvert.

## 4. Onglets (Tabs)

**Quand** : page avec 2+ vues ou sections distinctes.

- État : `let onglet: 'a' | 'b' = 'a'`
- `role="tablist"` sur le conteneur, `role="tab"` sur chaque bouton
- Descriptif par onglet : `_pc.onglets?.[onglet]?.descriptif`
- CSS : `.tabs` + `.tabs button.active`
- **Ne jamais utiliser** le pattern `view-toggle` / `view-btn` (pattern non-standard, supprimé)

Pages implémentées : `mon-lot`, `sondages`, `espace-cs`, `admin`, `calendrier`

### 🔴 4 bis. L'onglet ACTIF se voit — trois marques, pas une

Arbitré à l'écran le 30/08/2026 : *« on ne voit pas l'onglet actif ; ajoute ce
design dans l'UX et applique-le à tous »*.

`.tabs button.active` (`styles/ecrans.css`) porte les **trois** marques, et il
les faut toutes :

| Marque | Pourquoi elle ne suffit pas seule |
|---|---|
| **liseré bas** en couleur primaire | la seule qui se voie d'un coup d'œil — c'est celle qui manquait |
| **couleur** du texte en primaire | seule, elle se confond avec le survol |
| **graisse 600** | seule, elle est trop discrète ; et elle porte l'écart pour qui distingue mal les couleurs |

**Un écran ne redéfinit JAMAIS `.tabs button` en entier.** Il ne pose que son
écart — taille, espacement, icône — et hérite du reste.

⚠️ **Le défaut, et il est structurel.** `prestataires` redéfinissait les neuf
propriétés de la charte, dont `color` et `border-bottom: transparent` : les deux
que `.active` change. À spécificité égale, le style **scopé** d'un composant
Svelte est injecté APRÈS la feuille commune — il gagne. Le liseré de l'onglet
actif disparaissait donc, sans qu'aucune règle ne soit fausse.

🔴 Et un commentaire posé juste à côté affirmait *« cet écran ne garde que son
ÉCART »*. C'était faux, et il a survécu à deux lots qui le citaient : **un
commentaire n'est pas un garde-fou** — c'est la troisième fois que ce dépôt
l'apprend (#562, #491, celui-ci).

### 4 ter. L'onglet ouvert par défaut est celui que le MENU annonce

Signalé le même jour : *« quand on clique sur prestataire, la page affichée par
défaut est celle des contrats »*. Une entrée de menu qui ouvre autre chose que ce
qu'elle nomme fait douter d'avoir cliqué au bon endroit.

**Règle** : l'onglet initial porte le nom de l'écran, sauf raison écrite sur
place. Une ouverture directe par `?onglet=` reste prioritaire — c'est un choix
explicite du lien, pas un défaut.

## 5. Pill Buttons

**Quand** : choix exclusif ou multiple, ≤ 8 options, libellés courts.
**Préférer à** : `<select>`, `radio` en colonne, `checkbox` en colonne.

- Classes : `.perimetre-pills` (conteneur), `.pill`, `.pill-active`
- `type="button"` obligatoire (éviter soumission formulaire)
- Sélection multiple : toggle + reset auto vers défaut si aucun actif

Pages implémentées : `actualites`, `calendrier`

## 6. Ligne de publication

**Ordre** : `[📌 coin absolu] [Brouillon?] Titre [Statut] [🔹 Périmètre]`

- Badges : toujours **après** le titre
- Urgence : bord gauche rouge uniquement (pas de badge texte)
- Épingle : badge absolu coin haut-gauche (`.pin-badge`)

## 7. Prévisualisation 5 lignes

Tout bloc expansible affiche **exactement 5 lignes** en état replié.

```css
.clamp-5 {
    display: -webkit-box;
    -webkit-line-clamp: 5;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
```

Pages implémentées : `actualites`, `tableau-de-bord`, `faq`, `calendrier`, `sondages`

## 8. Archiver vs Supprimer

| Action | Qui | Où | API |
|--------|-----|-----|-----|
| 📦 Archiver | CS + admin | Vue principale | `PATCH { archivee: true }` |
| 🗑️ Supprimer | Admin seul | Vue Archives seule | `DELETE` (require_admin) |

Vue archives unifiée dans `calendrier/+page.svelte` (onglet Archives).

## 9. Champs de formulaire

> 🔴 **La largeur de saisie appartient au SQUELETTE, pas à la page (R1) — et elle
> change (18/08/2026).** Elle est désormais une **variable**,
> `--largeur-saisie`, définie dans `app.css` et posée par
> `(app)/+layout.svelte` : *une largeur unique, quels que soient la page et le
> formulaire, adaptée à l'écran du terminal avec une marge optimale* (arbitrage
> utilisateur). Motif : le cap à 720 px était plus étroit que tout le reste de la
> page — la boîte de création s'arrêtait bien avant les cartes de la liste posées
> juste en dessous.
>
> **La nouvelle valeur (`100%` du conteneur) n'est active que sur `/tickets`**,
> le temps d'être constatée à l'écran (R5) ; partout ailleurs le défaut reste
> 720 px. Généraliser = changer la ligne de `app.css` et **supprimer** la liste
> `ROUTES_LARGEUR_PLEINE` du squelette. Ne pas la laisser vivre : un mécanisme
> d'exception qui survit invite la valeur suivante — c'est la leçon de la prop
> `marge` d'`EntetePage` (§13). Ne **jamais** écrire une largeur dans une page.

**Largeur : `.largeur-saisie`, sur le conteneur du formulaire.** Vaut
pour les pages dédiées *et* les formulaires intégrés à une liste — le même geste
ne doit pas avoir deux largeurs selon l'écran.

Trois pratiques coexistaient avant le 15/08/2026 : 640 px sur les pages dédiées et
l'administration, pleine largeur sur les formulaires inline (actualités,
sondages). Signalé par l'utilisateur, pas par un contrôle.

⚠️ Les séparateurs `<hr>` d'un bloc de saisie portent la **même** classe : sinon
le trait s'arrête avant le formulaire, ce qui se voit immédiatement.

⚠️ Ne s'applique **pas aux modales**, qui ont leurs propres contraintes (celle du
calendrier reste à 640 px, délibérément).


- Champ requis : label suivi de ` *` — `Titre *`, `Périmètre *`
- **Pas** de mention « (optionnel) » : l'absence de `*` suffit
- Actions : bouton secondaire / Annuler **à gauche**, action primaire **à droite**

### Un champ, UNE nomenclature : `.field`

🔴 **`.field` (`app.css`) est la définition unique du champ** — mise en page,
fond beige, contour de focus, état lecture seule. Les deux écritures conviennent,
et elles seules :

```svelte
<label class="field">Titre *<input type="text" bind:value={titre} /></label>

<div class="field">
  <label for="ah-source">Pré-remplir depuis une actualité</label>
  <select id="ah-source" bind:value={source}>…</select>
</div>
```

**Le champ ne porte aucune classe** : `.field input`, `.field select` et
`.field textarea` le gouvernent. Deux modificateurs nommés, et rien d’autre :
`champ-large` (§9 bis) et **`champ-en-ligne`**, pour un champ posé dans une
rangée où le `gap` du parent porte déjà l’espacement.

🔒 **Garde-fou : `npm run lint:champs`** (`front/scripts/check-champs.mjs`), en CI
depuis le 19/08/2026. Tout `<input>` de saisie, `<select>` ou `<textarea>`
**associé à un libellé** doit vivre dans un `.field`. Un contrôle **sans**
libellé — filtre de barre d’outils, recherche, renommage en ligne — est hors
périmètre : l’y forcer donnerait des dérogations à la pelle, donc un contrôle
qu’on désarme.

**Why (#413, 19/08/2026)** : **six** nomenclatures coexistaient — `.field-label`
(3 définitions **incompatibles** : deux enveloppantes, une frère), `.form-group`
(3), `.champ`, `.ah-champ`/`.ah-select`, `.email-label`/`.email-input`, et le
`<label>` nu appuyé sur une règle `.form-grid label`. **Trois fichiers
redéfinissaient `.field` elle-même**, le nom canonique, avec d’autres valeurs.

⚠️ Et **deux ne renvoyaient à aucune définition** : `OngletWhatsApp` et
`acces-securite`, extraits d’`admin` sans ses styles, rendaient leurs champs nus
en production — `.form-grid` comprise, si bien que leurs formulaires n’étaient
même pas des grilles. C’est la régression des pastilles nues (v2.67.11),
appliquée au formulaire.

⚠️ **La leçon du contrôle, et c’est la vraie.** Le relevé de #374 cherchait un
`<label>` qui enveloppe son champ *sur une ligne*. Il a manqué la forme
multi-lignes (deux champs d’Admin), puis la forme « libellé frère » reliée par
`for=` — celle-là trouvée **en production par l’utilisateur**, un fond blanc au
milieu d’un site beige. Un relevé par motif textuel ne prouve rien sur ce qu’il
n’a pas cherché : `lint:champs` lit l’**arbre des balises**, où les trois formes
se ramènent à une seule question, et son `--selftest` le montre les refuser.

### Fusionner deux écrans : une UNION, jamais un remplacement

Deux écrans qui montrent la même donnée sous deux angles se fusionnent — mais la
fusion se **prouve capacité par capacité**, sinon elle en retire en silence. Les
« Modèles e-mail » et les « Designs des modèles d’e-mail » l’ont été le
19/08/2026, après avoir coexisté depuis #299 et attendu leur arbitrage dans #307.

Le geste, dans cet ordre :

1. **Dresser le tableau des capacités** de chacun, à la lecture du code — pas de
   mémoire. Ici : quatre venaient de l’écran secondaire (intention, aperçu du
   rendu, variables du gabarit, réinitialisation des designs), trois du principal
   (table, corps texte, historique des envois).
2. **Vérifier que les deux parlent au même endpoint.** C’était le cas
   (`/admin/modeles-email`), et le serveur acceptait déjà les cinq champs : la
   fusion ne demandait aucun changement d’API.
3. **Distinguer une capacité d’une promesse vide.** Le regroupement « par
   domaine » n’a pas été repris : `ModeleEmail` n’a ni `domaine` ni `categorie`,
   l’écran rangeait donc tout dans un unique groupe « général ».
4. ⚠️ **Reprendre, c’est relire.** « Variables disponibles » découpait sur les
   virgules un champ qui est un **tableau JSON**, et affichait `{{ ["civilite" }}`.
   Recopier le geste aurait recopié le défaut ; il est corrigé en le reprenant,
   avec un repli sur l’ancien format et cinq cas éprouvés.

🔴 **Le compte final se vérifie**, capacité par capacité, avant de supprimer
l’écran absorbé. C’est le seul moment où la perte est encore réversible.

### L’administration est UNE page — plus aucun écran autonome

Arbitré à l’écran le 19/08/2026 : *« fiche copropriété et Périmètre sont des pages
autonomes alors que les autres sont intégrées au menu Paramétrage : uniformise cela,
cela évitera le retour que je t’ai demandé »*.

🔴 **Un écran d’administration est un ONGLET de `admin/+page.svelte`, jamais une
route.** Les sept qui vivaient sur `/admin/<écran>` — fiche copropriété, périmètres,
audit lots, les trois imports, designs d’e-mail — sont devenus des composants
`Onglet*.svelte`. On ne quitte plus Paramétrage : le bouton « ← Retour » posé la
veille n’avait plus d’objet, et il a disparu.

| Ce qui fait foi | Où |
|---|---|
| la liste des onglets | `const ONGLETS = [...] as const` — **une seule**, elle sert au type ET à `?onglet=` |
| l’ouverture directe | `/admin?onglet=perimetres` — remplace les sept URL supprimées |
| le panneau | un composant `Onglet*.svelte`, jamais du balisage dans la page |

⚠️ **Trois listes doivent concorder** : `ONGLETS`, les boutons `<Onglet actif={onglet
=== …}>`, et les blocs `{:else if onglet === …}`. Un onglet déclaré sans bouton est
inatteignable ; sans rendu, il affiche une page vide ; employé hors de la liste, il ne
s’ouvre pas par l’URL. **Les trois sont silencieux** — `npm run lint:routes` les
refuse, et il a été vu échouer sur chacun.

⚠️ **Un lien vers un écran d’admin s’écrit `/admin?onglet=<clé>`.** Un modèle
d’e-mail pointait encore vers `/admin/telecommandes-import` : `test_liens_front.py`
l’a attrapé — sans lui, le destinataire du message « Vérifier les imports » serait
tombé sur une 404.

### L’anatomie d’un écran d’administration

Arbitré à l’écran le 19/08/2026 : *« l’écran WhatsApp n’est pas très beau, fais
ressortir les sections, on s’y perd visuellement »*, puis *« uniformise les
en-têtes avec la possibilité d’un retour »*, *« uniformise le footer »*, *« le look
des formulaires ne correspond pas à l’UX »*.

Chaque fois, le motif **existait déjà** et n’était pas employé. C’est la forme la
plus coûteuse du défaut : on croit avoir une charte, on a des copies.

| Élément | Le motif | Il était écrit à la main… |
|---|---|---|
| en-tête de page | `EntetePage` + `retour="/admin"` | 4 écrans sur 8, dont un **sans aucun retour** |
| bloc | `<section class="card config-section">` | `.config-section` n’avait **aucun fond** |
| sous-section | `SectionFormulaire` (+ `icone`) | un `<p>` gris gras, **16 fois**, et un `<hr>` **8 fois** |
| barre d’actions | `.form-actions` | **13 fois** en style en ligne, avec **4 marges différentes** |
| pied de modale | `.modal-footer` | 4 en ligne, 2 sous `.modal-actions` — **définie nulle part** |

🔴 **Le fond du champ est le BEIGE, celui de la carte est le BLANC.** Une couleur,
un rôle : le champ se lit comme un creux dans la carte. Cela n’a de sens que si
la carte est franchement blanche — les blocs d’admin étaient posés à même le fond
de page, qui est **le même beige que les champs**, si bien qu’un champ n’avait plus
que sa bordure pour exister. ⚠️ Ce beige n’avait jamais été décidé : `app.css`
portait `.field input` **deux fois**, une version blanche et une beige, et c’est
l’ordre de la cascade qui tranchait (#413).

⚠️ **Pas d’émoji dans un titre de section ni de bloc** : le tracé vient du
catalogue partagé `$lib/icones-svg.json`, via `icone` sur `SectionFormulaire` ou
`<Icon>` sur `.config-section-title`. Un émoji dépend de la police du système ;
l’en-tête de page prenait déjà ses tracés dans le catalogue — deux façons de
désigner une section, dont une seule est stable.

⚠️ **`.form-actions` n’est pas `.modal-footer`.** La première soumet un
formulaire, la seconde ferme une boîte de dialogue — et `lint:soumission` ne
regarde que la première, à raison : « Confirmer » est le bon verbe pour une
confirmation, « Enregistrer » pour une soumission.

### 9 bis. Ce qui décide de la largeur d'un champ, c'est son CONTENU

Les grilles (`.form-grid`) répartissent en colonnes de ~180-200 px. C'est juste
pour un champ **court** — date, montant, statut, fréquence — et faux pour tout le
reste : un titre y est écrasé dans le tiers le plus étroit, et un sélecteur de
périmètre y empile ses dix pastilles **une par ligne**, description comprimée.

**Ces champs prennent la LIGNE ENTIÈRE — `class="champ-large"` (app.css) :**

| Champ | Pourquoi |
|---|---|
| **Titre**, **Libellé** | texte libre, souvent long |
| **Description**, **Contenu**, **Notes** | éditeur riche, plusieurs lignes |
| **Périmètre** | pastilles + second niveau + description du nœud |
| **Destinataires** | pastilles de profils |

La classe se pose **sur le champ**, jamais sur la grille : c'est le contenu qui
décide de sa largeur, pas l'écran qui l'accueille.

**Why (16/08/2026)** : signalé **trois fois de suite** par l'utilisateur, sur trois
écrans différents — prestation, contrat, puis calendrier. Même défaut à chaque fois,
et chaque fois trouvé à l'œil après livraison.

### 9 ter. L'ordre est toujours : **Périmètre, puis Destinataires**

Le périmètre dit *de quoi* il s'agit, les destinataires *à qui* on l'adresse — le
premier cadre le second. Un écran qui les inverse fait relire deux fois.

### 9 quater. Le badge d'état à côté du libellé

Quand un sélecteur multiple a un défaut ou une sélection résumable, il porte un
**badge** à droite de son libellé : `Profils destinataires [Tous]`,
`Périmètre [Toute la résidence]`. On lit l'état sans dépiler les pastilles.
Inauguré par le sondage ; l'utilisateur a demandé de l'étendre au **standard** —
donc à `PerimetrePicker` et au sélecteur de destinataires, partout.

### 9 sexies. L'ORDRE des champs est imposé — il ne se discute pas par écran

| # | Section |
|---|---|
| 1 | **Titre** |
| 2 | **Champs spécifiques** à la page |
| 3 | **Workflow** — si l'objet en a un |
| 4 | **Périmètre** |
| 5 | **Destinataires** |
| 6 | **Description** |
| 7 | **Photos** |
| 8 | **Documents** |
| 9 | **Diffusion** |

**Workflow et Diffusion sont deux notions distinctes**, et les confondre est
l'erreur qui a fait poser la question :

| | Workflow | Diffusion |
|---|---|---|
| Répond à | *où en est cet objet ?* | *qui le voit, et où ?* |
| Contient | Ouvert / En cours / Résolu (ticket), Suivi Kanban (événement, prestation) | affichage au fil, épinglage, WhatsApp, syndic, conseil syndical, Publié / Brouillon |
| Se place | **avant** le Périmètre — c'est un champ spécifique de l'objet | **en fin**, après les documents |

🔴 **Le KANBAN du calendrier EST un workflow** (18/08/2026). Ses six colonnes —
AG · CS · Syndic · Prestataire · Terminé · Annulé — répondent exactement à *« où
en est cet objet ? »*. La section s'appelle donc **Workflow**, et non « Suivi
Kanban » : ce dernier nommait l'écran où on le voit, pas la notion. **Aucun
second champ d'état n'a été créé** — deux notions de suivi sur le même objet se
contredisent au premier écart, et rien ne dirait laquelle fait foi.

Corollaire : **un changement de colonne est une transition tracée**, avec son
avant et son après dans l'Historique ; toute autre modification reste une
correction. Le calendrier était le dernier écran du site à faire avancer un suivi
en silence.

🔴 **Ce qu'une entrée d'Historique ENVOIE parle d'ELLE** (18/08/2026). Rouvrir
la Diffusion sur un suivi ne suffit pas : il faut recâbler ce qui part. Le lot
de la veille avait ouvert la section et laissé l'appel existant — le groupe
WhatsApp recevait donc la description de l'ÉVÉNEMENT à chaque commentaire, le
même texte indéfiniment, et l'e-mail attachait les pièces de l'événement au
lieu de celles de l'entrée.

⚠️ **C'est le défaut typique de l'ajout d'un canal à une entité existante** :
on reprend l'appel qui marche, et l'appel qui marche parle de l'objet porteur.
Rien ne lève, rien ne manque dans les journaux — le message part, il est
simplement faux. Trois questions à se poser, dans cet ordre :

1. **le contenu** — texte de l'entrée, pas de l'objet ;
2. **les pièces** — celles de l'entrée, avec repli sur l'objet si elle n'en a
   pas (même règle que `flux/tickets.py`) ;
3. **le renvoi** — un commentaire se lit hors contexte : le message porte un
   lien vers l'objet, sinon le lecteur ne sait pas sur quoi il porte.

🔴 **Et le FIL doit apprendre la nouvelle table.** Le fil est une douzaine de
rubriques indépendantes ; rien n'oblige une table neuve à s'y déclarer.
`flux/evenements.py` ne lisait que `Evenement` et datait donc ses cartes de
l'annonce — une affaire qui avançait aujourd'hui restait noyée dans les
vieilles lignes. **Le fil date du dernier fait, jamais du premier.**

⚠️ Ajouter un TYPE pour la mise à jour aurait été le réflexe (c'est ce que font
les tickets, avec trois types). **Ne pas le faire ici** : le front teste
`type === 'evenement'` à six endroits — libellé, couleur, fond, lien, urgence,
et le filtre du tableau de bord qui **masque les AG** à qui n'y a pas droit. Un
type neuf serait passé à côté des six, et une AG commentée serait devenue
visible de tous, en silence. **C'est la donnée qui porte la différence** :
`evol_contenu` présent ⇒ la carte rend le bloc de suivi.

### 9 septies. Les sections 4 à 9 ne se réécrivent plus : `ChampsCommuns.svelte`

**L'ordre ci-dessus a un point d'héritage depuis le 16/08/2026.** Périmètre,
Destinataires, Description, Photos, Documents et Diffusion sont rendus par UN
composant, qui porte leur ordre, leurs intitulés et leurs séparations
(`SectionFormulaire`). Un écran déclare ce qu'il a, jamais où le mettre :

```svelte
<ChampsCommuns
  idPrefixe="ticket"
  avecPerimetre bind:perimetre={perimetreCible}
  avecDescription descriptionRequise bind:description
  avecPhotos bind:photos={photosUrls}
  avecDocuments bind:documents={fichiersUrls}
  avecDiffusion bind:whatsapp bind:syndic bind:cs
>
  <svelte:fragment slot="diffusion">…options propres à l'écran…</svelte:fragment>
</ChampsCommuns>
```

Les sections **1 à 3** (Titre, champs spécifiques, Workflow) restent dans l'écran :
lui seul sait ce qu'elles portent.

#### Une section à UN seul champ ne répète pas son nom

Première livraison, l'écran affichait :

```
PÉRIMÈTRE
Périmètre *                            [Copropriété entière]
```

Le nom deux fois, en deux typographies — signalé par l'utilisateur, capture à
l'appui, **le jour même de la mise en production**. La cause est mécanique :
`PerimetrePicker`, `DestinatairePicker` et `FichiersUpload` portent chacun leur
intitulé (c'est justement leur point d'héritage, §9 quater), et la section en
ajoutait un second.

**Règle** : quand une section ne contient qu'un champ, le **titre de section EST
le libellé**. Il porte l'astérisque (`requis`) et le badge d'état (`badge`) ; le
champ reçoit `titre=""` et n'écrit plus rien.

```
PÉRIMÈTRE *                            [Copropriété entière]
```

Les sections à **plusieurs** champs (Détails, Clôture, Diffusion) gardent leur
titre de groupe **et** les libellés de leurs champs : ce n'est pas une redite,
c'est une hiérarchie.

⚠️ **Le titre de section est un vrai libellé, donc il s'associe.** `SectionFormulaire`
rend un `<label for>` quand la section porte un contrôle **labelable** (`<select>`,
`<input>`) — prop `pour` —, et un `<h4 id>` sinon, l'appelant reliant son groupe par
`aria-labelledby` (prop `idTitre`). Les pastilles et l'éditeur riche ne sont PAS
labelables : un `for` posé dessus n'associe rien, **et le fait en silence**. C'est
d'ailleurs ce qui existait avant — `Périmètre *` était un `<div>`, donc un groupe de
boutons sans nom pour un lecteur d'écran.

Corollaire appliqué au passage : le `(max N)` a quitté l'intitulé des pièces
jointes. Le compteur `0/N` sous le bouton le dit déjà, et il le dit mieux — il se
met à jour. Les types acceptés sont en aide grise à côté du compteur, déduits
d'`ACCEPT_DOCUMENTS` et non récités.

**Why.** L'ordre était écrit, `SectionFormulaire` savait séparer — et les six
formulaires recomposaient quand même la suite à la main. L'utilisateur l'a
signalé ainsi : *« Les objets ont l'air d'être dupliqués, pas instanciés, car ils
diffèrent selon les pages. »* Relevé avant correction :

| Notion | Ce qui divergeait |
|---|---|
| Description | « Description » / « Description * » / « Notes » ; hauteur 60, 80, 90, 100 ou 120 px |
| Documents | `FichiersUpload` sur tickets et calendrier, `<input type="file">` **nu** sur actualités et prestations |
| Diffusion | aucune section nommée sur **4 écrans sur 6** |
| Ordre | Périmètre au milieu de la grille des champs spécifiques (prestations) ; Kanban rangé dans la diffusion (calendrier) ; « Saisi pour » **après** les pièces jointes (tickets) |

Aucune n'était voulue : ce sont les six recopies qui les produisent. La seule
façon de ne pas les voir revenir est qu'un seul endroit les écrive.

⚠️ **Une rubrique dont le parent n'existe pas encore** (documents d'actualité,
fichiers de prestation : leur endpoint réclame l'identifiant) passe par le mode
**différé** de `FichiersUpload` — `documentsDifferes` + `bind:documentsFichiers`.
L'écran téléverse après création. Ne PAS retomber sur un `<input type="file">`
nu : c'est ce qui produisait la deuxième apparence.

### 9 octies. Jamais de sélecteur d'ÉLÉMENT nu dans un composant

`input`, `textarea`, `select`, `button`, `label` seuls, dans un `<style>` de page
ou de composant : **interdit**, et refusé par `npm run lint:styles`.

**Why.** `sondages/+page.svelte` portait `input, textarea { width: 100% }`. Le
sélecteur visait les champs de saisie et atteignait **toutes les cases à cocher
de la page** : chacune s'étirait sur la largeur du formulaire et repoussait son
libellé à l'autre bout. L'utilisateur l'a signalé sur **deux écrans distincts**
(« Nouveau sondage » et « Déposer une annonce »), sans lien apparent entre eux —
c'était une seule ligne. Quatre composants annulaient déjà ce genre de règle case
par case avec un `style="width:auto"` recopié : le signe qu'on soignait le
symptôme.

Qualifier le sélecteur (`.case input[type="checkbox"]`) ou porter la règle dans
`app.css`, où elle est globale et assumée.

### 9 quinquies bis. Le bouton de soumission dit **« Enregistrer »**, partout

Verbe **générique**, sur tous les formulaires de création. Arbitré par
l'utilisateur le 17/08/2026 (#396), après un relevé de sept formulaires portant
**six** libellés — « Publier » / « Enregistrer brouillon », « Envoyer la demande »,
« Créer le sondage », « Publier l'annonce », « Soumettre », « Enregistrer » — plus
« Soumettre la demande » sur accès & badges, que le relevé du ticket avait manqué.

Aucun n'était faux ; l'ensemble n'avait pas de logique.

| | |
|---|---|
| au repos | `Enregistrer` |
| pendant l'envoi | `Enregistrement…` |

L'état d'attente est **inclus dans la règle** : il divergeait pareillement
(« Envoi… », « Création… », « Sauvegarde… », et même « … » tout court). C'est le
même libellé, vu pendant la seconde où l'utilisateur se demande si son geste a été
pris.

⚠️ **Le mode brouillon ne se dit plus dans le bouton.** L'actualité affichait
« Enregistrer brouillon » ou « Publier » selon la case cochée — or cette case est
déjà visible dans la section Diffusion, juste au-dessus. Le bouton la répétait.

**Hors périmètre, et volontairement** : les écrans d'authentification
(« Se connecter », « Créer mon compte »), les imports (« Importer ») et le
changement de mot de passe. Ce ne sont pas des créations d'objet.

**Garde-fou** : `npm run lint:soumission` (job `build-frontend`), sur les
composants `Formulaire*.svelte`. Les exceptions sont nommées avec leur raison et
le contrôle échoue si l'une devient inutile.

### 9 quinquies. Le bouton de soumission est **à droite**, via `.form-actions`

`.form-actions` (app.css) porte `justify-content: flex-end`. Un bouton posé nu dans
un `<form>` se cale à **gauche** et détonne : c'était le cas des sondages (« Créer
le sondage », « Publier l'annonce », « Soumettre » d'une idée), seuls de tout le
site, jusqu'au 16/08/2026. Ne jamais écrire un bouton de soumission hors de
`.form-actions`.

> ⚠️ **Question de nommage ouverte** (posée le 16/08/2026, non tranchée) : unifier
> **Libellé → Titre** et **Notes / Contenu → Description** ? C'est une décision
> fonctionnelle qui touche les libellés vus par les résidents, pas un renommage
> de classe.

## 10. Fil d'évolutions

Structure pour les tickets/publications avec historique :

- `.evol-list` : border autour, séparateurs `<hr class="evol-sep">`
- `.evol-item` : `.evol-icon` + `.evol-body` (`.evol-meta` + `.evol-text`)
- Pagination : si > 7 → afficher 5 + bouton `.evol-more`
- Formulaire inline : pills type + textarea + select statut → `.evol-form`

### 10 bis. Le workflow d'un objet : UNE liste, et UN geste par écran

**Les états proposables ne s'écrivent jamais dans un écran.** Pour un ticket, ils
viennent de `$lib/tickets` (`STATUT_TICKET_OPTIONS`, `…_LABELS`, `…_BADGE`,
`STATUTS_TICKET_FILTRE`, `estTicketActif`, `estTicketClos`), qui répond à
`StatutTicket` côté serveur. `api/tests/test_statuts_tickets.py` échoue sur toute
liste réécrite — y compris dans un fichier qui importe déjà le module.

**Où se change l'état :**

| Écran | Geste |
|---|---|
| `/tickets`, `/espace-cs` (listes) | formulaire d'évolution — état **et** commentaire en un envoi |
| `/tickets/[id]` (fiche) | **boutons** « Changer le statut », un clic ; le formulaire n'y sert qu'au commentaire |

La fiche portait **les deux**, à quelques centimètres l'une de l'autre, et elles
ne proposaient pas les mêmes états (#415). Un geste, un endroit : quand deux
commandes font la même chose sur un écran, ce n'est pas une commodité, c'est une
question posée à l'utilisateur — et deux occasions de diverger.

⚠️ `EvolForm` masque sa rangée de pastilles quand `statutOptions` est vide : un
choix à un seul choix n'est pas un choix.

**Ce qui a rendu la divergence invisible** : les cinq listes relevées étaient
chacune cohérente avec elle-même. Deux listes d'accord entre elles ne prouvent
rien — le seul contrôle qui vaille compare ce que l'écran **propose** à ce que
l'endpoint **accepte**.

## 11. Vignette & galerie de photos

Composants partagés. **Ne pas recréer** de `.xxx-thumb`, de rangée de photos ad hoc,
ni de visionneuse : `PiecesJointes` était déjà réécrit à l'identique dans quatre pages,
chacune avec sa propre expression régulière pour décider ce qui est une image.

| Composant | Rôle | Props |
|---|---|---|
| `$lib/components/PiecesJointes.svelte` | **affichage en lecture seule** d'une liste de pièces jointes (photos + documents) | `urls`, `size`, `compact`, `format` |
| `$lib/components/Lightbox.svelte` | visionneuse plein écran | `photos`, `index` · événement `fermer` |
| `$lib/components/Vignette.svelte` | vignette carrée (brique de bas niveau) | `src`, `alt`, `placeholder`, `count`, `size`, slot d'actions |
| `$lib/components/PhotosUpload.svelte` | galerie **éditable** | `urls`, `max`, `readonly`, `upload`, `remove` |
| `$lib/components/FichiersUpload.svelte` | **saisie** de pièces jointes ; `differe` retient les `File` quand le parent n'existe pas encore | `urls`, `fichiers`, `differe`, `mode`, `max`, `titre` |

Le téléversement est **délégué par callback** : chaque rubrique garde son propre
endpoint, le composant ne connaît pas l'API. La règle « qu'est-ce qu'une image, et
quel nom afficher » vit dans `$lib/fichiers.ts` (`separerFichiers`, `nomFichier`) —
jamais réimplémentée dans une page.

### Quel `format` de `PiecesJointes` — la vignette ne répond pas à la même question

| `format` | Où | Pourquoi |
|---|---|---|
| `'vignette'` (défaut) | là où l'on **survole** : listes, fils de messages | signale « il y a une photo » sans casser le rythme de lecture |
| `'grand'` | là où l'on a **demandé à voir** : fil déplié, annonce dépliée, fiche ticket, **et le fil d'évolutions** | l'utilisateur vient de déplier ; lui laisser un timbre-poste de 72 px lui impose un clic de plus pour ce qu'il demande |

🔴 **Le fil d'évolutions est passé de `'vignette'` à `'grand'` le 18/08/2026**, sur
constat à l'écran — ce tableau le rangeait du premier côté, avec un argument juste
mais mal appliqué. Un fil d'Historique ne s'atteint qu'en **dépliant** une carte :
quand on l'a sous les yeux, on a déjà demandé à voir. Et sur un événement de
calendrier, les photos du suivi sont **tout le contenu** (« voici les anomalies
relevées ») — elles étaient réduites à trois timbres-poste là où le même dossier,
en ticket, les montrait en grand avec son compteur « 1 / 3 ».

Le critère ne change pas : *survole-t-on, ou a-t-on demandé à voir ?* C'est son
application à ce cas qui était fausse.

### L'aperçu replié se REPLIE sur l'Historique (18/08/2026)

Quand l'objet ne porte aucune pièce mais que son Historique en porte, la carte
repliée montre celles de l'entrée **la plus récente** — `apercuAvecRepli()`
(`$lib/fichiers.ts`).

**Why** : un événement de calendrier n'a le plus souvent aucune photo propre, c'est
le suivi qui en apporte. Sa carte restait donc nue là où un ticket illustré montre
sa vignette d'un coup d'œil. La règle du repli existait déjà dans l'autre sens —
ce qu'une entrée diffuse porte ses pièces, « avec repli sur l'objet si elle n'en a
pas » (`flux/tickets.py`) — et elle suit la même logique que le fil, qui **date du
dernier fait, jamais du premier**.

⚠️ **Aucun chargement déclenché** : la fonction ne sert qu'aux écrans dont l'API
livre déjà l'Historique avec l'objet (calendrier : `EvenementRead.evolutions`). Les
**tickets** chargent leurs évolutions à la demande, au dépliage — les réclamer en
liste coûterait une requête par carte. C'est un changement d'API, suivi à part.

Le grand format **ne coûte aucun octet** : il n'existe pas de miniature côté serveur,
les photos sont réduites à 1600 px / JPEG q85 au téléversement, et la vignette
téléchargeait déjà ce fichier-là pour l'afficher en 72 px.

⚠️ **`object-fit: contain` en grand format, jamais `cover`.** Une photo portrait dans
un cadre carré perd ses bords haut et bas — sur un dégât des eaux, précisément ce
qu'on cherchait à montrer. `cover` reste correct pour la vignette, où l'on ne cherche
qu'à signaler la présence d'une image.

### Ce que la visionneuse impose (v2.42.0)

- **Un clic sur une photo n'ouvre jamais un onglet.** L'ancien `<a target="_blank">`
  sortait de la PWA vers le fichier brut, et le retour ramenait sur une page dont
  l'article s'était refermé — le geste le plus coûteux de l'écran, sur mobile surtout.
- **Le verrou de défilement est un état global** : fonction idempotente appelée depuis
  *chaque* sortie (fermeture, `Échap`, clic sur le fond) **et** depuis `onDestroy` —
  l'utilisateur peut naviguer ailleurs sans jamais fermer la visionneuse, et la page
  d'arrivée resterait figée jusqu'au rechargement. Cf. `standards/11-interface-et-ux.md`
  §12, et l'incident du 04/08/2026 qui est exactement ce cas.
- `Échap` ferme, les flèches naviguent, le compteur suit ; cible tactile **≥ 44 px**
  sur le bouton de fermeture — mesurée, pas supposée : la relecture avait laissé
  passer un bouton à 40 px, trouvé en mesurant dans un navigateur à 375×812.

## 12. Visibilité du Kanban (calendrier + widget tableau de bord)

Filtre des colonnes : `if (col.id === 'ag' || col.id === 'cs') return canSeeAG;`

| Colonne | Locataire | Copropriétaire | CS / Admin |
|---|---|---|---|
| AG | ✗ | ✓ | ✓ |
| CS | ✗ | ✓ | ✓ |
| Syndic | ✓ | ✓ | ✓ |
| Prestataire | ✓ | ✓ | ✓ |
| Terminé | ✓ (affichables) | ✓ (affichables) | ✓ (tout) |
| Annulé | masqué dashboard | masqué dashboard | masqué |

Items non-affichables : masqués aux non-CS/admin, sauf `maintenance_recurrente`.

## 13. En-tête de page — `EntetePage.svelte`, une seule écriture

**Ne jamais rendre `<div class="page-header">` à la main.** Le composant porte le
conteneur, le titre (icône + libellé + taille), le retour et la zone d'actions :

```svelte
<EntetePage titre={_pc.titre} icone={_pc.icone || 'newspaper'}>
  {#if $isCS}<button class="btn btn-primary page-header-btn">+ Nouvelle publication</button>{/if}
</EntetePage>
```

| Prop | Rôle |
|---|---|
| `titre` | obligatoire |
| `icone` | nom Lucide du catalogue `$lib/icones-svg.json` |
| `retour` | href — affiche `← Retour` **à gauche du titre** |
| ~~`marge`~~ | **retirée le 17/08/2026** — voir ci-dessous |
| slot par défaut | les actions, **à droite** |

**Disposition, la même partout** : `[retour] titre` à gauche · actions à droite.

⚠️ **Vérifier que l'icône existe** dans `$lib/icones-svg.json` : `Icon` retombe
**silencieusement** sur `help-circle` pour un nom inconnu. `message-square-plus`
n'existe pas et aurait affiché un point d'interrogation sans qu'aucun contrôle ne
le dise (constaté le 15/08/2026).

**Garde-fou** : `npm run lint:entetes` (job `build-frontend`) refuse un
`class="page-header"` écrit à la main, une redéfinition locale de `.page-header`,
et un `<h1>` portant `font-size` en ligne. Les exceptions sont **nommées avec leur
raison** dans le script, et le contrôle échoue si l'une devient inutile.

**Dette soldée le 17/08/2026 — la marge d'en-tête vaut `1.5rem`, sans exception.**

`marge` existait parce que **six** écrans divergeaient : `0` (FAQ), `.5rem`
(espace CS, prestataires), `.75rem` (délégations, résidence), `1rem` (calendrier),
contre `1.5rem` partout ailleurs. Centraliser les valeurs les avait rendues
explicites **sans les réduire** — la dette était nommée ici, et elle a duré.

Le symptôme se voyait : en passant d'`/actualites` à `/calendrier`, le titre et le
bouton **sautaient** de quelques pixels, alors que les deux pages utilisent le même
composant (#372). Arbitré par l'utilisateur : la valeur du plus grand nombre gagne.

**La prop n'existe plus.** C'est le point important : la laisser en place aurait
invité la septième valeur. Un écran qui aurait vraiment besoin d'autre chose doit
d'abord expliquer pourquoi lui — pas recevoir une prop qui rouvre les six.

⚠️ Le retrait a fait **échouer `lint:entetes`**, dont le cas zéro exige que
`EntetePage` expose ses props connues. C'est voulu : son message dit « le contrat a
changé — mettre ce contrôle à jour ». Un garde-fou qui n'aurait rien dit aurait
laissé passer une prop disparue, et donc laissé le contrôle vérifier un contrat
imaginaire.

> **La leçon, générale** : nommer une divergence ne la corrige pas. Centraliser
> six valeurs dans une prop les rend lisibles et **pérennes**. Tant que le
> mécanisme d'exception existe, l'exception se reproduit.

**Pages de détail** (`tickets/[id]`, `sondages/[id]`) : elles n'ont **pas**
d'en-tête de page — leur `<h1>` est le titre de l'objet, dans sa carte. Ne pas les
convertir mécaniquement : ce qu'il faut y mettre est instruit dans #365.

## 13 bis. 🔴 LE MODE SE LIT SUR L'ICÔNE QUI L'A OUVERT

**Corrigé le 18/08/2026, le soir même où la règle inverse avait été posée.**
Ce paragraphe disait : *« tout formulaire porte un titre, et c'est lui qui dit
le mode »*. Le diagnostic d'origine était bon — le mode ne se lisait nulle part,
signalé ainsi : *« on ne sait pas si on est en mode édition, en mode suivi »* —
mais le remède était mauvais, et l'écran l'a dit :

> « les titres d'état je ne trouve pas ça beau : je mettrais l'icône concernée
>   en plus gros ou inversée pour supprimer ce pseudo état qui éloigne du titre »

Un titre au-dessus du formulaire ajoute un **second en-tête** sous celui de la
carte : il repousse le contenu et éloigne le formulaire de l'objet auquel il se
rapporte. Le bon endroit pour dire « vous êtes en train de commenter » n'est pas
au-dessus du formulaire, c'est **sur l'icône qui l'a ouvert** — elle est déjà là,
déjà regardée, et son inversion se lit sans être lue.

### La règle

| Où | Ce qui dit le mode |
|---|---|
| formulaire **encadré** (création) | son titre : c'est l'en-tête de SA carte, pas un doublon |
| formulaire **dans la carte d'un objet** | l'icône qui l'a ouvert, **inversée** |

```svelte
<button class="btn-icon" aria-pressed={mode === 'evolution'} …>🔄</button>
<button class="btn-icon" aria-pressed={mode === 'edition'} …>✏️</button>
```

Le style vit dans `app.css`, une seule fois : fond plein en couleur primaire,
glyphe blanc, `scale(1.15)`. ⚠️ **Un simple changement de teinte ne suffit pas** :
il ne se distinguerait pas du survol, et l'on ne saurait plus si l'icône est
active ou seulement pointée.

⚠️ **`aria-pressed`, et non une classe.** L'état est alors annoncé par les
lecteurs d'écran en même temps qu'il se voit, aucun écran n'a de classe de plus à
penser — et un bouton bascule doit le porter de toute façon.

⚠️ **Le titre ne disparaît pas, il devient invisible** : `FormulaireCreation` le
passe en `aria-label` sur le groupe. Qui ne voit pas l'icône entend toujours
« Modifier le commentaire » en entrant dans le formulaire.

⚠️ `encadre` garde son autre rôle : à `false`, pas de carte imbriquée — deux
bordures pour un seul objet, c'est la « carte dans la carte » de #425. C'est le
composant qui décide, jamais l'écran.

## 14. Formulaire de création — `FormulaireCreation.svelte`, une boîte dans la page

**Un seul paradigme sur tout le site : la boîte dans la page.** Les actualités
sont le modèle, désigné par l'utilisateur.

```svelte
<EntetePage titre={_pc.titre} icone={_pc.icone} alignerSaisie={showForm}>
  {#if $isCS}
    <button class="btn btn-primary page-header-btn" on:click={() => (showForm = !showForm)}>
      {showForm ? '✕ Annuler' : '+ Nouvelle publication'}
    </button>
  {/if}
</EntetePage>

{#if showForm}
  <FormulaireCreation titre="Nouvelle publication">
    <form on:submit|preventDefault={creer}> … </form>
  </FormulaireCreation>
{/if}
```

**Ce qui était faux avant le 15/08/2026** (#367), et que l'utilisateur a dû
signaler **trois fois** :

- **trois paradigmes** pour la même intention — boîte (actualités, sondages),
  modale (calendrier, prestataires, accès & badges, fiche sondage), page dédiée
  (nouveau ticket) ;
- le bouton d'annulation **excentré** : il se posait au bord droit de l'ÉCRAN
  alors que la boîte s'arrête à 720 px ;
- sur le calendrier, **deux** commandes d'annulation — la croix de la modale et
  le bouton d'en-tête, ce dernier sous l'overlay, visible et inutilisable.

### Les trois règles

1. **La commande d'annulation reste dans l'en-tête**, où le bouton d'ouverture
   bascule en « ✕ Annuler ». Ne PAS en ajouter une seconde dans la boîte.
2. **`alignerSaisie={showForm}` sur `EntetePage`** dès qu'un formulaire s'ouvre
   dans la page — sans lui le bouton flotte loin de ce qu'il annule.
3. **Jamais de modale pour un formulaire de CRÉATION.** Les modales restent
   légitimes pour une confirmation, un téléversement ponctuel, la visionneuse —
   et, depuis le 30/08/2026, pour l'**édition** (voir §14 bis).

### 🔴 14 bis. LA MODALE EST LE FORMAT STANDARD D'ÉDITION (30/08/2026)

Arbitré à l'écran : *« d'une manière générale, je trouve qu'en édition le format
modal est plus net que le dépliement sur une même fenêtre. Mets dans l'UX que la
modale est le format standard d'édition et corrige partout. »*

| Geste | Format |
|---|---|
| **Créer** | la **boîte dans la page** — `FormulaireCreation`, §14 ci-dessus |
| **Éditer** un objet existant | **la modale** — `Modale`, qui porte titre, croix, `Échap` et verrou |

**Pourquoi la distinction tient** — elle n'est pas un compromis :

- une **création** part d'une page vide et s'inscrit dans le flux de l'écran : la
  boîte montre où l'objet va atterrir, et le bouton d'en-tête bascule en
  « ✕ Annuler », sans double commande ;
- une **édition** interrompt une lecture. Déplier un formulaire au milieu d'une
  liste déplace tout ce qui est en dessous, et l'on perd de vue l'objet qu'on
  modifie. La modale isole le geste et le referme sans rien décaler.

⚠️ **Ce que ce renversement ne remet PAS en cause.** #367 avait été arbitré après
que l'utilisateur l'ait signalé **trois fois**, et ses trois constats restent
vrais : pas de **double commande** d'annulation (celle du calendrier vivait sous
l'overlay, visible et inutilisable), pas de bouton **excentré**, et surtout pas
**trois paradigmes** pour une même intention. La règle passe de « un format pour
tout » à « un format par geste » — deux, nommés, et pas un de plus.

🔴 **Le garde-fou change de forme, il ne disparaît pas.** `lint:formulaires`
refusait toute modale contenant un `<form>`. Il doit désormais distinguer les
deux gestes, et **une modale de création reste refusée** — sans quoi la règle
redevient « au cas par cas », c'est-à-dire les trois paradigmes de #367.

⚠️ **R5 s'applique** : l'enrichissement se propose sur **UN** écran, se fait
constater, puis se généralise. La conversion ne se fait donc pas d'un bloc sur
les dix écrans concernés.

**Garde-fou** : `npm run lint:formulaires` (job `build-frontend`). Il refuse un
cadre `card largeur-saisie` enveloppant un `<form>`, et toute modale contenant un
`<form>`. Il a trouvé **deux écrans que l'audit manuel avait manqués**.

**Reste à traiter — `prestataires`**, déclaré en exception : quatre formulaires
encore en modale dans un fichier de 2 182 lignes qui doit d'abord être découpé, et
un écart de fond — le périmètre y est une **chaîne** dans un `<select>` là où
`PerimetrePicker` travaille sur un tableau. C'est un changement de contrat, pas un
remplacement de composant.

## 15. DROITS — qui peut éditer, qui peut commenter (18/08/2026)

| Geste | Qui |
|---|---|
| **✏️ éditer** le contenu | l'auteur · le « saisi pour » · l'admin |
| **🔄 commenter** et faire avancer le workflow | les mêmes **+ le conseil syndical** |

> « Seul l'auteur peut l'éditer ou le commenter, avec l'admin (en cas de Pb),
>   mais aussi le CS peut commenter, pas éditer »

🔴 **« Saisi pour » compte comme auteur**, et c'est la raison d'être du champ :
un membre du CS qui dépose un ticket au nom d'un résident ne le dépossède pas de
sa demande. Avant, ce résident était le **seul** à ne pas pouvoir corriger ce qui
parle de lui — pendant que n'importe quel membre du CS le pouvait.

Les deux règles vivent dans `auth/deps.py` (`peut_editer`, `peut_commenter`),
jamais dans un routeur ni dans un écran. `test_droits_editer_commenter.py` les
verrouille.

⚠️ **L'écran doit dire la même chose que le serveur, ni plus ni moins.** Un
bouton affiché plus largement que le droit produit un 403 sur un geste que
l'interface a elle-même proposé ; plus étroitement, il rend une capacité
introuvable. Les deux sont arrivés le même jour dans `RubriqueHistorique`.
## 16. WORKFLOW & ARCHIVAGE — ce qui a des étapes, et ce qui se range tout seul

🔴 **Trois questions distinctes**, que le produit a confondues jusqu'au 18/08/2026 :

| Question | Réponse |
|---|---|
| l'objet a-t-il des **étapes ordonnées franchies par plusieurs** ? | alors il a un **workflow** (section 3) |
| ces mouvements doivent-ils **laisser une trace** ? | c'est une **AUTRE** décision — l'annonce a cinq états et aucun fil |
| quand disparaît-il de la liste ? | **calculé**, jamais choisi — voir plus bas |

⚠️ Le test n'est pas « y a-t-il un champ `statut` ? ». Trois entités en portent un
et une seule a un workflow tracé. Confondre les deux fait importer un
`RubriqueHistorique` par réflexe sur un objet qui n'a rien à raconter.

### L'archivage se CALCULE, il ne se choisit pas

**30 jours** après l'entrée dans un état **terminal** — mesuré sur
`statut_change_le`, **jamais** sur `mis_a_jour_le`. *Annulé* disparaît
**immédiatement**. **Aucun bouton 📦.**

⚠️ `mis_a_jour_le` paraît équivalent et ne l'est pas : corriger une faute de
frappe sur un objet conclu **repousserait son archivage d'un mois**, à chaque
retouche. `Publication` porte `statut_change_le` pour exactement cette raison,
et les tickets mesuraient encore sur `mis_a_jour_le` au 18/08.

⚠️ Un bouton d'archivage crée **deux notions pour la même chose** — celle qu'on
pose et celle qui arrive — libres de se contredire dès qu'on rouvre l'objet.
L'archivage n'est pas une étape : c'est une conséquence du temps.

🔴 **Calculé côté SERVEUR**, transporté dans un champ `archivee`. Jamais
recalculé par un écran : sinon la liste et l'Historique tranchent différemment,
et c'est le bug du 17/07/2026 sur les actualités — un élément visible dans une
vue et pas dans l'autre.

🔴 **Une actualité n'a pas de workflow, et c'est définitif** (ré-arbitré le
18/08/2026, après l'avoir ouvert la veille). Elle n'a pas d'étapes de vie : elle
est publiée, puis bascule dans l'Historique au bout de son délai. « En cours »,
« Résolu », « Annulé » sont le vocabulaire d'un **ticket**, et les emprunter
faisait ressembler une annonce à un dossier suivi. Son Publié/Brouillon est une
décision de **diffusion**, et vit en section 2.

La déclaration le dit (`sansObjet`), et c'est elle qui l'impose : la section
disparaît de la création, de l'édition **et** de l'Historique — dans ce dernier,
parce que la liste d'états passée à `EvolForm` est **vide**, pas parce qu'une
condition en dur le décide.

⚠️ **Conséquence en cascade** : l'archivage manuel d'une actualité exigeait l'état
« Résolu ». Sans workflow, il ne pouvait plus être atteint — l'icône 📦 a donc
disparu avec lui. L'archivage **automatique**, lui, reste.

🔴 **REVIREMENT — une PETITE ANNONCE A un workflow** (arbitré le 18/08/2026, le
soir même où ce paragraphe affirmait le contraire). Cinq états : **En cours ·
Réservé · Vendu · Donné · Annulé**.

Ce paragraphe disait : *« l'annonce a un état, mais il lui manque la seconde
moitié de la question — qui l'y a mis ; il n'y a qu'un acteur »*. Le
raisonnement était cohérent et **faux** : il regardait **qui agit**, quand la
question de la section 3 est d'abord **où en est l'objet**. Un vendeur qui a
réservé, vendu ou renoncé a bien un cycle, et ses voisins ont besoin de le lire.

⚠️ **Ce que le revirement ne remet pas en cause** : il n'y a toujours pas de fil
d'évolutions sur une annonce. **Déclarer un workflow et le TRACER sont deux
décisions distinctes** — la seconde n'a pas été demandée. Ne pas les confondre
est ce qui évite d'importer un `RubriqueHistorique` par réflexe.

⚠️ **L'archivage n'est PAS un état.** Une annonce conclue reste un mois puis
bascule dans un Historique replié. C'est une conséquence du temps, pas une étape
qu'on choisit : elle se **calcule** (`est_archivee`), et en faire une sixième
pastille donnerait deux notions pour la même chose — celle qu'on pose et celle
qui arrive. Même règle que les actualités.

🔴 **La leçon de méthode, elle, tient** : c'est la deuxième fois en deux jours
que l'écran réfute le papier (« une actualité n'a pas de workflow » allait dans
l'autre sens). Il ne faut pas en conclure qu'il faut moins déclarer — **c'est la
déclaration qui rend le désaccord visible et corrigeable en un seul endroit**.
Sans elle, les deux raisonnements auraient coexisté dans deux écrans.

**Why (16/08/2026)** : la section finale s'appelait « État », terme qui mélangeait
l'étape de vie et la mise à disposition. Le Suivi Kanban s'y trouvait alors qu'il
dit *où en est le travail*, pas *qui le voit*. Termes retenus par l'utilisateur
après une première proposition inexacte de ma part.



## Checklist UX (à vérifier avant commit)

- [ ] Pattern existant réutilisé (pas de variante ad hoc)
- [ ] Méta toujours visible en mode collapsé
- [ ] `.clamp-5` sur les aperçus
- [ ] un assainisseur de `$lib/sanitize` sur tout `{@html}` — `safeHtml`, `safeRichContent` ou `safeDescription`, jamais un helper local (`lint:html`)
- [ ] Accessibilité : `role`, `tabindex`, `aria-label`, `on:keydown`
- [ ] Périmètre : pas affiché si `'résidence'`
- [ ] Archiver (pas supprimer) sur la vue principale
- [ ] Champs requis : label + ` *`
- [ ] Labels en français
- [ ] En-tête : `<EntetePage>`, jamais `<div class="page-header">` (§13)
- [ ] Icône vérifiée dans `$lib/icones-svg.json` — un nom inconnu échoue en silence
