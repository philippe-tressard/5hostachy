<!--
  Le formulaire de dépôt d'une idée — extrait de `sondages/+page.svelte` le
  16/08/2026.

  POURQUOI. La page portait TROIS formulaires de création (sondage, idée, annonce)
  et 868 lignes : le garde-fou de modularité a refusé qu'elle grossisse encore
  (`standards/02` §6). La règle est de découper quand on y touche, et c'est ce
  bloc-ci qui part — le plus autonome des trois, avec son propre état et sa propre
  responsabilité.

  Il suit le contrat de `FormulaireActualite` et `FormulaireTicket` : il porte sa
  boîte `FormulaireCreation` et signale la création par l'événement `cree`.

  ⚠️ Deux défauts d'UX corrigés au passage, tous deux du même genre que ceux
  signalés par l'utilisateur sur les autres écrans :
    • le bouton « Soumettre » était posé NU dans le formulaire, donc cadré à
      GAUCHE, alors que `.form-actions` aligne à droite partout ailleurs ;
    • le champ Titre portait une mise en forme en `style=` au lieu d'hériter de
      `.field`, et n'occupait pas la ligne entière alors que c'est un texte libre
      (skill `ux-patterns` §9 bis).
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import { sectionPresente, type Etat } from '$lib/entites/types';
	import { IDEE } from '$lib/entites/idee';
	import { perimetreDefautListe } from '$lib/perimetres';
	import { idees as ideesApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';

	//  L'API des idées ne rend pas de type dédié : l'événement porte l'objet créé
	//  tel quel, et la page recharge sa liste depuis le serveur.
	const dispatch = createEventDispatcher<{ cree: unknown; annule: void }>();

	let form = { titre: '', description: '' };
	let perimetreCible: string[] = perimetreDefautListe();
	let submitting = false;

	/**  Ce formulaire ne sert que le DÉPÔT. L'état est écrit en constante plutôt
	 *   qu'en prop : corriger une idée déposée n'existe pas côté produit, et
	 *   l'écrire ainsi rend le manque visible en relecture. */
	const etat: Etat = 'creation';

	async function creer() {
		if (!form.titre || !form.description) {
			toast('error', 'Titre et description obligatoires');
			return;
		}
		submitting = true;
		try {
			const idee = await ideesApi.create({ ...form, perimetre_cible: perimetreCible });
			form = { titre: '', description: '' };
			perimetreCible = perimetreDefautListe();
			toast('success', 'Idée soumise !');
			dispatch('cree', idee);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}
</script>

<FormulaireCreation titre="Nouvelle idée">
	<form on:submit|preventDefault={creer}>
		<label class="field champ-large">
			Titre *
			<input
				bind:value={form.titre}
				placeholder="Ex. Vélos électriques en libre-service"
				required
			/>
		</label>
		<!--  4 et 6 : le PÉRIMÈTRE et la description, hérités du composant partagé.
		      Le périmètre est arrivé le 18/08/2026 (migration 0153) — l'idée était la
		      dernière entité de la Communauté sans aucune notion de lieu, alors que
		      « un local à vélos dans le bâtiment 3 » et « l'éclairage du parking » ne
		      concernent pas les mêmes voisins.

		      Les sections 2, 5, 7, 8 et 9 sont `sansObjet` : la déclaration le dit, et
		      c'est elle qui les fait disparaître — pas une condition écrite ici. -->
		<ChampsCommuns
			idPrefixe="idee"
			avecPerimetre={sectionPresente(IDEE, etat, 'perimetre')}
			bind:perimetre={perimetreCible}
			avecDescription={sectionPresente(IDEE, etat, 'description')}
			descriptionRequise
			bind:description={form.description}
			descriptionPlaceholder="Décrivez votre idée…"
		/>
		<!--  « Annuler » est À CÔTÉ d'« Enregistrer » — norme du 18/08/2026, posée
		      sur Tickets, constatée, puis étendue. L'en-tête de page ne porte plus
		      de seconde commande d'annulation (#367). -->
		<div class="form-actions">
			<button type="button" class="btn btn-outline" on:click={() => dispatch('annule')}
				>Annuler</button
			>
			<button class="btn btn-primary" disabled={submitting}
				>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button
			>
		</div>
	</form>
</FormulaireCreation>
