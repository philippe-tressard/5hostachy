<script lang="ts">
	/**
	 * Le formulaire d'édition d'un compte utilisateur (Administration → Comptes).
	 *
	 * ## Pourquoi il est ici et non dans l'écran (#640, 30/08/2026)
	 *
	 * Ces huit champs étaient écrits **à même `admin/+page.svelte`**, comme
	 * `FormulaireAnnonceHall` l'était dans l'espace CS jusqu'au 18/08 — le motif
	 * que #453 nomme : *le refus du contrôle de modularité désigne un problème de
	 * placement, pas de taille.* Tous les autres formulaires du site sont des
	 * composants ; celui-ci ne l'était pas, sans raison.
	 *
	 * ⚠️ Il n'a **pas** de jumeau : contrairement au contrat, ce formulaire n'est
	 * rendu qu'à un endroit. On ne l'extrait donc pas pour supprimer une
	 * duplication, mais pour que l'écran cesse de porter une saisie qui ne le
	 * regarde pas — et pour que le prochain appelant hérite de sa forme au lieu
	 * de la réinventer.
	 *
	 * ## Ce qu'il porte, et ce qu'il laisse à l'appelant
	 *
	 * Le formulaire seul. Son cadre est choisi par le geste : ici `<Modale
	 * edition>`, puisque l'on corrige un objet existant (`ux-patterns` §14 bis).
	 */
	export let editForm: any;
	/** Les statuts proposables, tels que l'écran les connaît — jamais réécrits ici. */
	export let statutLabels: Record<string, string>;
	export let batimentsList: { id: number; numero: string | number }[] = [];

	export let onAnnuler: () => void;
	/** Appelé à la soumission du `<form>` — donc aussi sur la touche Entrée. */
	export let onEnregistrer: () => void;
</script>

<!--
	🔴 UN VRAI `<form>`. Les huit champs n'en avaient aucun : la touche Entrée ne
	soumettait pas, et rien ne le signalait. C'est aussi ce qui rend la modale
	visible à `lint:formulaires`, donc ce qui fait surveiller sa déclaration
	`edition` par un contrôle plutôt que par la vigilance.
-->
<form on:submit|preventDefault={onEnregistrer}>
	<div class="form-grid">
		<label class="field">Prénom<input type="text" bind:value={editForm.prenom} /></label>
		<label class="field">Nom<input type="text" bind:value={editForm.nom} /></label>
		<label class="field">E-mail<input type="email" bind:value={editForm.email} /></label>
		<label class="field">Téléphone<input type="text" bind:value={editForm.telephone} /></label>
		<label class="field">Société<input type="text" bind:value={editForm.societe} /></label>
		<label class="field"
			>Statut
			<select bind:value={editForm.statut}>
				{#each Object.entries(statutLabels) as [val, lbl] (val)}
					<option value={val}>{lbl}</option>
				{/each}
			</select>
		</label>
		<label class="field"
			>Bâtiment
			<select bind:value={editForm.batiment_id}>
				<option value={null}>— Aucun —</option>
				{#each batimentsList as b (b.id)}
					<option value={b.id}>Bât. {b.numero}</option>
				{/each}
			</select>
		</label>
		<label class="case" style="padding-top:1.2rem">
			<input type="checkbox" bind:checked={editForm.actif} />
			Compte actif
		</label>
	</div>
	<div class="modal-footer">
		<button type="button" class="btn btn-outline" on:click={onAnnuler}>Annuler</button>
		<button type="submit" class="btn btn-primary">Enregistrer</button>
	</div>
</form>
