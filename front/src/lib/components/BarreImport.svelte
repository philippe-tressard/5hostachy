<!--
  Les trois bandeaux d'un écran d'IMPORT : statistiques, téléversement, filtres.

  ## Pourquoi ce composant existe (27/08/2026, #453)

  Les trois écrans d'import de l'administration — lots, télécommandes, badges
  Vigik — portaient ces trois blocs **à l'identique**, aux données près : mêmes
  classes, même structure, même bouton, même libellé « Importer un fichier
  Excel ». Soixante lignes de balisage recopiées trois fois.

  ⚠️ Les trois écrans ne sont PAS le même objet, et ce composant ne prétend pas
  le contraire. Les imports de télécommandes et de badges l'étaient (identiques à
  87 %, fusionnés en `OngletImportAcces`) ; celui des LOTS ne l'est qu'à 38 % — il
  a un tri, une action « auto-résoudre » de plus, et un compte rendu de
  téléversement bien plus riche. Forcer les trois dans un composant unique aurait
  produit une pièce à vingt propriétés, plus difficile à lire que les deux
  fichiers qu'elle remplace.

  Ce qu'on extrait, c'est donc **ce qui est réellement commun** — la mise en
  forme —, pas ce qui se ressemble. La différence n'est pas cosmétique : le jour
  où un quatrième import arrive, il hérite des bandeaux sans hériter d'un
  comportement qui n'est pas le sien.

  ## Responsive

  Les trois bandeaux enveloppent (`flex-wrap`) : sur téléphone, les tuiles de
  statistiques passent à la ligne, et les boutons de filtre aussi. C'est ce que
  les copies faisaient déjà pour les statistiques et le téléversement — mais
  **pas** pour la rangée de filtres, dont le `display:flex` en ligne n'avait pas
  de `flex-wrap` : au-delà de quatre statuts, les boutons débordaient de la
  largeur de l'écran. Corrigé ici, pour les trois d'un coup.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/**
	 * Les tuiles du bandeau de statistiques. `couleur` est absente pour le total,
	 * qui reste neutre.
	 *
	 * ⚠️ Type écrit EN LIGNE et non `export interface` : le `<script>` d'un
	 * composant Svelte n'accepte pas de déclaration de type exportée — elle devrait
	 * vivre dans un `<script context="module">`. La forme est simple et locale,
	 * elle reste ici.
	 */
	export let tuiles: { valeur: number | string; libelle: string; couleur?: string }[] = [];
	/** Les colonnes attendues du fichier, affichées en aide. */
	export let colonnesAttendues: string;
	/** Le libellé de la case de remplacement — il diffère d'un import à l'autre. */
	export let libelleRemplacer = 'Remplacer les imports en attente existants';
	/** Un import est en cours : le bouton se verrouille. */
	export let enCours = false;
	/** Les statuts proposés au filtre, dans l'ordre. `''` = tous. */
	export let statuts: string[] = [];
	/** Libellé de chaque statut. */
	export let libellesStatuts: Record<string, string> = {};
	/** Le statut retenu (lié bidirectionnellement). */
	export let filtre = '';

	const dispatch = createEventDispatcher<{ importer: { fichier: File; remplacer: boolean }; filtrer: string }>();

	let fichier: FileList | null = null;
	let remplacer = false;

	function importer() {
		if (!fichier?.length) return;
		dispatch('importer', { fichier: fichier[0], remplacer });
		fichier = null;
	}
</script>

{#if tuiles.length > 0}
	<div class="imp-stats-bar card">
		{#each tuiles as t}
			<div class="imp-stat">
				<span class="imp-stat-val" style={t.couleur ? `color:${t.couleur}` : ''}>{t.valeur}</span>
				<span class="imp-stat-lbl">{t.libelle}</span>
			</div>
		{/each}
	</div>
{/if}

<div class="card imp-upload-section">
	<h2 class="section-title">Importer un fichier Excel</h2>
	<p class="muted" style="font-size:.85rem;margin-bottom:.75rem">
		Colonnes attendues : <code>{colonnesAttendues}</code>
	</p>
	<div class="imp-upload-row">
		<input type="file" accept=".xlsx,.xls" bind:files={fichier} class="imp-file-input" />
		<label class="imp-checkbox-label">
			<input type="checkbox" bind:checked={remplacer} />
			{libelleRemplacer}
		</label>
		<button class="btn btn-primary" on:click={importer} disabled={enCours || !fichier?.length}>
			{enCours ? 'Import…' : 'Importer'}
		</button>
	</div>
</div>

<div class="imp-toolbar">
	<div class="imp-filtres">
		<span class="muted" style="font-size:.85rem">Filtrer :</span>
		{#each statuts as s}
			<button
				class="btn btn-sm {filtre === s ? 'btn-primary' : 'btn-outline'}"
				on:click={() => {
					filtre = s;
					dispatch('filtrer', s);
				}}
			>
				{s === '' ? 'Tous' : (libellesStatuts[s] ?? s)}
			</button>
		{/each}
	</div>
	<!--  Les actions de masse (auto-match, auto-résoudre) diffèrent d'un import à
	      l'autre : elles restent chez l'appelant, qui les place ici. -->
	<div class="imp-actions">
		<slot name="actions" />
	</div>
</div>

<style>
	/*  Le style voyage avec le balisage : ces règles vivaient en ligne dans les
	    trois copies, donc rien n'empêchait l'une de changer sans les autres. */
	.imp-filtres,
	.imp-actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		/*  🔴 `flex-wrap` MANQUAIT sur la rangée de filtres des trois écrans : les
		    lots en proposent six, et au-delà de quatre les boutons débordaient de la
		    largeur d'un téléphone (`standards/11` §10). */
		flex-wrap: wrap;
	}
	.imp-actions {
		gap: 0.35rem;
	}
</style>
