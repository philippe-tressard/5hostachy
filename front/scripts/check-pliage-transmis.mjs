#!/usr/bin/env node
/**
 * Garde-fou : un composant qui PORTE une section en transmet le pliage.
 *
 * ## Le défaut, signalé deux fois à l'écran (22/09/2026)
 *
 * > « le périmètre "Pièces jointes" optionnel doit être plié »
 * > « PJ toujours déplié »
 *
 * La table le déclarait `pliee: true` **dans les cinq entités concernées**, et
 * la section restait ouverte. « Au nom de » aussi — alors que c'est la seule
 * exception de pliage du cadre, celle qu'on a pris le soin de motiver.
 *
 * ## 🔴 L'angle mort des composants PORTEURS
 *
 * `SectionsPiecesJointes` et `ChampSaisiPour` rendent leur propre
 * `SectionFormulaire`. Le pliage lu dans la table par `ChampsCommuns` ne leur
 * était donc jamais passé : il n'existait pas de prop pour le recevoir.
 *
 * C'est **exactement** l'angle mort qui avait rendu l'ordre des sections
 * incontrôlable (#1124) : ces composants n'écrivent aucun `titre=`, aucun
 * `pliable=`, et aucun contrôle ne les regardait. Deux défauts distincts, une
 * seule cause — une section rendue par un composant échappe à ce qui gouverne
 * les sections rendues par un écran.
 *
 * ## Ce qui est vérifié
 *
 * Tout composant qui rend `<SectionFormulaire>` avec un `titre` issu de
 * `SECTIONS_LIBELLE` doit :
 *
 *   1. accepter une prop `pliable`,
 *   2. la transmettre à ce `SectionFormulaire`.
 *
 * ⚠️ Ce contrôle ne dit pas si l'APPELANT passe la bonne valeur — cela, c'est
 * `lint:etats` qui le gouverne depuis la table. Il dit que le chemin existe :
 * sans lui, la valeur juste n'arrive nulle part.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

import { balisesOuvrantes, ligneDe } from './lib-balises.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

function svelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...svelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

/** Les manquements d'une source. PURE : éprouvable sans arborescence. */
export function pliageManquant(source) {
	//  Seuls les composants qui rendent une section DU CADRE sont concernés :
	//  une section « Le contrat » ou « Activation » n'est pas gouvernée par la
	//  table, et n'a donc pas de pliage déclaré.
	//  L'automate vit dans `lib-balises.mjs` depuis le 22/09/2026 : il etait
	//  ecrit ici, et une troisieme fois ailleurs. Le `>` d'une expression ne ferme
	//  pas une balise (`standards/04` §48) — et la quatrieme recopie manquerait le
	//  cas suivant.
	const balises = balisesOuvrantes(source, 'SectionFormulaire').filter((b) =>
		b.balise.includes('SECTIONS_LIBELLE.'),
	);
	if (balises.length === 0) return [];
	//  🔴 Ce qui compte est que la BALISE porte `pliable` — peu importe d'où la
	//  valeur vient. Un composant qui lit la table lui-même
	//  (`pliable={plie('quand')}`) est aussi juste qu'un composant qui reçoit la
	//  prop d'un appelant : dans les deux cas, le chemin existe.
	//
	//  ⚠️ Ma première écriture exigeait `export let pliable` partout, et criait
	//  donc sur `ChampsCommuns` — c'est-à-dire sur celui qui fait exactement ce
	//  qu'il faut. Un contrôle qui crie sur du légitime finit désarmé.
	const manques = [];
	for (const m of balises) {
		if (!/[^A-Za-z]pliable[^A-Za-z]/.test(m.balise)) {
			manques.push({ ligne: ligneDe(source, m.index) });
		}
	}
	return manques;
}

if (process.argv.includes('--selftest')) {
	const cas = [
		//  🔴 Le cas réel du 22/09 : la section du cadre, rendue sans pliage.
		['<SectionFormulaire titre={SECTIONS_LIBELLE.pieces_jointes}>', 1],
		//  La prop reçue d'un appelant…
		['<SectionFormulaire titre={SECTIONS_LIBELLE.pieces_jointes} {pliable}>', 0],
		//  …ou lue dans la table sur place : les deux sont justes.
		["<SectionFormulaire titre={SECTIONS_LIBELLE.quand} pliable={plie('quand')}>", 0],
		//  Une section HORS cadre n'est pas jugée.
		['<SectionFormulaire titre="Le contrat">', 0],
		//  🔴 Le `>` d'une EXPRESSION ne ferme pas la balise. Sans l'automate,
		//  l'analyse s'arretait a `length >` et ne voyait pas le `pliable` d'apres :
		//  le controle reclamait un attribut deja present (vecu le 22/09/2026).
		[
			'<SectionFormulaire titre={SECTIONS_LIBELLE.destinataires} rempli={d.length > 0} pliable={p}>',
			0,
		],
		//  Et l'autre sens : le meme `>` ne doit pas masquer un manque reel.
		['<SectionFormulaire titre={SECTIONS_LIBELLE.destinataires} rempli={d.length > 0}>', 1],
		//  Aucun SectionFormulaire : rien à dire.
		['<div>rien</div>', 0],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = pliageManquant(src).length;
		if (n !== attendu) {
			console.error(`  ✗ « ${src.slice(0, 64).replace(/\n/g, ' ⏎ ')} » → ${n}, attendu ${attendu}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.\n`);
		process.exit(1);
	}
	console.log(`✓ Auto-test : ${cas.length} cas — le pliage manquant est vu, le reste passe.`);
	process.exit(0);
}

const fautifs = [];
let porteurs = 0;
for (const chemin of svelte(RACINE)) {
	const source = readFileSync(chemin, 'utf8');
	if (!source.includes('SECTIONS_LIBELLE.')) continue;
	if (!source.includes('<SectionFormulaire')) continue;
	porteurs++;
	for (const m of pliageManquant(source)) {
		const relatif = relative(RACINE, chemin).split(sep).join('/');
		fautifs.push(`src/${relatif}:${m.ligne}  section du cadre rendue sans pliable`);
	}
}

//  Cas zéro : plus aucun porteur, et le contrôle ne mesure plus rien.
if (porteurs === 0) {
	console.error(
		'\n✗ Cas zéro : aucun composant ne rend une section du cadre — le motif a\n' +
			'  dérivé. Ne pas lire ceci comme un succès.\n',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error(`\n✗ ${fautifs.length} section(s) du cadre dont le pliage n'arrive jamais :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		"\n  La table déclare `pliee`, et la section reste ouverte : le chemin n'existe" +
			"\n  pas. C'est l'angle mort des composants PORTEURS — ils ne s'écrivent pas" +
			'\n  dans l’écran, donc rien ne les gouverne.' +
			'\n\n  → `export let pliable = false;` puis `{pliable}` sur la section.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Pliage : ${porteurs} composant(s) portent une section du cadre, tous en transmettent le pliage.`,
);
