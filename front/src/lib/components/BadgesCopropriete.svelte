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
	import { acces as accesApi, admin as adminApi, ApiError, type AccesAdmin } from '$lib/api';
	import { isAdmin } from '$lib/stores/auth';
	import BoutonNouveau from '$lib/components/BoutonNouveau.svelte';
	import FormulaireAcces from '$lib/components/FormulaireAcces.svelte';
	import TableParcAcces from '$lib/components/TableParcAcces.svelte';
	import { confirmerPuis } from '$lib/confirmation';
	import { tenter } from '$lib/erreurs';
	import { nomAffiche } from '$lib/noms';
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

	//  ── Les gestes, ouverts le 14/09/2026 (#953) ────────────────────────────
	//
	//  🔴 Cet écran était en LECTURE SEULE depuis le 06/09 (#805), et c'était une
	//  décision : trois routes d'écriture avaient été supprimées ce jour-là parce
	//  qu'enregistrer un badge était déjà couvert deux fois. Le choix est renversé
	//  sur demande explicite — le conseil syndical remet des badges en main
	//  propre, et rien ne le lui permettait.
	let porteurs: { id: number; nom: string }[] = [];
	let formOuvert = false;
	let editId: string | null = null;
	let enregistrement = false;

	const SAISIE_VIERGE = () => ({
		type: 'vigik',
		code: '',
		porteur_id: null as number | null,
		perimetre_cible: [] as string[],
		statut: 'actif',
		ticket_numero: '',
	});
	let saisie = SAISIE_VIERGE();

	function ouvrirCreation() {
		saisie = SAISIE_VIERGE();
		editId = null;
		formOuvert = true;
	}

	function ouvrirEdition(a: AccesAdmin & { type: string }) {
		saisie = {
			type: a.type,
			code: a.code,
			porteur_id: a.porteur_id,
			perimetre_cible: [...(a.perimetre_cible ?? [])],
			statut: String(a.statut),
			ticket_numero: '',
		};
		editId = `${a.type}-${a.id}`;
		formOuvert = false;
	}

	function fermer() {
		formOuvert = false;
		editId = null;
	}

	async function recharger() {
		[vigiks, telecommandes] = await Promise.all([
			accesApi.listVigiks(),
			accesApi.listTelecommandes(),
		]);
	}

	async function enregistrer() {
		enregistrement = true;
		//  ⚠️ `tenter` porte le message d'erreur : un `try/catch` local serait la
		//  soixante-huitième écriture de ce ternaire (`lint:message-erreur`).
		await tenter(async () => {
			const corps = {
				code: saisie.code.trim(),
				porteur_id: saisie.porteur_id,
				perimetre_cible: saisie.perimetre_cible,
				statut: saisie.statut,
				ticket_numero: saisie.ticket_numero.trim() || null,
			};
			if (editId) {
				const [type, id] = editId.split('-');
				await accesApi.modifierAcces(type, Number(id), corps);
			} else {
				await accesApi.creerAcces(saisie.type, corps);
			}
			await recharger();
			fermer();
		});
		enregistrement = false;
	}

	//  🔒 Réservé à l'admin côté SERVEUR : le bouton ne s'affiche que pour lui,
	//  et l'écran dit alors la même chose que le serveur — ni plus, ni moins.
	async function supprimer(a: AccesAdmin & { type: string }) {
		//  ⚠️ `confirmerPuis` et non `confirmer` + `tenter` : le couple
		//  « demander, faire, annoncer » est écrit UNE fois dans le dépôt, et le
		//  recomposer ici en serait la copie suivante.
		await confirmerPuis(
			{
				message:
					`Supprimer définitivement ${labelType[a.type]} ${a.code} ? ` +
					'Pour un badge perdu ou rendu, préférer le statut : il garde la ' +
					'trace que ce badge a existé, et donc qu’il circule.',
				libelleConfirmer: 'Supprimer',
				danger: true,
			},
			'Accès supprimé',
			async () => {
				await accesApi.supprimerAcces(a.type, a.id);
				await recharger();
			},
		);
	}

	onMount(async () => {
		try {
			[vigiks, telecommandes] = await Promise.all([
				accesApi.listVigiks(),
				accesApi.listTelecommandes(),
			]);
			//  Les porteurs proposés à la saisie. Chargés ici plutôt qu'à
			//  l'ouverture du formulaire : une liste qui se remplit après le
			//  premier rendu ferait clignoter le sélecteur.
			porteurs = (await adminApi.utilisateurs()).map((u: any) => ({
				id: u.id,
				nom: nomAffiche(u),
			}));
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
	let triCol: 'porteur' | 'type' | 'code' | 'lot' | 'acces' | 'statut' = 'porteur';
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
		//  ⚠️ Trié sur les CODES, pas sur le libellé : le libellé dépend de
		//  l'arbre, qui peut n'être pas encore chargé — l'ordre changerait alors
		//  sous les yeux. Les codes, eux, arrivent avec la ligne.
		if (triCol === 'acces') return (a.perimetre_cible ?? []).join(' ');
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

	<!--  ⚠️ L'ordre suit `ux-patterns` §0 ter : ce qui QUALIFIE la liste et ses
	      commandes restent au-dessus du formulaire, qui reste au-dessus de la
	      table. Ouvrir « Enregistrer » ne doit pas repousser la recherche hors
	      de l'écran.

	      🔗 L'export est un LIEN, pas un bouton : la réponse est un fichier, et
	      le navigateur sait le recevoir. Le faire passer par le client d'API
	      obligerait à fabriquer un `blob:` puis un lien de téléchargement — trois
	      gestes pour ce qu'une ancre fait seule, cookies de session compris. -->
	<div class="bc-actions">
		<BoutonNouveau
			ouvert={formOuvert}
			libelle="Enregistrer un accès"
			on:basculer={ouvrirCreation}
		/>
		<a class="btn btn-outline" href={accesApi.urlExportParc()} download>⬇️ Exporter (CSV)</a>
	</div>

	{#if formOuvert}
		<FormulaireAcces
			types={TYPES}
			{porteurs}
			bind:saisie
			{enregistrement}
			cle="creation"
			on:annule={fermer}
			on:enregistre={enregistrer}
		/>
	{/if}

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
			<TableParcAcces
				lignes={filtrees}
				{labelType}
				{badgeStatut}
				{triCol}
				{triAsc}
				{editId}
				estAdmin={$isAdmin}
				on:trier={(e) => trierPar(e.detail as typeof triCol)}
				on:editer={(e) => ouvrirEdition(e.detail)}
				on:supprimer={(e) => supprimer(e.detail)}
			>
				<svelte:fragment slot="edition">
					<!--  `encadre={false}` : le formulaire s'ouvre DANS une ligne de
					      tableau, et une bordure de plus y serait « la carte dans la
					      carte » (#425). Pas de `cle` non plus : rien n'a bougé. -->
					<FormulaireAcces
						types={TYPES}
						{porteurs}
						bind:saisie
						modeEdition
						{enregistrement}
						encadre={false}
						on:annule={fermer}
						on:enregistre={enregistrer}
					/>
				</svelte:fragment>
			</TableParcAcces>
			<p class="bc-compte">
				{filtrees.length} badge{filtrees.length !== 1 ? 's' : ''}
				{#if filtrees.length !== toutes.length}sur {toutes.length}{/if}
			</p>
		{/if}
	</EtatListe>
</section>

<style>
	/*  Les deux commandes de tête, sur une ligne — et qui s'enroule sous 767 px
	    plutôt que de déborder : c'est la largeur à laquelle tout le site bascule
	    en mobile (#839). */
	.bc-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		align-items: center;
		margin-bottom: 0.75rem;
	}
	/*  La ligne d'édition n'est pas une ligne de données : elle reprend le fond
	    de la page pour se distinguer de ce qu'elle interrompt. */

	/*  L'en-tête cliquable ressemble à un en-tête, pas à un bouton : c'est la
	    flèche qui dit qu'il trie, et le survol qui dit qu'il se clique. */
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
	.bc-compte {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		margin: 0.5rem 0 0;
		text-align: right;
	}
</style>
