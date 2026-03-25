<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { sondages as sondagesApi, ApiError } from '$lib/api';
	import { currentUser, isCS, isAdmin } from '$lib/stores/auth';
	import { safeHtml } from '$lib/sanitize';
	import { toast } from '$lib/components/Toast.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';

	let sondage: any = null;
	let loading = true;
	let selectedOption: number | null = null;
	let voting = false;
	let respectEngagement = false;
	let commentaireVote = '';
	let reponseLibre = '';

	$: optionSelectionnee = sondage?.options?.find((o: any) => o.id === selectedOption);
	$: champLibreActif = !!optionSelectionnee?.champ_libre;

	// Édition
	let showEditModal = false;
	let editForm = { question: '', description: '', cloture_le: '', resultats_publics: true };
	let saving = false;
	let deleting = false;

	$: sondageId = Number($page.params.id);
	$: peutModerer = $isCS || $isAdmin;
	$: estAuteur = sondage && $currentUser?.id === sondage.auteur_id;
	$: peutGerer = estAuteur || $isAdmin;

	onMount(async () => {
		if ($currentUser?.statut === 'syndic' || $currentUser?.statut === 'mandataire') {
			toast('error', 'La rubrique Communauté n\'est pas accessible à votre profil.');
			goto('/tableau-de-bord', { replaceState: true });
			loading = false;
			return;
		}
		try { sondage = await sondagesApi.get(sondageId); }
		catch { toast('error', 'Erreur de chargement'); }
		finally { loading = false; }
	});

	$: totalVotes = sondage?.options?.reduce((sum: number, o: any) => sum + o.nb_votes, 0) ?? 0;

	function pct(nb: number) {
		if (totalVotes === 0) return 0;
		return Math.round((nb / totalVotes) * 100);
	}

	async function voter() {
		if (!selectedOption) { toast('error', 'Sélectionnez une option'); return; }
		if (champLibreActif && !reponseLibre.trim()) { toast('error', 'Merci de préciser votre réponse dans le champ prévu'); return; }
		if (!respectEngagement) { toast('error', 'Vous devez accepter la charte de respect'); return; }
		voting = true;
		try {
			await sondagesApi.voter(sondageId, selectedOption, commentaireVote.trim() || undefined, reponseLibre.trim() || undefined);
			sondage = await sondagesApi.get(sondageId);
			commentaireVote = '';
			reponseLibre = '';
			toast('success', 'Vote enregistré');
		} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
		finally { voting = false; }
	}

	async function supprimerCommentaire(commentaireId: number) {
		try {
			await sondagesApi.supprimerCommentaire(sondageId, commentaireId);
			sondage = { ...sondage, commentaires: sondage.commentaires.filter((c: any) => c.id !== commentaireId) };
			toast('info', 'Commentaire supprimé');
		} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
	}

	function openEdit() {
		editForm = {
			question: sondage.question,
			description: sondage.description ?? '',
			cloture_le: sondage.cloture_le ? sondage.cloture_le.replace('Z','').slice(0,16) : '',
			resultats_publics: sondage.resultats_publics,
		};
		showEditModal = true;
	}

	async function saveEdit() {
		saving = true;
		try {
			await sondagesApi.modifier(sondageId, {
				question: editForm.question,
				description: editForm.description || null,
				cloture_le: editForm.cloture_le ? new Date(editForm.cloture_le).toISOString() : null,
				resultats_publics: editForm.resultats_publics,
			});
			sondage = await sondagesApi.get(sondageId);
			showEditModal = false;
			toast('success', 'Sondage mis à jour');
		} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
		finally { saving = false; }
	}

	async function stopperSondage() {
		if (!confirm('Stopper ce sondage maintenant ? Les résultats seront visibles immédiatement.')) return;
		try {
			await sondagesApi.cloturer(sondageId);
			sondage = { ...sondage, cloture: true, cloture_forcee: true };
			toast('success', 'Sondage clôturé');
		} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
	}

	async function supprimerSondage() {
		if (!confirm('Supprimer définitivement ce sondage ?')) return;
		deleting = true;
		try {
			await sondagesApi.supprimer(sondageId);
			toast('success', 'Sondage supprimé');
			location.href = '/sondages';
		} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); deleting = false; }
	}

	$: peutVoter = sondage && !sondage.cloture && sondage.mon_vote === null;
	$: aVote = sondage?.mon_vote !== null && sondage?.mon_vote !== undefined;
	$: voirResultats = sondage?.resultats_publics || sondage?.cloture || aVote;
