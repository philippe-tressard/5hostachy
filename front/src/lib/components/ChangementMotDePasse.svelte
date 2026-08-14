<!--
  Changer son mot de passe — extrait de `routes/(app)/profil/+page.svelte` le
  14/08/2026, au fil de l'eau : la page dépassait 800 lignes et le contrôle de
  modularité refuse qu'un fichier déjà au-dessus de 500 grossisse (rang 1 §4).

  C'est le bloc le plus autonome de cette page : trois champs, un appel, aucun
  état partagé avec le reste du profil. Il ne reçoit aucune prop — il n'a besoin
  de rien de son parent, et c'est précisément ce qui le rendait extractible.
-->
<script lang="ts">
	import Icon from './Icon.svelte';
	import PasswordStrength from './PasswordStrength.svelte';
	import { auth as authApi, ApiError } from '$lib/api';
	import { toast } from './Toast.svelte';

	let pwdActuel = '';
	let pwdNouv = '';
	let pwdConf = '';
	let savingPwd = false;
	let showPwdActuel = false;
	let showPwdNouv = false;
	let showPwdConf = false;

	async function changePassword() {
		if (pwdNouv !== pwdConf) { toast('error', 'Les mots de passe ne correspondent pas'); return; }
		savingPwd = true;
		try {
			await authApi.changePassword({ mot_de_passe_actuel: pwdActuel, nouveau_mot_de_passe: pwdNouv });
			pwdActuel = ''; pwdNouv = ''; pwdConf = '';
			toast('success', 'Mot de passe modifié');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingPwd = false;
		}
	}
</script>

	<section class="card" style="margin-bottom:1.5rem">
		<h2 class="section-title">Modifier le mot de passe</h2>
		<form on:submit|preventDefault={changePassword}>
			<div class="field">
				<label for="pwd-actuel">Mot de passe actuel *</label>
				<div class="input-eye">
					<input id="pwd-actuel" type={showPwdActuel ? 'text' : 'password'} bind:value={pwdActuel} required autocomplete="current-password" />
					<button type="button" class="eye-btn" on:click={() => showPwdActuel = !showPwdActuel} aria-label={showPwdActuel ? 'Masquer' : 'Afficher'}><Icon name={showPwdActuel ? 'eye-off' : 'eye'} size={18} /></button>
				</div>
			</div>
			<div class="field">
				<label for="pwd-nouv">Nouveau mot de passe *</label>
				<div class="input-eye">
					<input id="pwd-nouv" type={showPwdNouv ? 'text' : 'password'} bind:value={pwdNouv} required autocomplete="new-password" minlength="8" />
					<button type="button" class="eye-btn" on:click={() => showPwdNouv = !showPwdNouv} aria-label={showPwdNouv ? 'Masquer' : 'Afficher'}><Icon name={showPwdNouv ? 'eye-off' : 'eye'} size={18} /></button>
				</div>
				<PasswordStrength password={pwdNouv} />
			</div>
			<div class="field">
				<label for="pwd-conf">Confirmation *</label>
				<div class="input-eye">
					<input id="pwd-conf" type={showPwdConf ? 'text' : 'password'} bind:value={pwdConf} required autocomplete="new-password" minlength="8" />
					<button type="button" class="eye-btn" on:click={() => showPwdConf = !showPwdConf} aria-label={showPwdConf ? 'Masquer' : 'Afficher'}><Icon name={showPwdConf ? 'eye-off' : 'eye'} size={18} /></button>
				</div>
			</div>
			<div class="form-actions">
				<button type="submit" class="btn btn-primary" disabled={savingPwd}>
					{savingPwd ? 'Modification…' : 'Modifier'}
				</button>
			</div>
		</form>
	</section>

<style>
	/*  Ces règles vivaient dans le `<style>` de la page profil et n'ont pas suivi
	    le composant lors de l'extraction (14/08/2026) : l'œil, positionné en
	    absolu par rapport à `.input-eye`, est retombé SOUS le champ au lieu de
	    tenir dedans à droite. Signalé par l'utilisateur.

	    C'est le piège propre à Svelte : les styles sont scopés au composant, donc
	    déplacer du balisage sans ses règles ne casse rien à la compilation, rien
	    aux types, rien aux tests — seulement l'affichage. `svelte-check` l'avait
	    d'ailleurs signalé côté page (« Unused CSS selector »), ce qui est le
	    même défaut vu par l'autre bout. */
	.section-title { font-size:1rem; font-weight:600; margin-bottom:1rem; }
	.form-actions { display: flex; justify-content: flex-end; margin-top: .5rem; gap: .5rem; flex-wrap: wrap; }
	.input-eye { position: relative; display: flex; align-items: center; }
	.input-eye input { flex: 1; padding-right: 2.5rem; }
	.eye-btn { position: absolute; right: .6rem; background: none; border: none; padding: 0; cursor: pointer; color: var(--color-text-muted); display: flex; align-items: center; }
	.eye-btn:hover { color: var(--color-text); }
</style>
