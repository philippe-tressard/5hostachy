<!--
  ChampsCommuns.svelte — les sections 4 à 9 de TOUT formulaire de création,
  écrites une fois, dans l'ordre, avec leurs intitulés.

  ## Pourquoi ce composant (16/08/2026)

  L'ordre des sections était posé (`ux-patterns` §9 sexies) et `SectionFormulaire`
  savait les séparer à l'écran — mais chaque formulaire recomposait la suite à la
  main. Le résultat était exactement celui que `standards/02` §2 décrit :

  > « Les objets ont l'air d'être dupliqués, pas instanciés, car ils diffèrent
  >   selon les pages où ils sont implémentés. Il ne devrait pas y avoir de
  >   différence sur les objets Périmètre, Destinataires, Description, Photos,
  >   Fichiers et Diffusion — mais chaque page a des différences ! »

  Relevé avant correction, sur six écrans :

  | Notion       | Ce qui divergeait |
  |--------------|-------------------|
  | Description  | « Description » / « Description * » / « Notes » ; hauteur 60, 80, 90, 100 ou 120 px |
  | Photos       | `FichiersUpload` ici, absent là |
  | Documents    | `FichiersUpload` sur les tickets et le calendrier, `<input type="file">` nu sur les actualités et les prestations |
  | Diffusion    | aucune section nommée sur 4 écrans sur 6 |
  | Ordre        | Périmètre au milieu de la grille des champs spécifiques (prestations) ; Kanban rangé dans la diffusion (calendrier) |

  Aucune de ces différences n'était voulue. Elles sont le produit mécanique de
  six recopies : la seule façon de ne pas les voir revenir est qu'il n'y ait plus
  qu'UN endroit qui les écrive.

  ## Ce que ce composant décide, et ce qu'il ne décide pas

  Il décide **l'ordre, les intitulés et les séparations** des sections 4 à 9. Il
  ne décide RIEN du contenu métier : les sections 1 à 3 (Titre, champs
  spécifiques, Workflow) restent dans l'écran, qui seul sait ce qu'elles portent.

  Une section n'apparaît que si l'écran la déclare (`avecPerimetre`, `avecPhotos`…).
  Un sondage n'a pas de pièces jointes, une annonce n'a pas de diffusion : le
  contrat n'est pas « tous les écrans ont tout », c'est « quand un écran a une de
  ces notions, elle est à la même place et a la même tête ».

  ## L'ordre — il ne se discute pas par écran

  4. Périmètre · 5. Destinataires · 6. Description · 7. Photos · 8. Documents
  · 9. Diffusion.

  Le périmètre dit *de quoi* il s'agit, les destinataires *à qui* on l'adresse :
  le premier cadre le second (§9 ter). La **diffusion** (*qui le voit, et où ?*)
  est distincte du **workflow** (*où en est cet objet ?*), qui reste en section 3,
  avant le périmètre — les confondre est l'erreur d'origine.
