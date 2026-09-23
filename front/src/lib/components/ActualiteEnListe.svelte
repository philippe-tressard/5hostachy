<!--
  ActualiteEnListe.svelte — une actualité dans la liste des AFFAIRES.

  ## Pourquoi (23/09/2026, #1091 lot 4 et #1092)

  Arbitré à l'écran : *« la notion d'actualité n'existe plus ; c'est une affaire
  (tout est centralisé dans cette vue) »*. La page Actualités disparaît, et ses
  cartes paraissent dans la liste des affaires, sous le filtre « Actualité ».

  Une actualité y garde son ALLURE — `CarteActualite`, sans numéro ni état de
  suivi — parce que c'est ce qui la distingue d'un dossier à traiter. Ses
  GESTES, eux, sont ceux de toute affaire : ce composant reçoit le même objet
  `gestes` que `CarteTicket`, et n'écrit aucun appel à l'API de son côté — une
  seconde écriture divergerait au premier écart. `ListeTickets` choisit entre
  les deux cartes ; la page n'en sait rien.

  Ce qui vivait dans `routes/(app)/actualites/+page.svelte` et vit ici :

  | Geste | Relais |
  |---|---|
  | ↩️ Suite (commentaire, ciblage, mise en avant) | `gestes.evoluer` |
  | ✏️ correction — `FormulaireActualite`, en modale | `gestes.modifie` |
  | ⚙️ Options rapides — épinglage, urgence | `gestes.optionsEnregistrer` |
  | 🎯 En faire une affaire suivie (#1094) | `promouvoirActualite` → `gestes.modifie` |
  | 🗑️ Supprimer (admin) | `gestes.supprimer` |
-->
<script lang="ts">
	import { documents as docsApi, type Ticket, type TicketEvolution } from '$lib/api';
	import { contexteCommentaire } from '$lib/assistant';
	import { PUBLICATION } from '$lib/entites/publication';
	import { fichiersDepuisUrls } from '$lib/fichiers';
	import { SUITE } from '$lib/gestes';
	import { promouvoirActualite } from '$lib/gestes-actualite';
	import { motifWhatsappInterdit } from '$lib/options-publication';
	import { reserveAuConseil } from '$lib/destinataires';
	import { nomCopie } from '$lib/saisi-pour';
	import { currentUser, isCS } from '$lib/stores/auth';
	import { ticketUrgent, type GestesTicket } from '$lib/tickets';
	import ActionsActualite from './ActionsActualite.svelte';
	import CarteActualite from './CarteActualite.svelte';
	import EvolForm from './EvolForm.svelte';
	import FormulaireActualite from './FormulaireActualite.svelte';
	import PanneauOptionsPublication from './PanneauOptionsPublication.svelte';
	import RubriqueHistorique from './RubriqueHistorique.svelte';
	import SectionOptionsPublication from './SectionOptionsPublication.svelte';

	export let ticket: Ticket;
	export let evolutions: TicketEvolution[] = [];
	export let expanded = false;
	/** Allure d'archive — atténuée, sans épingle ni « New ». */
	export let archive = false;
	/** Ce que la page a ouvert sur CETTE carte — le même contrat que `CarteTicket`. */
	export let mode: 'lecture' | 'edition' | 'evolution' | 'options' = 'lecture';
	export let optionsRapidesEnCours = false;
	export let evolutionEnCours = false;
	export let evolEnEdition: number | null = null;
	export let evolCorrectionEnCours = false;
	export let peutAdministrer = false;
	export let gestes: GestesTicket;

	//  Mise en avant d'une actualité : épinglage et urgence (#1096). Copie de
	//  travail — on n'écrit dans l'affaire qu'après la réponse du serveur.
	const OPTIONS: ('epingle' | 'urgente')[] = ['epingle', 'urgente'];
	const optionsInitiales = () => ({
		epingle: ticket.epingle ?? false,
		urgente: ticketUrgent(ticket),
		brouillon: false,
		confidentiel: false,
	});
	let options = optionsInitiales();
	//  Reprise à chaque ouverture : un panneau abandonné ne laisse rien derrière.
	$: if (mode === 'options' || mode === 'evolution') options = optionsInitiales();

	//  Les `Document` des ANCIENNES publications, chargés au premier dépliage.
	//  Une actualité récente n'en a aucun : ses pièces sont en URLs.
	let documents: any[] = [];
	let documentsCharges = false;
	$: if (expanded && !documentsCharges) chargerDocuments();
	async function chargerDocuments() {
		documentsCharges = true;
		try {
			documents = await docsApi.listByTicket(ticket.id);
		} catch {
			/* la carte se lit sans eux */
		}
	}

	const idSi = (m: typeof mode) => (mode === m ? ticket.id : null);
</script>

<CarteActualite
	pub={ticket}
	{expanded}
	variante={archive ? 'historique' : 'fil'}
	{documents}
	formulaireOuvert={mode === 'evolution' || mode === 'options'}
	on:toggle={() => gestes.basculer(ticket)}
>
	<svelte:fragment slot="actions">
		{#if !archive}
			<ActionsActualite
				pub={ticket}
				commentaireOuvertId={idSi('evolution')}
				editionOuverteId={idSi('edition')}
				optionsOuvertesId={idSi('options')}
				onCommenter={gestes.evoluerOuvrir}
				onModifier={gestes.modifier}
				onOptions={gestes.optionsOuvrir}
				onPromouvoir={(p) => promouvoirActualite(p, gestes.modifie)}
				onSupprimer={gestes.supprimer}
			/>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="formulaire">
		{#if mode === 'options'}
			<PanneauOptionsPublication
				optionsRendues={OPTIONS}
				perimetreCible={ticket.perimetre_cible ?? []}
				dejaEpingle={ticket.epingle ?? false}
				bind:options
				enregistrement={optionsRapidesEnCours}
				on:enregistrer={() =>
					gestes.optionsEnregistrer(ticket, { epingle: options.epingle, urgente: options.urgente })}
				on:annuler={gestes.annuler}
			/>
		{:else if mode === 'evolution'}
			<!--  `role="presentation"` : ce conteneur n'est qu'un relais qui arrête la
			      propagation, pour que saisir ne referme pas la carte. -->
			<div
				class="evol-form"
				role="presentation"
				on:click|stopPropagation
				on:keydown|stopPropagation
			>
				<!--  AUCUNE option d'état : une actualité n'a pas de suivi (#1091). -->
				<EvolForm
					idPrefixe="actu-evol-{ticket.id}"
					auteurNom={nomCopie(ticket)}
					titre={SUITE.libelle}
					statutOptions={[]}
					whatsappInterdit={motifWhatsappInterdit(
						reserveAuConseil(ticket.public_cible),
						'actualité',
					)}
					defaultEnvoyerSyndic={ticket.destinataire_syndic ?? false}
					defaultEnvoyerCs={ticket.destinataire_cs ?? false}
					showEmail={$isCS}
					entite={PUBLICATION}
					assistant={contexteCommentaire(ticket)}
					saving={evolutionEnCours}
					perimetreCourant={ticket.perimetre_cible ?? []}
					initialDestinataires={ticket.public_cible ?? []}
					aidePerimetre="Le périmètre en vigueur est repris tel quel : le corriger ici corrige l'actualité entière."
					on:submit={(e) =>
						gestes.evoluer(ticket, {
							...e.detail,
							epingle: options.epingle,
							urgente: options.urgente,
						})}
					on:cancel={gestes.annuler}
				>
					<svelte:fragment slot="specifiques" let:premiere>
						<SectionOptionsPublication
							{premiere}
							options={OPTIONS}
							perimetreCible={ticket.perimetre_cible ?? []}
							dejaEpingle={ticket.epingle ?? false}
							bind:epingle={options.epingle}
							bind:urgente={options.urgente}
						/>
					</svelte:fragment>
				</EvolForm>
			</div>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="apres-corps">
		{#if evolutions.length}
			<div class="actu-fil">
				<RubriqueHistorique
					{evolutions}
					peutModifier={$isCS}
					currentUserId={$currentUser?.id}
					estAdmin={peutAdministrer}
					avecSuppression
					enEdition={evolEnEdition}
					on:modifier={(e) => gestes.evolModifier(e.detail)}
					on:supprimer={(e) => gestes.evolSupprimer({ ticket, evolId: e.detail })}
				>
					<svelte:fragment slot="edition" let:evol>
						<EvolForm
							idPrefixe="actu-evol-edit-{evol.id}"
							auteurNom={nomCopie(ticket)}
							titre="Modifier le commentaire"
							editMode={true}
							initialContenu={evol.contenu || ''}
							initialFichiers={fichiersDepuisUrls(evol.fichiers_urls)}
							entite={PUBLICATION}
							assistant={contexteCommentaire(ticket)}
							saving={evolCorrectionEnCours}
							on:submit={(e) => gestes.evolCorriger(ticket, e.detail)}
							on:cancel={gestes.evolAnnuler}
						/>
					</svelte:fragment>
				</RubriqueHistorique>
			</div>
		{/if}
	</svelte:fragment>
</CarteActualite>

<!--  Correction — LE MÊME composant qu'à la création (#433), en modale : il sort
      de la carte, que replier pendant la saisie effacerait avec elle (#640). -->
{#if mode === 'edition'}
	{#key ticket.id}
		<FormulaireActualite
			affaire={ticket}
			on:modifie={(e) => gestes.modifie(e.detail)}
			on:annule={gestes.annuler}
		/>
	{/key}
{/if}

<style>
	/*  La marge qui sépare le fil de ce qu'il suit — le parent seul sait ce
	    qu'il y a au-dessus. */
	.actu-fil {
		margin-top: 0.9rem;
	}
	.evol-form {
		padding: 0.5rem 0;
	}
</style>
