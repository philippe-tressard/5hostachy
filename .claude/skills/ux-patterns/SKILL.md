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
| Le garde-fou R4 | `npm run lint:etats` | il refuse une divergence sans motif, un motif `api` sans ticket, et **une section rendue hors déclaration** |

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

Séparateur multi-périmètre : ` · ` (espace · espace) — porté par `perimetreLabel()`.

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

## 4. Onglets (Tabs)

**Quand** : page avec 2+ vues ou sections distinctes.

- État : `let onglet: 'a' | 'b' = 'a'`
- `role="tablist"` sur le conteneur, `role="tab"` sur chaque bouton
- Descriptif par onglet : `_pc.onglets?.[onglet]?.descriptif`
- CSS : `.tabs` + `.tabs button.active`
- **Ne jamais utiliser** le pattern `view-toggle` / `view-btn` (pattern non-standard, supprimé)

Pages implémentées : `mon-lot`, `sondages`, `espace-cs`, `admin`, `calendrier`

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

**Why (16/08/2026)** : la section finale s'appelait « État », terme qui mélangeait
l'étape de vie et la mise à disposition. Le Suivi Kanban s'y trouvait alors qu'il
dit *où en est le travail*, pas *qui le voit*. Termes retenus par l'utilisateur
après une première proposition inexacte de ma part.

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
| `'vignette'` (défaut) | là où l'on **survole** : fils de messages, fils d'évolutions, listes | signale « il y a une photo » sans casser le rythme de lecture |
| `'grand'` | là où l'on a **demandé à voir** : fil déplié, annonce dépliée, fiche ticket | l'utilisateur vient de déplier ; lui laisser un timbre-poste de 72 px lui impose un clic de plus pour ce qu'il demande |

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

## 13 bis. 🔴 UN FORMULAIRE DIT TOUJOURS CE QU'IL FAIT

**Tout formulaire porte un titre**, et c'est lui qui dit le mode. Posé le
18/08/2026 après un constat à l'écran : *« sur toutes les pages on ne sait pas si
on est en mode édition, en mode suivi »*.

La cause n'était pas un manque de contraste : `EvolForm` était **le seul
formulaire du site sans en-tête**. `FormulaireTicket` et `FormulaireActualite`
passent par `FormulaireCreation`, qui leur donne un titre ; lui rendait ses
sections à nu. Le mode devait donc se **deviner** à partir de l'icône cliquée
trois secondes plus tôt — et **R1** dit que le squelette porte *en-tête · corps ·
pied*. Un formulaire sans nom viole le cadre.

| Geste | Titre |
|---|---|
| création | « Nouveau ticket » · « Nouvelle publication » · « Nouvel événement » |
| édition | « **Modifier** le ticket #123 » · « **Modifier** la publication » |
| évolution | « **Commenter ou changer l'état** », ou « Commenter » sans workflow |
| correction d'une entrée | « **Modifier le commentaire** » |

⚠️ **`FormulaireCreation` porte une prop `encadre`.** À `false`, il rend le titre
**sans la carte** — pour un formulaire qui s'ouvre déjà DANS une carte (ticket,
actualité, événement). Deux bordures imbriquées pour un seul objet, c'est la
« carte dans la carte » signalée sur #425 ; le titre, lui, reste dans les deux
cas. C'est le composant qui décide, jamais l'écran.

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
3. **Jamais de modale pour un formulaire de création.** Les modales restent
   légitimes pour une confirmation, un téléversement ponctuel ou la visionneuse —
   ce qui les distingue : elles n'ont pas de `<form>`.

**Garde-fou** : `npm run lint:formulaires` (job `build-frontend`). Il refuse un
cadre `card largeur-saisie` enveloppant un `<form>`, et toute modale contenant un
`<form>`. Il a trouvé **deux écrans que l'audit manuel avait manqués**.

**Reste à traiter — `prestataires`**, déclaré en exception : quatre formulaires
encore en modale dans un fichier de 2 182 lignes qui doit d'abord être découpé, et
un écart de fond — le périmètre y est une **chaîne** dans un `<select>` là où
`PerimetrePicker` travaille sur un tableau. C'est un changement de contrat, pas un
remplacement de composant.

## Checklist UX (à vérifier avant commit)

- [ ] Pattern existant réutilisé (pas de variante ad hoc)
- [ ] Méta toujours visible en mode collapsé
- [ ] `.clamp-5` sur les aperçus
- [ ] `safeHtml()` sur tout `{@html}`
- [ ] Accessibilité : `role`, `tabindex`, `aria-label`, `on:keydown`
- [ ] Périmètre : pas affiché si `'résidence'`
- [ ] Archiver (pas supprimer) sur la vue principale
- [ ] Champs requis : label + ` *`
- [ ] Labels en français
- [ ] En-tête : `<EntetePage>`, jamais `<div class="page-header">` (§13)
- [ ] Icône vérifiée dans `$lib/icones-svg.json` — un nom inconnu échoue en silence
