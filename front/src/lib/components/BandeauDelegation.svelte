<!--
  **Agir au nom de quelqu'un** — le sélecteur de délégation et le bandeau qui dit
  qu'elle est active.

  ## 🔴 Pourquoi ce composant (14/09/2026, #779)

  Les deux blocs étaient écrits **deux fois** dans `Nav.svelte` — une fois pour le
  menu latéral, une fois pour le menu plein écran du mobile —, à quatre-vingts
  lignes d'écart, identiques au retrait d'indentation près. Trouvés par un relevé
  mécanique des blocs répétés, pas à la lecture : les deux copies étaient
  cohérentes entre elles, et c'est la forme la plus durable d'un écart
  (`project_doublons_trouves_mecaniquement`).

  🔒 **Et ce n'est pas un bloc d'affichage comme un autre** : il pose `actingAs`,
  c'est-à-dire l'identité sous laquelle toutes les requêtes suivantes partent
  (en-tête `X-Acting-As`). Deux écritures d'un commutateur d'identité, ce sont
  deux occasions de diverger sur *qui* on devient — exactement ce que « la
  sécurité est centralisée » interdit.

  ⚠️ **Le serveur reste seul juge.** Ce composant ne fait que proposer : la
  délégation est vérifiée à chaque requête par `get_acting_user`, qui refuse une
  délégation absente, révoquée ou expirée. Un mandant bricolé ici n'ouvrirait
  rien.

  ## Ce qui différait entre les deux copies, et ce qu'il en reste

  Rien d'autre que deux espacements, posés en `style=` sur le menu mobile. Ils
  deviennent une variante nommée (`compact`), stylée **ici** : le balisage
  déménage avec ses règles, sinon Svelte les laisse derrière lui — c'est la
  panne des pastilles nues de la v2.67.11.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { currentUser, actingAs, isActingAsAidant } from '$lib/stores/auth';

	/** Menu plein écran du mobile : les deux blocs y sont un peu plus espacés. */
	export let compact = false;

	$: delegations = $currentUser?.delegations_aidant ?? [];

	/**  Le passage d'une identité à l'autre — écrit UNE fois.
	 *
	 *   ⚠️ `0` n'est pas un identifiant, c'est « moi-même » : le `<select>` ne
	 *   sait porter que des valeurs, et l'absence de délégation doit en être une.
	 *   Un mandant introuvable ne change RIEN plutôt que de poser un état
	 *   partiel — on ne devient pas à moitié quelqu'un d'autre. */
	function choisir(evenement: Event) {
		const val = Number((evenement.target as HTMLSelectElement).value);
		if (val === 0) {
			actingAs.set(null);
			return;
		}
		const d = delegations.find((x) => x.mandant_id === val);
		if (d) actingAs.set({ mandant_id: d.mandant_id, mandant_nom: d.mandant_nom });
	}
</script>

{#if delegations.length > 0}
	<div class="aidant-switcher" class:compact>
		<span class="aidant-switcher-label">Agir pour :</span>
		<select class="aidant-select" value={$actingAs?.mandant_id ?? 0} on:change={choisir}>
			<option value={0}>Moi-même</option>
			{#each delegations as d (d.mandant_id)}
				<option value={d.mandant_id}>{d.mandant_nom}</option>
			{/each}
		</select>
	</div>
{/if}

{#if $isActingAsAidant}
	<div class="aidant-banner" class:compact>
		<Icon name="heart-handshake" size={14} />
		<span>Vous agissez pour <strong>{$actingAs?.mandant_nom}</strong></span>
	</div>
{/if}

<style>
	/*  Ces règles vivaient dans le `<style>` de `Nav.svelte`. Elles partent avec
	    le balisage qui les porte — c'est la seule façon qu'elles s'appliquent :
	    Svelte scope le style au composant qui REND le balisage. */
	.aidant-switcher {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.4rem 0.75rem;
		margin-bottom: 0.25rem;
	}
	.aidant-switcher.compact {
		padding: 0.5rem 0.75rem;
	}
	.aidant-switcher-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text-muted);
		font-weight: 600;
	}
	.aidant-select {
		padding: 0.3rem 0.5rem;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		font-size: 0.8rem;
		background: var(--color-surface);
		width: 100%;
		cursor: pointer;
	}
	.aidant-banner {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.3rem 0.75rem;
		margin: 0 0.5rem 0.25rem;
		background: #fef3c7;
		color: #92400e;
		border-radius: var(--radius);
		font-size: 0.78rem;
		line-height: 1.3;
	}
	.aidant-banner.compact {
		margin: 0.25rem 0.75rem;
	}
</style>
