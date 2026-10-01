<!--
  L'onglet « Prestataires » (l'annuaire) de la page des prestataires — extrait
  le 01/10/2026 (#779), la page passait 788 lignes. Il possède ses filtres, la
  création, la correction dans la carte et le lien profond `#presta-<id>`. La
  page garde le chargement des listes et le bouton « Nouveau prestataire » de
  son en-tête, qui appelle `basculerCreation`.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { confirmerPuis } from '$lib/confirmation';
	import { tenter } from '$lib/erreurs';
	import { basculer } from '$lib/accordeon';
	import { prestataires as prestApi } from '$lib/api';
	import { isCS } from '$lib/stores/auth';
	import { toast } from '$lib/components/Toast.svelte';
	import {
		EQUIPEMENTS as equipements,
		TYPES_PRESTATAIRE as typesPrestataire,
		filtresVides,
		filtresActifs,
		filtrerPrestataires,
		contactsAEnvoyer,
		contactsDepuis,
		prestataireDepuis,
	} from '$lib/prestataires';
	import { telephonesDe } from '$lib/utils';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import FiltresPrestataires from '$lib/components/FiltresPrestataires.svelte';
	import ChampsPrestataire from '$lib/components/ChampsPrestataire.svelte';
	import CartePrestataire from '$lib/components/CartePrestataire.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import IntertitreGroupe from '$lib/components/IntertitreGroupe.svelte';

	export let prestataires: any[] = [];
	export let contrats: any[] = [];
	export let notations: any[] = [];
	/** La boîte de création est ouverte — lue par le bouton de l'en-tête. */
	export let creationOuverte = false;

	//  Une seule fiche dépliée à la fois (`$lib/accordeon`) : c'était un `Set`
	//  remis à un élément, déclaré en exception jusqu'au 01/10/2026 (#779).
	let ouvert: number | null = null;
	let submitting = false;

	let editPrestId: number | null = null;
	let prestForm = prestataireDepuis();
	let prestContacts = contactsDepuis();

	let filtres = filtresVides();
	$: filteredPrests = filtrerPrestataires(prestataires, contrats, filtres);
	$: compactPrests = filteredPrests.length > 7;

	//  Tous les contrats du prestataire, assurances et mandats compris : la carte
	//  les montre. `contratsDuPrestataire` (`$lib/prestataires`) répond à une
	//  autre question — sous quel contrat il peut INTERVENIR — et les écarte.
	function contratsForPrest(prestId: number): any[] {
		return contrats.filter((c) => c.prestataire_id === prestId);
	}

	function nextVisitForPrest(prestId: number): string | null {
		const dates = contrats
			.filter((c) => c.prestataire_id === prestId && c.prochaine_visite)
			.map((c) => c.prochaine_visite as string)
			.sort();
		return dates[0] ?? null;
	}

	//  Lien profond `#presta-<id>` : la page a déjà conduit ici l'adresse qui le
	//  portait (elle s'ouvre sur « Contrats » par défaut — signalé le 28/07/2026).
	onMount(() => {
		const idPresta = cibleDuHash('presta');
		if (idPresta === null) return;
		ouvert = idPresta;
		revelerCible(`presta-${idPresta}`);
	});

	function resetPrestForm() {
		prestForm = prestataireDepuis();
		prestContacts = contactsDepuis();
		editPrestId = null;
	}

	/** Le geste du bouton « Nouveau prestataire » de l'en-tête de la page. */
	export function basculerCreation() {
		creationOuverte = !creationOuverte;
		//  Ouvrir la création referme une correction en cours : deux boîtes
		//  ouvertes en même temps, c'est le défaut des contrats du 10/09.
		if (creationOuverte) editPrestId = null;
		else resetPrestForm();
	}

	function fermerCreation() {
		creationOuverte = false;
		resetPrestForm();
	}

	function startEditPrest(p: any) {
		prestForm = prestataireDepuis(p);
		prestContacts = contactsDepuis(p);
		//  🔴 On n'ouvre PAS le formulaire de tête, et on ne fait PAS défiler : la
		//  correction s'ouvre dans la carte du prestataire, là où est le crayon
		//  (`CartePrestataire`). Un `scrollTo` était la cause exacte du symptôme
		//  signalé le 11/09/2026 — la page remontait, et l'objet corrigé quittait
		//  sa place sous les yeux.
		editPrestId = p.id;
	}

	async function savePrest() {
		if (!prestForm.nom || !prestForm.specialite) {
			toast('error', 'Nom et équipement obligatoires');
			return;
		}
		const { contacts, telephone } = contactsAEnvoyer(prestContacts);
		submitting = true;
		await tenter(
			async () => {
				if (editPrestId) {
					await prestApi.update(editPrestId, { ...prestForm, telephone, contacts });
				} else {
					await prestApi.create({ ...prestForm, telephone, contacts });
				}
				prestataires = await prestApi.list();
				fermerCreation();
			},
			editPrestId ? 'Prestataire modifié' : 'Prestataire ajouté',
		);
		submitting = false;
	}

	async function deletePrest(id: number) {
		await confirmerPuis('Archiver ce prestataire ?', 'Archivé', async () => {
			await prestApi.delete(id);
			prestataires = prestataires.filter((p) => p.id !== id);
		});
	}
</script>

<FiltresPrestataires bind:filtres />

<!--  🔴 La CRÉATION seulement. Corriger un prestataire ouvre le formulaire DANS
      sa carte, à la place de son corps — le motif des tickets, appliqué aux
      contrats le 10/09/2026 et signalé ici le 11/09 : le crayon est dans la
      carte, la boîte s'ouvrait en tête de liste.
      Aucune `cle` : rien n'a bougé, il n'y a rien à ramener à l'écran. -->
{#if $isCS && creationOuverte}
	<FormulaireCreation titre="Nouveau prestataire">
		<form on:submit|preventDefault={savePrest}>
			<ChampsPrestataire
				bind:prestForm
				bind:prestContacts
				{typesPrestataire}
				{equipements}
				etat="creation"
			/>
			<PiedFormulaire enCours={submitting} on:annule={fermerCreation} />
		</form>
	</FormulaireCreation>
{/if}

{#if filteredPrests.length === 0}
	<div class="empty-state card">
		<h3>Aucun prestataire{filtresActifs(filtres) ? ' pour ces critères' : ''}</h3>
	</div>
{:else}
	{#each typesPrestataire.filter( (t) => filteredPrests.some((p) => p.type_prestataire === t.val) ) as typeGroup (typeGroup.val)}
		{#if !filtres.type}
			<IntertitreGroupe libelle={typeGroup.label} descriptif={typeGroup.desc} />
		{/if}
		{#each filteredPrests.filter((p) => p.type_prestataire === typeGroup.val) as p (p.id)}
			<CartePrestataire
				{p}
				cs={contratsForPrest(p.id)}
				nextVisit={nextVisitForPrest(p.id)}
				notations={notations.filter((n) => n.prestataire_id === p.id)}
				expanded={ouvert === p.id}
				{compactPrests}
				peutModifier={$isCS}
				{telephonesDe}
				{editPrestId}
				bind:prestForm
				bind:prestContacts
				{typesPrestataire}
				{equipements}
				{submitting}
				onBasculer={(id) => (ouvert = basculer(ouvert, id))}
				onModifier={startEditPrest}
				onArchiver={deletePrest}
				onAnnuler={fermerCreation}
				onEnregistrer={savePrest}
				on:supprimee={(e) => (notations = notations.filter((n) => n.id !== e.detail))}
			/>
		{/each}
	{/each}
{/if}
