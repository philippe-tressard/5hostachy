<!--
  Le CARNET D'ENTRETIEN — ce qui a été entretenu, réparé et contrôlé, et ce qui
  ne l'a pas été.

  Obligatoire depuis le décret n° 2001-477. Il n'existait nulle part, alors qu'il
  était déjà écrit en morceaux : contrats, interventions du calendrier, tickets
  clos. Le serveur les rassemble (`app/utils/carnet_entretien.py`) ; cet écran ne
  fait que les ranger.

  🔴 RÉSERVÉ aux copropriétaires, au conseil syndical et à l'admin (arbitré le
  10/09/2026). L'onglet est masqué aux locataires ET la route est refusée —
  masquer répond à ce qui s'affiche, refuser à ce qui s'atteint. Le droit est
  tenu par `require_proprietaire` côté serveur : cet écran ne fait que s'y
  conformer, il ne le décide pas.

  ⚠️ Le regroupement par ÉQUIPEMENT est le point de l'écran, pas une commodité de
  tri : c'est lui qui fait apparaître les trous. Une chaudière dont la dernière
  ligne date de trois ans se voit parce que ses voisines en ont de récentes —
  dans une liste chronologique, elle serait simplement plus bas.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { carnet as carnetApi, type Carnet, type EntreeCarnet } from '$lib/api';
	import { EQUIPEMENTS } from '$lib/prestataires';
	import { perimetreLabel } from '$lib/perimetres';
	import FiltrePerimetre from './FiltrePerimetre.svelte';
	import { fmtDate } from '$lib/date';
	import { essayer } from '$lib/chargement';
	import EtatListe from './EtatListe.svelte';

	let donnees: Carnet | null = null;
	let erreur = '';
	let chargement = true;
	/**  Un CODE de périmètre (`'bat:3'`, `'parking'`), jamais un identifiant de
	 *   bâtiment : c'est ce qui permet de filtrer sur un espace qui n'en a pas. */
	let perimetreChoisi: string | null = null;

	async function charger() {
		chargement = true;
		[donnees, erreur] = await essayer<Carnet | null>(carnetApi.lire(perimetreChoisi), null);
		chargement = false;
	}

	onMount(charger);

	/**  Le libellé d'un équipement vient d'`EQUIPEMENTS`, la table unique déjà
	 *   comparée à l'énumération du serveur par `test_types_equipement.py`. Le
	 *   serveur envoie la valeur ; en écrire une seconde table ici en ferait la
	 *   troisième écriture. */
	function libelleEquipement(valeur: string | null): string {
		if (!valeur) return 'Sans équipement rattaché';
		return EQUIPEMENTS.find((e) => e.val === valeur)?.label ?? valeur;
	}

	/**  La PORTÉE d'une entrée, toujours dite.
	 *
	 *   🔴 Elle est écrite même sous un filtre — surtout sous un filtre : un
	 *   contrat qui couvre toute la résidence apparaît sous « Bât. 3 », parce
	 *   qu'il l'entretient aussi. Sans sa portée, il s'y lirait comme propre à ce
	 *   bâtiment, et le filtre mentirait plus discrètement que celui qu'il
	 *   remplace.
	 *
	 *   `perimetreLabel` est la source unique du libellé — celle qui qualifie un
	 *   espace par son parent et trie par l'arbre, jamais par l'ordre des clics. */
	function portee(codes: string[]): string {
		return perimetreLabel(codes ?? []);
	}

	/**  Les entrées rangées par équipement, chaque groupe gardant l'ordre du
	 *   serveur — du fait le plus récent au plus ancien.
	 *
	 *   ⚠️ Les groupes sont triés par leur entrée la plus RÉCENTE, pas par ordre
	 *   alphabétique : ce qui a bougé récemment se lit en premier, et l'équipement
	 *   dont plus rien ne bouge tombe en bas — où il se remarque. */
	$: groupes = (() => {
		const par = new Map<string, EntreeCarnet[]>();
		for (const entree of donnees?.entrees ?? []) {
			const cle = entree.equipement ?? '';
			if (!par.has(cle)) par.set(cle, []);
			par.get(cle)!.push(entree);
		}
		return [...par.entries()].sort((a, b) => (a[1][0].date < b[1][0].date ? 1 : -1));
	})();

	$: enRetard = (donnees?.entrees ?? []).filter((e) => e.alerte).length;

	const ORIGINES: Record<string, string> = {
		contrat: 'Contrat',
		intervention: 'Intervention',
		incident: 'Incident',
	};
