<!--
  L'historique des envois WhatsApp — les derniers messages et leur verdict.

  Extrait de `OngletWhatsApp.svelte` le 28/09/2026 (#1329), avec ses règles à
  l'identique : l'onglet n'avait aucune feuille, tout y était en attributs
  `style`. Seule la teinte du verdict reste en ligne : elle vient de la donnée.
-->
<script lang="ts">
	import type { JournalEnvoiWhatsApp } from '$lib/api';
	import { fmtDatetimeShort } from '$lib/date';

	export let journaux: JournalEnvoiWhatsApp[] = [];
	export let recharger: () => unknown = () => {};

	//  Un seuil employé pour couper ET pour comparer se nomme : écrit deux fois,
	//  il donne un aperçu tronqué à une longueur et une décision prise à une autre
	//  le jour où l'un des deux bouge (#1076).
	const MAX_APERCU_MESSAGE = 120;

	//  Un envoi a trois issues, pas deux : réussi, échoué, ou sans réponse du
	//  bridge. Ce dernier cas s'affichait « ❌ échec » alors que le message était
	//  le plus souvent bien arrivé dans le groupe — c'est cette lecture qui a
	//  fait renvoyer trois fois le message des encombrants le 14/08/2026.
	function icone(statut: string): string {
		if (statut === 'envoyé') return '✅';
		if (statut === 'incertain') return '⚠️';
		if (statut === 'en cours') return '⏳';
		return '❌';
	}
	function teinte(statut: string): string {
		if (statut === 'envoyé')
			return 'background:var(--color-success-fond);color:var(--color-success)';
		if (statut === 'incertain' || statut === 'en cours')
			return 'background:var(--color-warning-fond);color:var(--color-warning-texte)';
		return 'background:var(--color-danger-fond);color:var(--color-danger)';
	}
</script>

<div class="largeur-saisie">
	<div class="wa-outils">
		<button
			class="btn btn-outline wa-rafraichir"
			on:click={recharger}
			aria-label="Rafraîchir l'historique">&#x1F504;</button
		>
	</div>
	{#if journaux.length === 0}
		<p class="wa-vide">Aucun message envoyé.</p>
	{:else}
		<div class="wa-liste">
			{#each journaux as log (log.id)}
				<div class="wa-envoi">
					<div class="wa-envoi-tete">
						<span class="wa-envoi-titre">{log.label}</span>
						<div class="wa-envoi-meta">
							<span class="wa-verdict" style={teinte(log.statut)}>
								{icone(log.statut)}
								{log.statut}
							</span>
							<span class="wa-date">{log.envoye_le ? fmtDatetimeShort(log.envoye_le) : ''}</span>
						</div>
					</div>
					<p class="wa-texte">
						{log.message.length > MAX_APERCU_MESSAGE
							? log.message.slice(0, MAX_APERCU_MESSAGE) + '…'
							: log.message}
					</p>
					{#if log.erreur}
						<p class="wa-erreur">&#x26A0;&#xFE0F; {log.erreur}</p>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.wa-outils {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.wa-rafraichir {
		font-size: var(--fs-2xs);
		padding: 0.1rem 0.4rem;
	}
	.wa-vide {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.wa-liste {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.wa-envoi {
		border: 1px solid var(--color-border);
		border-radius: 6px;
		padding: 0.5rem 0.75rem;
		font-size: var(--fs-sm);
		background: var(--color-surface);
	}
	.wa-envoi-tete {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.25rem;
	}
	.wa-envoi-titre {
		font-weight: 600;
	}
	.wa-envoi-meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.wa-verdict {
		padding: 0.1rem 0.3rem;
		border-radius: 4px;
		font-size: var(--fs-2xs);
	}
	.wa-date {
		color: var(--color-text-muted);
		font-size: var(--fs-xs);
	}
	.wa-texte {
		margin: 0;
		white-space: pre-wrap;
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.wa-erreur {
		margin: 0.2rem 0 0;
		color: var(--color-danger);
		font-size: var(--fs-xs);
	}
</style>
