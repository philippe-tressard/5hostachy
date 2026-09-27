<!--
  Ce que l'assistant IA a **consommé** — jetons, appels, échecs, refus, coût
  estimé — par mois, usage et modèle (#1383).

  🔴 Pourquoi. L'assistant a un usage AUTOMATIQUE (les réponses du syndic par
  courriel, relevées toutes les dix minutes) et rien ne comptait ses appels. Une
  boucle aurait facturé en silence jusqu'à la facture du fournisseur.

  ⚠️ Le coût est une ESTIMATION au tarif saisi dans Administration › Assistant IA,
  et il se tait sans tarif — un « 0 € » se lirait « gratuit ». Les réglages
  (prix, plafond) restent dans l'onglet de l'assistant ; cette carte ne fait que
  montrer, là où l'on vient surveiller.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import EtatListe from './EtatListe.svelte';
	import { config as configApi, type ConsommationIA, type LigneConsommationIA } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { fmtMonthYear } from '$lib/date';
	import { fmtMontant } from '$lib/utils';

	let donnees: ConsommationIA | null = null;
	let chargement = true;
	let erreur = '';

	const nombre = (n: number) => n.toLocaleString('fr-FR');
	const jetons = (l: LigneConsommationIA) => l.jetons_entree + l.jetons_sortie;
	//  Le coût d'un mois n'existe que si CHAQUE ligne en a un : additionner les
	//  lignes chiffrées en taisant les autres afficherait un total faux.
	function coutDuMois(lignes: LigneConsommationIA[]): number | null {
		if (!lignes.length || lignes.some((l) => l.cout_centimes === null)) return null;
		return lignes.reduce((s, l) => s + (l.cout_centimes ?? 0), 0);
	}
	const part = (consommes: number, plafond: number) =>
		Math.min(100, Math.round((consommes / plafond) * 100));

	onMount(async () => {
		try {
			donnees = await configApi.llmConsommation();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});
</script>

<section class="card config-section">
	<SectionFormulaire titre="Consommation de l’assistant IA" icone="bar-chart-3" />
	<p class="muted config-section-intro">
		Chaque appel au fournisseur, compté en jetons — la question envoyée et la réponse produite. Le
		coût est estimé au tarif saisi pour chaque usage dans <strong>Assistant IA</strong>, où se règle
		aussi le <strong>plafond mensuel</strong>&nbsp;: atteint, l’usage est refusé avant tout envoi,
		et le contrôle de 6&nbsp;h le signale. Aucune question ni réponse n’est conservée.
	</p>

	<EtatListe
		{chargement}
		{erreur}
		vide={!donnees?.mois.length}
		titreErreur="Impossible d’afficher la consommation"
		titreVide="Aucun appel enregistré"
		messageVide="Le compte commence au premier appel à l’assistant après cette mise à jour."
	>
		{#if donnees}
			{@const plafonnes = donnees.plafonds.filter((p) => p.plafond > 0)}
			{#if plafonnes.length}
				<h4 class="sous-titre">Plafonds de {fmtMonthYear(donnees.mois_courant)}</h4>
				<ul class="plafonds">
					{#each plafonnes as p (p.usage)}
						<li>
							<span>{p.libelle}</span>
							<span class="muted"
								>{nombre(p.consommes)} / {nombre(p.plafond)} jetons ({part(
									p.consommes,
									p.plafond,
								)}&nbsp;%)</span
							>
							<span
								class="jauge"
								role="progressbar"
								aria-label="Plafond de {p.libelle}"
								aria-valuemin="0"
								aria-valuemax="100"
								aria-valuenow={part(p.consommes, p.plafond)}
							>
								<span
									class="jauge-plein"
									class:jauge-alerte={part(p.consommes, p.plafond) >= 80}
									style="width:{part(p.consommes, p.plafond)}%"
								></span>
							</span>
						</li>
					{/each}
				</ul>
			{/if}

			{#each donnees.mois as m (m.mois)}
				{@const cout = coutDuMois(m.usages)}
				<div class="mois">
					<h4 class="sous-titre">
						<span class="mois-libelle">{fmtMonthYear(m.mois)}</span>
						<span class="muted total"
							>{cout === null ? 'coût non renseigné' : `${fmtMontant(cout / 100)} estimés`}</span
						>
					</h4>
					<ul class="lignes">
						{#each m.usages as l (l.usage + l.modele)}
							<li>
								<strong>{l.libelle}</strong>
								<span class="muted">{l.modele}</span>
								<span>
									{nombre(l.appels)} appel{l.appels > 1 ? 's' : ''} · {nombre(jetons(l))} jetons
									<span class="muted"
										>({nombre(l.jetons_entree)} envoyés, {nombre(l.jetons_sortie)} produits)</span
									>
									{#if l.cout_centimes !== null}· {fmtMontant(l.cout_centimes / 100)}{/if}
								</span>
								{#if l.erreurs}<span class="badge badge-red">{l.erreurs} en échec</span>{/if}
								{#if l.refus}<span class="badge badge-orange"
										>{l.refus} refusé{l.refus > 1 ? 's' : ''} au plafond</span
									>{/if}
							</li>
						{/each}
					</ul>
				</div>
			{/each}
		{/if}
	</EtatListe>
</section>

<style>
	.sous-titre {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.25rem 0.6rem;
		margin: 0 0 0.4rem;
		font-size: 0.9rem;
	}
	/*  « septembre 2026 » → « Septembre 2026 » en tête de mois seulement : un
	    `capitalize` sur le titre mettait une capitale à chaque mot. */
	.mois-libelle {
		display: inline-block;
	}
	.mois-libelle::first-letter {
		text-transform: uppercase;
	}
	.total {
		font-weight: 400;
		font-size: 0.8rem;
	}
	.mois + .mois,
	.plafonds + .mois {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}
	.plafonds,
	.lignes {
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: 0.85rem;
	}
	.plafonds li,
	.lignes li {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.2rem 0.6rem;
		margin-bottom: 0.5rem;
		overflow-wrap: anywhere;
	}
	.jauge {
		flex-basis: 100%;
		height: 6px;
		border-radius: 3px;
		background: var(--color-border);
		overflow: hidden;
	}
	.jauge-plein {
		display: block;
		height: 100%;
		background: var(--color-primary);
	}
	.jauge-alerte {
		background: var(--color-warning);
	}
</style>
