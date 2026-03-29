<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { auth as authApi, ApiError } from '$lib/api';
	import { getSiteNom } from '$lib/stores/pageConfig';

	const _siteNom = getSiteNom();

	let status: 'loading' | 'success' | 'error' | 'expired' = 'loading';
	let errorMessage = '';
	let resendEmail = '';
	let resendDone = false;
	let resendLoading = false;

	onMount(async () => {
		const token = $page.url.searchParams.get('token');
		if (!token) {
			status = 'error';
			errorMessage = 'Lien de vérification invalide.';
			return;
		}
		try {
			await authApi.verifierEmail(token);
			status = 'success';
		} catch (e: any) {
			status = 'expired';
			errorMessage = e instanceof ApiError ? e.message : 'Lien de vérification invalide ou expiré.';
		}
	});

	async function resend() {
		if (!resendEmail.trim()) return;
		resendLoading = true;
		try {
			await authApi.renvoyerVerification(resendEmail.trim());
			resendDone = true;
		} catch {
			resendDone = true;
		} finally {
			resendLoading = false;
		}
	}
</script>

<svelte:head><title>Vérification e-mail — {_siteNom}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card card">
		<div class="auth-header">
			<span class="auth-logo">&#x1F4E7;</span>
			<h1>Vérification e-mail</h1>
		</div>

		{#if status === 'loading'}
			<p style="text-align:center; color:var(--color-text-muted)">Vérification en cours…</p>

		{:else if status === 'success'}
			<div class="alert alert-success">
				<strong>Adresse e-mail vérifiée !</strong><br />
				Votre adresse a été confirmée. Votre compte est maintenant en attente de validation par le conseil syndical.<br />
				Vous recevrez un e-mail dès qu'il sera activé.
			</div>
			<div style="text-align:center; margin-top:1rem">
				<a href="/auth/connexion" class="btn btn-primary">Retour à la connexion</a>
			</div>

		{:else if status === 'expired'}
			<div class="alert alert-error">
				{errorMessage}
			</div>
			<div style="margin-top:1.5rem">
				<p style="font-size:.9rem; color:var(--color-text-muted); margin-bottom:.75rem">
					Vous pouvez demander un nouveau lien de vérification :
				</p>
				{#if resendDone}
					<div class="alert alert-success" style="font-size:.9rem">
						Si un compte non vérifié existe pour cette adresse, un nouveau lien vous a été envoyé.
					</div>
				{:else}
					<form on:submit|preventDefault={resend} style="display:flex; gap:.5rem">
						<input type="email" bind:value={resendEmail} placeholder="Votre e-mail" required class="input" style="flex:1" />
						<button type="submit" class="btn btn-primary" disabled={resendLoading}>
							{resendLoading ? 'Envoi…' : 'Renvoyer'}
						</button>
					</form>
				{/if}
			</div>
			<div style="text-align:center; margin-top:1rem">
				<a href="/auth/connexion" style="font-size:.85rem; color:var(--color-text-muted)">Retour à la connexion</a>
			</div>

		{:else}
			<div class="alert alert-error">{errorMessage}</div>
			<div style="text-align:center; margin-top:1rem">
				<a href="/auth/connexion" class="btn btn-outline">Retour à la connexion</a>
			</div>
		{/if}
	</div>
</div>
