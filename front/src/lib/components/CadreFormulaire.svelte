<!--
  **Le cadre d'un formulaire** — la boîte dans la page, ou la fenêtre. Un geste,
  un format, et la règle écrite UNE fois.

  | Geste | Cadre | Depuis |
  |---|---|---|
  | **créer** | `FormulaireCreation`, la boîte dans la page | #367, 15/08/2026 |
  | **éditer** | `Modale` | #640, 30/08/2026 (`ux-patterns` §14 bis) |

  ## 🔴 Pourquoi ce composant existe (02/09/2026)

  Ce choix s'écrivait **cinq fois**, à l'identique ou presque :

      FormulaireActualite · FormulaireBail · FormulaireDocument
      FormulaireEvenement · FormulaireFaq

  Chacune portait son `<svelte:component this={… ? Modale : FormulaireCreation}>`,
  son étalement `{...edition ? { edition: true } : {}}`, ses deux imports, et un
  commentaire expliquant la même chose dans des mots différents. `FormulaireAnnonce`
  allait être la sixième.

  ⚠️ **Elles avaient déjà divergé**, et c'est la forme la plus trompeuse de la
  duplication — celle où chaque copie a l'air juste :

  - `fermetureAuFond={false}` était passé par **deux** des cinq, avec un
    commentaire d'incident (« un clic à côté effaçait tout »). Les trois autres ne
    le passaient pas. Aucune n'avait tort : `Modale` l'impose depuis longtemps dès
    que `edition` est posé (`fondFermant = fermetureAuFond && !edition && …`). Les
    deux props étaient **redondantes**, et leur commentaire faisait croire que les
    trois autres écrans avaient un défaut. Retirées ici.
  - `classeBoite` valait `modal` (Actualité, Événement), `modal-box` (Bail,
    Document) ou `modal-box card` (FAQ). Cette divergence a été **déclarée et non
    résolue** le 02/09 au matin : *« uniformiser un rendu ne se décide pas dans une
    factorisation, ça se regarde »*.

  🔴 **L'ÉCRAN A REGARDÉ, LE MÊME JOUR, ET IL A TRANCHÉ** (« Modifier l'annonce »,
  signalé en capture). Ces deux valeurs ne sont pas décoratives : elles décident
  **où vit le padding**. `.modal` ne pose rien sur la boîte — il appartient à
  l'en-tête et au corps (`.modal-body`) ; `.modal-box` le pose sur la boîte.

  Six formulaires, **deux techniques** pour le même besoin — et `FormulaireAnnonce`
  n'avait NI l'une NI l'autre : ses bandes de section sortaient à fleur de fenêtre,
  le titre collé au bord. Personne ne l'avait vu parce que c'était le seul des six
  dans ce cas, et que rien ne rapproche « j'ai choisi `modal` » de « j'ai pensé au
  corps ».

  Le cadre le garantit désormais : sur la classe par défaut, il enveloppe lui-même
  le contenu dans `.modal-body`. Un écran qui passe une autre classe déclare qu'il
  s'en charge — c'est le cas de la FAQ, plus étroite à dessein.

  ## Ce que ce composant NE fait pas

  Il ne pose **aucun bouton** et ne connaît ni l'enregistrement ni ce qu'annuler
  veut dire — comme `FormulaireCreation`, dont il hérite la retenue. Il relaie
  `on:fermer`, et c'est tout.

  Il ne décide pas non plus du **contenu** du formulaire selon le geste : les
  sections viennent du cadre #430 (`$lib/entites/*` + `sectionPresente`), et
  `npm run lint:etats` refuse qu'on remette une condition en dur.

  🔒 `Modale` et `FormulaireCreation` sont nommées **ici**, dans le `this={…}` —
  c'est ce que lit `npm run lint:formulaires`, qui suit désormais l'indirection
  jusqu'à ce fichier. Un cadre choisi dans une variable compilerait aussi bien et
  sortirait la modale du champ du contrôle.
-->
<script lang="ts">
	import FormulaireCreation from './FormulaireCreation.svelte';
	import Modale from './Modale.svelte';

	/**  Le geste. `false` = création (boîte dans la page), `true` = correction
	 *   d'un objet existant (fenêtre).
	 *
	 *   ⚠️ **Une déclaration, pas une commodité** — même contrat que `Modale.edition`,
	 *   qu'il transmet. C'est lui qui distingue « créer » de « corriger », et rien
	 *   dans le balisage ne permettrait de le deviner. */
	export let edition = false;

	/** Le titre du cadre — en-tête de la boîte, ou titre annoncé de la fenêtre. */
	export let titre: string;

	/**  Où vit le PADDING de la fenêtre, et c'est tout ce que cette prop décide.
	 *
	 *   `.modal` ne pose aucun padding sur la boîte : il appartient à l'en-tête et
	 *   au corps (`.modal-body`). `.modal-box` le pose sur la boîte elle-même. Les
	 *   deux marchent — mais il FAUT l'un des deux, et c'est ce qui manquait. */
	const CLASSE_PAR_DEFAUT = 'modal';
	export let classeBoite = CLASSE_PAR_DEFAUT;
	/** Style de la fenêtre, pour une largeur propre à l'écran — édition seulement. */
	export let styleBoite = '';

	/**  Le cadre visible de la boîte — **création seulement**. `false` quand le
	 *   formulaire s'ouvre déjà DANS une carte : deux bordures imbriquées pour un
	 *   seul objet, c'est « la carte dans la carte » (#425). */
	export let encadre = true;
	/**  Ce qui identifie l'objet en cours — **création seulement**. Il change, et
	 *   `FormulaireCreation` ramène le formulaire à l'écran. */
	export let cle: unknown = undefined;
</script>

<svelte:component
	this={edition ? Modale : FormulaireCreation}
	{titre}
	{...edition ? { edition: true, classeBoite, styleBoite } : { encadre, cle }}
	on:fermer
>
	{#if edition && classeBoite === CLASSE_PAR_DEFAUT}
		<div class="modal-body"><slot /></div>
	{:else}
		<slot />
	{/if}
</svelte:component>
