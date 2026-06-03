<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import PasswordStrength from '$lib/components/PasswordStrength.svelte';
	import { auth as authApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getSiteNom } from '$lib/stores/pageConfig';

	export let data: { token: string };

	const _siteNom = getSiteNom();

	let token = data.token;
	let nouveauMdp = '';
	let confirmMdp = '';
	let showPassword = false;
	let showConfirm = false;
	let capsLockOn = false;
	let saving = false;
	let done = false;
	let tokenInvalide = !token;

	function checkCapsLock(e: KeyboardEvent) {
		capsLockOn = e.getModifierState('CapsLock');
	}

	async function submit() {
		if (nouveauMdp !== confirmMdp) {
			toast('Les mots de passe ne correspondent pas.', 'error');
			return;
		}
		saving = true;
		try {
			await authApi.resetPassword({ token, nouveau_mot_de_passe: nouveauMdp });
			done = true;
		} catch (e) {
			if (e instanceof ApiError && e.status === 400) {
				toast('Lien invalide ou expiré. Faites une nouvelle demande.', 'error');
				tokenInvalide = true;
			} else {
				toast('Une erreur est survenue. Réessayez.', 'error');
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
				<div class="field">
					<label for="mdp-nouveau">Nouveau mot de passe *</label>
					<div class="input-eye">
						<input id="mdp-nouveau" type={showPassword ? 'text' : 'password'} bind:value={nouveauMdp}
							required autocomplete="new-password" minlength="8"
							on:keydown={checkCapsLock} on:keyup={checkCapsLock} on:focus={checkCapsLock} />
						<button type="button" class="eye-btn" on:click={() => showPassword = !showPassword}
							aria-label={showPassword ? 'Masquer' : 'Afficher'}>
							<Icon name={showPassword ? 'eye-off' : 'eye'} size={18} />
						</button>
					</div>
					<PasswordStrength password={nouveauMdp} />
					{#if capsLockOn && !showPassword}
						<div class="capslock-warn" role="alert">⚠️ <strong>Verr. Maj. activée</strong> — votre mot de passe pourrait être incorrect.</div>
					{/if}
				</div>
				<div class="field">
					<label for="mdp-confirm">Confirmer le mot de passe *</label>
					<div class="input-eye">
						<input id="mdp-confirm" type={showConfirm ? 'text' : 'password'} bind:value={confirmMdp}
							required autocomplete="new-password" minlength="8" />
						<button type="button" class="eye-btn" on:click={() => showConfirm = !showConfirm}
							aria-label={showConfirm ? 'Masquer' : 'Afficher'}>
							<Icon name={showConfirm ? 'eye-off' : 'eye'} size={18} />
						</button>
					</div>
				</div>
				<div class="btn-wrapper">
					<a href="/auth/connexion" class="btn btn-secondary">Annuler</a>
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
	.error-box {
		background: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: .5rem;
		padding: 1rem 1.25rem;
		font-size: .875rem;
		color: #991b1b;
		line-height: 1.6;
	}
	.field { margin-bottom: 1rem; }
	.field label { display: block; font-size: .875rem; font-weight: 500; margin-bottom: .35rem; }
	.input-eye {
		position: relative;
		display: flex;
		align-items: center;
	}
	.input-eye input {
		flex: 1;
		padding-right: 2.5rem;
	}
	.eye-btn {
		position: absolute;
		right: .6rem;
		background: none;
		border: none;
		padding: 0;
		cursor: pointer;
		color: var(--color-text-muted);
		display: flex;
		align-items: center;
	}
	.eye-btn:hover { color: var(--color-text); }
	.capslock-warn {
		margin-top: .4rem;
		padding: .45rem .7rem;
		background: #fffbeb;
		border: 1px solid #fde68a;
		border-radius: .375rem;
		font-size: .8rem;
		color: #92400e;
	}
	.btn-wrapper {
		display: flex;
		justify-content: center;
		gap: .75rem;
		margin-top: 1.25rem;
	}
</style>
