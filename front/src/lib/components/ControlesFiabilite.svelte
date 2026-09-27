<!--
  Les **contrôles de fiabilité** (`check-reliability.sh`, C1 à C30), nœud par
  nœud, avec leurs constats en cours.

  🔴 Pourquoi cette carte (27/09/2026). Ces contrôles tournent toutes les quinze
  minutes sur les deux Raspberry Pi — split-brain, tunnel, parité de code, disque,
  sudo, en-têtes de sécurité, mises à jour système… — et leurs verdicts n'allaient
  qu'à un journal et à des courriels. L'écran de maintenance ne pouvait donc dire
  ni ce qui était en vigilance, ni si le contrôleur tournait encore. C'est ainsi
  que rpi2 est resté cinq mois sans correctif de sécurité (#1377) : rien, ici, ne
  regardait ce qui se met à jour.

  ⚠️ La carte montre le DERNIER compte rendu de chaque nœud. Le script n'en
  envoie un que quand l'ensemble des constats change, et au moins une fois par
  jour : c'est donc l'état courant, pas un instantané. Si le contrôleur se tait,
  c'est la synthèse des tâches, juste au-dessus, qui le dit (« Exécution
  manquante »).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import EtatListe from './EtatListe.svelte';
	import { admin as adminApi, type RapportFiabilite } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { fmtDatetime } from '$lib/date';
	//  Le titre est le NOM de la tâche dans la synthèse : une seule écriture,
	//  sinon la ligne de la synthèse cesse de renvoyer à cette carte.
	import { LIBELLE_TACHE } from '$lib/taches';

	let rapports: RapportFiabilite[] = [];
	let chargement = true;
	let erreur = '';

	//  Le plus récent de chaque nœud — l'API les rend du plus récent au plus ancien.
	$: parNoeud = rapports.reduce<RapportFiabilite[]>(
		(acc, r) => (r.noeud && !acc.some((x) => x.noeud === r.noeud) ? [...acc, r] : acc),
		[],
	);

	//  « [WARN] Disque rpi1 à 81 % » → le niveau et le texte. Le préfixe est celui
	//  que `check-reliability.sh` écrit (`warn()`, `fail()`) ; un constat sans
	//  préfixe reste lisible, en vigilance.
	function lire(constat: string): { niveau: 'fail' | 'warn'; texte: string } {
		const m = /^\[(FAIL|WARN)\]\s*/.exec(constat);
		return {
			niveau: m?.[1] === 'FAIL' ? 'fail' : 'warn',
			texte: m ? constat.slice(m[0].length) : constat,
		};
	}

	onMount(async () => {
		try {
			rapports = await adminApi.controlesFiabilite();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});
</script>

<section class="card config-section">
	<SectionFormulaire titre={LIBELLE_TACHE.reliability} icone="shield-check" />
	<p class="muted config-section-intro">
		Les vérifications de <strong>check-reliability</strong>, toutes les 15&nbsp;minutes sur chaque
		Raspberry&nbsp;Pi&nbsp;: site public, split-brain, tunnel, parité du code, disque, rotation des
		journaux, droits sudo, en-têtes de sécurité, <strong>mises à jour système</strong>… Un échec est
		envoyé par courriel dans l’heure, les points de vigilance en un résumé quotidien. Ci-dessous,
		les constats <strong>en cours</strong> de chaque nœud.
	</p>

	<EtatListe
		{chargement}
		{erreur}
		vide={parNoeud.length === 0}
		titreErreur="Impossible d’afficher les contrôles"
		titreVide="Aucun rapport reçu"
		messageVide="Les nœuds rendent compte au premier passage de check-reliability (15 min au plus) après leur mise à jour."
	>
		{#each parNoeud as r (r.noeud)}
			{@const constats = (r.details?.constats ?? []).map(lire)}
			<div class="noeud">
				<div class="noeud-entete">
					<strong>{r.noeud?.toUpperCase()}</strong>
					{#if r.details?.fail}
						<span class="badge badge-red">{r.details.fail} en échec</span>
					{/if}
					{#if r.details?.warn}
						<span class="badge badge-orange">{r.details.warn} en vigilance</span>
					{/if}
					{#if !r.details?.fail && !r.details?.warn}
						<span class="badge badge-green">Tout est vert</span>
					{/if}
					<span class="muted date">rapport du {fmtDatetime(r.cree_le)}</span>
				</div>
				{#if constats.length}
					<ul class="constats">
						{#each constats as c, i (i)}
							<li>
								<span
									class="badge"
									class:badge-red={c.niveau === 'fail'}
									class:badge-orange={c.niveau === 'warn'}
									>{c.niveau === 'fail' ? 'Échec' : 'Vigilance'}</span
								>
								<span>{c.texte}</span>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		{/each}
	</EtatListe>
</section>

<style>
	.noeud + .noeud {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}
	.noeud-entete {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem 0.6rem;
	}
	.date {
		font-size: 0.8rem;
	}
	.constats {
		margin: 0.6rem 0 0;
		padding: 0;
		list-style: none;
		font-size: 0.85rem;
	}
	/*  Le badge ne rétrécit pas : c'est le texte, souvent long, qui passe à la ligne. */
	.constats li {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin-bottom: 0.45rem;
		overflow-wrap: anywhere;
	}
	.constats .badge {
		flex-shrink: 0;
	}
</style>