</script>

<div class="carnet">
	<p class="aide">
		Ce que la copropriété a fait entretenir, réparer et contrôler. Il est constitué automatiquement
		à partir des contrats, des interventions du calendrier et des tickets résolus — rien n'y est
		saisi à la main.
	</p>

	<!--  Le filtre est le composant STANDARD : il prend ses pastilles dans
	      l'arborescence administrée, donc un périmètre créé demain y apparaît
	      sans qu'on touche à cet écran. -->
	<FiltrePerimetre bind:choisi={perimetreChoisi} on:changer={charger} />

	{#if enRetard > 0}
		<!--  L'alerte est en TÊTE parce que c'est ce que le carnet apprend et que
		      rien d'autre ne dit. La date de prochaine visite existe en base depuis
		      toujours ; aucun écran ne la comparait à aujourd'hui. -->
		<p class="retard" role="status">
			⚠️ <strong
				>{enRetard} visite{enRetard > 1 ? 's' : ''} attendue{enRetard > 1 ? 's' : ''}</strong
			>
			dont l'échéance est dépassée.
		</p>
	{/if}

	<EtatListe
		{chargement}
		{erreur}
		vide={groupes.length === 0}
		messageVide="Aucun contrat, aucune intervention terminée ni aucun ticket résolu pour ce périmètre."
	>
		<div class="groupes">
			{#each groupes as [equipement, entrees] (equipement)}
				<section>
					<h3 class="groupe-titre">{libelleEquipement(equipement)}</h3>
					<ol class="entrees">
						{#each entrees as entree (entree.origine + entree.lien + entree.date)}
							<li class="entree" class:alertee={!!entree.alerte}>
								<span class="quand">{fmtDate(entree.date)}</span>
								<span class="quoi">
									<a href={entree.lien}>{entree.libelle}</a>
									<span class="detail">
										{entree.detail}{#if entree.detail}&nbsp;·
										{/if}{portee(entree.perimetre)}
									</span>
									{#if entree.alerte}
										<span class="alerte">⚠️ {entree.alerte}</span>
									{/if}
								</span>
								<span class="badge badge-gray origine">{ORIGINES[entree.origine]}</span>
							</li>
						{/each}
					</ol>
				</section>
			{/each}
		</div>
	</EtatListe>
</div>

<style>
	.carnet {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	.retard {
		margin: 0;
		padding: 0.55rem 0.8rem;
		background: #fffbeb;
		border: 1px solid #fcd34d;
		border-radius: var(--radius);
		color: #92400e;
		font-size: 0.88rem;
	}
	.groupes {
		display: flex;
		flex-direction: column;
		gap: 1.4rem;
	}
	.groupe-titre {
		margin: 0 0 0.5rem;
		font-size: 0.95rem;
		color: var(--color-primary);
		border-bottom: 1px solid var(--color-border);
		padding-bottom: 0.35rem;
	}
	.entrees {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	/*  Trois colonnes : la date est FIXE et tabulaire pour que les jours
	    s'alignent, le libellé est élastique, la provenance se cale à droite. */
	.entree {
		display: grid;
		grid-template-columns: 6rem minmax(0, 1fr) auto;
		gap: 0.3rem 0.75rem;
		align-items: baseline;
		padding: 0.35rem 0.4rem;
		border-radius: var(--radius);
	}
	.entree:nth-child(odd) {
		background: var(--color-bg);
	}
	.entree.alertee {
		box-shadow: inset 3px 0 0 var(--color-warning);
	}
	.quand {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
	}
	.quoi {
		min-width: 0;
	}
	.quoi a {
		color: var(--color-text);
		text-decoration: none;
	}
	.quoi a:hover,
	.quoi a:focus-visible {
		color: var(--color-primary);
		text-decoration: underline;
	}
	.detail,
	.alerte {
		display: block;
		font-size: 0.78rem;
		color: var(--color-text-muted);
		line-height: 1.45;
	}
	.alerte {
		color: var(--color-warning);
	}
	.origine {
		white-space: nowrap;
	}
	/*  Sous 560 px, la colonne de droite passe sous le libellé : trois colonnes
	    écrasent le titre, qui est ce qu'on vient lire. */
	@media (max-width: 480px) {
		.entree {
			grid-template-columns: 5rem minmax(0, 1fr);
		}
		.origine {
			grid-column: 2;
			justify-self: start;
		}
	}
</style>
