<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth as authApi, ApiError } from '$lib/api';
	import { setUser } from '$lib/stores/auth';
	import { loadSiteConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import Icon from '$lib/components/Icon.svelte';

	onMount(() => { loadSiteConfig(); });

	$: _siteNom       = $siteNomStore;
	$: brandIcon      = $configStore['site_icone'] ?? 'building-2';
	$: loginSousTitre = $configStore['login_sous_titre'] ?? 'Votre espace numérique de résidence';

	let email = '';
	let password = '';
	let showPassword = false;
	let capsLockOn = false;
	let error = '';
	let loading = false;

	function checkCapsLock(e: KeyboardEvent) {
		capsLockOn = e.getModifierState('CapsLock');
	}

	async function submit() {
		error = '';
		loading = true;
		try {
			const user = await authApi.login(email, password);
			setUser(user);
			goto('/tableau-de-bord');
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Erreur de connexion';
		} finally {
			loading = false;
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
			<div class="alert alert-error">{error}</div>
		{/if}

		<form on:submit|preventDefault={submit}>
			<div class="field">
				<label for="email">Email *</label>
				<input id="email" type="email" bind:value={email} required autocomplete="email" />
			</div>

			<div class="field">
				<label for="password">Mot de passe *</label>
				<div class="input-eye">
					<input
						id="password"
						type={showPassword ? 'text' : 'password'}
						bind:value={password}
						required
						autocomplete="current-password"
						on:keydown={checkCapsLock}
						on:keyup={checkCapsLock}
						on:focus={checkCapsLock}
					/>
					<button type="button" class="eye-btn" on:click={() => showPassword = !showPassword} aria-label={showPassword ? 'Masquer' : 'Afficher'}>
						<Icon name={showPassword ? 'eye-off' : 'eye'} size={18} />
					</button>
				</div>
				{#if capsLockOn && !showPassword}
					<div class="capslock-warn" role="alert">⚠️ <strong>Verr. Maj. activée</strong> — votre mot de passe pourrait être incorrect.</div>
				{/if}
			</div>

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
	.auth-page {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--color-bg);
		padding: 1rem;
	}

	.auth-card {
		width: 100%;
		max-width: 400px;
		padding: 2rem;
	}

	.auth-header {
		text-align: center;
		margin-bottom: 1.5rem;
	}

	.auth-logo { font-size: 2.5rem; display: block; margin-bottom: .5rem; }

	.auth-header h1 {
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--color-primary);
		margin-bottom: .3rem;
	}

	.auth-header p { color: var(--color-text-muted); font-size: .875rem; }

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
		border: 1px solid #fcd34d;
		border-radius: var(--radius);
		font-size: .8rem;
		color: #92400e;
		line-height: 1.4;
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
		gap: .5rem;
		margin-top: 1rem;
		font-size: .875rem;
	}

	.auth-legal {
		display: flex;
		justify-content: center;
		gap: .5rem;
		margin-top: 1.25rem;
		font-size: .75rem;
		color: var(--color-text-muted);
	}
</style>
