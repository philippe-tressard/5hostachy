<!--
  Le formulaire d'un événement de calendrier.

  Extrait de `calendrier/+page.svelte` le 15/08/2026 : le fichier dépassait le
  plafond de modularité et le garde-fou a refusé qu'il grossisse en recevant le
  chevron et le survol de #362. La règle est « on découpe le fichier QUAND on y
  touche » — c'est ce qui est fait ici, et la frontière est nette : ce bloc n'est
  QUE de la saisie, la décision (`save`, `resetForm`) reste dans la page.

  Les champs passent par `.field`, dont `app.css` porte le style. Ils étaient
  écrits à la main dans une grille maison, et un sélecteur cassé depuis la v1.0
  les laissait SANS aucun style — apparence native du navigateur, blancs à
  bordure noire, là où tout le site est gris et arrondi (#372). Le défaut était
  masqué par la modale ; le passage à la boîte dans la page l'a révélé.
-->
<script lang="ts">
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import { ACCEPT_PHOTOS } from '$lib/fichiers';
	import AlerteEpinglage from '$lib/components/AlerteEpinglage.svelte';
	import CanauxNotification from '$lib/components/CanauxNotification.svelte';

	/** L'objet de saisie, lié en deux sens : la page porte son cycle de vie. */
	export let form: any;
	export let photosUrls: string[] = [];
	export let fichiersUrls: string[] = [];
	export let types: { val: string; label: string }[] = [];
	export let prestataires: any[] = [];
	export let submitting = false;
	/** Périmètre ciblé, lié en deux sens comme `form`. */
	export let formPerimetreCible: string[] = [];
	/**  Épinglage à l'OUVERTURE : sans lui, l'avertissement de plafond compterait
	 *   une seconde fois un événement déjà épinglé. */
	export let epingleInitial = false;
	/**  Colonnes du kanban. Passées en prop et NON importées : elles sont une
	 *   constante locale de la page, pas un module partagé — les dupliquer ici
	 *   créerait la deuxième liste qui dérive. */
	export let kanbanCols: { id: string; label: string }[] = [];
	/** Appelé à la soumission. La page garde la décision d'enregistrer. */
	export let onSubmit: () => void;
</script>

<form on:submit|preventDefault={onSubmit}>
	<div>
		<div class="form-grid">
			<div class="field champ-large">
				<label>Titre *</label>
				<input bind:value={form.titre} required />
			</div>
			<div class="field">
				<label>Type</label>
				<select bind:value={form.type}>
					{#each types as t}<option value={t.val}>{t.label}</option>{/each}
				</select>
			</div>
			<div class="field">
				<label>Date de début *</label>
				<input type="date" bind:value={form.debut} required />
			</div>
			<div class="field">
				<label>Heure (optionnelle)</label>
				<input type="time" bind:value={form.debut_heure} />
			</div>
			<div class="field">
				<label>Fin</label>
				<input type="datetime-local" bind:value={form.fin} />
			</div>
			<div class="field">
				<label>Lieu</label>
				<input bind:value={form.lieu} />
			</div>
			<div class="field">
				<label>Prestataire</label>
				<select bind:value={form.prestataire_id}>
					<option value=''>— Aucun —</option>
					{#each prestataires.filter(p => p.actif !== false) as p}
						<option value={String(p.id)}>{p.nom}</option>
					{/each}
				</select>
			</div>
		</div>
		{#if form.prestataire_id && form.type !== 'maintenance_recurrente'}
		<!--  Conteneur de grille, pas un champ : il portait `.field` et contenait
		      des `.field`, ce qui empilait deux fois le même style. -->
		<div style="margin-top:.75rem;display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
			<div class="field">
				<label>Fréquence (optionnelle)</label>
				<select bind:value={form.frequence_type}>
					<option value=''>— Pas de récurrence —</option>
					<option value='fois_par_an'>× / an</option>
					<option value='mois'>Tous les N mois</option>
					<option value='semaines'>Toutes les N semaines</option>
				</select>
			</div>
			{#if form.frequence_type}
			<div class="field">
				<label>Valeur</label>
				<input type="number" min="1" bind:value={form.frequence_valeur} placeholder="ex: 2" />
			</div>
			{/if}
		</div>
		{/if}
		<!--  ORDRE : Périmètre, Description, Photos, Documents, puis État —
		      dont le Kanban, l'affichage au fil et la diffusion font partie.
		      La diffusion était placée AVANT la description, seule de tout le
		      site à l'être (signalé le 16/08/2026). -->
		<div class="field" style="margin-top:.75rem">
			<PerimetrePicker bind:value={formPerimetreCible} />
		</div>
		<div class="field" style="margin-top:.75rem">
			<label for="ev-description">Description</label>
			<RichEditor id="ev-description" bind:value={form.description} placeholder="Description de l'événement…" minHeight="80px" />
		</div>
		<div class="field" style="margin-top:.75rem">
			<FichiersUpload id="ev-photos" bind:urls={photosUrls}
				label="Ajouter une photo" accept={ACCEPT_PHOTOS} size={72} />
		</div>
		<div class="field" style="margin-top:.75rem">
			<FichiersUpload id="ev-documents" bind:urls={fichiersUrls} />
		</div>
		<div class="field" style="margin-top:.75rem">
			<label>Suivi Kanban</label>
			<select bind:value={form.statut_kanban} style="max-width:280px;padding:.4rem .6rem;border:1px solid var(--color-border);border-radius:var(--radius);font-size:.875rem;background:var(--color-bg)">
				<option value="">— Pas de suivi Kanban —</option>
				{#each kanbanCols as col}
					<option value={col.id}>{col.label}</option>
				{/each}
			</select>
		</div>
		<div class="field" style="margin-top:.75rem">
			<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer">
				<input type="checkbox" bind:checked={form.affichable}
					disabled={form.type === 'maintenance_recurrente'} style="width:auto;margin:0" />
				<span>Afficher dans le fil d'activité du tableau de bord</span>
			</label>
			<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer;margin-top:.4rem"
				class:desactive={!form.affichable}>
				<input type="checkbox" bind:checked={form.epingle}
					disabled={!form.affichable} style="width:auto;margin:0" />
				<span>📌 Épingler dans le fil d'activité</span>
			</label>
			<AlerteEpinglage coche={form.epingle} dejaEpingle={epingleInitial} />
			{#if !form.affichable}
				<p style="margin:.2rem 0 0 1.6rem;font-size:.8rem;color:var(--color-text-muted)">
					Un événement absent du fil ne peut pas y être épinglé.
				</p>
			{/if}
			{#if form.type === 'maintenance_recurrente'}
				<p style="margin:.3rem 0 0 1.6rem;font-size:.8rem;color:var(--color-text-muted)">
					Les maintenances récurrentes restent hors du fil d'activité : elles se suivent dans le Kanban.
				</p>
			{/if}
		</div>
		<div class="field" style="margin-top:.75rem">
			<CanauxNotification
				bind:whatsapp={form.partager_whatsapp}
				bind:syndic={form.envoyer_syndic}
				bind:cs={form.envoyer_cs}
			/>
		</div>
	</div>
	<div class="form-actions">
		<button class="btn btn-primary" disabled={submitting}>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button>
	</div>
</form>

<style>
	/*  Mêmes règles, même raison que dans `FormulairePrestation` : le balisage
	    part avec ses styles, sinon la grille reste dans la page et le formulaire
	    s'affiche en une colonne écrasée (#344, reproduit le 15/08/2026). */
	.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); gap: .75rem; }
	.form-grid .field { margin-bottom: 0; }
</style>
