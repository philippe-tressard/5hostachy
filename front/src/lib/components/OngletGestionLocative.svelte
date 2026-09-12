<!--
  **L'onglet « Gestion locative »** de « Mes lots & accès » : les baux d'un
  bailleur, ses locataires, et ce qu'il leur a confié.

  ## Pourquoi extrait (12/09/2026, #928)

  La page a reçu deux sous-onglets d'accès, et le plafond de modularité a refusé
  les quarante-trois lignes que cela lui ajoutait. C'est le refus attendu : #928
  l'avait annoncé avant d'écrire une ligne — *« il faut factoriser dans `mon-lot`
  d'abord »*.

  🔴 Trois migrations vers `tenter` n'ont pas suffi (neuf lignes), et c'est une
  information : ce fichier n'était pas long par duplication, il était long parce
  qu'il porte DEUX écrans — les lots et la gestion locative. La coupe suit donc
  cette frontière-là, celle que la barre d'onglets dessine déjà.

  ⚠️ Le composant ne décide RIEN : il reçoit les baux, les libellés et les
  gestes. Les modales de confirmation (terminer, supprimer, accès) restent dans
  l'écran, avec l'état qu'elles pilotent — les faire voyager aurait demandé de
  remonter trois états liés pour n'en descendre qu'un.
-->
<script lang="ts">
	import FormulaireBail from '$lib/components/FormulaireBail.svelte';
	import InventaireBail from '$lib/components/InventaireBail.svelte';
	import { fmtDateShort as fmt } from '$lib/date';
	import { safeHtml } from '$lib/sanitize';
	import GesteEnPlace from '$lib/components/GesteEnPlace.svelte';
	import Onglet from '$lib/components/Onglet.svelte';
	import { isAdmin, isCS } from '$lib/stores/auth';
	import { TITRE_ARCHIVES } from '$lib/archives';

	//  Les routes viennent de la TABLE, jamais écrites ici (`lint:pages`).
	const ROUTE_BAUX_ACTIFS = routeSousOnglet('mon-lot', 'location', 'actif');
	const ROUTE_BAUX_ARCHIVES = routeSousOnglet('mon-lot', 'location', 'archives');
	import { routeSousOnglet } from '$lib/routes-onglets';

	/** Les baux, tels que l'écran les tient. */
	export let baux: any[] = [];
	export let bauxActifs: any[] = [];
	export let bauxTermines: any[] = [];
	export let bauxLoading = false;
	export let lots: any[] = [];

	/** Le sous-onglet courant — « actif » ou « archives ». */
	export let bailTab = 'actif';

	/** La boîte de création, ouverte depuis l'en-tête de page. */
	export let showNewBail = false;
	export let newBail: any;
	export let newBailLotIds: Set<number> = new Set();
	export let newBailLocataireId: number | null = null;
	export let lotsACocher: any[] = [];
	export let savingBail = false;

	/** Les gestes — l'écran les tient, parce qu'il tient les listes. */
	export let creerBail: () => void | Promise<void>;
	export let affecterAuto: (bail: any) => void | Promise<void>;
	export let ouvrirEditionLocataire: (bail: any) => void;
	export let ouvrirAccesBail: (bail: any) => void;
	export let majObjets: (bailId: number, objets: any[]) => void;
	export let statutBailLabel: Record<string, string>;
	export let nomLocataire: (bail: any) => string;

	/**  Les trois gestes de confirmation restent pilotés par l'ÉCRAN : leurs
	 *   modales y vivent, avec l'état qu'elles ferment. Les faire voyager
	 *   demanderait de remonter trois états liés pour n'en descendre qu'un. */
	export let bailATerminer: any = null;
	export let bailASupprimer: any = null;
	export let dateSortie = '';
	export let confirmerTerminer: () => void | Promise<void>;
</script>

