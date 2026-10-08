<!--
  Le réglage du PIED DE PAGE, dans Admin › Site (08/10/2026).

  Les éléments facultatifs se masquent, les trois que la loi ou la licence
  imposent restent ; l'année de création fait « © 2026–2027 » les années
  suivantes ; le texte libre est une pastille parmi les autres, qui se place
  avec ← → (arbitrés à l'écran). La règle vit dans `$lib/piedDePage`.

  L'aperçu est le VRAI composant du squelette : il ne peut pas montrer autre
  chose que le site. Extrait d'`OngletSite`, qui le portait en ligne.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import LibelleGroupe from '$lib/components/LibelleGroupe.svelte';
	import Pastille from '$lib/components/Pastille.svelte';
	import PiedDePage from '$lib/components/PiedDePage.svelte';
	import {
		deplacerTexte,
		ELEMENTS_MASQUABLES,
		ELEMENTS_VERROUILLES,
		ordreComplet,
		TEXTE_PIED_MAX,
		type ReglagePied,
	} from '$lib/piedDePage';

	/** Lié : la page porte l'état et l'enregistre. */
	export let reglage: ReglagePied;
	export let siteSaving = false;
	export let saveSiteConfig: () => void;

	const libelles = new Map(ELEMENTS_MASQUABLES.map((e) => [e.code, e.libelle]));
	const verrouilles = ELEMENTS_VERROUILLES.map((e) => e.libelle).join(', ');

	//  Les pastilles dans l'ordre du pied de page : le texte libre y est à SA place.
	$: pastilles = ordreComplet(reglage.texteApres).filter((c) => libelles.has(c));
	$: texteActif = !reglage.masques.includes('texte');
	$: avant = deplacerTexte(reglage, -1);
	$: apres = deplacerTexte(reglage, 1);

	/** Affiche ou masque un élément — l'aperçu suit aussitôt. */
	function basculer(code: string) {
		const masques = reglage.masques;
		reglage.masques = masques.includes(code)
			? masques.filter((c) => c !== code)
			: [...masques, code];
	}
</script>

<section class="card config-section">
	<h2 class="config-section-title"><Icon name="pencil" size={17} />Pied de page</h2>
	<div class="largeur-saisie">
		<LibelleGroupe titre="Éléments affichés" id="pied-elements" classe="perimetre-pills">
			{#each pastilles as code (code)}
				{#if code === 'texte' && texteActif}
					<!--  Les flèches font 44 px au doigt : groupées avec leur pastille, elles
					      n'étirent plus toute la rangée à leur hauteur. -->
					<span class="texte-place">
						<button
							type="button"
							class="btn-icon deplacer"
							aria-label="Avancer le texte libre"
							title="Avancer le texte libre"
							disabled={avant === reglage.texteApres}
							on:click={() => (reglage.texteApres = avant)}>←</button
						>
						<Pastille petite bascule active on:click={() => basculer(code)}
							>{libelles.get(code)}</Pastille
						>
						<button
							type="button"
							class="btn-icon deplacer"
							aria-label="Reculer le texte libre"
							title="Reculer le texte libre"
							disabled={apres === reglage.texteApres}
							on:click={() => (reglage.texteApres = apres)}>→</button
						>
					</span>
				{:else}
					<Pastille
						petite
						bascule
						active={!reglage.masques.includes(code)}
						on:click={() => basculer(code)}>{libelles.get(code)}</Pastille
					>
				{/if}
			{/each}
		</LibelleGroupe>
		<p class="aide">
			Toujours affichés : {verrouilles}. La licence du logiciel et la loi imposent qu’ils restent
			accessibles depuis chaque page.
		</p>
		<div class="champs-pied">
			<label class="field champ-court">
				Année de création
				<input
					type="number"
					bind:value={reglage.anneeDebut}
					min="1900"
					max="9999"
					placeholder="2026"
				/>
				<span class="aide"
					>« © 2026 » cette année, « © 2026–2027 » l’an prochain. Vide : l’année en cours seule.</span
				>
			</label>
			<label class="field">
				Texte libre
				<input
					type="text"
					bind:value={reglage.texte}
					maxlength={TEXTE_PIED_MAX}
					placeholder="Un texte court, placé avec ← → parmi les éléments"
				/>
			</label>
		</div>
		<div class="apercu-pied" role="group" aria-label="Aperçu du pied de page">
			<PiedDePage {reglage} />
		</div>
	</div>
	<div class="form-actions largeur-saisie">
		<button class="btn btn-primary" on:click={saveSiteConfig} disabled={siteSaving}>
			{siteSaving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</section>

<style>
	.champs-pied {
		display: grid;
		grid-template-columns: minmax(8rem, 12rem) 1fr;
		gap: 0.75rem;
		margin-top: 0.75rem;
	}
	@media (max-width: 767px) {
		.champs-pied {
			grid-template-columns: 1fr;
		}
	}
	.texte-place {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}
	.deplacer:disabled {
		opacity: 0.25;
		cursor: not-allowed;
	}
	.apercu-pied {
		margin-top: 0.75rem;
		border: 1px dashed var(--color-border);
		border-radius: var(--radius);
	}
</style>
