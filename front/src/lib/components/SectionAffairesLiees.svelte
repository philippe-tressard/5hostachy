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

  La liste se charge quand le champ prend le focus, pas à l'ouverture du
  formulaire : la section est pliée, et la plupart des affaires n'en lient
  aucune.

  Champ vide, elle propose les affaires ENCORE OUVERTES les plus récentes
  (demandé à l'écran le 26/09/2026) — c'est le plus souvent parmi elles qu'on
  cherche ; une frappe cherche dans toutes, closes comprises.
-->
<script lang="ts">
	import { tickets as ticketsApi } from '$lib/api';
	import type { AffaireLiee } from '$lib/api/types';
	import PastilleRetirable from '$lib/components/PastilleRetirable.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';
	import { estTicketActif } from '$lib/tickets';

	/** Les affaires retenues — lié : l'appelant en envoie les `id`. */
	export let liees: AffaireLiee[] = [];
	/** L'affaire qu'on édite : elle ne se propose pas à elle-même. */
	export let exclure: number | null = null;
	export let idPrefixe = 'ticket';
	/** Relayé depuis la déclaration (`lint:pliage-transmis`). */
	export let pliable = false;
	export let inactive = '';

	/** Combien de propositions à la fois : au-delà, on affine la recherche. */
	const PROPOSITIONS_MAX = 8;

	let recherche = '';
	let choix: AffaireLiee[] | null = null;
	let echec = false;
	/** La liste est-elle déroulée ? Le focus l'ouvre, sa sortie la referme. */
	let deroulee = false;
	let zone: HTMLElement;

	async function charger() {
		if (choix !== null) return;
		try {
			choix = await ticketsApi.choix();
		} catch {
			//  Une liste absente n'empêche pas d'enregistrer le reste : on le dit.
			echec = true;
			choix = [];
		}
	}

	$: terme = recherche.trim().toLowerCase();
	$: retenues = new Set(liees.map((l) => l.id));
	//  `choix` arrive du plus récent au plus ancien : les premières sont les dernières.
	$: propositions = deroulee
		? (choix ?? [])
				.filter(
					(a) =>
						a.id !== exclure &&
						!retenues.has(a.id) &&
						(terme
							? `${a.numero} ${a.titre}`.toLowerCase().includes(terme)
							: estTicketActif(a.statut)),
				)
				.slice(0, PROPOSITIONS_MAX)
		: [];

	function ouvrir() {
		deroulee = true;
		void charger();
	}

	/** Le focus quitte la zone (champ + liste) : la liste se referme. */
	function sortie(e: FocusEvent) {
		if (!zone?.contains(e.relatedTarget as Node | null)) deroulee = false;
	}

	function retenir(a: AffaireLiee) {
		liees = [...liees, a];
		recherche = '';
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
	<div bind:this={zone} on:focusout={sortie}>
		<div class="field">
			<input
				id="{idPrefixe}-affaires-liees"
				type="search"
				placeholder="Numéro ou mots du titre"
				autocomplete="off"
				bind:value={recherche}
				on:focus={ouvrir}
				on:input={ouvrir}
				on:keydown={(e) => e.key === 'Escape' && (deroulee = false)}
			/>
		</div>
		{#if propositions.length > 0}
			{#if !terme}<p class="aide">Les plus récentes encore ouvertes :</p>{/if}
			<ul class="propositions" aria-label="Affaires proposées">
				{#each propositions as a (a.id)}
					<li>
						<button type="button" class="proposition" on:click={() => retenir(a)}>
							<span class="numero">{a.numero}</span>
							<span class="titre">{a.titre}</span>
						</button>
					</li>
				{/each}
			</ul>
		{:else if deroulee && choix !== null}
			<!--  Rien à proposer n'empêche jamais de chercher : on le dit. -->
			<p class="aide">
				{echec
					? 'La liste des affaires n’a pas pu être chargée.'
					: terme
						? 'Aucune affaire ne correspond.'
						: 'Aucune affaire ouverte récente : tapez un numéro ou un mot du titre pour chercher parmi toutes.'}
			</p>
		{/if}
	</div>
	<p class="aide">Le lien vaut dans les deux sens : l’autre affaire citera celle-ci.</p>
</SectionFormulaire>

<style>
	.liees {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 0.5rem;
	}
	.propositions {
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.propositions li + li {
		border-top: 1px solid var(--color-border);
	}
	/*  Une ligne entière cliquable, à hauteur de pouce (`standards/11` §10). */
	.proposition {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
		width: 100%;
		min-height: 44px;
		padding: 0.5rem 0.75rem;
		border: none;
		background: var(--color-surface, #fff);
		text-align: left;
		cursor: pointer;
		font: inherit;
	}
	.proposition:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: -2px;
	}
	@media (hover: hover) and (pointer: fine) {
		.proposition:hover .titre {
			color: var(--color-primary);
		}
	}
	.numero {
		flex-shrink: 0;
		font-size: 0.8rem;
		font-weight: 700;
		color: var(--color-text-muted);
	}
	.titre {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
