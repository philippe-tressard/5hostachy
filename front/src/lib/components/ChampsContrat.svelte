<!--
  ChampsContrat.svelte — les champs d'un contrat d'entretien, écrits UNE fois.

  ## Pourquoi (30/08/2026, #453 · #491)

  `prestataires/+page.svelte` rendait ce formulaire **deux fois** : dans la
  modale « Nouveau / Modifier contrat », et dans l'édition en ligne au sein de la
  carte du contrat. Quatre-vingt-dix lignes chacune, à l'indentation près.

  Le garde-fou de modularité a refusé un ajout de quatorze lignes à ce fichier.
  Il ne disait pas « il est trop long », il disait **« le code est au mauvais
  endroit »** (#453, la troisième des trois réponses possibles).

  ## 🔴 Les quatre divergences que la copie avait fabriquées

  Comparées ligne à ligne, indentation retirée — aucune n'est une décision :

  | | Modale | Édition en ligne |
  |---|---|---|
  | **Équipement** | présent | **ABSENT** — on ne pouvait pas le changer là |
  | Libellé | `champ-large` | `field` nu, donc écrasé dans un tiers de grille |
  | Notes, pour un lecteur d'écran | `ariaLabelledby` | **rien** — groupe sans nom |
  | Aide des notes | « Notes sur le contrat… » | « Notes… » |

  La première est un **champ manquant** : le type d'équipement appartient au
  contrat, il se saisit dans les deux rendus ou dans aucun. Le cadre #430 pose la
  question ainsi — *devant un écart entre deux états, lequel des deux a tort ?* —
  et ici c'est l'édition en ligne.

  Ce n'est pas de l'inattention : **c'est la duplication du rendu qui le
  produit**, mécaniquement, comme le crayon et la corbeille du fil de tickets
  (#431) qui avaient divergé deux fois dans les deux sens.

  ## Ce qui reste dans l'écran

  Le bloc **Documents** : sa source d'identifiant diffère (`editContratId` dans
  la modale, `c.id` dans la carte) et son enveloppe aussi (`.contrat-section`).
  Le passer ici demanderait de faire voyager la table des documents et son
  téléversement — un autre lot, et il est nommé dans #390.
-->
<script context="module" lang="ts">
	let compteur = 0;
</script>

<script lang="ts">
	import RichEditor from '$lib/components/RichEditor.svelte';

	/** Le formulaire lié — l'écran porte l'état et l'enregistre. */
	export let contratForm: any;
	/** Les prestataires proposables. */
	export let prestataires: any[] = [];
	/** La table des équipements (`{ val, label }`). */
	export let equipements: readonly { val: string; label: string }[] = [];

	//  Un identifiant par instance : les deux rendus coexistent dans la même page,
	//  et deux `id` identiques feraient pointer les deux `aria-labelledby` sur le
	//  premier — un défaut qui ne se voit qu'au lecteur d'écran.
	const idNotes = `contrat-notes-${++compteur}`;
</script>

<div class="form-grid">
	<label class="field champ-large"
		>Libellé *<input bind:value={contratForm.libelle} required /></label
	>
	<label class="field"
		>Prestataire *
		<select bind:value={contratForm.prestataire_id} required>
			<option value="">— Sélectionner —</option>
			{#each prestataires as pr}<option value={String(pr.id)}>{pr.nom}</option>{/each}
		</select>
	</label>
	<!--  🔴 Ce champ MANQUAIT à l'édition en ligne avant le 30/08/2026 : le type
	      d'équipement d'un contrat ne s'y modifiait pas, et rien ne le disait. -->
	<label class="field"
		>Équipement
		<select bind:value={contratForm.type_equipement}>
			{#each equipements as e}<option value={e.val}>{e.label}</option>{/each}
		</select>
	</label>
	<label class="field">N° contrat<input bind:value={contratForm.numero_contrat} /></label>
	<label class="field"
		>Début *<input type="date" bind:value={contratForm.date_debut} required /></label
	>
	<label class="field"
		>Durée initiale
		<div style="display:flex;gap:.4rem">
			<input
				type="number"
				min="1"
				placeholder="Ex. 12"
				bind:value={contratForm.duree_initiale_valeur}
				style="flex:1"
			/>
			<select bind:value={contratForm.duree_initiale_unite} style="width:auto">
				<option value="mois">mois</option>
				<option value="ans">ans</option>
			</select>
		</div>
	</label>
	<label class="field"
		>Fréquence
		<select bind:value={contratForm.frequence_type}>
			<option value="">— Aucune —</option>
			<option value="semaines">Toutes les X semaines</option>
			<option value="mois">Mensuelle</option>
			<option value="fois_par_an">X fois par an</option>
			<option value="ans">Tous les X ans</option>
		</select>
	</label>
	{#if contratForm.frequence_type === 'semaines'}
		<label class="field"
			>Toutes les … sem.<input
				type="number"
				min="1"
				bind:value={contratForm.frequence_valeur}
			/></label
		>
	{:else if contratForm.frequence_type === 'fois_par_an'}
		<label class="field"
			>… fois/an<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label
		>
	{:else if contratForm.frequence_type === 'ans'}
		<label class="field"
			>Tous les … ans<input
				type="number"
				min="1"
				bind:value={contratForm.frequence_valeur}
			/></label
		>
	{/if}
	<label class="field"
		>Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label
	>
</div>
<div style="margin-top:.6rem">
	<span class="libelle-groupe" id={idNotes} style="font-weight:600;margin-bottom:.3rem">Notes</span>
	<RichEditor
		bind:value={contratForm.notes}
		ariaLabelledby={idNotes}
		placeholder="Notes sur le contrat…"
		minHeight="60px"
	/>
</div>
