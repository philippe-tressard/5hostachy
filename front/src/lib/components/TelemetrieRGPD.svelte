<!--
  **Les droits RGPD sur SA télémétrie** — opposition, portabilité, effacement.

  ## Pourquoi ce composant (#835, 08/09/2026)

  Extrait de `profil/+page.svelte` quand le garde-fou de modularité a refusé de
  le laisser grossir (739 → 754 lignes). Le refus disait vrai : cent onze lignes,
  cinq variables d'état, trois appels d'API et aucun lien avec le reste de la
  page — celle-ci en portait pourtant tout l'état.

  Les trois routes servies vivent elles-mêmes à part depuis le même lot
  (`routers/auth_telemetrie.py`), pour la même raison : elles ne parlent pas
  d'authentification.

  ⚠️ **Aucune prop.** Le composant lit l'utilisateur courant dans le store et
  parle directement à l'API. La page n'a rien à lui dire et rien à en apprendre :
  lui passer `opt_out_telemetrie` en prop aurait créé une seconde vérité sur une
  valeur que le serveur détient déjà.
-->
<script lang="ts">
	import { onMount } from 'svelte';

	import { auth as authApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { currentUser, setUser } from '$lib/stores/auth';
	import { setTelemetryOptOut } from '$lib/telemetry';

	let optOutTelemetrie = false;
	let savingOptOut = false;
	let deletingTelemetrie = false;
	let exportingTelemetrie = false;
	let confirmDeleteTelemetrie = false;

	//  ⚠️ Lu à l'ouverture ET non lié en deux sens au store : la case reflète ce
	//  que le serveur a enregistré, et c'est l'appel qui fait foi. Un `$:` sur le
	//  store la remettrait à la valeur d'avant pendant l'enregistrement.
	onMount(() => {
		optOutTelemetrie = $currentUser?.opt_out_telemetrie ?? false;
	});
</script>

<!-- Télémétrie opt-out -->
<div style="margin-top:1rem;padding-top:.75rem;border-top:1px solid #fde68a">
	<label class="checkbox-field" style="margin-bottom:.4rem">
		<input
			type="checkbox"
			bind:checked={optOutTelemetrie}
			disabled={savingOptOut}
			on:change={async () => {
				savingOptOut = true;
				try {
					await authApi.toggleOptOutTelemetrie({ opt_out_telemetrie: optOutTelemetrie });
					setTelemetryOptOut(optOutTelemetrie);
					const updated = await authApi.me();
					setUser(updated);
					toast(
						'success',
						optOutTelemetrie
							? 'Collecte de statistiques désactivée.'
							: 'Collecte de statistiques réactivée.',
					);
				} catch {
					optOutTelemetrie = !optOutTelemetrie;
					toast('error', 'Erreur lors de la mise à jour.');
				}
				savingOptOut = false;
			}}
		/>
		Refuser la collecte de statistiques de navigation
	</label>
	<p style="font-size:.78rem;color:var(--color-text-muted);margin:0 0 .75rem;padding-left:1.55rem">
		Ces statistiques anonymisées permettent au gestionnaire d'identifier les fonctionnalités les
		plus utilisées, de détecter d'éventuels problèmes de navigation et d'orienter les améliorations
		futures vers ce qui vous est réellement utile au quotidien. Elles ne contiennent aucune donnée
		personnelle sensible et ne sont jamais partagées avec des tiers. En les désactivant, vous nous
		privez d'informations précieuses pour vous offrir une meilleure expérience.
	</p>

	<div style="display:flex;gap:.5rem;flex-wrap:wrap">
		<button
			type="button"
			class="btn btn-sm"
			style="font-size:.8rem"
			disabled={exportingTelemetrie}
			on:click={async () => {
				exportingTelemetrie = true;
				try {
					const data = await authApi.exportTelemetrie();
					const json = JSON.stringify(data, null, 2);
					const blob = new Blob([json], { type: 'application/json' });
					const url = URL.createObjectURL(blob);
					const a = document.createElement('a');
					a.href = url;
					a.download = 'mes-donnees-telemetrie.json';
					a.click();
					URL.revokeObjectURL(url);
					toast('success', 'Export téléchargé.');
				} catch {
					toast('error', "Erreur lors de l'export.");
				}
				exportingTelemetrie = false;
			}}
		>
			📥 Exporter mes données de navigation
		</button>

		{#if !confirmDeleteTelemetrie}
			<button
				type="button"
				class="btn btn-sm btn-danger"
				style="font-size:.8rem"
				on:click={() => (confirmDeleteTelemetrie = true)}
			>
				🗑️ Effacer mes données de navigation
			</button>
		{:else}
			<span style="display:inline-flex;gap:.35rem;align-items:center;font-size:.8rem">
				<strong style="color:var(--color-danger)">Confirmer ?</strong>
				<button
					type="button"
					class="btn btn-sm btn-danger"
					style="font-size:.78rem"
					disabled={deletingTelemetrie}
					on:click={async () => {
						deletingTelemetrie = true;
						try {
							await authApi.effacerTelemetrie();
							toast('success', 'Données de navigation effacées.');
						} catch {
							toast('error', 'Erreur lors de la suppression.');
						}
						deletingTelemetrie = false;
						confirmDeleteTelemetrie = false;
					}}
				>
					Oui, effacer
				</button>
				<button
					type="button"
					class="btn btn-sm"
					style="font-size:.78rem"
					on:click={() => (confirmDeleteTelemetrie = false)}
				>
					Annuler
				</button>
			</span>
		{/if}
	</div>
</div>
