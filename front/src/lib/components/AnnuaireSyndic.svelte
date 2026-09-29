<!--
  **Le syndic dans l'annuaire de l'espace CS** — son en-tête (le contrat fait
  foi, #535) et la fiche de chacun de ses interlocuteurs, dans l'ordre où un
  arrivant les lit.

  Sorti d'`espace-cs/+page.svelte` le 29/09/2026 (#779, modularité), avec son
  pendant `AnnuaireConseil` : même amorçage, mêmes données de référence.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { annuaireAdmin } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { tenter } from '$lib/erreurs';
	import { nomAffiche } from '$lib/noms';
	import {
		REPLIE,
		ajouter,
		basculer,
		editer,
		retirer,
		type EtatDepliable,
	} from '$lib/listeDepliable';
	import { inscritParNom, type SourcesRapprochement } from '$lib/annuaire-rapprochement';
	import EnteteSyndic from '$lib/components/EnteteSyndic.svelte';
	import { type Geste } from '$lib/components/ActionsMembre.svelte';
	import CarteMembre, { type MembreBase } from '$lib/components/CarteMembre.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';

	/** Les données de référence du rapprochement par le nom. */
	export let sources: SourcesRapprochement;

	interface MembreSyndicForm extends MembreBase {
		fonction: string;
		email: string;
		telephones: string[];
		est_principal: boolean;
	}

	let chargement = true;
	let nomSyndic = '';
	/** D'où vient le nom affiché — le contrat fait foi (#535, `utils/syndic.py`). */
	let nomSyndicSource: 'contrat' | 'saisie' | 'aucune' = 'aucune';
	let adresseSyndic = '';
	let siteWebSyndic = '';
	let membresSyndic: MembreSyndicForm[] = [];
	let enTeteEdite = false;
	let enregistrement = false;
	let enregistrementIdx: number | null = null;
	let syndic: EtatDepliable = REPLIE;

	onMount(async () => {
		try {
			const donnees = await annuaireAdmin.getSyndic();
			nomSyndic = donnees.nom_syndic ?? '';
			nomSyndicSource = donnees.nom_syndic_source ?? 'aucune';
			adresseSyndic = donnees.adresse ?? '';
			siteWebSyndic = donnees.site_web ?? '';
			membresSyndic = (donnees.membres ?? []).map((m: any): MembreSyndicForm => ({
				genre: m.genre ?? 'Mme',
				prenom: m.prenom ?? '',
				nom: m.nom ?? '',
				fonction: m.fonction ?? '',
				email: m.email ?? '',
				telephones: m.telephone
					? m.telephone
							.split(',')
							.map((t: string) => t.trim())
							.filter(Boolean)
					: [''],
				est_principal: m.est_principal ?? false,
				user_id: m.user_id ?? null,
			}));
		} catch {
			toast('error', 'Erreur chargement annuaire');
		} finally {
			chargement = false;
		}
	});

	function ajouterMembre() {
		membresSyndic = [
			...membresSyndic,
			{
				genre: 'Mme',
				prenom: '',
				nom: '',
				fonction: '',
				email: '',
				telephones: [''],
				est_principal: false,
				user_id: null,
			},
		];
		syndic = ajouter(membresSyndic.length);
	}
	function retirerMembre(i: number) {
		membresSyndic = membresSyndic.filter((_, j) => j !== i);
		syndic = retirer(syndic, i);
	}

	function delier(i: number) {
		membresSyndic[i] = { ...membresSyndic[i], user_id: null };
		membresSyndic = [...membresSyndic];
	}

	/** Le nom saisi lie le membre à un inscrit — sans logement : il n'habite pas ici. */
	function surNom(i: number) {
		if (membresSyndic[i].user_id) return;
		const inscrit = inscritParNom(sources.inscrits, membresSyndic[i].nom);
		if (inscrit) {
			membresSyndic[i] = { ...membresSyndic[i], user_id: inscrit.id };
			membresSyndic = [...membresSyndic];
		}
	}

	function designerPrincipal(i: number) {
		membresSyndic = membresSyndic.map((m, j) => ({ ...m, est_principal: j === i }));
	}

	/**
	 * La charge utile de `putSyndic`, écrite UNE fois : réordonnancement, en-tête
	 * et fiche l'envoient entière. Elle l'a été trois fois, à l'identique.
	 */
	function chargeUtile() {
		return {
			nom_syndic: nomSyndic,
			adresse: adresseSyndic,
			site_web: siteWebSyndic || null,
			membres: membresSyndic.map((m) => ({
				genre: m.genre,
				prenom: m.prenom,
				nom: m.nom,
				fonction: m.fonction || null,
				email: m.email || null,
				telephone:
					m.telephones
						.map((t) => t.trim())
						.filter(Boolean)
						.join(',') || null,
				est_principal: m.est_principal,
				user_id: m.user_id,
			})),
		};
	}

	async function deplacer(i: number, sens: -1 | 1) {
		const j = i + sens;
		if (j < 0 || j >= membresSyndic.length) return;
		const liste = [...membresSyndic];
		[liste[i], liste[j]] = [liste[j], liste[i]];
		membresSyndic = liste;
		syndic = REPLIE;
		// Sauvegarde silencieuse de l'ordre
		try {
			await annuaireAdmin.putSyndic(chargeUtile());
		} catch {
			/* silencieux */
		}
	}

	/*
	 *  Les trois gestes que la liste du syndic a de plus que celle du CS :
	 *  l'ordre d'affichage compte (c'est lui que voit un arrivant), et l'un des
	 *  membres est l'interlocuteur principal. Passés en DONNÉES à `ActionsMembre`.
	 */
	function gestesOrdre(i: number, estPrincipal: boolean) {
		const gestes: Geste[] = [];
		if (i > 0)
			gestes.push({
				variante: 'deplacer',
				libelle: 'Monter',
				glyphe: '↑',
				onClic: () => deplacer(i, -1),
			});
		gestes.push({
			variante: 'deplacer',
			libelle: 'Descendre',
			glyphe: '↓',
			desactive: i === membresSyndic.length - 1,
			onClic: () => deplacer(i, 1),
		});
		if (!estPrincipal)
			gestes.push({
				variante: 'designer',
				libelle: 'Définir interlocuteur principal',
				glyphe: '★',
				onClic: () => designerPrincipal(i),
			});
		return gestes;
	}

	const aUnTelephone = (m: MembreSyndicForm) => m.telephones.some((t) => t.trim());

	async function enregistrerEnTete() {
		const sansTel = membresSyndic.find((m) => !aUnTelephone(m));
		if (sansTel) {
			toast('error', `Au moins un téléphone requis pour ${nomAffiche(sansTel) || '…'}`);
			return;
		}
		enregistrement = true;
		if (await tenter(() => annuaireAdmin.putSyndic(chargeUtile()), 'Syndic enregistré'))
			enTeteEdite = false;
		enregistrement = false;
	}

	async function enregistrerMembre(i: number) {
		if (!aUnTelephone(membresSyndic[i])) {
			toast('error', 'Au moins un téléphone requis');
			return;
		}
		enregistrementIdx = i;
		if (
			await tenter(
				() => annuaireAdmin.putSyndic(chargeUtile()),
				`${nomAffiche(membresSyndic[i])} enregistré`,
			)
		)
			syndic = REPLIE;
		enregistrementIdx = null;
	}

	function retirerTelephone(i: number, ti: number) {
		membresSyndic[i].telephones = membresSyndic[i].telephones.filter((_, j) => j !== ti);
		membresSyndic = [...membresSyndic];
	}
	function ajouterTelephone(i: number) {
		membresSyndic[i].telephones = [...membresSyndic[i].telephones, ''];
		membresSyndic = [...membresSyndic];
	}
</script>

{#if chargement}
	<EtatListe chargement />
{:else}
	<!--  L'en-tête vit dans son composant (#535) : c'est lui qui porte la règle
	      « le contrat fait foi », et le champ désactivé qui la montre. -->
	<EnteteSyndic
		bind:nom={nomSyndic}
		bind:adresse={adresseSyndic}
		bind:siteWeb={siteWebSyndic}
		bind:edition={enTeteEdite}
		source={nomSyndicSource}
		{enregistrement}
		onEnregistrer={enregistrerEnTete}
	/>

	{#each membresSyndic as m, i (m)}
		<CarteMembre
			bind:membre={membresSyndic[i]}
			ouvert={syndic.ouvert === i}
			edite={syndic.edite === i}
			enregistrement={enregistrementIdx === i}
			accent={m.est_principal ? 'principal' : null}
			gestes={gestesOrdre(i, m.est_principal)}
			on:basculer={() => (syndic = basculer(syndic, i))}
			on:editer={() => (syndic = editer(i))}
			on:supprimer={() => retirerMembre(i)}
			on:enregistrer={() => enregistrerMembre(i)}
			on:annuler={() => (syndic = REPLIE)}
			on:nom={() => surNom(i)}
			on:delier={() => delier(i)}
		>
			<svelte:fragment slot="badge">
				{#if m.est_principal}
					<span
						class="summary-role-badge summary-role-badge-principal"
						title="Interlocuteur principal du syndic">&#x2B50; Interlocuteur principal</span
					>
				{/if}
			</svelte:fragment>

			<svelte:fragment slot="champs">
				<label class="field">
					Fonction
					<input
						type="text"
						bind:value={membresSyndic[i].fonction}
						placeholder="ex. Directeur de gérance"
					/>
				</label>
				<label class="field">
					Email
					<input type="email" bind:value={membresSyndic[i].email} placeholder="Email" />
				</label>
			</svelte:fragment>

			<svelte:fragment slot="edition">
				<div class="syndic-telephones">
					<div class="syndic-telephones-titre">
						Téléphone{m.telephones.length > 1 ? 's' : ''}
					</div>
					{#each m.telephones as _tel, ti}
						<div class="syndic-telephone">
							<input
								bind:value={membresSyndic[i].telephones[ti]}
								placeholder="ex. 01 23 45 67 89"
							/>
							{#if m.telephones.length > 1}
								<button
									type="button"
									class="btn btn-sm btn-outline btn-retirer-tel"
									aria-label="Retirer ce numéro"
									on:click={() => retirerTelephone(i, ti)}
								>
									-
								</button>
							{/if}
						</div>
					{/each}
					<button type="button" class="btn btn-sm btn-outline" on:click={() => ajouterTelephone(i)}>
						+ N° de téléphone
					</button>
				</div>
			</svelte:fragment>

			<svelte:fragment slot="resume">
				{#if m.fonction}<span class="summary-fonction">{m.fonction}</span>{/if}
				{#if m.email}<span class="summary-loc">{m.email}</span>{/if}
				{#if m.telephones[0]}
					<span class="summary-loc">{m.telephones.filter((t) => t.trim()).join(' · ')}</span>
				{/if}
				{#if m.user_id}
					<span class="summary-lien">&#x1F517; Inscrit lié</span>
				{/if}
			</svelte:fragment>
		</CarteMembre>
	{/each}

	<button type="button" class="btn btn-sm btn-outline ajout-membre" on:click={ajouterMembre}>
		+ Nouveau membre Syndic
	</button>
{/if}

<style>
	/*  Les téléphones d'un membre du syndic — le seul champ qui ne tient pas dans
	    la grille d'identité, parce qu'il en faut plusieurs. Le rouge du retrait
	    est celui de la charte (`--color-danger`), jamais écrit en dur. */
	.syndic-telephones {
		margin-top: 0.65rem;
	}
	.syndic-telephones-titre {
		font-size: var(--fs-md);
		font-weight: 600;
		margin-bottom: 0.35rem;
	}
	.syndic-telephone {
		display: flex;
		gap: 0.4rem;
		margin-bottom: 0.35rem;
	}
	.syndic-telephone input {
		flex: 1;
	}
	.btn-retirer-tel {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}
</style>
