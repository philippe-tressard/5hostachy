<script lang="ts">
	import { onMount } from 'svelte';
	import { perimetres as perimetresApi, ApiError } from '$lib/api';
	import Icon from '$lib/components/Icon.svelte';
	import { perimetresStore, rechargerPerimetres } from '$lib/stores/perimetres';
	import { ICONES_PERIMETRE, type Perimetre } from '$lib/perimetres';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import { toast } from '$lib/components/Toast.svelte';

	$: _siteNom = $siteNomStore;

	let chargement = true;
	let enregistrement = false;
	let ouvert: string | null = null;

	//  Une seule fiche ouverte à la fois — le pattern des listes du produit.
	function basculer(code: string) {
		ouvert = ouvert === code ? null : code;
	}

	onMount(async () => {
		await rechargerPerimetres();
		chargement = false;
	});

	// ── Édition ───────────────────────────────────────────────────────────────
	let edite: Perimetre | null = null;
	let form = {
		libelle: '', libelle_court: '', description: '', icone: '',
		portee_globale: false, selectionnable: true, ordre: 0, actif: true,
	};

	function editer(n: Perimetre) {
		edite = n;
		form = {
			libelle: n.libelle,
			libelle_court: n.libelle_court === n.libelle ? '' : n.libelle_court,
			description: n.description,
			icone: n.icone ?? '',
			portee_globale: n.portee_globale,
			selectionnable: n.selectionnable,
			ordre: n.ordre,
			actif: n.actif,
		};
	}

	async function enregistrer() {
		if (!edite) return;
		enregistrement = true;
		try {
			await perimetresApi.update(edite.id, {
				libelle: form.libelle,
				libelle_court: form.libelle_court || null,
				description: form.description,
				icone: form.icone || null,
				portee_globale: form.portee_globale,
				selectionnable: form.selectionnable,
				ordre: Number(form.ordre) || 0,
				actif: form.actif,
			} as any);
			await rechargerPerimetres();
			toast('success', 'Périmètre enregistré');
			edite = null;
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur à l’enregistrement');
		} finally {
			enregistrement = false;
		}
	}

	// ── Création ──────────────────────────────────────────────────────────────
	let creation: { parent: string | null } | null = null;
	let nouveau = { code: '', libelle: '', description: '' };

	function creer(parent: string | null) {
		creation = { parent };
		nouveau = { code: '', libelle: '', description: '' };
	}

	//  Le code est proposé à partir du libellé et du parent, mais reste modifiable :
	//  il est IMMUABLE après création (il est stocké dans les contenus publiés), donc
	//  c'est le seul moment où on peut le choisir.
	$: codePropose = (() => {
		if (!creation) return '';
		const slug = nouveau.libelle
			.toLowerCase()
			.normalize('NFD')
			.replace(/[̀-ͯ]/g, '')
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-|-$/g, '');
		if (!slug) return '';
		return creation.parent ? `${creation.parent}/${slug}` : slug;
	})();

	async function enregistrerNouveau() {
		enregistrement = true;
		try {
			await perimetresApi.create({
				code: (nouveau.code || codePropose).trim(),
				libelle: nouveau.libelle.trim(),
				description: nouveau.description,
				parent: creation?.parent ?? null,
			} as any);
			await rechargerPerimetres();
			toast('success', 'Périmètre créé');
			creation = null;
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur à la création');
		} finally {
			enregistrement = false;
		}
	}

	async function supprimer(n: Perimetre) {
		if (!confirm(`Supprimer définitivement « ${n.libelle} » ?`)) return;
		try {
			await perimetresApi.remove(n.id);
			await rechargerPerimetres();
			toast('success', 'Périmètre supprimé');
		} catch (e) {
			//  Le serveur refuse la suppression d'un nœud cité par un contenu et dit
			//  quoi faire à la place : on relaie son message tel quel.
			toast('error', e instanceof ApiError ? e.message : 'Suppression impossible');
		}
	}

	async function deplacer(n: Perimetre, delta: number) {
		try {
			await perimetresApi.update(n.id, { ordre: (n.ordre ?? 0) + delta } as any);
			await rechargerPerimetres();
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Déplacement impossible');
		}
	}

	$: noeuds = $perimetresStore;
</script>

<svelte:head><title>Périmètres · {_siteNom}</title></svelte:head>

<p class="page-desc">
	L’arborescence qui sert à localiser une demande — un ticket, une actualité, un
	événement. Elle est propre à cette copropriété : renommez, réorganisez, ajoutez
	ou retirez ce qui n’existe pas ici.
</p>

<div class="barre">
	<button class="btn-primary" on:click={() => creer(null)}>+ Périmètre de premier niveau</button>
</div>

