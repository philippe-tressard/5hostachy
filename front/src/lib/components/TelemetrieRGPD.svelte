<!--
  **Le refus de la mesure d'audience** — la seule chose que le résident règle sur
  sa télémétrie.

  ## Pourquoi ce composant (#835, 08/09/2026)

  Extrait de `profil/+page.svelte` quand le garde-fou de modularité a refusé de
  le laisser grossir : cinq variables d'état, trois appels d'API et aucun lien
  avec le reste de la page.

  ## 🔴 Plus d'export ni d'effacement (#1545, 02/10/2026)

  Le composant offrait aussi « Exporter » et « Effacer mes données de
  navigation ». La mesure d'audience ne porte plus d'identifiant : il n'y a plus
  de données de navigation À SOI — exporter rendrait une liste vide, effacer ne
  toucherait rien, et les deux boutons prétendraient répondre à un droit.

  Le refus reste, et c'est voulu : une collecte anonyme peut garder un refus
  volontaire. Il s'applique dans le navigateur (`$lib/telemetry`) — qui refuse
  n'envoie plus rien — et le compte le retient d'un appareil à l'autre.

  ⚠️ Le texte sous la case disait que, sans ces statistiques, le résident « nous
  prive d'informations précieuses » : un refus doit être aussi simple et aussi
  neutre que l'acceptation (`standards/14` §4). La phrase est retirée.

  ⚠️ **Aucune prop.** Le composant lit l'utilisateur courant dans le store et
  parle directement à l'API : lui passer `opt_out_telemetrie` en prop aurait créé
  une seconde vérité sur une valeur que le serveur détient déjà.
-->
<script lang="ts">
	import { auth as authApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { currentUser, quandAuthResolue, setUser } from '$lib/stores/auth';
	import { setTelemetryOptOut } from '$lib/telemetry';

	let optOutTelemetrie = false;
	let savingOptOut = false;

	//  ⚠️ Lu à l'ouverture ET non lié en deux sens au store : la case reflète ce
	//  que le serveur a enregistré, et c'est l'appel qui fait foi. Un `$:` sur le
	//  store la remettrait à la valeur d'avant pendant l'enregistrement.
	//  Pas `onMount` : il précède le layout qui charge l'utilisateur (#1486).
	quandAuthResolue(() => {
		optOutTelemetrie = $currentUser?.opt_out_telemetrie ?? false;
	});
</script>

<!-- Mesure d'audience : refus -->
<div style="margin-top:1rem;padding-top:.75rem;border-top:1px solid var(--color-warning-bordure)">
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
	<p style="font-size:var(--fs-sm);color:var(--color-text-muted);margin:0;padding-left:1.55rem">
		Ces statistiques comptent les pages consultées pour savoir quels écrans servent. Elles sont
		enregistrées <strong>sans identifiant</strong> — ni votre compte, ni votre adresse IP — et à l'heure
		près. Si vous cochez la case, votre navigateur ne les envoie plus.
	</p>
</div>
