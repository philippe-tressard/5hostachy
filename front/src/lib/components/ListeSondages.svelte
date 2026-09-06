<!--
  La liste des sondages — le `{#each}` et la carte, écrits **une seule fois**.

  ## Pourquoi ce composant existe (#515, 02/09/2026)

  L'onglet en rend maintenant **deux** : les sondages courants, et les Archives
  repliées — 30 jours après la date de clôture, règle du site portée par
  `app/utils/archivage.py`.

  🔴 Recopier le bloc `{#each}` sous la section repliée aurait fait soixante-dix
  lignes de carte en double. C'est ce que le rang 1 interdit, et ce qui est arrivé
  six fois au fil des tickets (#431). Troisième extraction de la même forme sur le
  même écran, après `ListeAnnonces` (18/08) et `ListeIdees` (ce jour) — les trois
  rubriques de Communauté ont enfin la même structure.

  ⚠️ Ce composant ne décide de RIEN : `s.cloture` et `s.archivee` sont tous deux
  calculés par le serveur. Le premier l'est depuis #468, après que la liste eut
  recalculé la clôture en JavaScript et divergé sur le fuseau ; le second l'est
  pour la même raison.

  Les gestes — arrêter, supprimer — restent chez le parent : c'est lui qui parle à
  l'API et recharge la liste.
-->
<script lang="ts">
	import { fmtDateShort, isNouveau } from '$lib/date';
	import BoutonLien from '$lib/components/BoutonLien.svelte';
	import { safeHtml } from '$lib/sanitize';
	import { estPerimetreParDefaut, perimetreLabel } from '$lib/perimetres';
	import { concerneTousLesResidents, destinatairesLabel } from '$lib/destinataires';
	import { currentUser, isAdmin } from '$lib/stores/auth';

	/** Les sondages à rendre, déjà filtrés par l'appelant. */
	export let sondages: any[] = [];
	export let arreterSondage: (s: any, e: Event) => void;
	export let supprimerSondage: (s: any, e: Event) => void;
	/**  Corriger son sondage (#783). Même condition que « Stopper » : l'auteur
	 *   ou un admin, et **pas** un sondage clôturé — le serveur le refuse, et un
	 *   bouton qui déclencherait un refus serait pire qu'absent. */
	export let modifierSondage: (s: any, e: Event) => void;
</script>

{#each sondages as s (s.id)}
	<a href="/sondages/{s.id}" class="sondage-card card">
		<div class="sondage-body">
			<strong class="sondage-question"
				>{s.question}
				{#if isNouveau(s.cree_le)}<span
						class="badge badge-gray"
						style="margin-left:.5em;font-size:.82em;font-weight:500;vertical-align:middle">New</span
					>{/if}
			</strong>
			{#if s.description}<div class="sondage-desc rich-content clamp-5">
					{@html safeHtml(s.description)}
				</div>{/if}
			<small style="color:var(--color-text-muted)">
				{fmtDateShort(s.cree_le)}
				{#if s.cloture_le}
					· {s.cloture ? '🔒 Clôturé' : `Clôture le ${fmtDateShort(s.cloture_le)}`}
				{/if}
				·
				<span class="sondage-votants"
					>{s.nb_votants ?? 0} votant{(s.nb_votants ?? 0) !== 1 ? 's' : ''}</span
				>
			</small>
			<!--  Ciblage affiché comme PARTOUT ailleurs : 🔹 pour le périmètre logique
      (jamais 📍, qui est réservé au lieu physique), et rien du tout quand le
      ciblage est le défaut — le redire n'apprend rien. Les badges rendaient
      jusqu'ici les valeurs BRUTES de la base (« copropriétaire_résident »,
      « Bât. 3 » reconstitué à la main), faute de traduction disponible. -->
			{#if !estPerimetreParDefaut(s.perimetre_cible) || !concerneTousLesResidents(s.public_cible)}
				<div class="sondage-ciblage">
					{#if !estPerimetreParDefaut(s.perimetre_cible)}
						<span class="badge badge-blue sondage-badge"
							>&#x1F539; {perimetreLabel(s.perimetre_cible)}</span
						>
					{/if}
					{#if !concerneTousLesResidents(s.public_cible)}
						<span class="badge badge-orange sondage-badge"
							>{destinatairesLabel(s.public_cible)}</span
						>
					{/if}
				</div>
			{/if}
		</div>
		<div class="sondage-actions">
			<!--  Un sondage a sa page : on copie SON adresse, pas celle de la liste. -->
			<BoutonLien chemin="/sondages/{s.id}" quoi="le sondage" />
			{#if s.cloture}
				<span class="badge badge-gray">Clôturé</span>
			{:else}
				<span class="badge badge-green">Ouvert</span>
			{/if}
			{#if ($currentUser?.id === s.auteur_id || $isAdmin) && !s.cloture}
				<button
					class="btn-icon"
					aria-label="Modifier ce sondage"
					title="Modifier"
					on:click={(e) => modifierSondage(s, e)}>&#x270F;&#xFE0F;</button
				>
			{/if}
			{#if ($currentUser?.id === s.auteur_id || $isAdmin) && !s.cloture}
				<button
					class="btn-icon-warn"
					aria-label="Stopper ce sondage"
					title="Stopper"
					on:click={(e) => arreterSondage(s, e)}>⏹️</button
				>
			{/if}
			{#if $currentUser?.id === s.auteur_id || $isAdmin}
				<button
					class="btn-icon-danger"
					aria-label="Supprimer"
					title="Supprimer"
					on:click={(e) => supprimerSondage(s, e)}>&#x1F5D1;️</button
				>
			{/if}
		</div>
	</a>
{/each}

<style>
	.sondage-card {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: 1rem 1.25rem;
		margin-bottom: 0.5rem;
		text-decoration: none;
		color: var(--color-text);
		transition: border-color 0.12s;
	}
	.sondage-card:hover {
		border-color: var(--color-primary);
	}
	.sondage-actions {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.35rem;
		flex-shrink: 0;
	}
	.sondage-question {
		font-size: 0.95rem;
		font-weight: 600;
		display: block;
		margin-bottom: 0.2rem;
	}
	.sondage-desc {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin: 0.2rem 0 0.3rem;
	}
	.sondage-votants {
		font-weight: 600;
	}
	.sondage-ciblage {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin-top: 0.35rem;
	}
	.sondage-badge {
		font-size: 0.7rem;
	}
</style>
