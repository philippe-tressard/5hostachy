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

### Structure 2 lignes
- **Ligne 1** : icône + titre + badges clé
- **Ligne 2 (méta)** : lieu + périmètre + auteur — **toujours visible** (collapsé ET expandé)

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

**Largeur : `.largeur-saisie` (720 px), sur le conteneur du formulaire.** Vaut
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

| # | Champ |
|---|---|
| 1 | **Titre** |
| 2 | **Champs spécifiques** à la page |
| 3 | **Périmètre** |
| 4 | **Destinataires** |
| 5 | **Descriptif** |
| 6 | **Photos** |
| 7 | **Documents** |
| 8 | **État** — dont la diffusion (épingler, partager, envoyer) fait partie |

La **diffusion** n'est pas un bloc à part : épingler, partager sur le groupe,
envoyer au syndic ou au conseil syndical sont des décisions de publication, donc
de l'**État**. C'est un objet à part entière, modularisé par héritage.

**Les actualités sont le modèle** : leur formulaire respectait déjà cet ordre
quand la règle a été posée. Les autres écrans s'y alignent.

**Why (16/08/2026)** : le calendrier plaçait la diffusion AVANT le descriptif,
seul de tout le site ; les prestations commençaient par « Prestataire » et non
par le titre. Signalé à l'écran, écran par écran, faute d'une règle écrite.

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
| `marge` | marge basse dérogatoire (quatre écrans l'utilisent — dette, cf. plus bas) |
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

**Dette assumée** : `marge` existe parce que quatre écrans divergeaient
(`0`, `.5rem`, `.75rem`, `1rem` au lieu de `1.5rem`). La valeur est désormais
explicite et centralisée au lieu d'être un `style=` en ligne, mais le bon écart se
tranche **à l'écran**. Ne pas ajouter de cinquième valeur sans avoir regardé.

**Pages de détail** (`tickets/[id]`, `sondages/[id]`) : elles n'ont **pas**
d'en-tête de page — leur `<h1>` est le titre de l'objet, dans sa carte. Ne pas les
convertir mécaniquement : ce qu'il faut y mettre est instruit dans #365.

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
