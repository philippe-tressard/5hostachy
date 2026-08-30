<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { sondages as sondagesApi, signalements as signalementsApi, ApiError } from '$lib/api';
	import { currentUser, isCS, isAdmin } from '$lib/stores/auth';
	import { safeHtml } from '$lib/sanitize';
	import { toast } from '$lib/components/Toast.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import FilAriane from '$lib/components/FilAriane.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import Reponses from '$lib/components/Reponses.svelte';
	import { fmtDateShort } from '$lib/date';

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
	//  `options` ne porte que l'`id` et le LIBELLÉ : le serveur n'accepte rien
	//  d'autre, et c'est ce qui rend l'ajout et le retrait impossibles par
	//  construction plutôt que par un contrôle qu'on pourrait oublier (#467).
	let editForm: {
		question: string;
		description: string;
		cloture_le: string;
		resultats_publics: boolean;
		options: { id: number; libelle: string }[];
	} = { question: '', description: '', cloture_le: '', resultats_publics: true, options: [] };
	let saving = false;
	let deleting = false;

	$: sondageId = Number($page.params.id);
	$: peutModerer = $isCS || $isAdmin;
	$: estAuteur = sondage && $currentUser?.id === sondage.auteur_id;
	$: peutGerer = estAuteur || $isAdmin;

	onMount(async () => {
		if ($currentUser?.statut === 'syndic' || $currentUser?.statut === 'mandataire') {
			//  Le motif vient de l'API : cet écran ne réécrit pas la règle
			//  d'accès à la Communauté (29/08/2026).
			toast(
				'error',
				$currentUser.communaute_motif_refus ??
					"La rubrique Communauté n'est pas accessible à votre profil.",
			);
			goto('/tableau-de-bord', { replaceState: true });
			loading = false;
			return;
		}
		try {
			sondage = await sondagesApi.get(sondageId);
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	//  `nb_votes` est ABSENT quand les résultats sont masqués (l'API ne l'envoie
	//  pas, plutôt que d'envoyer 0 qui se lirait « personne n'a voté ») : sans ce
	//  repli la somme vaudrait NaN et les pourcentages aussi.
	$: totalVotes =
		sondage?.options?.reduce((sum: number, o: any) => sum + (o.nb_votes ?? 0), 0) ?? 0;

	function pct(nb: number) {
		if (totalVotes === 0) return 0;
		return Math.round((nb / totalVotes) * 100);
	}

	async function voter() {
		if (!selectedOption) {
			toast('error', 'Sélectionnez une option');
			return;
		}
		if (champLibreActif && !reponseLibre.trim()) {
			toast('error', 'Merci de préciser votre réponse dans le champ prévu');
			return;
		}
		if (!respectEngagement) {
			toast('error', 'Vous devez accepter la charte de respect');
			return;
		}
		voting = true;
		try {
			await sondagesApi.voter(
				sondageId,
				selectedOption,
				commentaireVote.trim() || undefined,
				reponseLibre.trim() || undefined,
			);
			sondage = await sondagesApi.get(sondageId);
			commentaireVote = '';
			reponseLibre = '';
			toast('success', 'Vote enregistré');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			voting = false;
		}
	}

	async function supprimerCommentaire(commentaireId: number) {
		try {
			await sondagesApi.supprimerCommentaire(sondageId, commentaireId);
			sondage = {
				...sondage,
				commentaires: sondage.commentaires.filter((c: any) => c.id !== commentaireId),
			};
			toast('info', 'Commentaire supprimé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function repondreSondage(contenu: string) {
		try {
			await sondagesApi.commenter(sondageId, contenu);
			sondage = await sondagesApi.get(sondageId);
			toast('success', 'Commentaire publié');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
			throw e;
		}
	}

	async function signalerDetail(cibleType: string, cibleId: number) {
		const motif = prompt('Pourquoi signalez-vous ce contenu au conseil syndical ?');
		if (motif === null) return;
		if (!motif.trim()) {
			toast('error', 'Le motif est obligatoire');
			return;
		}
		try {
			await signalementsApi.creer(cibleType, cibleId, motif.trim());
			toast('success', 'Signalement transmis au conseil syndical');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	function openEdit() {
		editForm = {
			question: sondage.question,
			description: sondage.description ?? '',
			cloture_le: sondage.cloture_le ? sondage.cloture_le.replace('Z', '').slice(0, 16) : '',
			resultats_publics: sondage.resultats_publics,
			options: (sondage.options ?? []).map((o: any) => ({ id: o.id, libelle: o.libelle })),
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
				options: editForm.options,
			});
			sondage = await sondagesApi.get(sondageId);
			showEditModal = false;
			toast('success', 'Sondage mis à jour');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			saving = false;
		}
	}

	async function stopperSondage() {
		if (!confirm('Stopper ce sondage maintenant ? Les résultats seront visibles immédiatement.'))
			return;
		try {
			await sondagesApi.cloturer(sondageId);
			sondage = { ...sondage, cloture: true, cloture_forcee: true };
			toast('success', 'Sondage clôturé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function supprimerSondage() {
		if (!confirm('Supprimer définitivement ce sondage ?')) return;
		deleting = true;
		try {
			await sondagesApi.supprimer(sondageId);
			toast('success', 'Sondage supprimé');
			location.href = '/sondages';
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
			deleting = false;
		}
	}

	$: peutVoter = sondage && !sondage.cloture && sondage.mon_vote === null;
	//  Décision prise par l'API, pas recomposée ici. Cette ligne valait
	//  `resultats_publics || cloture || aVote` — et cinquante lignes plus bas un
	//  second `&& sondage.resultats_publics` écrasait le tout, rendant les deux
	//  dernières branches mortes : un sondage à case décochée ne montrait JAMAIS
	//  ses résultats, pas même une fois clôturé (#397).
	$: voirResultats = sondage?.resultats_visibles ?? false;
</script>

<svelte:head><title>{sondage ? sondage.question : 'Sondage'} — 5Hostachy</title></svelte:head>

<FilAriane
	segments={[{ libelle: 'Communauté', href: '/sondages' }]}
	courant={sondage?.question ?? 'Sondage'}
/>

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
					{sondage.cloture ? 'Clôturé' : 'Clôture'} le {fmtDateShort(sondage.cloture_le)}
				</small>
			{/if}
			{#if peutGerer}
				<div class="owner-actions">
					{#if !sondage.cloture}
						<button class="btn btn-outline btn-sm" on:click={openEdit}>✏️ Modifier</button>
						<button
							class="btn btn-outline btn-sm"
							style="color:#d97706;border-color:#d97706"
							on:click={stopperSondage}>⏹ Stopper</button
						>
					{/if}
					<button
						class="btn btn-outline btn-sm"
						style="color:#dc2626;border-color:#dc2626"
						disabled={deleting}
						on:click={supprimerSondage}>&#x1F5D1; Supprimer</button
					>
				</div>
			{/if}
		</div>

		<h1 style="font-size:1.3rem;font-weight:700;margin-bottom:.5rem">{sondage.question}</h1>
		{#if sondage.description}
			<div class="rich-content" style="color:var(--color-text-muted);margin-bottom:.75rem">
				{@html safeHtml(sondage.description)}
			</div>
		{/if}

		<div style="margin-top:1.5rem">
			{#if totalVotes > 0}
				<p style="font-size:.85rem;color:var(--color-text-muted);margin-bottom:1rem">
					{totalVotes} vote{totalVotes > 1 ? 's' : ''}
				</p>
			{/if}

			{#if peutVoter}
				<!-- Mode vote -->
				<form on:submit|preventDefault={voter}>
					{#each sondage.options as opt (opt.id)}
						<label class="option-label" class:selected={selectedOption === opt.id}>
							<input
								type="radio"
								name="vote"
								value={opt.id}
								bind:group={selectedOption}
								on:change={() => (reponseLibre = '')}
							/>
							<span>{opt.libelle}</span>
							{#if opt.champ_libre}<span
									class="champ-libre-badge"
									title="Cette réponse inclut un champ de précision">✏️</span
								>{/if}
							{#if voirResultats}
								<span style="margin-left:auto;font-size:.8rem;color:var(--color-text-muted)"
									>{opt.nb_votes} vote{opt.nb_votes !== 1 ? 's' : ''}</span
								>
							{/if}
						</label>
					{/each}

					<!-- Champ libre conditionnel -->
					{#if champLibreActif}
						<!--  `.field` exigé par `lint:champs` dès le libellé associé (#561). -->
						<div class="champ-libre-box">
							<div class="field">
								<label for="sondage-reponse-libre" style="font-weight:600">
									Précisez votre réponse <span style="color:var(--color-danger)">*</span>
								</label>
								<textarea
									id="sondage-reponse-libre"
									bind:value={reponseLibre}
									placeholder="Décrivez votre réponse…"
									rows="3"
									style="border-color:var(--color-primary);resize:vertical"></textarea>
							</div>
						</div>
					{/if}

					<!-- Commentaire optionnel -->
					<div class="field" style="margin-top:1rem">
						<label for="sondage-commentaire-vote">Commentaire</label>
						<textarea
							id="sondage-commentaire-vote"
							bind:value={commentaireVote}
							placeholder="Partagez votre point de vue…"
							rows="3"
							style="resize:vertical"></textarea>
					</div>

					<!-- Charte de respect -->
					<label class="respect-pledge">
						<input type="checkbox" bind:checked={respectEngagement} />
						<span>
							Je m'engage à rester respectueux envers tous les membres de la résidence. Tout propos
							irrespectueux pourra entraîner la suppression du commentaire et la suspension de mon
							compte.
						</span>
					</label>

					<button
						class="btn btn-primary"
						style="margin-top:1rem"
						disabled={voting ||
							!selectedOption ||
							!respectEngagement ||
							(champLibreActif && !reponseLibre.trim())}
					>
						{voting ? 'Envoi…' : 'Voter'}
					</button>
				</form>
			{:else if !voirResultats}
				<!--  A voté (ou ne peut plus voter) mais les résultats sont masqués
				      jusqu'à la clôture. Le dire, plutôt que d'afficher des barres
				      vides : l'API n'envoie pas les décomptes dans ce cas, et un
				      « 0 vote » se lirait comme « personne n'a voté ». -->
				<p class="resultats-masques">
					Les résultats de ce sondage ne seront visibles qu'après sa clôture.
				</p>
			{:else}
				<!-- Mode résultats -->
				{#each sondage.options as opt (opt.id)}
					<div class="result-row" class:winner={opt.id === sondage.mon_vote}>
						<div class="result-label">
							{opt.libelle}
							{#if opt.champ_libre}<span class="champ-libre-badge" title="Champ de précision"
									>✏️</span
								>{/if}
							{#if opt.id === sondage.mon_vote}<span
									class="badge badge-blue"
									style="margin-left:.5rem">Mon vote ✓</span
								>{/if}
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
			<Reponses
				reponses={sondage.commentaires ?? []}
				currentUserId={$currentUser?.id}
				isCS={peutModerer}
				placeholder="Votre commentaire sur ce sondage…"
				expanded={true}
				onSubmit={repondreSondage}
				onDelete={supprimerCommentaire}
				onReport={(rid) => signalerDetail('commentaire', rid)}
			/>
		</div>
	</div>
{/if}

<!-- Modal édition sondage -->
{#if showEditModal}
	<FormulaireCreation titre="Modifier le sondage">
		<form on:submit|preventDefault={saveEdit}>
			<label class="field">
				Question *
				<input bind:value={editForm.question} required />
			</label>
			<label
				for="sondage-edit-description"
				style="display:flex;flex-direction:column;gap:.3rem;margin-bottom:.75rem"
			>
				Description
				<RichEditor
					id="sondage-edit-description"
					bind:value={editForm.description}
					placeholder="Description du sondage…"
					minHeight="80px"
				/>
			</label>
			<!--  Les RÉPONSES : leur libellé se corrige, la liste ne bouge pas.
			      Ni ajout ni retrait — un vote déjà exprimé sur une option retirée n'a
			      pas de repli honnête : le compter ailleurs fausse le résultat, le
			      supprimer efface l'expression de quelqu'un sans le lui dire (#467).
			      L'interface dit donc EXACTEMENT ce que le serveur accepte : pas de
			      bouton « + », pas de croix, et l'ordre ne se change pas non plus. -->
			{#if editForm.options.length}
				<div class="field">
					<span class="champ-titre">Réponses possibles</span>
					{#each editForm.options as opt, i (opt.id)}
						<input
							class="reponse-saisie"
							bind:value={editForm.options[i].libelle}
							aria-label="Libellé de la réponse {i + 1}"
							required
						/>
					{/each}
					<p class="aide-reponses">
						Seul le <strong>texte</strong> se corrige. Ajouter ou retirer une réponse invaliderait les
						votes déjà exprimés : il faudrait alors créer un nouveau sondage.
					</p>
				</div>
			{/if}

			<label class="field">
				Date de clôture
				<input type="datetime-local" bind:value={editForm.cloture_le} />
			</label>
			<p class="aide-reponses">
				Elle peut être <strong>reculée</strong>, jamais avancée une fois qu'un vote a été exprimé —
				raccourcir priverait de leur voix ceux qui n'ont pas encore voté.
			</p>
			<label style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem;cursor:pointer">
				<input type="checkbox" bind:checked={editForm.resultats_publics} />
				Afficher les résultats avant la clôture
			</label>
			<p style="margin:-.6rem 0 1rem 1.6rem;font-size:.8rem;color:var(--color-text-muted)">
				Ils seront lus par les destinataires du sondage. Sinon, ils n'apparaissent qu'une fois le
				sondage clôturé.
			</p>
			<div style="display:flex;gap:.5rem;justify-content:flex-end">
				<button type="button" class="btn btn-outline" on:click={() => (showEditModal = false)}
					>Annuler</button
				>
				<button type="submit" class="btn btn-primary" disabled={saving}
					>{saving ? 'Sauvegarde…' : 'Enregistrer'}</button
				>
			</div>
		</form>
	</FormulaireCreation>
{/if}

<style>
	/*  Saisie des libellés de réponse dans la modale d'édition (#467). */
	.champ-titre {
		display: block;
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--color-text);
		margin-bottom: 0.3rem;
	}
	.reponse-saisie {
		width: 100%;
		margin-bottom: 0.35rem;
	}
	.aide-reponses {
		margin: 0.1rem 0 1rem;
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}
	/*  `.back-link` est parti dans `FilAriane` (#365). Il disait « Communauté »
	    ici et « Retour aux tickets » sur la fiche de ticket : deux pages du même
	    site, deux conventions, aucune ne nommant la rubrique. */
	.option-label {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		margin-bottom: 0.5rem;
		cursor: pointer;
		transition: border-color 0.12s;
	}
	.option-label:hover {
		border-color: var(--color-primary);
	}
	.option-label.selected {
		border-color: var(--color-primary);
		background: var(--color-primary-light);
	}
	.option-label input {
		accent-color: var(--color-primary);
	}
	.result-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.6rem;
	}
	.result-label {
		min-width: 10rem;
		font-size: 0.9rem;
	}
	.result-bar-wrap {
		flex: 1;
		height: 0.7rem;
		background: var(--color-bg);
		border-radius: 99px;
		overflow: hidden;
		border: 1px solid var(--color-border);
	}
	.result-bar {
		height: 100%;
		background: var(--color-primary);
		border-radius: 99px;
		transition: width 0.3s;
	}
	.result-pct {
		min-width: 3rem;
		text-align: right;
		font-size: 0.85rem;
		font-weight: 600;
	}
	.result-votes {
		min-width: 3rem;
		text-align: right;
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}
	.resultats-masques {
		font-size: 0.875rem;
		color: var(--color-text-muted);
		background: var(--color-bg);
		border-radius: var(--radius);
		padding: 0.75rem 1rem;
		margin: 0;
	}
	.winner .result-bar {
		background: var(--color-success, #22c55e);
	}

	/* Charte de respect */
	.respect-pledge {
		display: flex;
		align-items: flex-start;
		gap: 0.6rem;
		margin-top: 0.85rem;
		padding: 0.75rem 1rem;
		background: #fdf3e0;
		border: 1px solid #e8c87a;
		border-radius: var(--radius);
		font-size: 0.82rem;
		color: #7a5a1a;
		cursor: pointer;
		line-height: 1.45;
	}
	.respect-pledge input {
		margin-top: 0.15rem;
		flex-shrink: 0;
		accent-color: var(--color-accent);
	}

	/* Champ libre */
	.champ-libre-badge {
		font-size: 0.8rem;
		margin-left: 0.35rem;
	}
	.champ-libre-box {
		margin-top: 0.75rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius);
		background: var(--color-primary-light, #eff6ff);
	}

	/* Réponses libres dans les résultats */
	.reponses-libres-list {
		padding: 0.35rem 0 0.6rem 1rem;
	}
	.reponse-libre-item {
		margin: 0.25rem 0;
		padding: 0.3rem 0.6rem;
		border-left: 3px solid var(--color-primary);
		font-size: 0.82rem;
		color: var(--color-text-muted);
		font-style: italic;
	}

	/* Commentaires (rendu par le composant partagé Reponses.svelte) */
	.comments-section {
		margin-top: 2rem;
		border-top: 1px solid var(--color-border);
		padding-top: 1.25rem;
	}
	.comments-title {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 1rem;
	}

	/* Actions propriétaire */
	.owner-actions {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin-left: auto;
	}

	/* Modal */
</style>
