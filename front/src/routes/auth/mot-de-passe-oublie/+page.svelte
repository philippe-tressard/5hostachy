<script lang="ts">
	import { auth as authApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getSiteNom } from '$lib/stores/pageConfig';

	const _siteNom = getSiteNom();

	let email = '';
	let sending = false;
	let done = false;

	async function submit() {
		sending = true;
		try {
			await authApi.requestPasswordReset({ email });
			done = true;
		} catch (e) {
			// Ne pas révéler si l'e-mail existe ou non (sécurité)
			done = true;
		} finally {
			sending = false;
		}
	}
</script>

<svelte:head><title>Mot de passe oublié — {_siteNom}</title></svelte:head>

<div class="auth-wrapper">
	<div class="auth-card">
		<h1>Mot de passe oublié</h1>

		{#if done}
			<div class="success-box">
				<p>Si un compte est associé à cet e-mail, un lien de réinitialisation vous a été envoyé.</p>
				<p>Vérifiez votre boîte de réception (et les spams).</p>
			</div>
			<div class="btn-wrapper">
				<a href="/auth/connexion" class="btn btn-primary">Retour à la connexion</a>
			</div>
		{:else}
			<p style="font-size:.875rem;color:var(--color-text-muted);margin-bottom:1.5rem">
				Saisissez votre adresse e-mail et nous vous enverrons un lien pour réinitialiser votre mot de passe.
			</p>
			<form on:submit|preventDefault={submit}>
				<div class="field">
					<label for="reset-email">Adresse e-mail *</label>
					<input id="reset-email" type="email" bind:value={email} required autocomplete="email" />
				</div>
				<div class="btn-wrapper">
					<button type="submit" class="btn btn-primary" disabled={sending}>
						{sending ? 'Envoi…' : 'Envoyer le lien'}
					</button>
				</div>
			</form>
			<p style="text-align:center;font-size:.8rem;margin-top:1rem">
				<a href="/auth/connexion" style="color:var(--color-primary)">Retour à la connexion</a>
			</p>
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
	.auth-card {
		background: #fff;
		border: 1px solid var(--color-border, #e5e7eb);
		border-radius: .75rem;
		padding: 2rem;
		width: 100%;
		max-width: 400px;
		box-shadow: 0 2px 12px rgba(0,0,0,.06);
	}
	h1 { font-size: 1.3rem; font-weight: 700; margin-bottom: .25rem; }
	.success-box {
		background: #f0fdf4;
		border: 1px solid #bbf7d0;
		border-radius: .5rem;
		padding: 1rem 1.25rem;
		font-size: .875rem;
		color: #166534;
		line-height: 1.6;
	}
	.success-box p + p { margin-top: .4rem; }

	.btn-wrapper {
		display: flex;
		justify-content: center;
		margin-top: 1.25rem;
	}
	.btn-wrapper :global(.btn) {
		padding-left: 2.5rem;
		padding-right: 2.5rem;
	}
</style>
