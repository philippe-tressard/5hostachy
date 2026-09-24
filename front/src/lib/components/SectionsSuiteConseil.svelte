<!--
  SectionsSuiteConseil.svelte — ce que le CONSEIL pose dans une Suite 🔄 :
  Équipement, Quand, Intervenant, puis les options de publication.

  ## Pourquoi (#1207, arbitré le 24/09/2026)

  Un membre du conseil qui n'est pas administrateur n'avait AUCUN chemin
  d'écran pour dater l'affaire d'un résident, désigner son intervenant ou son
  équipement : le crayon ne lui est pas montré (`droits.peutEditer`), et le
  serveur refuse qu'il réécrive le texte d'un autre. Ces trois sections sont
  pourtant les siennes (`inactivePour.resident`). Arbitré : « via la Suite » —
  chaque changement laisse sa trace au fil de l'affaire.

  Rendu dans le créneau `specifiques` d'`EvolForm`, à la place des seules
  options : la carte et la fiche d'une affaire l'emploient, jamais une copie.
  Hors conseil, ou sur une actualité, il ne rend que les options — comme avant.
  Les règles serveur sont celles de la correction (`utils/intervenant`,
  `_appliquer_quand`), appliquées par `add_evolution`.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { prestataires as prestatairesApi, type Ticket } from '$lib/api';
	import { essayer } from '$lib/chargement';
	import { depuisChampLocal, pourChampLocal } from '$lib/date';
	import { estBati, intervenantPropose, natureDe } from '$lib/formulaire-affaire';
	import { isCS } from '$lib/stores/auth';
	import OptionsEvolutionTicket from './OptionsEvolutionTicket.svelte';
	import SectionEquipement from './SectionEquipement.svelte';
	import SectionIntervenant from './SectionIntervenant.svelte';
	import SectionQuand from './SectionQuand.svelte';

	export let ticket: Ticket;
	export let premiere = false;
	/** Les options de publication, liées comme avant — et `planification`, ce
	 *  que la Suite envoie en plus, qu'`optionsVersTicket` fait voyager. Le serveur
	 *  ne change que ce qui diffère de l'affaire : renvoyer une valeur inchangée
	 *  est muet. Vide hors conseil. */
	export let options: {
		epingle: boolean;
		urgente: boolean;
		brouillon: boolean;
		suiviKanban: boolean;
		planification?: Record<string, unknown>;
	};

	$: conseil = $isCS && natureDe(ticket.categorie) !== 'actualite';
	$: bati = estBati(ticket.categorie);

	let equipement = ticket.equipement ?? '';
	let prestataireId: number | null = ticket.prestataire_id ?? null;
	let debut = pourChampLocal(ticket.debut);
	let fin = pourChampLocal(ticket.fin);
	let prestataires: { id: number; nom: string; actif?: boolean; specialite?: string | null }[] = [];
	let contrats: {
		actif?: boolean;
		type_equipement?: string | null;
		prestataire_id?: number | null;
	}[] = [];
	let erreur = '';

	onMount(async () => {
		if (!conseil || !bati) return;
		[prestataires, erreur] = await essayer(prestatairesApi.list(), []);
		[contrats] = await essayer(prestatairesApi.contrats(), []);
	});

	//  L'équipement PROPOSE l'intervenant sous contrat, comme dans le formulaire.
	let equipementVu = equipement;
	$: if (equipement !== equipementVu) {
		equipementVu = equipement;
		if (prestataireId === null)
			prestataireId = intervenantPropose(equipement, contrats, prestataires);
	}

	$: options.planification = !conseil
		? {}
		: {
				debut: depuisChampLocal(debut),
				fin: depuisChampLocal(fin),
				...(bati ? { equipement: equipement || null, prestataire_id: prestataireId } : {}),
			};
</script>

{#if conseil}
	{#if bati}
		<SectionEquipement idPrefixe="suite-{ticket.id}" pliable bind:equipement />
	{/if}
	<SectionQuand idPrefixe="suite-{ticket.id}-quand" pliable bind:debut bind:fin />
	{#if bati}
		<SectionIntervenant
			idPrefixe="suite-{ticket.id}"
			pliable
			{equipement}
			{erreur}
			bind:prestataires
			bind:prestataireId
		/>
	{/if}
{/if}
<OptionsEvolutionTicket {premiere} bind:options />
