<!--
  **Demander un nouvel accès, ou en déclarer un qu'on détient déjà.**

  ## Pourquoi séparé (12/09/2026, #928)

  `OngletAcces` est né au-dessus du plafond de modularité en extrayant l'écran
  `/acces-securite`. La coupe suit la nature : d'un côté **ce que je possède**
  (mes listes, leur historique), de l'autre **ce que je demande**.

  🔴 Les deux formulaires vont ensemble et ne vont qu'ensemble : ils remplissent
  la même table côté serveur, et l'utilisateur choisit entre eux — « je n'en ai
  pas, j'en veux un » contre « j'en ai un, il n'est pas chez vous ». Les séparer
  aurait donné deux composants dont chacun n'a de sens que si l'autre existe.

  ⚠️ Ils sont OUVERTS depuis l'en-tête de page, par deux boutons (#928), et non
  par des sections à faire défiler. Leur visibilité est donc une prop liée : un
  second état chez l'hôte finirait par se désaccorder de celui-ci.
-->
<script lang="ts">
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';

	/** Les formulaires ouverts — liés à l'en-tête, qui porte les boutons. */
	export let showForm = false;
	export let showDeclareForm = false;

	/** Les lots de l'utilisateur, pour rattacher la demande. */
	export let mesLots: any[] = [];

	/**  Ce que l'hôte sait faire : il tient les listes, donc il enregistre.
	 *   Ce composant ne parle qu'à l'utilisateur. */
	export let soumettreCommande: () => void;
	export let declarerBadge: () => void;

	export let formLotId = '';
	export let formType = 'vigik';
	export let formQuantite = 1;
	export let formMotif = '';
	export let submitting = false;
	/** L'enregistrement d'une DÉCLARATION est en cours (distinct de `submitting`,
	 *  qui porte la demande : les deux formulaires peuvent être ouverts). */
	export let declaring = false;
	export let declareType = 'telecommande';
	export let declareCode = '';
</script>

{#if showForm}
	<FormulaireCreation titre="Nouvelle demande d'accès">
		<form on:submit|preventDefault={soumettreCommande}>
			<div class="modal-body">
				<div class="form-grid">
					<label class="field">
						Type d'accès *
						<select bind:value={formType}>
							<option value="vigik">Badge Vigik</option>
							<option value="telecommande">Télécommande parking</option>
						</select>
					</label>
					<label class="field">
						Lot concerné *
						<select bind:value={formLotId} required>
							<option value="">— Sélectionner —</option>
							{#each mesLots as lot (lot.id)}
								<option value={lot.id}>Lot {lot.numero}</option>
							{/each}
						</select>
					</label>
					<label class="field">
						Quantité *
						<input type="number" bind:value={formQuantite} min="1" max="5" />
					</label>
					<label class="field">
						Motif
						<textarea bind:value={formMotif} rows="2" placeholder="Raison de la demande…"
						></textarea>
					</label>
				</div>
			</div>
			<div class="modal-footer">
				<button type="button" class="btn btn-outline" on:click={() => (showForm = false)}
					>Annuler</button
				>
				<button class="btn btn-primary" disabled={submitting}>
					{submitting ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</form>
	</FormulaireCreation>
{/if}

{#if showDeclareForm}
	<FormulaireCreation titre="Déclarer un accès existant">
		<form on:submit|preventDefault={declarerBadge}>
			<div class="modal-body">
				<div class="form-grid">
					<label class="field"
						>Type d'accès *
						<select bind:value={declareType}>
							<option value="telecommande">Télécommande parking</option>
							<option value="vigik">Badge Vigik</option>
						</select>
					</label>
					<label class="field"
						>Code / référence *
						<input
							type="text"
							bind:value={declareCode}
							placeholder="Ex : 1234567890"
							style="font-family:monospace"
							required
						/>
					</label>
				</div>
				<p style="font-size:.82rem;color:var(--color-text-muted);margin:.5rem 0 0">
					Si ce code figure dans nos imports, l'entrée sera automatiquement liée à votre compte.
				</p>
			</div>
			<div class="modal-footer">
				<button type="button" class="btn btn-outline" on:click={() => (showDeclareForm = false)}
					>Annuler</button
				>
				<button class="btn btn-primary" disabled={declaring}
					>{declaring ? 'Enregistrement…' : 'Enregistrer cet accès'}</button
				>
			</div>
		</form>
	</FormulaireCreation>
{/if}
