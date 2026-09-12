<!--
  **Quels badges circulent, et chez qui** — la vue du conseil syndical.

  ## 🔴 Pourquoi cet écran (#805, 06/09/2026)

  `GET /acces/admin/vigiks` et `/admin/telecommandes` existaient depuis
  longtemps, réservées au CS, et **aucun écran ne les appelait**. Le ticket posait
  la question franchement : les livrer, ou les retirer ?

  Arbitrage : **lecture seule**. Trois autres routes, qui créaient et modifiaient
  des badges, ont été supprimées le même jour — enregistrer un badge est déjà
  couvert deux fois (l'import Excel en masse, `declarer-badge` par le résident à
  l'unité), et une troisième voie jamais exercée est du code qui dérive.

  Ces deux lectures-ci restent parce qu'elles répondent à une question
  qu'**aucun autre écran ne sait poser** : *« qui a le badge 4521 ? »*. Sur une
  copropriété, elle se pose — au départ d'un locataire, ou quand un badge est
  retrouvé dans le hall.

  ## ⚠️ La route a dû être ENRICHIE pour être utile

  Elle rendait l'objet brut, donc `user_id` : un écran bâti dessus aurait affiché
  « badge 4521 → utilisateur 37 », c'est-à-dire rien. Le nom du porteur et le
  libellé du lot sont résolus côté serveur, une fois — pas par un rapprochement
  que cet écran referait à sa façon.

  C'est la leçon générale de #801 : une route sans appelant n'est jamais mise à
  l'épreuve de la question à laquelle elle est censée répondre.

  ## Ce que cet écran ne fait PAS, et c'est délibéré

  Aucun geste. Pas de création, pas de changement de statut, pas de suppression.
  Un résident gère **ses** badges depuis cette même page (déclarer, signaler
  perdu, supprimer) ; le CS y ajoute la vue d'ensemble, et rien de plus. Ouvrir
  l'écriture ici rouvrirait la troisième voie qu'on vient de fermer.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { acces as accesApi, ApiError, type AccesAdmin } from '$lib/api';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';

	let vigiks: AccesAdmin[] = [];
	let telecommandes: AccesAdmin[] = [];
	let chargement = true;
	/**  Non vide = on n'a PAS pu regarder. Distinct de « regardé, il n'y a rien »
	 *   — un relevé de badges vide se lirait « aucun badge en circulation », ce
	 *   qui serait faux et rassurant (`standards/04`, #519). */
	let erreur = '';

	//  Deux types, donc deux pastilles plus « Tous » : sous le seuil des listes
	//  courtes, `ChoixPastilles` s'impose (`ux-patterns`).
	const TYPES = [
		{ val: 'vigik', label: '\u{1F3F7}\u{FE0F} Vigik' },
		{ val: 'telecommande', label: '\u{1F4E1} Télécommande' },
	] as const;
	let filtreType = '';
	let recherche = '';

	onMount(async () => {
		try {
			[vigiks, telecommandes] = await Promise.all([
				accesApi.listVigiks(),
				accesApi.listTelecommandes(),
			]);
		} catch (e) {
			erreur = e instanceof ApiError ? e.message : 'Chargement impossible';
		} finally {
			chargement = false;
		}
	});

	//  Le type est porté par la LIGNE, pas par deux tableaux séparés : c'est ce
	//  qui permet de chercher un code sans savoir de quel objet il s'agit — et
	//  c'est justement la situation où l'on pose la question.
	$: toutes = [
		...vigiks.map((v) => ({ ...v, type: 'vigik' as const })),
		...telecommandes.map((t) => ({ ...t, type: 'telecommande' as const })),
	];

	/**  La colonne de tri, et son sens.
	 *
	 *  🔴 « Porteur » par défaut, demandé à l'écran le 12/09/2026 : la question
	 *  qu'on pose à cette table est « qui détient quoi », et surtout « que détient
	 *  CETTE personne » — au départ d'un locataire, ou quand un badge est
	 *  retrouvé. Triée par code, elle dispersait les trois badges d'un même
	 *  porteur sur trois écrans.
	 *
	 *  ⚠️ Un tri, pas un regroupement : les lignes restent des lignes. Grouper
	 *  demanderait de décider ce qu'on affiche pour un porteur sans badge, et la
	 *  table ne répond pas à cette question-là. */
	let triCol: 'porteur' | 'type' | 'code' | 'lot' | 'statut' = 'porteur';
	let triAsc = true;

	function trierPar(col: typeof triCol) {
		//  Recliquer la même colonne inverse le sens — le geste que tout tableau
		//  du web a, et qu'il serait surprenant de ne pas trouver.
		if (triCol === col) triAsc = !triAsc;
		else {
			triCol = col;
			triAsc = true;
		}
	}

	/**  La valeur comparée pour une ligne. `localeCompare` avec `sensitivity`
	 *   pour que « Ébert » se range après « Dupont » et non en fin de liste. */
	function cle(a: any): string {
		if (triCol === 'porteur') return a.porteur_nom ?? '';
		if (triCol === 'type') return a.type ?? '';
		if (triCol === 'lot') return a.lot_libelle ?? '';
		if (triCol === 'statut') return a.statut ?? '';
		return a.code ?? '';
	}

	$: q = recherche.trim().toLowerCase();
	$: filtrees = toutes
		.filter((a) => !filtreType || a.type === filtreType)
		.filter(
			(a) =>
				!q ||
				a.code.toLowerCase().includes(q) ||
				a.porteur_nom.toLowerCase().includes(q) ||
				(a.lot_libelle ?? '').toLowerCase().includes(q),
		)
		//  ⚠️ Trié APRÈS les filtres : trier d'abord ferait le même travail sur des
		//  lignes qu'on s'apprête à écarter.
		.sort(
			(x, y) => (triAsc ? 1 : -1) * cle(x).localeCompare(cle(y), 'fr', { sensitivity: 'base' }),
		);

	const badgeStatut: Record<string, string> = {
		actif: 'badge-green',
		perdu: 'badge-red',
		desactive: 'badge-gray',
	};
	const labelType: Record<string, string> = Object.fromEntries(TYPES.map((t) => [t.val, t.label]));
</script>

<section class="card bc-carte">
	<div class="section-header">
		<h2 class="section-title">Tous les badges de la copropriété</h2>
	</div>
	<p class="bc-aide">
		Qui détient quoi, badges Vigik et télécommandes confondus. Cette vue est en
		<strong>lecture seule</strong> : un badge s'enregistre par l'import Excel, ou par le résident lui-même
		depuis cette page.
	</p>

	<ChoixPastilles
		options={TYPES}
		bind:valeur={filtreType}
		tous="Tous"
		libelle="Filtrer par type d’accès"
	/>

	<div class="field">
		<label for="bc-recherche">Rechercher un code, un nom ou un lot</label>
		<input
			id="bc-recherche"
			type="search"
			bind:value={recherche}
			placeholder="4521, Dupont, appartement 12…"
		/>
	</div>

	<EtatListe
		{chargement}
		{erreur}
		vide={toutes.length === 0}
		titreErreur="Impossible d’afficher les badges"
		titreVide="Aucun badge enregistré"
		messageVide="Les badges apparaissent ici une fois l’import Excel résolu, ou déclarés par leurs porteurs."
	>
		{#if filtrees.length === 0}
			<p class="bc-aide">Aucun badge ne correspond à cette recherche.</p>
		{:else}
			<div class="table-wrap">
				<table class="table" style="font-size:0.85rem">
					<thead>
						<!--  🔴 De vrais `<button>` dans les `<th>` : un `<th>` cliquable sans
						      bouton n'est ni atteignable au clavier ni annoncé comme
						      actionnable (`CLAUDE.md`, règle 3). `aria-sort` dit au lecteur
						      d'écran ce que la flèche montre à l'œil. -->
						<tr>
							{#each [['type', 'Type'], ['code', 'Code'], ['porteur', 'Porteur'], ['lot', 'Lot'], ['statut', 'Statut']] as [col, libelle] (col)}
								<th aria-sort={triCol === col ? (triAsc ? 'ascending' : 'descending') : 'none'}>
									<button type="button" class="th-tri" on:click={() => trierPar(col as any)}>
										{libelle}<span class="th-fleche" aria-hidden="true"
											>{triCol === col ? (triAsc ? '▲' : '▼') : ''}</span
										>
									</button>
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each filtrees as a (a.type + a.id)}
							<tr>
								<td>{labelType[a.type]}</td>
								<td class="bc-code">{a.code}</td>
								<td>
									{a.porteur_nom}
									{#if a.chez_locataire}
										<span class="badge badge-blue bc-chez">Chez le locataire</span>
									{/if}
								</td>
								<td>{a.lot_libelle ?? '—'}</td>
								<td>
									<span class="badge {badgeStatut[a.statut] ?? 'badge-gray'}">{a.statut}</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="bc-compte">
				{filtrees.length} badge{filtrees.length !== 1 ? 's' : ''}
				{#if filtrees.length !== toutes.length}sur {toutes.length}{/if}
			</p>
		{/if}
	</EtatListe>
</section>

<style>
	/*  L'en-tête cliquable ressemble à un en-tête, pas à un bouton : c'est la
	    flèche qui dit qu'il trie, et le survol qui dit qu'il se clique. */
	.th-tri {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		color: inherit;
		cursor: pointer;
	}
	.th-tri:hover {
		color: var(--color-primary);
	}
	.th-fleche {
		font-size: 0.7em;
	}
	/*  `.section` n'est PAS globale - elle vit dans `acces-securite`, scopee a ce
	    fichier-la. L'employer ici aurait rendu la carte sans son cadre : c'est la
	    regression des pastilles nues (`standards/02` §4 ter), et `lint:classes-nues`
	    l'a refusee. Le padding est donc pose ici, avec la carte qui le porte. */
	.bc-carte {
		padding: 1.25rem;
		margin-top: 1rem;
	}
	.bc-aide {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin: 0 0 0.75rem;
	}
	.bc-code {
		font-family: monospace;
	}
	.bc-chez {
		font-size: 0.7rem;
		margin-left: 0.35rem;
	}
	.bc-compte {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		margin: 0.5rem 0 0;
		text-align: right;
	}
</style>
