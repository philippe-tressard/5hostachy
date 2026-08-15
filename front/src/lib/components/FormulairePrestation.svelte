<!--
  Le formulaire d'une prestation ponctuelle.

  Extrait de `prestataires/+page.svelte` le 15/08/2026 : le fichier fait plus de
  2 000 lignes et le garde-fou de modularité a refusé qu'il grossisse en recevant
  le déplacement du formulaire au-dessus de la liste (#372). La règle est « on
  découpe le fichier QUAND on y touche ».

  La frontière est la même que pour `FormulaireEvenement` : ce bloc n'est QUE de
  la saisie. `saveDevis`, `closeDevisForm` et le cycle de vie restent dans la page.
-->
<script lang="ts">
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';

	/** L'objet de saisie, lié en deux sens : la page porte son cycle de vie. */
	export let devisForm: any;
	export let prestataires: any[] = [];
	export let statutsDevis: { val: string; label: string }[] = [];
	/** Clé de remontage de l'input fichier, pour le vider après enregistrement. */
	export let devisFichierKey = 0;
	export let devisFichierFiles: FileList | null = null;
	export let submitting = false;
	export let onFilesChange: (e: Event) => void;
	export let onSave: () => void;
	export let onCancel: () => void;
</script>

<div>
	<p class="devis-form-help">Les prestations ponctuelles alimentent le Calendrier et le Kanban selon leur statut.</p>
	<div class="form-grid">
		<label>Prestataire *
			<select bind:value={devisForm.prestataire_id} required>
				<option value="">— Sélectionner —</option>
				{#each prestataires as p}<option value={String(p.id)}>{p.nom}</option>{/each}
			</select>
		</label>
		<div class="field">
			<label>Périmètre *</label>
			<PerimetrePicker mode="single"
				value={devisForm.perimetre ? [devisForm.perimetre] : []}
				on:change={(e) => (devisForm.perimetre = e.detail[0] ?? '')} />
		</div>
		<label>Titre *<input bind:value={devisForm.titre} required /></label>
		<label>Date de prestation<input type="date" bind:value={devisForm.date_prestation} /></label>
		<label>Montant estimé (€)<input type="number" min="0" step="0.01" bind:value={devisForm.montant_estime} placeholder="Ex. 1200" /></label>
		<label>Suivi Kanban
			<select bind:value={devisForm.statut}>
				{#each statutsDevis as s}<option value={s.val}>{s.label}</option>{/each}
			</select>
		</label>
		<label>Fréquence
			<select bind:value={devisForm.frequence_type}>
				<option value=''>— Ponctuelle —</option>
				<option value='fois_par_an'>× / an</option>
				<option value='mois'>Tous les N mois</option>
				<option value='semaines'>Toutes les N semaines</option>
				<option value='ans'>Tous les N ans</option>
			</select>
		</label>
		{#if devisForm.frequence_type}
			<label>Valeur<input type="number" min="1" bind:value={devisForm.frequence_valeur} /></label>
		{/if}
	</div>
	<div style="margin-top:.75rem">
		<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer">
			<input type="checkbox" bind:checked={devisForm.affichable} style="width:auto;margin:0" />
			<span style="font-size:.875rem">Afficher dans le tableau de bord</span>
		</label>
	</div>
	<div style="margin-top:.6rem">
		<label style="font-size:.85rem;font-weight:600;display:block;margin-bottom:.3rem">Notes</label>
		<RichEditor bind:value={devisForm.notes} placeholder="Notes…" minHeight="60px" />
	</div>
	<div style="margin-top:.6rem">
		<label style="font-size:.85rem;font-weight:600;display:block;margin-bottom:.3rem">Fichiers</label>
		{#key devisFichierKey}
			<input type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png" on:change={onFilesChange} />
		{/key}
		{#if devisFichierFiles && devisFichierFiles.length > 0}<span class="devis-file-note">📎 {devisFichierFiles.length} fichier{devisFichierFiles.length > 1 ? 's' : ''}</span>{/if}
	</div>
</div>
<div class="form-actions">
	<button class="btn btn-outline" on:click={onCancel}>Annuler</button>
	<button class="btn btn-primary" disabled={submitting} on:click={onSave}>{submitting ? '…' : 'Enregistrer'}</button>
</div>

<style>
	/*  ⚠️ CES RÈGLES SONT PARTIES AVEC LE BALISAGE, et elles devaient partir avec
	    lui. Svelte scope les styles au FICHIER : laissées dans la page, elles ne
	    s'appliquaient plus au formulaire extrait — la grille disparaissait et les
	    champs s'alignaient en une seule ligne illisible. C'est la régression du
	    14/08/2026 (#344), reproduite à l'identique le 15/08 en extrayant ce
	    composant, et vue en production par l'utilisateur avant tout contrôle.

	    `svelte-check` ne l'a PAS signalée : les sélecteurs restaient « utilisés »
	    dans la page, qui porte d'autres `.form-grid`. Le signal « aucun sélecteur
	    orphelin » ne dit donc rien quand la classe existe des deux côtés. */
	.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr)); gap: .65rem; }
	.form-grid .field { margin-bottom: 0; }
	.devis-form-help { margin: 0 0 .75rem; font-size: .82rem; color: var(--color-text-muted); line-height: 1.45; }
	.devis-file-note { display: inline-block; margin-top: .35rem; font-size: .8rem; color: var(--color-text-muted); }
	.form-actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: .75rem; }
</style>
