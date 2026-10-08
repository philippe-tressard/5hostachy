<!--
  **Accueillir un arrivant déjà inscrit** — la modale de l'onglet Utilisateurs
  qui déclenche les actions d'accueil : bienvenue, consignes, étiquette de boîte
  aux lettres (syndic), interphone (CS).

  Extraite d'`OngletUtilisateurs` le 30/09/2026 (#779) : elle a son état, son
  envoi et son rendu, et ne reçoit que le compte visé.

  ⚠️ C'est une MODALE, et elle le reste à dessein : un geste sur un utilisateur
  EXISTANT, déclenché depuis la liste des comptes, pas la correction d'un objet
  en place (#889). `lint:geste-edition` le déclare (liste `MODALES`).
-->
<script lang="ts">
	import { messageErreur } from '$lib/erreurs';
	import { createEventDispatcher } from 'svelte';
	import { admin as adminApi, type User } from '$lib/api';
	import Modale from '$lib/components/Modale.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { nomAffiche } from '$lib/noms';

	export let utilisateur: User;
	export let batimentsMap: Record<number, string> = {};

	const dispatch = createEventDispatcher<{ fermer: void }>();
	const fermer = () => dispatch('fermer');

	let batiment = utilisateur.batiment_id ? (batimentsMap[utilisateur.batiment_id] ?? '') : '';
	let ancienResident = '';
	let envoi = false;

	async function lancer() {
		envoi = true;
		try {
			await adminApi.accueilArrivant(utilisateur.id, {
				batiment: batiment || null,
				ancien_resident: ancienResident || null,
			});
			toast('success', `Actions d'accueil envoyées pour ${nomAffiche(utilisateur)}.`);
			fermer();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			envoi = false;
		}
	}
</script>

<Modale
	edition
	titre="🏠 Accueil nouvel arrivant"
	classeBoite="modal-box card"
	styleBoite="max-width:480px"
	on:fermer={fermer}
>
	<p style="font-size:var(--fs-md);margin-bottom:.1rem">
		<strong>{nomAffiche(utilisateur)}</strong>
	</p>
	<p style="font-size:var(--fs-sm);color:var(--color-text-muted);margin-bottom:.75rem">
		Déclenche : bienvenue, consignes de copropriété, demande d'étiquette BAL (syndic), demande
		d'interphone (CS), avec copie des démarches au résident.
	</p>
	<div class="form-grid form-grid-2" style="margin-bottom:.75rem">
		<label class="field"
			>Bâtiment / logement
			<input bind:value={batiment} placeholder="Ex: Bât. A, Apt. 12…" />
		</label>
		<label class="field"
			>Ancien résident
			<input bind:value={ancienResident} placeholder="Nom de l'ancien occupant…" />
		</label>
	</div>
	<div class="modal-footer">
		<button class="btn btn-outline" on:click={fermer}>Annuler</button>
		<button class="btn btn-primary" disabled={envoi} on:click={lancer}>
			{envoi ? 'En cours…' : "Lancer les actions d'accueil"}
		</button>
	</div>
</Modale>
