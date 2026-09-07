<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth as authApi, ApiError } from '$lib/api';
	import { setUser } from '$lib/stores/auth';
	import { destinationApresConnexion } from '$lib/redirection';
	import { loadSiteConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import Icon from '$lib/components/Icon.svelte';
	import ChampMotDePasse from '$lib/components/ChampMotDePasse.svelte';

	onMount(() => {
		loadSiteConfig();
	});

	$: _siteNom = $siteNomStore;
	$: brandIcon = $configStore['site_icone'] ?? 'building-2';
	$: loginSousTitre = $configStore['login_sous_titre'] ?? 'Votre espace numérique de résidence';

	let email = '';
	let password = '';
	let error = '';
	let loading = false;
	let emailNotVerified = false;
	let resendDone = false;
	let resendLoading = false;

	async function submit() {
		error = '';
		emailNotVerified = false;
		resendDone = false;
		loading = true;
		email = email.trim().toLowerCase();
		try {
			const user = await authApi.login(email, password);
			setUser(user);
			goto(destinationApresConnexion());
		} catch (e: any) {
			const msg = e instanceof ApiError ? e.message : 'Erreur de connexion';
			if (msg.includes('rifier votre adresse') || msg.includes('email')) {
				emailNotVerified = true;
			}
			error = msg;
		} finally {
			loading = false;
		}
	}

	async function resendVerification() {
		resendLoading = true;
		try {
			await authApi.renvoyerVerification(email);
			resendDone = true;
		} catch {
			resendDone = true;
		} finally {
			resendLoading = false;
		}
	}
</script>

<svelte:head><title>Connexion — {_siteNom}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card card">
		<div class="auth-header">
			<span class="auth-logo"><Icon name={brandIcon} size={48} /></span>
			<h1>{_siteNom}</h1>
			{#if loginSousTitre}<p>{loginSousTitre}</p>{/if}
		</div>

		{#if error}
			<div class="alert alert-error">
				{error}
				{#if emailNotVerified}
					<div style="margin-top:.5rem">
						{#if resendDone}
							<span style="color:var(--color-text-muted); font-size:.85rem"
								>Un nouveau lien a été envoyé si un compte non vérifié existe pour cette adresse.</span
							>
						{:else}
							<button
								type="button"
								class="btn btn-sm btn-outline"
								style="margin-top:.25rem"
								disabled={resendLoading}
								on:click={resendVerification}
							>
								{resendLoading ? 'Envoi…' : 'Renvoyer le lien de vérification'}
							</button>
						{/if}
					</div>
				{/if}
			</div>
		{/if}

		<form on:submit|preventDefault={submit}>
			<div class="field">
				<label for="email">Email *</label>
				<input id="email" type="email" bind:value={email} required autocomplete="email" />
			</div>

			<ChampMotDePasse
				id="password"
				libelle="Mot de passe"
				bind:valeur={password}
				autocomplete="current-password"
			/>

			<div class="btn-wrapper">
				<button class="btn btn-primary" type="submit" disabled={loading}>
					{loading ? 'Connexion…' : 'Se connecter'}
				</button>
			</div>
		</form>

		<div class="auth-links">
			<a href="/auth/mot-de-passe-oublie">Mot de passe oublié ?</a>
			<span>·</span>
			<a href="/auth/inscription">Créer un compte</a>
		</div>

		<div class="auth-legal">
			<a href="/mentions-legales">Mentions légales</a>
			<span>·</span>
			<a href="/politique-de-confidentialite">Politique de confidentialité</a>
		</div>
	</div>
</div>

<style>
	/*  `.auth-page`, `.auth-card`, `.auth-header` et `.auth-logo` : copies au
	    caractère près de `styles/composants.css`, donc inertes. Retirées le
	    28/08/2026. Ce qui suit habille le CONTENU de l'en-tête, pas la carte. */
	.auth-header h1 {
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--color-primary);
		margin-bottom: 0.3rem;
	}

	.auth-header p {
		color: var(--color-text-muted);
		font-size: 0.875rem;
	}

	.btn-wrapper {
		display: flex;
		justify-content: center;
		margin-top: 1.25rem;
	}

	.btn-wrapper .btn {
		padding-left: 2.5rem;
		padding-right: 2.5rem;
	}

	.auth-links {
		display: flex;
		justify-content: center;
		gap: 0.5rem;
		margin-top: 1rem;
		font-size: 0.875rem;
	}

	.auth-legal {
		display: flex;
		justify-content: center;
		gap: 0.5rem;
		margin-top: 1.25rem;
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}
</style>
