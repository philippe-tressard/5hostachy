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
