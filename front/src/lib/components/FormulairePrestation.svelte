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
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';

	/** L'objet de saisie, lié en deux sens : la page porte son cycle de vie. */
	export let devisForm: any;
	export let prestataires: any[] = [];
	export let statutsDevis: { val: string; label: string }[] = [];
	/**  Fichiers RETENUS, téléversés par la page une fois la prestation créée.
	     Ils ne peuvent pas partir à la sélection : ils sont stockés dans le
	     répertoire PRIVÉ et servis par une route authentifiée propre au devis —
	     les envoyer par l'endpoint générique les rendrait lisibles autrement, ce
	     qui est un changement d'exposition et non un détail d'implémentation.
	     D'où le mode différé de `FichiersUpload`.

	     ⚠️ Ne pas écrire ce chemin en toutes lettres ici : `test_endpoints_orphelins`
	     cherche les routes dans le TEXTE des sources, et un commentaire qui la
	     cite la ferait passer pour appelée. Elle ne l'est pas — son URL est
	     construite par le serveur et stockée en base. */
	export let devisFichiers: File[] = [];
	export let submitting = false;
	export let onSave: () => void;

	//  Le devis stocke UN code de périmètre (colonne `perimetre`), là où le
	//  sélecteur travaille sur une liste. La conversion se fait ICI et nulle part
	//  ailleurs. Passer le devis au tableau demanderait une migration — c'est un
	//  changement de contrat, pas un remplacement de composant, et il est suivi
	//  à part.
	let perimetreListe: string[] = [];
	let dernierDevis: any = null;
	$: if (devisForm !== dernierDevis) {
		dernierDevis = devisForm;
		perimetreListe = devisForm?.perimetre ? [devisForm.perimetre] : [];
	}
	$: if (devisForm) devisForm.perimetre = perimetreListe[0] ?? '';
</script>

<p class="devis-form-help">Les prestations ponctuelles alimentent le Calendrier et le Kanban selon leur statut.</p>

<!--  1. Titre. -->
<SectionFormulaire premiere>
	<div class="field champ-large">
		<label for="presta-titre">Titre *</label>
		<input id="presta-titre" bind:value={devisForm.titre} required />
	</div>
</SectionFormulaire>

<!--  2. Champs spécifiques. Le PÉRIMÈTRE était ici, coincé au milieu de la
      grille entre « Prestataire » et « Date » : c'est la section 4, elle vient
      après le workflow (`ux-patterns` §9 sexies, signalé le 16/08/2026). -->
<SectionFormulaire titre="Détails">
	<div class="form-grid">
		<div class="field champ-large">
			<label for="presta-prestataire">Prestataire *</label>
			<select id="presta-prestataire" bind:value={devisForm.prestataire_id} required>
				<option value="">— Sélectionner —</option>
				{#each prestataires as p}<option value={String(p.id)}>{p.nom}</option>{/each}
			</select>
		</div>
		<div class="field">
			<label for="presta-date">Date de prestation</label>
			<input id="presta-date" type="date" bind:value={devisForm.date_prestation} />
		</div>
		<div class="field">
			<label for="presta-montant">Montant estimé (€)</label>
			<input id="presta-montant" type="number" min="0" step="0.01" bind:value={devisForm.montant_estime} placeholder="Ex. 1200" />
		</div>
		<div class="field">
			<label for="presta-frequence">Fréquence</label>
			<select id="presta-frequence" bind:value={devisForm.frequence_type}>
				<option value=''>— Ponctuelle —</option>
				<option value='fois_par_an'>× / an</option>
				<option value='mois'>Tous les N mois</option>
				<option value='semaines'>Toutes les N semaines</option>
				<option value='ans'>Tous les N ans</option>
			</select>
		</div>
		{#if devisForm.frequence_type}
			<!--  Champ conditionnel : il n'apparaît qu'une fois une fréquence choisie,
			      ce qui explique qu'il ait échappé au premier passage — la capture qui
			      a servi à signaler les champs blancs ne le montrait pas. -->
			<div class="field">
				<label for="presta-frequence-valeur">Valeur</label>
				<input id="presta-frequence-valeur" type="number" min="1" bind:value={devisForm.frequence_valeur} />
			</div>
		{/if}
	</div>
</SectionFormulaire>

<!--  3. Workflow — où en est la prestation. -->
<SectionFormulaire titre="Suivi Kanban" pour="presta-kanban">
	<div class="field champ-large">
		<select id="presta-kanban" bind:value={devisForm.statut}>
			{#each statutsDevis as s}<option value={s.val}>{s.label}</option>{/each}
		</select>
	</div>
</SectionFormulaire>

<!--  4 à 9 : ordre, intitulés et séparations hérités du composant partagé.
      Les canaux de diffusion n'étaient rendus QUE dans le formulaire d'édition
      de la même page : on pouvait modifier une prestation pour la partager, pas
      la créer en la partageant. -->
<ChampsCommuns
	idPrefixe="presta"
	avecPerimetre perimetreMode="single" bind:perimetre={perimetreListe}
	avecDescription bind:description={devisForm.notes}
	descriptionPlaceholder="Description de la prestation…"
	avecDocuments documentsDifferes bind:documentsFichiers={devisFichiers}
	avecDiffusion
	bind:whatsapp={devisForm.partager_whatsapp}
	bind:syndic={devisForm.envoyer_syndic}
	bind:cs={devisForm.envoyer_cs}
>
	<svelte:fragment slot="diffusion">
		<div class="field champ-large">
			<label class="case">
				<input type="checkbox" bind:checked={devisForm.affichable} />
				<span>Afficher dans le tableau de bord</span>
			</label>
		</div>
	</svelte:fragment>
</ChampsCommuns>

<!--  PAS de bouton « Annuler » ici : la commande vit dans l'en-tête de page,
      où le bouton d'ouverture bascule (`BoutonNouveau`). Deux commandes pour
      un seul formulaire est le défaut relevé sur la modale du calendrier (#367). -->
<div class="form-actions">
	<button class="btn btn-primary" disabled={submitting} on:click={onSave}>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button>
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
	.form-grid { grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr)); gap: .65rem; }
	.form-grid .field { margin-bottom: 0; }

	.devis-form-help { margin: 0 0 .75rem; font-size: .82rem; color: var(--color-text-muted); line-height: 1.45; }

	/*  `.intitule-champ` et `.devis-file-note` ont disparu : la description et les
	    fichiers passent par `ChampsCommuns`, qui porte leur intitulé et leur
	    compteur. `.form-actions` n'est PAS redéfini non plus — app.css le porte,
	    et cette copie était identique, donc inerte (même nettoyage que le 15/08). */

	/*  Une case et son libellé, nommés au lieu d'être écrits en `style=` avec un
	    `width:auto` posé à la main pour annuler le `width:100%` des champs. */
</style>