</script>

<svelte:head><title>{sondage ? sondage.question : 'Sondage'} — 5Hostachy</title></svelte:head>

<a href="/sondages" class="back-link">← Communauté</a>

{#if loading}
	<p style="color:var(--color-text-muted);margin-top:1rem">Chargement…</p>
{:else if !sondage}
	<p style="color:var(--color-danger)">Sondage introuvable.</p>
{:else}
	<div style="margin-top:1.25rem">
		<div style="display:flex;gap:.75rem;align-items:center;margin-bottom:.5rem;flex-wrap:wrap">
			{#if sondage.cloture}
				<span class="badge badge-gray">Clôturé</span>
			{:else}
				<span class="badge badge-green">Ouvert</span>
			{/if}
			{#if sondage.cloture_le}
				<small style="color:var(--color-text-muted)">
					{sondage.cloture ? 'Clôturé' : 'Clôture'} le {new Date(sondage.cloture_le).toLocaleDateString('fr-FR')}
				</small>
			{/if}
			{#if peutGerer}
				<div class="owner-actions">
					{#if !sondage.cloture}
						<button class="btn btn-outline btn-sm" on:click={openEdit}>✏️ Modifier</button>
						<button class="btn btn-outline btn-sm" style="color:#d97706;border-color:#d97706" on:click={stopperSondage}>⏹ Stopper</button>
					{/if}
					<button class="btn btn-outline btn-sm" style="color:#dc2626;border-color:#dc2626" disabled={deleting} on:click={supprimerSondage}>&#x1F5D1; Supprimer</button>
				</div>
			{/if}
		</div>

		<h1 style="font-size:1.3rem;font-weight:700;margin-bottom:.5rem">{sondage.question}</h1>
		{#if sondage.description}
			<div class="rich-content" style="color:var(--color-text-muted);margin-bottom:.75rem">{@html safeHtml(sondage.description)}</div>
		{/if}

		<div style="margin-top:1.5rem">
			{#if totalVotes > 0}
				<p style="font-size:.85rem;color:var(--color-text-muted);margin-bottom:1rem">{totalVotes} vote{totalVotes > 1 ? 's' : ''}</p>
			{/if}

			{#if peutVoter}
				<!-- Mode vote -->
				<form on:submit|preventDefault={voter}>
					{#each sondage.options as opt}
						<label class="option-label" class:selected={selectedOption === opt.id}>
							<input type="radio" name="vote" value={opt.id} bind:group={selectedOption} on:change={() => reponseLibre = ''} />
							<span>{opt.libelle}</span>
							{#if opt.champ_libre}<span class="champ-libre-badge" title="Cette option inclut un champ de précision">✏️</span>{/if}
							{#if voirResultats && sondage.resultats_publics}
								<span style="margin-left:auto;font-size:.8rem;color:var(--color-text-muted)">{opt.nb_votes} vote{opt.nb_votes !== 1 ? 's' : ''}</span>
							{/if}
						</label>
					{/each}

					<!-- Champ libre conditionnel -->
					{#if champLibreActif}
					<div class="champ-libre-box">
						<label style="display:block;font-size:.85rem;font-weight:600;margin-bottom:.3rem">
							Précisez votre réponse <span style="color:var(--color-danger)">*</span>
						</label>
						<textarea
							bind:value={reponseLibre}
							placeholder="Décrivez votre réponse…"
							rows="3"
							style="width:100%;padding:.5rem .75rem;border:1px solid var(--color-primary);border-radius:var(--radius);font-size:.875rem;resize:vertical"
						></textarea>
					</div>
					{/if}

					<!-- Commentaire optionnel -->
					<div style="margin-top:1rem">
						<label style="display:block;font-size:.85rem;font-weight:500;margin-bottom:.3rem">
							Commentaire <span style="color:var(--color-text-muted);font-weight:400">(optionnel)</span>
						</label>
						<textarea
							bind:value={commentaireVote}
							placeholder="Partagez votre point de vue…"
							rows="3"
							style="width:100%;padding:.5rem .75rem;border:1px solid var(--color-border);border-radius:var(--radius);font-size:.875rem;resize:vertical"
						></textarea>
					</div>

					<!-- Charte de respect -->
					<label class="respect-pledge">
						<input type="checkbox" bind:checked={respectEngagement} />
						<span>
							Je m'engage à rester respectueux envers tous les membres de la résidence.
							Tout propos irrespectueux pourra entraîner la suppression du commentaire et la suspension de mon compte.
						</span>
					</label>

					<button class="btn btn-primary" style="margin-top:1rem" disabled={voting || !selectedOption || !respectEngagement || (champLibreActif && !reponseLibre.trim())}>
						{voting ? 'Envoi…' : 'Voter'}
					</button>
				</form>
			{:else}
				<!-- Mode résultats -->
				{#each sondage.options as opt}
					<div class="result-row" class:winner={opt.id === sondage.mon_vote}>
						<div class="result-label">
							{opt.libelle}
							{#if opt.champ_libre}<span class="champ-libre-badge" title="Champ de précision">✏️</span>{/if}
							{#if opt.id === sondage.mon_vote}<span class="badge badge-blue" style="margin-left:.5rem">Mon vote ✓</span>{/if}
						</div>
						<div class="result-bar-wrap">
							<div class="result-bar" style="width:{pct(opt.nb_votes)}%"></div>
						</div>
						<div class="result-pct">{pct(opt.nb_votes)} %</div>
						<div class="result-votes">{opt.nb_votes}</div>
					</div>
					{#if opt.champ_libre && opt.reponses_libres?.length > 0}
					<div class="reponses-libres-list">
						{#each opt.reponses_libres as rep}
						<blockquote class="reponse-libre-item">«&nbsp;{rep}&nbsp;»</blockquote>
						{/each}
					</div>
					{/if}
				{/each}
			{/if}
		</div>

		<!-- ── Section commentaires ── -->
		<div class="comments-section">
			<h2 class="comments-title">&#x1F4AC; Commentaires ({(sondage.commentaires ?? []).length})</h2>

			{#if (sondage.commentaires ?? []).length === 0}
				<p style="color:var(--color-text-muted);font-size:.875rem">Aucun commentaire pour l'instant.</p>
			{:else}
				{#each sondage.commentaires as c}
					<div class="comment-card">
						<div class="comment-header">
							<strong class="comment-author">{c.auteur_nom}</strong>
							<span class="comment-date">{new Date(c.cree_le).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
							{#if peutModerer || c.auteur_id === $currentUser?.id}
							<button class="btn-icon-danger" style="margin-left:auto" aria-label="Supprimer ce commentaire" title="Supprimer" on:click={() => supprimerCommentaire(c.id)}>&#x1F5D1;️</button>
							{/if}
						</div>
						<p class="comment-body">{c.contenu}</p>
					</div>
				{/each}
			{/if}
		</div>
	</div>
{/if}

<!-- Modal édition sondage -->
{#if showEditModal}
<div class="modal-overlay" on:click|self={() => showEditModal = false} role="dialog" aria-modal="true" tabindex="-1">
	<div class="modal-box card">
		<h2 style="font-size:1rem;font-weight:700;margin-bottom:1rem">Modifier le sondage</h2>
		<form on:submit|preventDefault={saveEdit}>
			<label style="display:flex;flex-direction:column;gap:.3rem;margin-bottom:.75rem">
				Question *
				<input bind:value={editForm.question} required />
			</label>
			<label for="sondage-edit-description" style="display:flex;flex-direction:column;gap:.3rem;margin-bottom:.75rem">
				Description
				<RichEditor id="sondage-edit-description" bind:value={editForm.description} placeholder="Description du sondage…" minHeight="80px" />
			</label>
			<label style="display:flex;flex-direction:column;gap:.3rem;margin-bottom:.75rem">
				Date de clôture
				<input type="datetime-local" bind:value={editForm.cloture_le} />
			</label>
			<label style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem;cursor:pointer">
				<input type="checkbox" bind:checked={editForm.resultats_publics} />
				Résultats visibles avant clôture
			</label>
			<div style="display:flex;gap:.5rem;justify-content:flex-end">
				<button type="button" class="btn btn-outline" on:click={() => showEditModal = false}>Annuler</button>
				<button type="submit" class="btn btn-primary" disabled={saving}>{saving ? 'Sauvegarde…' : 'Enregistrer'}</button>
			</div>
		</form>
	</div>
</div>
{/if}

<style>
	.back-link { display: inline-flex; align-items: center; gap: .3rem; font-size: .85rem; color: var(--color-text-muted); text-decoration: none; margin-bottom: .75rem; }
	.back-link:hover { color: var(--color-primary); }
	.option-label {
		display: flex; align-items: center; gap: .75rem; padding: .75rem 1rem;
		border: 1px solid var(--color-border); border-radius: var(--radius);
		margin-bottom: .5rem; cursor: pointer; transition: border-color .12s;
	}
	.option-label:hover { border-color: var(--color-primary); }
	.option-label.selected { border-color: var(--color-primary); background: var(--color-primary-light); }
	.option-label input { accent-color: var(--color-primary); }
	.result-row { display: flex; align-items: center; gap: .75rem; margin-bottom: .6rem; }
	.result-label { min-width: 10rem; font-size: .9rem; }
	.result-bar-wrap { flex: 1; height: .7rem; background: var(--color-bg); border-radius: 99px; overflow: hidden; border: 1px solid var(--color-border); }
	.result-bar { height: 100%; background: var(--color-primary); border-radius: 99px; transition: width .3s; }
	.result-pct { min-width: 3rem; text-align: right; font-size: .85rem; font-weight: 600; }
	.result-votes { min-width: 3rem; text-align: right; font-size: .8rem; color: var(--color-text-muted); }
	.winner .result-bar { background: var(--color-success, #22c55e); }

	/* Charte de respect */
	.respect-pledge {
		display: flex; align-items: flex-start; gap: .6rem;
		margin-top: .85rem; padding: .75rem 1rem;
		background: #FDF3E0; border: 1px solid #E8C87A; border-radius: var(--radius);
		font-size: .82rem; color: #7a5a1a; cursor: pointer; line-height: 1.45;
	}
	.respect-pledge input { margin-top: .15rem; flex-shrink: 0; accent-color: var(--color-accent); }

	/* Champ libre */
	.champ-libre-badge { font-size: .8rem; margin-left: .35rem; }
	.champ-libre-box {
		margin-top: .75rem; padding: .75rem 1rem;
		border: 1px solid var(--color-primary); border-radius: var(--radius);
		background: var(--color-primary-light, #eff6ff);
	}

	/* Réponses libres dans les résultats */
	.reponses-libres-list { padding: .35rem 0 .6rem 1rem; }
	.reponse-libre-item {
		margin: .25rem 0; padding: .3rem .6rem;
		border-left: 3px solid var(--color-primary); font-size: .82rem;
		color: var(--color-text-muted); font-style: italic;
	}

	/* Commentaires */
	.comments-section { margin-top: 2rem; border-top: 1px solid var(--color-border); padding-top: 1.25rem; }
	.comments-title { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }
	.comment-card {
		padding: .75rem 1rem; border: 1px solid var(--color-border);
		border-radius: var(--radius); margin-bottom: .6rem; background: var(--color-surface);
	}
	.comment-header { display: flex; align-items: center; gap: .5rem; margin-bottom: .3rem; flex-wrap: wrap; }
	.comment-author { font-size: .875rem; }
	.comment-date { font-size: .78rem; color: var(--color-text-muted); }

	.comment-body { font-size: .875rem; color: var(--color-text); white-space: pre-wrap; }

	/* Actions propriétaire */
	.owner-actions { display: flex; gap: .4rem; flex-wrap: wrap; margin-left: auto; }

	/* Modal */
	.modal-overlay {
		position: fixed; top: 0; right: 0; bottom: 0; left: 0; background: rgba(0,0,0,.45); z-index: 50;
		display: flex; align-items: center; justify-content: center; padding: 1rem;
	}
	.modal-box { max-width: 30rem; width: 100%; padding: 1.5rem; }
	.modal-box input, .modal-box textarea {
		padding: .45rem .6rem; border: 1px solid var(--color-border); border-radius: var(--radius);
		font-size: .9rem; background: var(--color-bg); width: 100%;
	}
</style>
