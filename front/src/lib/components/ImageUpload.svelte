<!--
  Composant réutilisable de téléchargement d'image.
  Props :
    - currentUrl   : URL de l'image actuelle (optionnel)
    - placeholder  : emoji ou texte affiché si pas d'image
    - label        : libellé du bouton
    - accept       : types MIME acceptés (défaut JPEG/PNG/WebP)
    - shape        : "circle" | "rect" (défaut "rect")
    - uploading    : état de chargement géré par le parent
  Events :
    - change(detail: File) — émis quand l'utilisateur sélectionne un fichier
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let currentUrl: string | undefined = undefined;
	export let placeholder = '\u{1F4F7}';
	export let label = 'Changer la photo';
	export let accept = 'image/jpeg,image/png,image/webp';
	export let shape: 'circle' | 'rect' = 'rect';
	export let uploading = false;
	export let previewSize = '120px';

	const dispatch = createEventDispatcher<{ change: File }>();

	let input: HTMLInputElement;
	let localPreview: string | undefined;

	$: displayUrl = localPreview ?? currentUrl;

	function handleChange(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (!file) return;
		// Prévisualisation locale immédiate
		localPreview = URL.createObjectURL(file);
		dispatch('change', file);
	}
</script>

<div class="img-upload-wrap" style="--preview-size: {previewSize}">
	<div
		class="preview"
		class:circle={shape === 'circle'}
		role="button"
		tabindex="0"
		on:click={() => input.click()}
		on:keydown={(e) => e.key === 'Enter' && input.click()}
		title={label}
	>
		{#if displayUrl}
			<img src={displayUrl} alt="Aperçu" />
		{:else}
			<span class="placeholder">{placeholder}</span>
		{/if}

		<div class="overlay">
			{#if uploading}
				<span class="spinner" />
			{:else}
				<span class="overlay-label">&#x1F4F7;</span>
			{/if}
		</div>
	</div>

	<button
		type="button"
		class="btn-link"
		on:click={() => input.click()}
		disabled={uploading}
	>
		{uploading ? 'Chargement…' : label}
	</button>

	<input
		bind:this={input}
		type="file"
		{accept}
		style="display:none"
		on:change={handleChange}
	/>
</div>

<style>
	.img-upload-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: .5rem;
	}

	.preview {
		position: relative;
		width: var(--preview-size);
		height: var(--preview-size);
		border-radius: 8px;
		border: 2px dashed var(--color-border, #e2e8f0);
		overflow: hidden;
		cursor: pointer;
		background: var(--color-bg-subtle, #f8fafc);
		display: flex;
		align-items: center;
		justify-content: center;
		transition: border-color .2s;
	}

	.preview:hover { border-color: var(--color-primary, #2563eb); }
	.preview.circle { border-radius: 50%; }

	.preview img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.placeholder { font-size: 2rem; opacity: .4; }

	.overlay {
		position: absolute;
		top: 0; right: 0; bottom: 0; left: 0;
		background: rgba(0,0,0,.35);
		display: flex;
		align-items: center;
		justify-content: center;
		opacity: 0;
		transition: opacity .2s;
	}

	.preview:hover .overlay,
	.preview:focus-visible .overlay { opacity: 1; }

	.overlay-label { font-size: 1.5rem; }

	.spinner {
		width: 24px;
		height: 24px;
		border: 3px solid rgba(255,255,255,.4);
		border-top-color: #fff;
		border-radius: 50%;
		animation: spin .7s linear infinite;
	}

	@keyframes spin { to { transform: rotate(360deg); } }

	.btn-link {
		background: none;
		border: none;
		color: var(--color-primary, #2563eb);
		font-size: .8rem;
		cursor: pointer;
		padding: 0;
		text-decoration: underline;
	}

	.btn-link:disabled { opacity: .5; cursor: default; }
</style>
