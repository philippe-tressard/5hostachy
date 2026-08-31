<script lang="ts">
	/**
	 * Les lignes de la base qui référencent un parent disparu — relevé et purge.
	 *
	 * ## Pourquoi cet écran (#546)
	 *
	 * SQLite tourne ici à `foreign_keys=OFF` : aucune clé étrangère n'est
	 * vérifiée. Des suppressions incomplètes ont donc laissé des lignes
	 * orphelines — **50** au relevé du 30/08/2026. Activer les clés ne les
	 * efface pas ; il faut les compter, puis décider.
	 *
	 * ## 🔴 Pourquoi la purge n'est PAS appelable par un script
	 *
	 * Le relevé, lui, l'est : les crons d'exploitation ont une clé partagée. La
	 * purge non — un secret qui vit en clair sur deux machines n'a pas à pouvoir
	 * effacer des lignes. La personne qui décide d'une suppression irréversible
	 * est celle qui l'exécute, et c'est cet écran qui le permet.
	 *
	 * ## Le geste en deux temps, et le premier ne touche à rien
	 *
	 * « Analyser » mesure. « Purger » **simule d'abord**, montre ce qui partirait,
	 * et ne supprime qu'après une confirmation qui répète le compte. L'endpoint
	 * porte la même prudence : sans `confirmer=true`, il ne fait rien.
	 */
	import { api } from '$lib/api';
	import { confirmer } from '$lib/confirmation';
	import { toast } from '$lib/components/Toast.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';

	type Relation = { table: string; colonne: string; table_parente: string; lignes: number };
	type Releve = {
		ok: boolean;
		inconnu: boolean;
		orphelins?: number;
		par_relation?: Relation[];
		erreur?: string;
	};

	let releve: Releve | null = null;
	let enCours = false;

	async function analyser() {
		enCours = true;
		try {
			releve = await api.get<Releve>('/admin/db/cles-etrangeres');
			//  ⚠️ « n'a pas pu mesurer » n'est pas « rien à signaler ». L'API
			//  distingue les deux ; l'écran doit le dire aussi, sinon il rassure
			//  sur une mesure qui n'a pas eu lieu.
			if (releve.inconnu)
				toast('error', `Mesure impossible : ${releve.erreur ?? 'raison inconnue'}`);
		} catch (e: any) {
			releve = null;
			toast('error', e?.message ?? 'Analyse impossible');
		} finally {
			enCours = false;
		}
	}

	async function purger() {
		enCours = true;
		try {
			//  1er temps : la SIMULATION. L'endpoint ne supprime rien sans
			//  `confirmer=true` — on lui demande donc d'abord ce qui partirait.
			const simulation = await api.post<{
				seraient_supprimees?: number;
				seraient_deliees?: number;
			}>('/admin/db/purger-orphelins');
			const aSupprimer = simulation.seraient_supprimees ?? 0;
			const aDelier = simulation.seraient_deliees ?? 0;
			if (!aSupprimer && !aDelier) {
				toast('success', 'Aucune ligne orpheline à réparer.');
				await analyser();
				return;
			}
			//  2e temps : la confirmation REPÈTE les comptes — et depuis le
			//  31/08/2026 elle en annonce DEUX.
			//
			//  🔴 Elle n'en disait qu'un, et il agrégeait deux gestes de nature
			//  opposée. Le 30/08, l'écran a annoncé « 50 lignes vont être
			//  supprimées » : 49 l'ont été à juste titre, et la 50e — un membre du
			//  conseil syndical dont le compte lié avait disparu — a été détruite
			//  alors qu'il fallait seulement délier. On approuvait une destruction
			//  en croyant en approuver une autre.
			const lignes = [
				aSupprimer
					? `• ${aSupprimer} ligne(s) SUPPRIMÉE(S) : leur parent est obligatoire, elles ne peuvent pas exister sans lui.`
					: null,
				aDelier
					? `• ${aDelier} ligne(s) CONSERVÉE(S), lien mis à vide : le parent était facultatif, c'est la référence qui est cassée.`
					: null,
			].filter(Boolean);
			const ok = await confirmer({
				titre: 'Réparer les lignes orphelines',
				message:
					`${lignes.join('\n')}\n\n` +
					"La suppression est irréversible. Vérifiez qu'une sauvegarde hors site récente existe.",
				libelleConfirmer: aSupprimer ? `Réparer (${aSupprimer} suppression·s)` : 'Réparer',
				danger: aSupprimer > 0,
			});
			if (!ok) return;
			const resultat = await api.post<{ supprimees: number; deliees: number }>(
				'/admin/db/purger-orphelins?confirmer=true',
			);
			toast(
				'success',
				`${resultat.supprimees} ligne(s) supprimée(s), ${resultat.deliees} déliée(s).`,
			);
			await analyser();
		} catch (e: any) {
			toast('error', e?.message ?? 'Purge impossible');
		} finally {
			enCours = false;
		}
	}
</script>

<section class="card config-section">
	<SectionFormulaire titre="Intégrité référentielle" icone="database" />
	<p class="muted intro">
		Recherche les lignes qui référencent un élément supprimé. Ces lignes ne sont visibles nulle part
		ailleurs&nbsp;: elles pointent vers des objets qui n'existent plus.
	</p>

	<div class="actions-diagnostic">
		<button type="button" class="btn btn-outline" disabled={enCours} on:click={analyser}>
			{enCours ? 'Analyse…' : 'Analyser'}
		</button>
		{#if releve && !releve.inconnu && (releve.orphelins ?? 0) > 0}
			<button type="button" class="btn btn-primary" disabled={enCours} on:click={purger}>
				Supprimer les lignes orphelines
			</button>
		{/if}
	</div>

	{#if releve}
		{#if releve.inconnu}
			<p class="etat etat-inconnu">
				⚠️ La mesure n'a pas pu avoir lieu — <strong>ce n'est pas « rien à signaler »</strong>.
				{releve.erreur ?? ''}
			</p>
		{:else if (releve.orphelins ?? 0) === 0}
			<p class="etat etat-sain">✓ Aucune ligne orpheline.</p>
		{:else}
			<p class="etat etat-alerte">
				🔴 <strong>{releve.orphelins}</strong> ligne(s) orpheline(s)&nbsp;:
			</p>
			<ul class="liste-relations">
				{#each releve.par_relation ?? [] as r (r.table + r.colonne + r.table_parente)}
					<li>
						<strong>{r.lignes}</strong> — <code>{r.table}.{r.colonne}</code> →
						<code>{r.table_parente}</code>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
</section>

<style>
	/*  `.muted` est GLOBALE (`styles/ecrans.css`) : la redéfinir ici, fût-ce à
	    l'identique, est exactement ce que `lint:charte` refuse. On ne pose que
	    l'écart propre à cet écran. */
	.intro {
		font-size: 0.85rem;
		margin-bottom: 0.75rem;
	}
	/*  PAS `.form-actions` : cette classe dit « ce formulaire se soumet », et
	    `lint:soumission` exige alors le verbe commun. Or il n'y a pas de
	    formulaire ici — deux gestes d'exploitation, dont un destructeur qui doit
	    dire ce qu'il détruit. */
	.actions-diagnostic {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.etat {
		font-size: 0.9rem;
		margin-top: 0.75rem;
	}
	.etat-sain {
		color: var(--color-success);
	}
	.etat-alerte,
	.etat-inconnu {
		color: var(--color-danger);
	}
	.liste-relations {
		font-size: 0.85rem;
		margin: 0.4rem 0 0 1.1rem;
		line-height: 1.7;
	}
</style>
