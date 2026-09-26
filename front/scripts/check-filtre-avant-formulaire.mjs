#!/usr/bin/env node
/**
 * Garde-fou : les FILTRES d'une liste sont rendus AVANT sa boîte de création.
 *
 * ## La règle (`ux-patterns` §0 ter, 12/09/2026)
 *
 * Sous le titre de page : ce qui qualifie la liste, puis les **filtres**, puis
 * le **formulaire de création** quand il est ouvert, puis la **liste**. Le
 * bouton reste en haut (R1) ; la boîte qu'il ouvre prend sa place APRÈS ce qui
 * qualifie la liste.
 *
 * ## 🔴 Pourquoi un contrôle (#1186, 24/09/2026)
 *
 * La règle était écrite depuis douze jours, appliquée aux Affaires, aux
 * prestataires et aux badges — et la Boîte à idées comme les Petites annonces
 * rendaient toujours leur filtre SOUS la boîte. L'écart ne se voit que le
 * formulaire OUVERT, donc jamais pendant une relecture d'écran : signalé par
 * l'utilisateur, captures à l'appui.
 *
 * ## Ce qui est vérifié
 *
 * Dans chaque `.svelte`, découpé en BRANCHES d'onglet (`{#if onglet …}` /
 * `{:else if onglet …}`) : si la branche porte un filtre (`ChoixPastilles`,
 * `.filters`, `.filter-select`), aucun formulaire (`<Formulaire…>`) ne la
 * précède. Un formulaire rendu APRÈS le filtre — la boîte de création à sa
 * place, ou la correction DANS une carte — passe.
 *
 * ⚠️ Le découpage par onglet n'est pas un raffinement : `prestataires` rend le
 * formulaire de contrat dans un onglet et les filtres d'annuaire dans un autre.
 * Sans lui, le contrôle crierait sur un écran conforme — et un contrôle qui
 * crie sur du légitime finit désarmé.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

const FILTRE = /<ChoixPastilles\b|class="[^"]*\bfilters?\b|class="[^"]*\bfilter-select\b/;
const FORMULAIRE = /<Formulaire[A-Z]\w*/;
const BRANCHE_ONGLET = /\{[#:](?:else )?if\s+onglet\b/g;

function svelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...svelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

/** Les formulaires rendus avant le filtre de leur branche. PURE. */
export function formulairesAvantFiltre(source) {
	//  Le balisage seul : un commentaire qui NOMME un formulaire n'en rend pas.
	const debut = source.lastIndexOf('</script>');
	//  🔴 Une rangée de pastilles LIBELLÉE (`libelleVisible`) est un CHAMP de
	//  formulaire, pas un filtre (#1329) : les listes courtes des formulaires
	//  sont passées en pastilles le 26/09/2026, et le contrôle les prenait pour
	//  des filtres rendus après leur boîte. Neutralisées à longueur égale.
	const balisage = (debut >= 0 ? source.slice(debut) : source)
		.replace(/<!--[\s\S]*?-->/g, (c) => c.replace(/[^\n]/g, ' '))
		.replace(/<ChoixPastilles\b[^>]*\blibelleVisible\b[^>]*>/g, (c) => c.replace(/[^\n]/g, ' '));
	const decalage = debut >= 0 ? source.slice(0, debut).split('\n').length - 1 : 0;
	const coupes = [
		0,
		...[...balisage.matchAll(BRANCHE_ONGLET)].map((m) => m.index),
		balisage.length,
	];
	const fautes = [];
	for (let i = 0; i < coupes.length - 1; i++) {
		const branche = balisage.slice(coupes[i], coupes[i + 1]);
		const filtre = branche.search(FILTRE);
		if (filtre < 0) continue;
		const form = branche.search(FORMULAIRE);
		if (form >= 0 && form < filtre) {
			const index = coupes[i] + form;
			fautes.push({
				ligne: decalage + balisage.slice(0, index).split('\n').length,
				nom: branche.slice(form).match(FORMULAIRE)[0].slice(1),
			});
		}
	}
	return fautes;
}

if (process.argv.includes('--selftest')) {
	const cas = [
		//  🔴 Le cas réel de #1186 : la boîte, puis le filtre.
		['</script>{#if showForm}<FormulaireIdee />{/if}<ChoixPastilles />', 1],
		//  L'ordre de la règle.
		['</script><ChoixPastilles />{#if showForm}<FormulaireIdee />{/if}', 0],
		//  La correction DANS une carte, après le filtre : légitime.
		['</script><div class="filters"></div><Liste><FormulaireAnnonce {annonce} /></Liste>', 0],
		['</script>{#if showForm}<FormulaireAnnonce />{/if}<div class="filters"></div>', 1],
		//  Deux onglets : le formulaire de l'un ne précède pas le filtre de l'autre.
		[
			"</script>{#if onglet === 'a'}<FormulaireContrat />{:else if onglet === 'b'}<ChoixPastilles />{/if}",
			0,
		],
		//  Un commentaire qui nomme un formulaire n'en rend pas.
		['</script><!-- <FormulaireIdee /> --><ChoixPastilles />', 0],
		//  Un CHAMP en pastilles dans la boîte n'est pas un filtre (#1329).
		[
			'</script><FormulaireCreation><ChoixPastilles libelleVisible radio="t" /></FormulaireCreation>',
			0,
		],
		//  Pas de filtre : rien à ordonner.
		['</script>{#if showForm}<FormulaireIdee />{/if}<Liste />', 0],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = formulairesAvantFiltre(src).length;
		if (n !== attendu) {
			console.error(`  ✗ « ${src.slice(0, 70)} » → ${n}, attendu ${attendu}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.\n`);
		process.exit(1);
	}
	console.log(
		`✓ Auto-test : ${cas.length} cas — la boîte avant le filtre est vue, le reste passe.`,
	);
	process.exit(0);
}

const fautifs = [];
let ecrans = 0;
for (const chemin of svelte(RACINE)) {
	const source = readFileSync(chemin, 'utf8');
	if (!FILTRE.test(source) || !FORMULAIRE.test(source)) continue;
	ecrans++;
	const relatif = relative(RACINE, chemin).split(sep).join('/');
	for (const f of formulairesAvantFiltre(source)) {
		fautifs.push(`src/${relatif}:${f.ligne}  <${f.nom}> rendu avant le filtre de la liste`);
	}
}

//  Cas zéro : aucun écran ne porte à la fois un filtre et un formulaire — le
//  motif a changé de forme, et le contrôle ne mesure plus rien.
if (ecrans === 0) {
	console.error(
		'\n✗ Cas zéro : aucun écran ne rend à la fois un filtre et un formulaire —\n' +
			'  les motifs ont dérivé. Ne pas lire ceci comme un succès.\n',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error(`\n✗ ${fautifs.length} boîte(s) de création rendue(s) avant les filtres :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  Ce qui qualifie la liste — avertissement, filtres — reste au-dessus du' +
			'\n  formulaire ouvert (`ux-patterns` §0 ter). Déplacer le bloc `{#if showForm}`' +
			'\n  après les filtres.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Filtres : ${ecrans} écran(s) rendent un filtre et un formulaire, filtres toujours en premier.`,
);
