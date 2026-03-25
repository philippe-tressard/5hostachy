<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth as authApi, ApiError } from '$lib/api';
	import { getSiteNom } from '$lib/stores/pageConfig';
	import Icon from '$lib/components/Icon.svelte';
	import PasswordStrength from '$lib/components/PasswordStrength.svelte';

	const _siteNom = getSiteNom();

	let nom = '';
	let prenom = '';
	let email = '';
	let telephone = '';
	let societe = '';
	let fonction = '';
	let password = '';
	let nom_proprietaire = '';
	let statut = 'copropriétaire_résident';
	let batiment_id: number | null = null;
	let batiments: { id: number; numero: string }[] = [];
	let consentement_rgpd = false;
	let consentement_communications = false;
	let showPassword = false;
	let capsLockOn = false;
	let error = '';

	function checkCapsLock(e: KeyboardEvent) {
		capsLockOn = e.getModifierState('CapsLock');
	}
	let success = false;
	let loading = false;

	const statuts = [
		{ value: 'copropriétaire_résident', label: 'Copropriétaire résident' },
		{ value: 'copropriétaire_bailleur', label: 'Copropriétaire bailleur' },
		{ value: 'locataire', label: 'Locataire' },
		{ value: 'syndic', label: 'Syndic' },
		{ value: 'mandataire', label: 'Mandataire' },
	];

	$: isProfessional = statut === 'syndic' || statut === 'mandataire';
	$: isLocataire = statut === 'locataire';
	$: showBatiment = batiments.length > 0 && !isProfessional;

	onMount(async () => {
		try {
			batiments = await authApi.batiments();
		} catch {
			// pas bloquant
		}
	});

	async function submit() {
		if (!consentement_rgpd) {
			error = 'Vous devez accepter la politique de confidentialité pour continuer.';
			return;
		}
		error = '';
		loading = true;
		try {
			await authApi.register({ nom, prenom, email, telephone, societe: societe || null, fonction: fonction || null, password, statut, batiment_id: showBatiment ? batiment_id : null, consentement_rgpd, consentement_communications, nom_proprietaire: isLocataire ? nom_proprietaire : null });
			success = true;
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Erreur lors de la création du compte';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head><title>Créer un compte — {_siteNom}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card card">
		<div class="auth-header">
			<span class="auth-logo">&#x1F3E2;</span>
			<h1>Créer un compte</h1>
				<p>{_siteNom}</p>
		</div>

		{#if success}
			<div class="alert alert-success">
				<strong>Demande envoyée !</strong><br />
				Votre compte est en attente de validation par le conseil syndical.
				Vous recevrez un email dès qu'il sera activé.
			</div>
			<div class="btn-wrapper">
				<a href="/auth/connexion" class="btn btn-outline">Retour à la connexion</a>
			</div>
		{:else}
			{#if error}
				<div class="alert alert-error">{error}</div>
			{/if}

			<form on:submit|preventDefault={submit}>
				<div class="field-row">
					<div class="field">
						<label for="prenom">Prénom *</label>
						<input id="prenom" type="text" bind:value={prenom} required />
					</div>
					<div class="field">
					<label for="nom">NOM *</label>
					<input id="nom" type="text" bind:value={nom} required
						style="text-transform:uppercase"
						on:input={() => nom = nom.toUpperCase()} />
					</div>
				</div>

				<div class="field">
					<label for="email">Email *</label>
					<input id="email" type="email" bind:value={email} required autocomplete="email" />
				</div>

				<div class="field">
					<label for="telephone">Téléphone</label>
					<input id="telephone" type="tel" bind:value={telephone} />
				</div>

				<div class="field">
					<label for="statut">Profil d'utilisateur *</label>
					<select id="statut" bind:value={statut} required>
						{#each statuts as s}
							<option value={s.value}>{s.label}</option>
						{/each}
					</select>
				</div>

				{#if isProfessional}
				<div class="field">
					<label for="societe">Société *</label>
					<input id="societe" type="text" bind:value={societe} required placeholder="Cabinet de gestion, agence…" />
				</div>
				<div class="field">
					<label for="fonction">Fonction *</label>
					<input id="fonction" type="text" bind:value={fonction} required placeholder="Gestionnaire, Mandataire…" />
				</div>
				{/if}

				{#if isLocataire}
				<div class="field">
					<label for="nom-proprietaire">Nom du propriétaire *</label>
					<input id="nom-proprietaire" type="text" bind:value={nom_proprietaire} required placeholder="Nom du propriétaire bailleur" />
					<p class="field-hint">Permet au conseil syndical de rattacher votre compte au bon lot.</p>
				</div>
				{/if}

				{#if showBatiment}
				<div class="field">
					<label for="batiment">Bâtiment *</label>
					<select id="batiment" bind:value={batiment_id} required>
						<option value={null}>-- Sélectionnez votre bâtiment --</option>
						{#each batiments as b}
							<option value={b.id}>Bâtiment {b.numero}</option>
						{/each}
					</select>
				</div>
				{/if}

				<div class="field">
					<label for="password">Mot de passe *</label>
					<div class="input-eye">
						<input id="password" type={showPassword ? 'text' : 'password'} bind:value={password} required minlength="8" autocomplete="new-password"
							on:keydown={checkCapsLock} on:keyup={checkCapsLock} on:focus={checkCapsLock} />
						<button type="button" class="eye-btn" on:click={() => showPassword = !showPassword} aria-label={showPassword ? 'Masquer' : 'Afficher'}>
							<Icon name={showPassword ? 'eye-off' : 'eye'} size={18} />
						</button>
					</div>
					<PasswordStrength {password} />
					{#if capsLockOn && !showPassword}
						<div class="capslock-warn" role="alert">⚠️ <strong>Verr. Maj. activée</strong> — votre mot de passe pourrait être incorrect.</div>
					{/if}
				</div>

				<div class="rgpd-box">
					<p class="rgpd-info">
						<strong>Responsable du traitement :</strong> Admin de 5Hostachy (CS de la copropriété).<br />
						<strong>Finalité :</strong> Gestion de la copropriété (Art. 6.1.b RGPD).<br />
						<strong>Conservation :</strong> Durée de résidence + 3 ans.<br />
						<a href="/politique-de-confidentialite" target="_blank" rel="noopener">Voir la politique complète</a> · <a href="/mentions-legales" target="_blank" rel="noopener">Mentions légales</a>
					</p>

					<label class="checkbox-field">
						<input type="checkbox" bind:checked={consentement_rgpd} required />
						J'ai lu et j'accepte la <a href="/politique-de-confidentialite" target="_blank" rel="noopener" on:click|stopPropagation>politique de confidentialité</a>*
					</label>

					<label class="checkbox-field">
						<input type="checkbox" bind:checked={consentement_communications} />
						J'accepte de recevoir les notifications de l'application par e-mail (optionnel).
					</label>
				</div>

				<div class="btn-wrapper">
				<button class="btn btn-primary" type="submit" disabled={loading}>
					{loading ? 'Création…' : 'Créer mon compte'}
				</button>
				</div>
			</form>

			<div class="auth-links">
				Déjà un compte ? <a href="/auth/connexion">Se connecter</a>
			</div>
		{/if}
	</div>
</div>

<style>
	.auth-page {
		min-height: 100vh;
		display: flex;
		align-items: flex-start;
		justify-content: center;
		background: var(--color-bg);
		padding: 2rem 1rem;
	}

	.auth-card {
		width: 100%;
		max-width: 480px;
		padding: 2rem;
	}

	.auth-header {
		text-align: center;
		margin-bottom: 1.5rem;
	}

	.auth-logo { font-size: 2rem; display: block; margin-bottom: .4rem; }
	.auth-header h1 { font-size: 1.4rem; font-weight: 700; color: var(--color-primary); }
	.auth-header p  { color: var(--color-text-muted); font-size: .875rem; }

	.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }

	.rgpd-box {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: .75rem;
		margin-bottom: 1rem;
	}

	.rgpd-info { font-size: .78rem; color: var(--color-text-muted); margin-bottom: .5rem; line-height: 1.5; }

	.checkbox-field {
		display: flex;
		align-items: flex-start;
		gap: .5rem;
		font-size: .85rem;
		margin-top: .4rem;
		line-height: 1.4;
		cursor: pointer;
	}

	.field-hint {
		font-size: .78rem;
		color: var(--color-text-muted);
		margin-top: .25rem;
	}

	.auth-links {
		text-align: center;
		margin-top: 1rem;
		font-size: .875rem;
		color: var(--color-text-muted);
	}

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
		margin-bottom: .25rem;
	}
	.btn-wrapper .btn {
		padding-left: 2.5rem;
		padding-right: 2.5rem;
	}
</style>
