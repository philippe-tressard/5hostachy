<!--
  L'onglet **Reporting** de l'espace CS : la barre des six vues, le chargement
  commun de leurs données, et l'impression.

  POURQUOI CE COMPOSANT (#453). `espace-cs/+page.svelte` faisait 3 262 lignes et
  le garde-fou de modularité (rang 1) y refusait des ajouts de deux lignes ; on y
  avait répondu trois fois en tassant des attributs — donc en satisfaisant le
  contrôle par la mise en forme, pas par la structure. Ce bloc-ci pesait 657
  lignes de balisage à lui seul, un cinquième de la page.

  ⚠️ **Une vue = un fichier, et c'est la seule découpe qui tienne.** Tout ramener
  dans UN composant donnait 1 400 lignes : le même défaut, déplacé d'un fichier à
  l'autre. Ce qui est partagé monte d'un cran — les types et les calculs dans
  `$lib/reporting.ts`, le vocabulaire de style dans `app.css`.

  🔴 **Les tickets sont chargés ICI depuis le 28/08/2026.** Ils arrivaient en
  prop de la page, avec cette raison : « l'onglet Tickets et l'analyse du
  reporting lisent la MÊME liste ». L'onglet « Tickets résidence » a été retiré
  (redondant avec `/tickets`), et sa disparition emporte la prémisse : il ne
  reste qu'un consommateur, et la page n'a plus aucune raison de tenir une liste
  qu'elle n'affiche pas. Un passe-plat gardé après la mort de son motif se lit
  comme une contrainte encore vraie.

  ⚠️ La classe `print-reporting` posée sur <body> est une mutation d'état global
  (`standards/11` §12) : elle est posée ET retirée ici, sur le cycle de vie de ce
  composant — trois filets, dont un `onDestroy` qui couvre maintenant le simple
  changement d'onglet. Elle vivait dans la page, qui, elle, restait montée.
-->
<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { prestataires as prestApi, calendrier as calApi, diagnostics as diagnosticsApi, tickets as ticketsApi, type Ticket } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { fmtDatetime } from '$lib/date';
	import { apiMessage } from '$lib/utils';
	import { REPORT_VUES, type ReportVue, type ReportEvenement, type ReportPrestataire, type ReportContrat, type DiagType } from '$lib/reporting';
	import VueKanban from './VueKanban.svelte';
	import VueTickets from './VueTickets.svelte';
	import VuePrestataires from './VuePrestataires.svelte';
	import VueRenouvellements from './VueRenouvellements.svelte';
	import VueRelanceSyndic from './VueRelanceSyndic.svelte';

	/** Libellé de l'onglet, pour l'en-tête d'impression. */
	export let titreOnglet = 'Reporting';
	/** Vue demandée par l'URL (`?vue=…`), à l'arrivée depuis le tableau de bord. */
	export let vueInitiale: string | null = null;

	let tickets: Ticket[] = [];
	let reportView: ReportVue = 'kanban';
	let reportingLoading = false;
	let reportingLoaded = false;
	let reportPrintTitle = '';
	let reportPrestataires: ReportPrestataire[] = [];
	let reportEvenements: ReportEvenement[] = [];
	let reportContrats: ReportContrat[] = [];
	let reportDiagTypes: DiagType[] = [];
	let reportNoteMoyParPrest: Map<number, { moy: number; nb: number }> = new Map();

	//  « Relance syndic » charge ses propres données ; elle rend compte de son état
	//  à la barre d'outils, qui doit savoir quoi rafraîchir et si la page est vide
	//  avant d'ouvrir la boîte d'impression.
	let vueRelance: VueRelanceSyndic | null = null;
	let relanceChargement = false;
	let relanceVide = true;

	/* La classe `print-reporting` vit sur <body> : tant qu'elle y reste, elle
	   déborde de cette page. Le nettoyage ne peut donc PAS dépendre du chemin
	   nominal — il était posé après `window.print()`, si bien qu'une exception
	   levée là le sautait, la classe restait, et la barre de navigation
	   disparaissait dans TOUTE l'application jusqu'à un rechargement complet
	   (signalé par l'utilisateur le 04/08/2026 depuis la vue « Relance syndic »).
	   Même classe que le bridge WhatsApp du 24/07 : une fonction `async` dont
	   personne n'attrape le rejet meurt sans un mot.
	   Trois filets désormais, et `restaurer` est idempotente : `afterprint`
	   (le signal fiable), `finally` (même si `print()` lève), et `onDestroy`
	   (si on quitte la page avant la fin). */
	let annulerImpression: (() => void) | null = null;

	async function printReporting(title: string) {
		if (typeof window === 'undefined' || typeof document === 'undefined') return;
		const titrePrecedent = document.title;
		const dateStr = new Date().toISOString().slice(0, 10);
		const slug = title.replace(/^Reporting CS — /, '').replace(/[^\w\dÀ-ÿ]+/g, '-').replace(/-+$/, '');
		const titreImpression = `CS-${slug}-${dateStr}`;

		let fait = false;
		const restaurer = () => {
			if (fait) return;
			fait = true;
			document.body.classList.remove('print-reporting');
			// Ne rendre le titre que s'il est encore le nôtre : si l'utilisateur a
			// navigué entre-temps, l'écraser afficherait le titre d'une autre page.
			if (document.title === titreImpression) document.title = titrePrecedent;
			window.removeEventListener('afterprint', restaurer);
			annulerImpression = null;
		};
		annulerImpression = restaurer;

		try {
			reportPrintTitle = title;
			document.body.classList.add('print-reporting');
			document.title = titreImpression;
			await tick();
			window.addEventListener('afterprint', restaurer);
			window.print();
		} catch {
			toast('error', "Impression impossible — l'affichage a été rétabli.");
		} finally {
			// `afterprint` n'est pas garanti partout : filet de sécurité. Volontairement
			// LONG — un délai court retirerait la classe pendant qu'un aperçu est encore
			// ouvert et gâcherait la mise en page imprimée. Le retard est sans effet
			// visible, les règles `body.print-reporting` (app.css) ne s'appliquant
			// qu'à l'impression.
			setTimeout(restaurer, 60000);
		}
	}

	onDestroy(() => annulerImpression?.());

	function printCurrentReporting() {
		const titles: Record<ReportVue, string> = {
			kanban: 'Reporting CS — Dossiers AG / CS / Syndic',
			tickets: 'Reporting CS — Analyse tickets',
			prestataires: 'Reporting CS — Synthèse prestataires',
			renouvellements: 'Reporting CS — Renouvellement contrats & audits',
			relance: 'Reporting CS — Relance syndic',
		};
		// Rien à imprimer : le dire, plutôt qu'ouvrir la boîte de dialogue sur une
		// page vide. C'est le cas qu'a rencontré l'utilisateur (04/08/2026) — la vue
		// « Relance syndic » n'affichait qu'un état vide, sans aucun ticket.
		if (reportView === 'relance' && !relanceChargement && relanceVide) {
			toast('info', 'Aucun ticket syndic en cours — rien à imprimer.');
			return;
		}
		void printReporting(titles[reportView]);
	}

	async function loadReporting(force = false) {
		if (reportingLoaded && !force) return;
		reportingLoading = true;
		try {
			const [ticketsList, prestataires, evenements, contrats, diagTypes, notations] = await Promise.all([
				ticketsApi.list(), prestApi.list(), calApi.list(),
				prestApi.contrats(), diagnosticsApi.listTypes(),
				prestApi.notations()
			]);
			tickets = ticketsList;
			reportPrestataires = prestataires as ReportPrestataire[];
			reportEvenements = evenements as ReportEvenement[];
			reportContrats = contrats as ReportContrat[];
			reportDiagTypes = diagTypes as DiagType[];
			// Calcul note moyenne par prestataire
			const noteMap = new Map<number, number[]>();
			for (const n of notations as { prestataire_id: number; note: number }[]) {
				if (!noteMap.has(n.prestataire_id)) noteMap.set(n.prestataire_id, []);
				noteMap.get(n.prestataire_id)!.push(n.note);
			}
			reportNoteMoyParPrest = new Map();
			for (const [pid, notes] of noteMap) {
				reportNoteMoyParPrest.set(pid, { moy: Math.round(notes.reduce((a, b) => a + b, 0) / notes.length * 10) / 10, nb: notes.length });
			}
			reportingLoaded = true;
		} catch (e: any) {
			toast('error', apiMessage(e, 'Erreur chargement reporting'));
		} finally {
			reportingLoading = false;
		}
	}

	function refreshReporting() {
		if (reportView === 'relance') vueRelance?.recharger();
		else loadReporting(true);
	}

	onMount(() => {
		if (vueInitiale && (REPORT_VUES as readonly string[]).includes(vueInitiale)) {
			reportView = vueInitiale as ReportVue;
		}
		//  La page appelait `loadRelanceSyndic()` dès qu'un `?vue=` était présent,
		//  quelle que soit la vue demandée : `?vue=kanban` chargeait donc les relances
		//  et laissait la vue affichée VIDE. On charge ce que la vue montre — la
		//  relance, elle, se charge d'elle-même à son montage.
		if (reportView !== 'relance') loadReporting();
	});
</script>

<div class="reporting-panel">
		<div class="reporting-toolbar no-print">
			<div class="reporting-switch">
				<button class="pill" class:pill-active={reportView === 'kanban'} on:click={() => (reportView = 'kanban')}>
					&#x1F4CC; AG / CS / Syndic
				</button>
				<button class="pill" class:pill-active={reportView === 'tickets'} on:click={() => (reportView = 'tickets')}>
					&#x1F4CA; Analyse tickets
				</button>
				<button class="pill" class:pill-active={reportView === 'prestataires'} on:click={() => (reportView = 'prestataires')}>
					&#x1F3E2; Prestataires
				</button>
				<button class="pill" class:pill-active={reportView === 'renouvellements'} on:click={() => (reportView = 'renouvellements')}>
					&#x1F4C5; Renouvellements
				</button>
				<button class="pill" class:pill-active={reportView === 'relance'} on:click={() => (reportView = 'relance')}>
					&#x1F514; Relance syndic
				</button>
			</div>
			<div class="reporting-actions">
				<button class="btn btn-sm btn-outline" on:click={refreshReporting} disabled={reportView === 'relance' ? relanceChargement : reportingLoading} title="Rafraîchir les données">
					&#x1F504;{(reportView === 'relance' ? relanceChargement : reportingLoading) ? ' …' : ''}
				</button>
				<button class="btn btn-sm btn-primary" on:click={printCurrentReporting}>
					&#x1F5A8; Imprimer / PDF
				</button>
			</div>
		</div>

	<div class="reporting-print-header">
		<h2>{reportPrintTitle || titreOnglet}</h2>
		<p>Édité le {fmtDatetime(new Date().toISOString())}</p>
	</div>

	{#if reportingLoading}
		<p style="color:var(--color-text-muted)">Chargement des reportings…</p>
	{:else if reportView === 'kanban'}
		<VueKanban {reportEvenements} />
	{:else if reportView === 'tickets'}
		<VueTickets {tickets} />
	{:else if reportView === 'prestataires'}
		<VuePrestataires {reportPrestataires} />
	{:else if reportView === 'renouvellements'}
		<VueRenouvellements {reportContrats} {reportPrestataires} {reportDiagTypes} {reportNoteMoyParPrest} />
	{:else if reportView === 'relance'}
		<VueRelanceSyndic bind:this={vueRelance} bind:chargement={relanceChargement} bind:estVide={relanceVide} />
	{/if}
</div>
