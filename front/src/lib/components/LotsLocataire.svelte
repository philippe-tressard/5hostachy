<!--
  **La vue locataire de « Mes lots »** — le lot loué, son bail et son
  propriétaire, puis les lots que le locataire possède en propre.

  Extraite de `mon-lot/+page.svelte` le 01/10/2026 (#779), en pendant de
  `LotsBailleur` : la page choisit la vue selon le rôle, chaque vue rend la
  sienne. Au passage, deux copies ont rejoint leur source :

  - le badge du bail était recomposé ici — « Bail actif », TOUJOURS vert, et
    `statut.replace('_', ' ')` sinon. Un bail en cours de sortie y serait sorti
    vert et mal libellé ; il passe par `BadgeStatutBail` (`lint:statut-recalcule`) ;
  - les caractéristiques du lot, écrites deux fois ici et une fois dans la
    page, passent par `CaracteristiquesLot` (`lint:caracteristiques-lot`).
-->
<script lang="ts">
	import BadgeStatutBail from '$lib/components/BadgeStatutBail.svelte';
	import CaracteristiquesLot from '$lib/components/CaracteristiquesLot.svelte';
	import { fmtDateShort as fmt } from '$lib/date';
	import { nomAffiche } from '$lib/noms';

	/** Le bail du locataire (`bailleur.monBail()`), ou `null` s'il n'en a pas. */
	export let bail: any = null;
	/** Les lots qu'il possède en propre, s'il en a. */
	export let lots: any[] = [];
</script>

{#if bail}
	<div class="lots-section-label">🏠 Lot loué</div>
	<div class="card largeur-saisie carte-lot">
		<div class="carte-lot-entete">
			<span class="lbc-lot-badge">{bail.lot_batiment_nom ?? '—'} / {bail.lot_numero ?? '—'}</span>
			<BadgeStatutBail statut={bail.statut} compact />
		</div>
		<CaracteristiquesLot
			type={bail.lot_type}
			typeAppartement={bail.lot_type_appartement}
			etage={bail.lot_etage}
			superficie={bail.lot_superficie}
		>
			<svelte:fragment slot="avant">
				<dt>Bâtiment</dt>
				<dd>{bail.lot_batiment_nom ?? '—'}</dd>
			</svelte:fragment>
			<svelte:fragment slot="apres">
				<dt>Entrée</dt>
				<dd>{fmt(bail.date_entree)}</dd>
				{#if bail.date_sortie_prevue}
					<dt>Sortie prévue</dt>
					<dd>{fmt(bail.date_sortie_prevue)}</dd>
				{/if}
			</svelte:fragment>
		</CaracteristiquesLot>
		{#if bail.bailleur_nom || bail.bailleur_prenom}
			<div class="proprietaire">
				🏢 Propriétaire : <strong>{nomAffiche(bail.bailleur_prenom, bail.bailleur_nom)}</strong>
				{#if bail.bailleur_email}<br />📬
					<a href="mailto:{bail.bailleur_email}">{bail.bailleur_email}</a>{/if}
				{#if bail.bailleur_telephone}<br />📞 {bail.bailleur_telephone}{/if}
			</div>
		{/if}
	</div>
{:else}
	<div class="empty-state">
		<h3>Aucun bail actif</h3>
		<p>
			Votre propriétaire doit vous rattacher depuis la section <strong>Gestion locative</strong> de son
			espace.
		</p>
	</div>
{/if}

{#if lots.length > 0}
	<div class="lots-section-label lots-en-propre">🏢 Lots en propriété ({lots.length})</div>
	{#each lots as lot (lot.id)}
		<div class="card largeur-saisie carte-lot">
			<h2 class="carte-lot-titre">{lot.batiment_nom ?? '—'} / {lot.numero}</h2>
			<CaracteristiquesLot
				type={lot.type}
				typeAppartement={lot.type_appartement}
				etage={lot.etage}
				superficie={lot.superficie}
			/>
		</div>
	{/each}
{/if}

<style>
	.carte-lot {
		margin-bottom: 1.5rem;
	}
	.carte-lot-entete {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.carte-lot-titre {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 0.75rem;
	}
	.lots-en-propre {
		margin-top: 1.5rem;
	}
	.proprietaire {
		margin-top: 0.75rem;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
	.proprietaire a {
		color: var(--color-primary);
	}
</style>