{#if chargement}
	<p>Chargement…</p>
{:else if noeuds.length === 0}
	<p class="empty-state">
		Aucun périmètre. Créez-en un : tant que l’arborescence est vide, un contenu
		sans périmètre reste visible de tous.
	</p>
{:else}
	<div class="ref-list">
		{#each noeuds as n (n.code)}
			{@const deplie = ouvert === n.code}
			<div class="ref-item" class:expanded={deplie} class:inactif={!n.actif}>
				<div
					class="ref-tete"
					style="padding-left:{0.6 + n.profondeur * 1.1}rem"
					role="button"
					tabindex="0"
					on:click={() => basculer(n.code)}
					on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && basculer(n.code)}
				>
					{#if n.icone}<Icon name={n.icone} size={16} />{/if}
					<span class="ref-titre">{n.libelle}</span>
					{#if n.portee_globale}
						<span class="badge badge-blue" title="Ce périmètre porte lui-même la portée globale : visible de tous les résidents">tous</span>
					{:else if n.concerne_tous}
						<!--  Hérité d'un ancêtre. Sans cette distinction, la pastille « tous »
						      s'affichait à côté d'une case décochée — deux informations exactes
						      qui se lisent comme une contradiction (signalé le 13/08/2026). -->
						<span class="badge badge-gray" title="Hérité d’un périmètre parent — la case de ce nœud est décochée, et c’est normal">tous (hérité)</span>
					{/if}
					{#if !n.selectionnable}
						<span class="badge badge-gray" title="Non proposé à la saisie">regroupement</span>
					{/if}
					{#if !n.actif}<span class="badge badge-orange">désactivé</span>{/if}
					{#if n.utilise}
						<span class="badge badge-green" title="Cité par des contenus publiés">utilisé</span>
					{/if}
					<code class="ref-code">{n.code}</code>
					<span class="chevron" class:open={deplie}>›</span>
				</div>

				{#if deplie}
					<div class="ref-corps">
						{#if n.description}<p class="ref-desc">{n.description}</p>{/if}
						<div class="ref-actions">
							<button class="btn-icon-edit" title="Modifier" on:click={() => editer(n)}>✏️</button>
							<button class="btn-icon" title="Ajouter un sous-périmètre" on:click={() => creer(n.code)}>＋</button>
							<button class="btn-icon" title="Monter" on:click={() => deplacer(n, -1)}>▲</button>
							<button class="btn-icon" title="Descendre" on:click={() => deplacer(n, 1)}>▼</button>
							<button class="btn-icon-danger" title="Supprimer" on:click={() => supprimer(n)}>🗑️</button>
						</div>
					</div>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<!-- ── Modification ────────────────────────────────────────────────────────── -->
{#if edite}
	<!--  Pas de fermeture au clic sur le fond : on saisit ici un libellé et une
	      description, et un clic à côté effaçait tout sans prévenir. `Échap` et
	      « Annuler » suffisent, et sont des gestes voulus. -->
	<div class="modal-overlay" on:keydown={(e) => e.key === 'Escape' && (edite = null)} role="presentation">
		<div class="modal-box" role="dialog" aria-modal="true" tabindex="-1" on:keydown|stopPropagation>
			<h2>{edite.libelle}</h2>
			<p class="modal-code">
				Code <code>{edite.code}</code> — non modifiable : il est enregistré dans les
				contenus déjà publiés.
			</p>

			<label class="field">Libellé *
				<input bind:value={form.libelle} required />
			</label>
			<label class="field">Libellé court
				<input bind:value={form.libelle_court} placeholder={edite.libelle} />
				<span class="field-hint">Employé sur les pastilles étroites du calendrier.</span>
			</label>
			<div class="field">Icône
				<div class="icones">
					<button
						type="button" class="icone" class:icone-active={!form.icone}
						title="Aucune icône" on:click={() => (form.icone = '')}
					>—</button>
					{#each ICONES_PERIMETRE as ic (ic.nom)}
						<button
							type="button" class="icone" class:icone-active={form.icone === ic.nom}
							title={ic.libelle} aria-label={ic.libelle}
							on:click={() => (form.icone = ic.nom)}
						>
							<Icon name={ic.nom} size={18} />
						</button>
					{/each}
				</div>
				<span class="field-hint">
					Affichée sur la pastille du sélecteur, devant le libellé.
				</span>
			</div>

			<label class="field">Description
				<textarea bind:value={form.description} rows="4"></textarea>
				<span class="field-hint">
					Affichée sous le sélecteur, au moment où l’on choisit ce périmètre.
				</span>
			</label>
			<label class="field">Ordre
				<input type="number" bind:value={form.ordre} />
			</label>

			<label class="field-check">
				<input type="checkbox" bind:checked={form.selectionnable} />
				Proposé à la saisie
				<span class="field-hint">
					Décochez pour un regroupement, ou pour retirer un périmètre des formulaires
					sans toucher aux contenus qui le citent déjà.
				</span>
			</label>

			<label class="field-check">
				<input type="checkbox" bind:checked={form.actif} />
				Actif
			</label>

			<label class="field-check danger">
				<input type="checkbox" bind:checked={form.portee_globale} />
				Concerne tous les résidents
				{#if edite.concerne_tous && !edite.portee_globale}
					<span class="field-hint herite">
						ℹ️ Ce périmètre concerne <strong>déjà</strong> tous les résidents, par
						héritage de son parent — la case ci-dessus est décochée, et c’est normal.
						La cocher n’ajouterait rien ; la laisser décochée ne retire rien. Pour
						changer cela, il faut décocher la case du périmètre parent.
					</span>
				{/if}
				<span class="field-hint">
					⚠️ Un contenu ciblé sur ce périmètre — ou sur l’un de ses sous-périmètres —
					sera visible de <strong>tous les résidents</strong> et notifiera
					<strong>l’ensemble du conseil syndical</strong>, quel que soit leur bâtiment.
				</span>
			</label>

			<div class="modal-actions">
				<button class="btn btn-outline" on:click={() => (edite = null)}>Annuler</button>
				<button class="btn-primary" disabled={enregistrement || !form.libelle.trim()} on:click={enregistrer}>
					{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Création ────────────────────────────────────────────────────────────── -->
{#if creation}
	<div class="modal-overlay" on:keydown={(e) => e.key === 'Escape' && (creation = null)} role="presentation">
		<div class="modal-box" role="dialog" aria-modal="true" tabindex="-1" on:keydown|stopPropagation>
			<h2>{creation.parent ? `Sous-périmètre de ${creation.parent}` : 'Nouveau périmètre'}</h2>

			<label class="field">Libellé *
				<input bind:value={nouveau.libelle} required />
			</label>
			<label class="field">Code *
				<input bind:value={nouveau.code} placeholder={codePropose} />
				<span class="field-hint">
					Laissé vide, il vaudra <code>{codePropose || '…'}</code>. Il ne pourra plus
					être modifié : c’est lui qui sera enregistré dans les contenus.
				</span>
			</label>
			<label class="field">Description
				<textarea bind:value={nouveau.description} rows="3"></textarea>
			</label>

			<div class="modal-actions">
				<button class="btn btn-outline" on:click={() => (creation = null)}>Annuler</button>
				<button
					class="btn-primary"
					disabled={enregistrement || !nouveau.libelle.trim() || !(nouveau.code || codePropose)}
					on:click={enregistrerNouveau}
				>
					{enregistrement ? 'Création…' : 'Créer'}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.page-desc { color: var(--color-text-muted); margin-bottom: 1rem; }
	.barre { margin-bottom: 1rem; }
	.ref-list { border: 1px solid var(--color-border); border-radius: var(--radius); overflow: hidden; }
	.ref-item { border-bottom: 1px solid var(--color-border); background: var(--color-surface); }
	.ref-item:last-child { border-bottom: none; }
	.ref-item.inactif { opacity: .55; }
	.ref-tete { display: flex; align-items: center; gap: .5rem; padding: .55rem .8rem; cursor: pointer; }
	.ref-tete:hover { background: var(--color-bg); }
	.ref-titre { font-size: .9rem; }
	.ref-code { font-size: .72rem; color: var(--color-text-muted); margin-left: auto; }
	.chevron { transition: transform .15s; color: var(--color-text-muted); }
	.chevron.open { transform: rotate(90deg); }
	.ref-corps { padding: .2rem 1rem .8rem 1.6rem; border-top: 1px dashed var(--color-border); }
	.ref-desc { font-size: .84rem; color: var(--color-text-muted); line-height: 1.55; margin: .5rem 0; }
	.ref-actions { display: flex; gap: .3rem; }
	.icones { display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .3rem; }
	.icone { display: inline-flex; align-items: center; justify-content: center; width: 2rem; height: 2rem; border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-surface); cursor: pointer; color: var(--color-text-muted); font-size: .8rem; }
	.icone:hover { border-color: var(--color-primary); color: var(--color-text); }
	.icone-active { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
	.modal-box { background: var(--color-surface); border-radius: var(--radius); padding: 1.25rem; max-width: 560px; width: 92%; max-height: 88vh; overflow-y: auto; }
	.modal-code { font-size: .8rem; color: var(--color-text-muted); margin: -.4rem 0 1rem; }
	.field-check { display: block; font-size: .85rem; margin-bottom: .8rem; }
	.herite { border-left: 2px solid var(--color-border); padding-left: .5rem; margin-top: .4rem; }
	.field-check.danger { border-left: 3px solid var(--color-warning, #d97706); padding-left: .6rem; }
	.modal-actions { display: flex; justify-content: space-between; gap: .5rem; margin-top: 1rem; }
</style>
