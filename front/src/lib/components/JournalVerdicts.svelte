<!--
  Un journal : des lignes, chacune avec son verdict, sa date et ce qu'elle dit.

  Né le 28/09/2026 (#1447) de `HistoriqueEnvoisWhatsApp`, quand la relève des
  réponses par courriel a demandé le même rendu — un message, son issue, sa
  raison. Le recopier aurait fait deux journaux qui divergent au premier
  changement ; les deux écrans ne font plus que DIRE ce qu'ils montrent
  (`EntreeJournal`), et c'est ici qu'on le rend.

  Le verdict est une pastille `.badge-*` de la charte — son contraste est
  mesuré par `lint:charte-valeurs` — et non plus une teinte écrite en ligne.
-->
<script context="module" lang="ts">
	export type TonVerdict = 'succes' | 'info' | 'attention' | 'danger' | 'neutre';

	/** Une ligne de journal, telle que l'écran appelant la décrit. */
	export interface EntreeJournal {
		/** Clé du `{#each}` — l'identifiant de la ligne côté serveur. */
		cle: number;
		titre: string;
		/** Sous le titre, en gris : qui, d'où. */
		sousTitre?: string;
		verdict: string;
		/** La gravité, jamais le nom : elle choisit la pastille de la charte. */
		ton: TonVerdict;
		date: string | null;
		texte: string;
		/** Une mise en garde, en rouge sous le texte. */
		alerte?: string;
		lien?: { href: string; libelle: string };
	}
</script>

<script lang="ts">
	import { fmtDatetimeShort } from '$lib/date';
	import EtatListe from '$lib/components/EtatListe.svelte';

	export let entrees: EntreeJournal[] = [];
	/** Non vide = le journal n'a pas pu être lu : il ne se dit pas « vide » (#1459). */
	export let erreur = '';
	export let vide = 'Rien à afficher.';
	export let recharger: () => unknown = () => {};
	/** Ce que le bouton de rafraîchissement annonce aux lecteurs d'écran. */
	export let libelleRecharger = 'Rafraîchir';
</script>

<div class="largeur-saisie">
	<div class="jv-outils">
		<button class="btn btn-outline jv-rafraichir" on:click={recharger} aria-label={libelleRecharger}
			>&#x1F504;</button
		>
	</div>
	{#if erreur}
		<EtatListe compact {erreur} />
	{:else if entrees.length === 0}
		<p class="jv-vide">{vide}</p>
	{:else}
		<ul class="jv-liste">
			{#each entrees as e (e.cle)}
				<li class="jv-ligne">
					<div class="jv-tete">
						<span class="jv-titre">{e.titre}</span>
						<span class="jv-meta">
							<span
								class="badge"
								class:badge-green={e.ton === 'succes'}
								class:badge-blue={e.ton === 'info'}
								class:badge-orange={e.ton === 'attention'}
								class:badge-red={e.ton === 'danger'}
								class:badge-gray={e.ton === 'neutre'}>{e.verdict}</span
							>
							{#if e.date}<time class="jv-date" datetime={e.date}>{fmtDatetimeShort(e.date)}</time
								>{/if}
						</span>
					</div>
					{#if e.sousTitre}<p class="jv-sous-titre">{e.sousTitre}</p>{/if}
					<p class="jv-texte">{e.texte}</p>
					{#if e.alerte}<p class="jv-alerte">&#x26A0;&#xFE0F; {e.alerte}</p>{/if}
					{#if e.lien}<a class="jv-lien" href={e.lien.href}>{e.lien.libelle}</a>{/if}
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.jv-outils {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.jv-rafraichir {
		font-size: var(--fs-2xs);
		padding: 0.1rem 0.4rem;
	}
	.jv-vide {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.jv-liste {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.jv-ligne {
		border: 1px solid var(--color-border);
		border-radius: 6px;
		padding: 0.5rem 0.75rem;
		font-size: var(--fs-sm);
		background: var(--color-surface);
		/*  Une adresse ou un objet sans espace ne doit pas élargir la page au
		    téléphone : il se coupe plutôt que de pousser le cadre. */
		overflow-wrap: anywhere;
	}
	.jv-tete {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.25rem 0.5rem;
		margin-bottom: 0.25rem;
	}
	.jv-titre {
		font-weight: 600;
		min-width: 0;
	}
	.jv-meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-shrink: 0;
	}
	.jv-date {
		color: var(--color-text-muted);
		font-size: var(--fs-xs);
		font-variant-numeric: tabular-nums;
	}
	.jv-sous-titre {
		margin: 0 0 0.2rem;
		color: var(--color-text-muted);
		font-size: var(--fs-xs);
	}
	.jv-texte {
		margin: 0;
		white-space: pre-wrap;
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.jv-alerte {
		margin: 0.2rem 0 0;
		color: var(--color-danger);
		font-size: var(--fs-xs);
	}
	.jv-lien {
		/*  Une cible qu'on touche au pouce : la hauteur vient du cadre, pas du
		    texte en petit corps (standards/11 §10). */
		display: inline-flex;
		align-items: center;
		min-height: 1.75rem;
		margin-top: 0.1rem;
		font-size: var(--fs-xs);
	}
</style>