<div style="max-width:900px">
	<!--  🔴 LA BOÎTE DANS LA PAGE, et non une modale (#367 / #672).

	      « Nouveau bail » était la dernière modale de création du site. Elle y
	      avait échappé parce que `lint:formulaires` ne cherchait qu'un `<form>`,
	      et ce formulaire n'en porte aucun — seulement des `.field`.

	      ⚠️ Le corps vit dans `FormulaireBail.svelte` : cette page pesait 2 229
	      lignes, et le contrôle de modularité refusait d'y ajouter la moindre
	      ligne. Comme les huit refus précédents, il désignait un PLACEMENT — la
	      saisie d'un bail n'a rien à faire dans l'écran qui liste les lots, les
	      baux, les accès et les diagnostics. -->
	{#if showNewBail}
		<FormulaireBail
			lots={lotsACocher}
			bind:lotIds={newBailLotIds}
			bind:bail={newBail}
			bind:locataireId={newBailLocataireId}
			enregistrement={savingBail}
			on:annuler={() => (showNewBail = false)}
			on:enregistrer={creerBail}
		/>
	{/if}

	<!--  Deux LIENS, pas deux boutons : le sous-onglet a une adresse, donc il
	      s'envoie, le bouton Précédent le retrouve et le clic milieu l'ouvre à
	      côté. Et c'est `Onglet` qui les rend : `.bail-tabs` était une rangée
	      d'onglets de plus, avec ses 25 lignes de style et sans les trois marques
	      de l'onglet actif (`ux-patterns` §4 bis). -->
	<div class="tabs sous-onglets">
		<Onglet href={ROUTE_BAUX_ACTIFS} actif={bailTab === 'actif'}>
			Baux actifs ({bauxActifs.length})
		</Onglet>
		<Onglet href={ROUTE_BAUX_ARCHIVES} actif={bailTab === 'archives'}>
			{TITRE_ARCHIVES} ({bauxTermines.length})
		</Onglet>
	</div>

	{#if bauxLoading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else}
		{@const displayed = bailTab === 'actif' ? bauxActifs : bauxTermines}
		{@const grouped = (() => {
			const map = new Map();
			for (const b of displayed) {
				const key = b.locataire_id ?? `ext_${b.id}`;
				if (!map.has(key)) map.set(key, { bail: b, baux: [] });
				map.get(key).baux.push(b);
			}
			return [...map.values()];
		})()}

		{#if grouped.length === 0}
			<div class="empty-state">
				<p>{bailTab === 'actif' ? 'Aucun bail actif.' : 'Aucun bail terminé.'}</p>
			</div>
		{:else}
			{#each grouped as group (group)}
				{@const premierBail = group.bail}
				<div class="card" style="margin-bottom:1.5rem;padding:1.25rem">
					<!-- En-tête locataire -->
					<div
						style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:1rem"
					>
						<div>
							<div style="font-weight:700;font-size:1rem">{nomLocataire(premierBail)}</div>
							{#if premierBail.locataire_email}
								<div style="font-size:0.82rem;color:var(--color-text-muted)">
									{premierBail.locataire_email}
								</div>
							{/if}
							{#if premierBail.locataire_telephone}
								<div style="font-size:0.82rem;color:var(--color-text-muted)">
									{premierBail.locataire_telephone}
								</div>
							{/if}
						</div>
						<div class="form-actions">
							<span
								class="badge {premierBail.statut === 'actif'
									? 'badge-green'
									: premierBail.statut === 'en_cours_sortie'
										? 'badge-yellow'
										: 'badge-gray'}"
							>
								{statutBailLabel[premierBail.statut] ?? premierBail.statut}
							</span>
						</div>
					</div>

					<!-- Actions globales locataire -->
					{#if premierBail.statut !== 'termine'}
						<div style="display:flex;gap:0.5rem;margin-bottom:1.25rem;flex-wrap:wrap">
							<button
								class="btn-icon-edit"
								aria-label="Modifier"
								title="Modifier"
								on:click={() => ouvrirEditionLocataire(premierBail)}>&#x270F;&#xFE0F;</button
							>
							<button class="btn btn-sm" on:click={() => ouvrirAccesBail(premierBail)}
								>&#x1F511; Accès</button
							>
						</div>
					{/if}

					<!-- Détails par bail (lot) -->
					{#each group.baux as bail (bail.id)}
						{@const lot = lots.find((l) => l.id === bail.lot_id)}
						<div style="border-top:1px solid var(--color-border);padding-top:1rem;margin-top:1rem">
							<div
								style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.6rem;flex-wrap:wrap;gap:.5rem"
							>
								<div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
									{#if lot}
										<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
										<span
											class="badge badge-gray"
											style="font-size:.72rem;text-transform:capitalize"
											>{lot.type.replace('_', ' ')}{lot.type_appartement
												? ` – ${lot.type_appartement}`
												: ''}</span
										>
									{/if}
									{#if group.baux.length > 1}
										<span
											class="badge {bail.statut === 'actif'
												? 'badge-green'
												: bail.statut === 'en_cours_sortie'
													? 'badge-yellow'
													: 'badge-gray'}"
											style="font-size:.7rem"
										>
											{statutBailLabel[bail.statut] ?? bail.statut}
										</span>
									{/if}
								</div>
								{#if bail.statut !== 'termine'}
									<button
										class="btn btn-xs btn-outline"
										on:click={() => affecterAuto(bail)}
										title="Affecter automatiquement les accès recommandés"
									>
										⚡ Auto
									</button>
									<!--  Le MODE se lit sur le bouton qui l'a ouvert
									      (`aria-pressed`, `ux-patterns` §13 bis). -->
									<button
										class="btn btn-xs btn-danger"
										aria-pressed={bailATerminer?.id === bail.id}
										on:click={() => {
											bailATerminer = bailATerminer?.id === bail.id ? null : bail;
											dateSortie = '';
										}}
									>
										{bailATerminer?.id === bail.id ? 'Annuler' : 'Terminer'}
									</button>
								{/if}
								{#if $isAdmin || $isCS}
									<button
										class="btn btn-xs btn-danger"
										on:click={() => {
											bailASupprimer = bail;
										}}
									>
										🗑️ Supprimer
									</button>
								{/if}
							</div>

							<!--  Le geste s'ouvre DANS la carte du bail (#889) : il était en
							      fenêtre, pour UN champ de date sur un objet de liste. -->
							{#if bailATerminer?.id === bail.id}
								<GesteEnPlace
									danger
									question={`Confirmer la fin du bail de <strong>${nomLocataire(bail)}</strong> ?`}
									onAnnuler={() => (bailATerminer = null)}
									onValider={confirmerTerminer}
								>
									<label class="field champ-moyen">
										Date de sortie réelle
										<input type="date" bind:value={dateSortie} />
									</label>
								</GesteEnPlace>
							{/if}

							<div
								style="display:flex;gap:2rem;font-size:0.85rem;margin-bottom:.75rem;flex-wrap:wrap"
							>
								<span><strong>Entrée :</strong> {fmt(bail.date_entree)}</span>
								<span><strong>Sortie prévue :</strong> {fmt(bail.date_sortie_prevue)}</span>
								{#if bail.date_sortie_reelle}
									<span><strong>Sortie réelle :</strong> {fmt(bail.date_sortie_reelle)}</span>
								{/if}
							</div>

							{#if bail.notes}
								<div
									class="rich-content"
									style="font-size:0.85rem;color:var(--color-text-muted);margin-bottom:.75rem;font-style:italic"
								>
									{@html safeHtml(bail.notes)}
								</div>
							{/if}

							<InventaireBail
								bailId={bail.id}
								objets={bail.objets}
								modifiable={bail.statut !== 'termine'}
								on:change={(e) => majObjets(bail.id, e.detail)}
							/>
						</div>
					{/each}
				</div>
			{/each}
		{/if}
	{/if}
</div>

<style>
	/*  Le style suit le BALISAGE : ces règles étaient restées dans l'écran quand
	    l'onglet est parti ici (12/09/2026, #928). */
	.sous-onglets {
		margin-bottom: 1.5rem;
	}
	.lbc-lot-badge {
		font-weight: 700;
		font-size: 0.92rem;
	}
</style>