-->
<script lang="ts">
	import SectionFormulaire from './SectionFormulaire.svelte';
	import PerimetrePicker from './PerimetrePicker.svelte';
	import DestinatairePicker from './DestinatairePicker.svelte';
	import RichEditor from './RichEditor.svelte';
	import FichiersUpload from './FichiersUpload.svelte';
	import CanauxNotification from './CanauxNotification.svelte';
	import { ACCEPT_PHOTOS } from '$lib/fichiers';

	/** Préfixe des `id` des champs — deux formulaires peuvent coexister à l'écran,
	    et deux `<label for="…">` pointant le même id ne désignent plus rien. */
	export let idPrefixe: string;

	//  ── 4. Périmètre ──────────────────────────────────────────────────────────
	export let avecPerimetre = false;
	export let perimetre: string[] = [];
	/**  `single` : un seul code retenu. Le rendu est le MÊME (des pastilles) —
	     seule la sélection change. Utilisé par les prestations, dont la colonne
	     `perimetre` ne porte qu'un code ; les passer au tableau demande une
	     migration, suivie à part. */
	export let perimetreMode: 'multi' | 'single' = 'multi';

	//  ── 5. Destinataires ──────────────────────────────────────────────────────
	export let avecDestinataires = false;
	export let destinataires: string[] = ['résidents'];

	//  ── 6. Description ────────────────────────────────────────────────────────
	export let avecDescription = false;
	export let description = '';
	export let descriptionRequise = false;
	export let descriptionPlaceholder = '';
	/**  Hauteur minimale de l'éditeur. Elle valait 60, 80, 90, 100 ou 120 px selon
	     l'écran, sans qu'aucune de ces valeurs ait de raison : 120 px est retenu
	     comme défaut — c'est celui des deux écrans les plus utilisés (actualités,
	     tickets). Ne la surcharger que pour une vraie contrainte de place. */
	export let descriptionHauteur = '120px';

	//  ── 7. Photos ─────────────────────────────────────────────────────────────
	export let avecPhotos = false;
	export let photos: string[] = [];

	//  ── 8. Documents ──────────────────────────────────────────────────────────
	export let avecDocuments = false;
	export let documents: string[] = [];
	/**  Mode différé : les documents d'une actualité deviennent des entités
	     `Document` rattachées à la publication, qui n'existe pas encore. Le
	     composant retient les `File`, l'écran les téléverse après création.
	     Voir l'en-tête de `FichiersUpload.svelte`. */
	export let documentsDifferes = false;
	export let documentsFichiers: File[] = [];

	//  ── 9. Diffusion ──────────────────────────────────────────────────────────
	export let avecDiffusion = false;
	/**  Les trois canaux (WhatsApp, syndic, CS). Un écran peut avoir une section
	     Diffusion SANS canaux — les actualités les rendent elles-mêmes, à travers
	     `OptionsPublication`, qui porte en plus le confidentiel et l'affiche de hall. */
	export let avecCanaux = true;
	export let whatsapp = false;
	export let syndic = false;
	export let cs = false;
	export let aideWhatsapp = '';
</script>

{#if avecPerimetre}
	<SectionFormulaire titre="Périmètre">
		<div class="field champ-large">
			<PerimetrePicker bind:value={perimetre} mode={perimetreMode} />
		</div>
	</SectionFormulaire>
{/if}

{#if avecDestinataires}
	<SectionFormulaire titre="Destinataires">
		<div class="field champ-large">
			<DestinatairePicker bind:value={destinataires} />
		</div>
	</SectionFormulaire>
{/if}

{#if avecDescription}
	<SectionFormulaire titre="Description">
		<div class="field champ-large">
			<label for="{idPrefixe}-description">Description{#if descriptionRequise} *{/if}</label>
			<RichEditor id="{idPrefixe}-description" bind:value={description}
				placeholder={descriptionPlaceholder} minHeight={descriptionHauteur} />
		</div>
	</SectionFormulaire>
{/if}

{#if avecPhotos}
	<SectionFormulaire titre="Photos">
		<div class="field champ-large">
			<FichiersUpload id="{idPrefixe}-photos" bind:urls={photos}
				label="Ajouter une photo" accept={ACCEPT_PHOTOS} size={80} />
		</div>
	</SectionFormulaire>
{/if}

{#if avecDocuments}
	<SectionFormulaire titre="Documents">
		<div class="field champ-large">
			<FichiersUpload id="{idPrefixe}-documents" mode="documents"
				differe={documentsDifferes}
				bind:urls={documents} bind:fichiers={documentsFichiers} />
		</div>
	</SectionFormulaire>
{/if}

{#if avecDiffusion}
	<SectionFormulaire titre="Diffusion">
		<!--  Les options propres à l'écran (épingler, brouillon, afficher au fil…)
		      passent AVANT les canaux : elles décident de ce qui est publié, les
		      canaux de qui en est prévenu. -->
		<slot name="diffusion" />
		{#if avecCanaux}
			<CanauxNotification bind:whatsapp bind:syndic bind:cs {aideWhatsapp} />
		{/if}
	</SectionFormulaire>
{/if}
