<script lang="ts">
	import ChampMotDePasse from '$lib/components/ChampMotDePasse.svelte';
	import { auth as authApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getSiteNom } from '$lib/stores/pageConfig';

	export let data: { token: string };

	const _siteNom = getSiteNom();

	let token = data.token;
	let nouveauMdp = '';
	let confirmMdp = '';
	let saving = false;
	let done = false;
	let tokenInvalide = !token;

	/* Même défaut qu'au profil (issue #344) : la divergence des deux saisies
	   était connue à la frappe et n'était dite qu'au clic. On ne la signale
	   qu'une fois la confirmation entamée, pour ne pas crier sur un champ vide. */
	$: confirmationDivergente = confirmMdp.length > 0 && nouveauMdp !== confirmMdp;

	async function submit() {
		if (nouveauMdp !== confirmMdp) {
			toast('error', 'Les mots de passe ne correspondent pas.');
			return;
		}
		saving = true;
		try {
			await authApi.resetPassword({ token, nouveau_mot_de_passe: nouveauMdp });
			done = true;
		} catch (e) {
			if (e instanceof ApiError && e.status === 400) {
				toast('error', 'Lien invalide ou expiré. Faites une nouvelle demande.');
				tokenInvalide = true;
			} else {
				toast('error', 'Une erreur est survenue. Réessayez.');
			}
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head><title>Nouveau mot de passe — {_siteNom}</title></svelte:head>

<div class="auth-wrapper">
	<div class="auth-card">
		<h1>Nouveau mot de passe</h1>

		{#if done}
			<div class="success-box">
				<p>Votre mot de passe a été modifié avec succès.</p>
			</div>
			<div class="btn-wrapper">
				<a href="/auth/connexion" class="btn btn-primary">Se connecter</a>
			</div>
		{:else if tokenInvalide}
			<div class="error-box">
				<p>Ce lien est invalide ou a expiré.</p>
			</div>
			<div class="btn-wrapper">
				<a href="/auth/mot-de-passe-oublie" class="btn btn-primary">Nouvelle demande</a>
			</div>
		{:else}
			<p style="font-size:.875rem;color:var(--color-text-muted);margin-bottom:1.5rem">
				Choisissez un nouveau mot de passe pour votre compte.
			</p>
			<form on:submit|preventDefault={submit}>
				<ChampMotDePasse
					id="mdp-nouveau"
					libelle="Nouveau mot de passe"
					bind:valeur={nouveauMdp}
					autocomplete="new-password"
					longueurMini={8}
					robustesse
				/>
				<ChampMotDePasse
					id="mdp-confirm"
					libelle="Confirmer le mot de passe"
					bind:valeur={confirmMdp}
					autocomplete="new-password"
					longueurMini={8}
					erreur={confirmationDivergente ? 'Cette saisie diffère du nouveau mot de passe.' : ''}
				/>
				<div class="btn-wrapper">
					<a href="/auth/connexion" class="btn btn-outline">Annuler</a>
					<button type="submit" class="btn btn-primary" disabled={saving}>
						{saving ? 'Enregistrement…' : 'Enregistrer'}
					</button>
				</div>
			</form>
		{/if}
	</div>
</div>

<style>
	.auth-wrapper {
		min-height: 100dvh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--color-bg-alt, #f9fafb);
		padding: 1.5rem;
	}
	/*  🔴 Cette carte ecrivait `#fff` EN DUR et un rayon `.75rem` au lieu des
	    jetons : elle ne suivait donc NI le theme NI la charte, sur un ecran
	    d'authentification qu'on ne regarde jamais (#607, 28/08/2026).
	    Seule l'ombre lui est propre. */
	.auth-card {
		box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
	}
	h1 {
		font-size: 1.3rem;
		font-weight: 700;
		margin-bottom: 0.25rem;
	}
	.success-box {
		background: #f0fdf4;
		border: 1px solid #bbf7d0;
		border-radius: 0.5rem;
		padding: 1rem 1.25rem;
		font-size: 0.875rem;
		color: #166534;
		line-height: 1.6;
	}
	.error-box {
		background: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: 0.5rem;
		padding: 1rem 1.25rem;
		font-size: 0.875rem;
		color: #991b1b;
		line-height: 1.6;
	}
	/* `.field` et `.field label` vivaient aussi ici, à l'identique de `app.css`
	   qui s'applique déjà à cette route : deux copies de la même règle, dont
	   celle-ci n'était même plus atteinte depuis que la saisie appartient à
	   `ChampMotDePasse`. Supprimées avec le reste de l'œil recopié. */
	.btn-wrapper {
		display: flex;
		justify-content: center;
		gap: 0.75rem;
		margin-top: 1.25rem;
	}
</style>
