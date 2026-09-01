<!--
  Le relevé des violations de la politique de sécurité de contenu (CSP).

  ## Pourquoi cet écran existe (01/09/2026, #536)

  `GET /admin/csp-violations` agrège les rapports des navigateurs et **persiste**
  son état dans `ConfigSite` — il survit donc aux redémarrages, contrairement au
  journal du conteneur. Il existait depuis des semaines, et **rien ne l'appelait** :
  la donnée était collectée, et personne ne pouvait la lire.

  🔴 C'est un contrôle sans destinataire (`standards/04` §7) — la même forme de
  défaut que les cinq contrôles WARN muets de #449. Et c'est ce qui bloquait
  #536 : on ne bascule pas `script-src` de *report-only* à *appliqué* sur une
  intuition, on le fait sur un relevé.

  ## ⚠️ Un relevé vide ne prouve RIEN

  Il peut vouloir dire « le site est conforme »… ou « l'en-tête `Report-Only`
  n'est pas servi, et aucun navigateur n'a rien à signaler à personne ». Le
  serveur le dit lui-même dans `note`, et cet écran l'affiche en **avertissement**,
  jamais en réussite.

  De même, `ignores` n'est pas du bruit : un chiffre élevé veut dire que des
  rapports arrivent dans un format qu'on ne sait pas lire, ou que le plafond de
  clés est atteint — dans les deux cas le relevé est INCOMPLET, et le taire
  ferait conclure « il n'y a plus rien à corriger ».
-->
<script lang="ts">
	import { onMount } from 'svelte';

	import { admin, ApiError, type CspReleve } from '$lib/api';
	import Icon from '$lib/components/Icon.svelte';
	import { toast } from '$lib/components/Toast.svelte';

	let releve: CspReleve | null = null;
	let chargement = true;

	async function charger() {
		chargement = true;
		try {
			releve = await admin.cspViolations();
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Relevé indisponible');
		} finally {
			chargement = false;
		}
	}

	onMount(charger);
</script>

<div class="page-header">
	<h2><Icon name="shield" size={20} /> Politique de sécurité de contenu</h2>
	<button class="btn btn-outline btn-sm" on:click={charger} disabled={chargement}>
		{chargement ? 'Chargement…' : 'Rafraîchir'}
	</button>
</div>

<p class="page-desc">
	Ce que les navigateurs des résidents ont refusé de charger, si la politique était
	<strong>appliquée</strong>. Elle est aujourd'hui servie en <em>report-only</em> : rien n'est bloqué,
	tout est compté.
</p>

{#if chargement && !releve}
	<p>Chargement…</p>
{:else if releve}
	{#if releve.note}
		<!--  🔴 En AVERTISSEMENT, jamais en réussite : « aucun rapport » peut
		      vouloir dire « aucune violation » comme « l'en-tête n'est pas servi ». -->
		<p class="csp-alerte">⚠️ {releve.note}</p>
	{/if}

	<div class="csp-chiffres">
		<div class="csp-chiffre">
			<span class="csp-valeur">{releve.recus}</span>
			<span class="csp-libelle">rapports reçus</span>
		</div>
		<div class="csp-chiffre">
			<span class="csp-valeur">{releve.cles_distinctes}</span>
			<span class="csp-libelle">violations distinctes</span>
		</div>
		<div class="csp-chiffre" class:csp-vigilance={releve.ignores > 0}>
			<span class="csp-valeur">{releve.ignores}</span>
			<span class="csp-libelle">rapports non lus</span>
		</div>
	</div>

	{#if releve.plafond_atteint}
		<p class="csp-alerte">
			⚠️ Le plafond de violations distinctes est atteint : les <strong>nouvelles</strong> ne sont plus
			comptées. Le relevé ci-dessous est incomplet — traiter les plus fréquentes, puis rafraîchir.
		</p>
	{:else if releve.ignores > 0}
		<p class="csp-alerte">
			⚠️ {releve.ignores} rapport(s) reçus dans un format non reconnu. Le relevé est incomplet : ne pas
			en conclure qu'il ne reste rien à corriger.
		</p>
	{/if}

	{#if releve.violations.length === 0}
		<p class="empty">Aucune violation enregistrée.</p>
	{:else}
		<div class="report-table-wrap">
			<table class="report-table compact">
				<thead>
					<tr><th>Directive</th><th>Ressource refusée</th><th>Occurrences</th></tr>
				</thead>
				<tbody>
					{#each releve.violations as v (v.directive + '|' + v.bloque)}
						<tr>
							<td><code>{v.directive}</code></td>
							<td class="csp-bloque">{v.bloque}</td>
							<td>{v.compte}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{/if}

<style>
	/*  `.page-desc` et `.empty` ne vivent PAS dans la feuille globale : Svelte
	    scope ses styles au fichier, et les autres onglets les définissent chacun
	    chez eux (`OngletPerimetres`). `lint:classes` refuse de les employer sans
	    les définir — c'est ce qui évite l'écran nu. */
	.page-desc {
		color: var(--color-text-muted);
		margin-bottom: 1rem;
	}
	.empty {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}
	.csp-alerte {
		font-size: 0.85rem;
		padding: 0.6rem 0.8rem;
		margin: 0 0 1rem;
		border-left: 3px solid var(--color-warning, #d97706);
		background: var(--color-bg);
		border-radius: var(--radius);
	}
	.csp-chiffres {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		margin-bottom: 1.25rem;
	}
	.csp-chiffre {
		flex: 1 1 8rem;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.7rem 0.9rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}
	.csp-valeur {
		font-size: 1.4rem;
		font-weight: 600;
	}
	.csp-libelle {
		font-size: 0.78rem;
		color: var(--color-text-muted);
	}
	.csp-vigilance {
		border-color: var(--color-warning, #d97706);
	}
	.csp-bloque {
		font-size: 0.8rem;
		word-break: break-all;
	}
</style>
