<!--
  Le COÛT d'un usage de l'assistant : son plafond mensuel et ses trois prix
  (#1383, prix en dollars et cache le 30/09/2026). Sorti de `BlocUsageIA` le
  30/09/2026 : le bloc franchissait 500 lignes (modularité, rang 1).

  Il ÉCRIT dans `valeurs` (lié), comme le bloc : c'est l'onglet qui enregistre,
  d'un seul geste. Le ✨ qui cherche le tarif reste dans le bloc, à côté du
  modèle ; ce composant n'en montre que le compte rendu (`tarifEnregistre`).
-->
<script context="module" lang="ts">
	import type { PrixIA } from '$lib/api';

	//  🔴 Les prix, en DOLLARS par million de jetons (30/09/2026, arbitré :
	//  « comme les grilles »), et TROIS — l'entrée lue en cache a le sien chez
	//  OpenAI. Stockés tels que saisis, en texte décimal (« 0.075 ») : jamais
	//  un flottant, et plus des centimes, où 0,075 $ ne tenait pas. Un champ
	//  par prix, écrit UNE fois : les trois ne diffèrent que par leurs mots.
	export const PRIX: { champ: PrixIA; libelle: string; aide: string }[] = [
		{
			champ: 'prix_entree',
			libelle: 'Prix des jetons envoyés',
			aide: 'Comme la grille de votre fournisseur.',
		},
		{
			champ: 'prix_sortie',
			libelle: 'Prix des jetons produits',
			aide: 'La réponse, raisonnement compris. Sans prix, la consommation (Maintenance) s’affiche en jetons seuls.',
		},
		{
			champ: 'prix_cache',
			libelle: 'Prix des jetons en cache',
			aide: 'L’entrée déjà vue, que le fournisseur relit en cache et facture moins cher (« cached input »). Vide : elle compte au prix des jetons envoyés.',
		},
	];
</script>

<script lang="ts">
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import type { UsageIA } from '$lib/api';

	/** Toutes les valeurs de configuration, liées : le composant écrit les siennes. */
	export let valeurs: Record<string, string>;
	export let cles: UsageIA['cles'];
	/** Le compte rendu du ✨ quand il vient d'enregistrer un tarif, sinon vide. */
	export let tarifEnregistre = '';

	//  Le plafond est en jetons par mois, 0 = aucun.
	$: plafondMois = Number(valeurs[cles.plafond_mois]) || 0;

	function poser(cle: string, valeur: string) {
		valeurs = { ...valeurs, [cle]: valeur };
	}
</script>

<SectionFormulaire titre="Coût et plafond">
	<div class="form-grid">
		<label class="field">
			Plafond mensuel
			<input
				type="number"
				value={plafondMois || ''}
				min="0"
				step="10000"
				placeholder="Aucun"
				on:input={(e) => poser(cles.plafond_mois, e.currentTarget.value)}
			/>
			<span class="aide">
				En jetons (question et réponse), du premier au dernier jour du mois. Atteint, l’usage est
				refusé avant tout envoi — l’automatique s’arrête — et le contrôle de 6&nbsp;h le signale.
				Vide&nbsp;: aucun plafond.
			</span>
		</label>
		{#each PRIX as p (p.champ)}
			<label class="field">
				{p.libelle} ($ / million)
				<input
					type="number"
					value={valeurs[cles[p.champ]] ?? ''}
					min="0"
					step="any"
					inputmode="decimal"
					placeholder="Non renseigné"
					on:input={(e) => poser(cles[p.champ], e.currentTarget.value)}
				/>
				<span class="aide">{p.aide}</span>
			</label>
		{/each}
	</div>
	{#if tarifEnregistre}
		<p class="aide">✅ Tarif enregistré — {tarifEnregistre}</p>
	{/if}
</SectionFormulaire>
