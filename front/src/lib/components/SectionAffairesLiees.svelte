<!--
  SectionAffairesLiees.svelte — « Affaires liées » (#1342, 26/09/2026).

  Les affaires qui parlent de la même chose : une fuite et la tache qu'elle a
  faite au plafond du dessous. Chaque affaire se RECONNAÎT à son titre, dans la
  liste proposée comme une fois retenue — c'était la demande : un numéro seul
  ne dit rien.

  ## Ce que le serveur décide, et que cet écran ne rejoue pas

  - la liste proposée (`GET /tickets/choix`) ne contient que ce que le lecteur
    peut LIRE ; une affaire liée qu'il ne peut pas lire ne lui est pas rendue ;
  - le lien est réciproque ; une Suite ajoute sans retirer
    (`api/app/utils/affaires_liees.py`).

  La recherche elle-même — chargement au focus, affaires ouvertes récentes
  quand le champ est vide — est `ChoixAffaire`, partagée avec la réaffectation
  d'un transfert de courriel (#1482).
-->
<script lang="ts">
	import type { AffaireLiee } from '$lib/api/types';
	import ChoixAffaire from '$lib/components/ChoixAffaire.svelte';
	import PastilleRetirable from '$lib/components/PastilleRetirable.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';

	/** Les affaires retenues — lié : l'appelant en envoie les `id`. */
	export let liees: AffaireLiee[] = [];
	/** L'affaire qu'on édite : elle ne se propose pas à elle-même. */
	export let exclure: number | null = null;
	export let idPrefixe = 'ticket';
	/** Relayé depuis la déclaration (`lint:pliage-transmis`). */
	export let pliable = false;
	export let inactive = '';

	$: ecartees = [...(exclure === null ? [] : [exclure]), ...liees.map((l) => l.id)];

	function retenir(a: AffaireLiee) {
		liees = [...liees, a];
	}

	function retirer(id: number) {
		liees = liees.filter((l) => l.id !== id);
	}

	$: resume = liees.length === 0 ? 'aucune' : liees.map((l) => l.numero).join(', ');
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.affaires_liees}
	{pliable}
	{inactive}
	rempli={liees.length > 0}
	{resume}
	valeurModifiee={liees.length > 0}
	pour="{idPrefixe}-affaires-liees"
>
	{#if liees.length > 0}
		<div class="liees">
			{#each liees as l (l.id)}
				<PastilleRetirable
					prefixe={l.numero}
					nom={l.titre}
					aideRetirer="Retirer ce lien"
					on:click={() => retirer(l.id)}
				/>
			{/each}
		</div>
	{/if}
	<ChoixAffaire
		id="{idPrefixe}-affaires-liees"
		exclure={ecartees}
		on:choisir={(e) => retenir(e.detail)}
	/>
	<p class="aide">Le lien vaut dans les deux sens : l’autre affaire citera celle-ci.</p>
</SectionFormulaire>

<style>
	.liees {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 0.5rem;
	}
</style>
