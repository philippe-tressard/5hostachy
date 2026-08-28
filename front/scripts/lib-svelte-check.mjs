/**
 * lib-svelte-check.mjs — lire le rapport de `svelte-check`, une seule fois.
 *
 * Module IMPORTÉ ; son `--selftest` est lancé par la CI.
 *
 * ## Pourquoi il existe (#561, 28/08/2026)
 *
 * `svelte-check` produit 44 avertissements que le job de CI ne regarde pas — il
 * ne bloque que sur les **erreurs**, et à raison : rendre les avertissements
 * bloquants d'un coup rendrait le job rouge en permanence, donc désarmé.
 *
 * La méthode qui marche, inaugurée par `check-css-orphelin` (#557) : prendre
 * **une famille** d'avertissements, la ramener à zéro, et la rendre bloquante —
 * elle seule. Les autres restent des avertissements tant qu'elles ne le sont pas.
 *
 * 🔴 Mais dès la **deuxième** famille, tout le tuyau se recopiait : lancer la
 * commande, retirer les couleurs, reconnaître un rapport valide, apparier chaque
 * avertissement à son emplacement. Quatre gestes délicats, dont deux ont déjà
 * coûté un défaut dans ce dépôt (le caractère de contrôle invisible dans un motif
 * ANSI, et le cas zéro d'une sortie non reconnue). Recopiés, ils divergent — et
 * c'est du côté non testé qu'ils sont faux (`standards/04` §11).
 *
 * Ce module porte donc le tuyau **une fois**. Chaque contrôle ne garde que sa
 * question et ses tolérances.
 *
 * Self-test : node scripts/lib-svelte-check.mjs --selftest
 */
import { spawnSync } from 'node:child_process';

/** Sortie INCONNU normalisée — ni succès ni échec, code 2 (`standards/04` §1). */
export function inconnu(raison, detail) {
	console.error(`\n⚠️  INCONNU — ${raison}`);
	if (detail) console.error(`   ${String(detail).trim().split('\n').slice(0, 5).join('\n   ')}`);
	console.error(
		"   Le relevé n'a PAS été mesuré : ce n'est ni un succès ni un échec. Relancer le job.\n",
	);
	process.exit(2);
}

/**
 * Les lignes du rapport, couleurs retirées.
 *
 * ⚠️ `svelte-check` sort en 1 dès qu'il trouve une ERREUR, et en 0 avec des
 * avertissements : son code de sortie ne dit rien de ce qui nous intéresse. C'est
 * sa SORTIE qui fait foi, et son illisibilité qui vaut INCONNU.
 */
export function lignesDuRapport() {
	//  🔴 `svelte-kit sync` D'ABORD, et le MÊME `--tsconfig` que le script `check`
	//  du package.json (28/08/2026).
	//
	//  Sans le sync, `.svelte-kit/tsconfig.json` n'existe pas, `svelte-check`
	//  n'analyse AUCUN fichier — et rend « 0 errors and 0 warnings » en une
	//  seconde. Sur le poste on ne le voyait jamais : le répertoire `.svelte-kit`
	//  y traîne depuis un build précédent. En intégration continue, où le dépôt
	//  est neuf et où ces étapes passent AVANT le build, les trois contrôles qui
	//  s'appuient sur ce module rendaient donc « aucun défaut » sans avoir rien
	//  analysé.
	//
	//  ⚠️ C'est la definition même du faux vert, et il a tenu parce que le
	//  résultat attendu de deux d'entre eux est ZÉRO : « rien lu » y ressemble
	//  trait pour trait. Seul `lint:a11y`, qui porte une exception à SERVIR, a pu
	//  le révéler — il a cru l'écran devenu conforme.
	const sync = spawnSync('npx svelte-kit sync', { encoding: 'utf8', shell: true });
	if (sync.status !== 0) {
		inconnu(
			'`svelte-kit sync` a échoué — `svelte-check` n\'analyserait aucun fichier',
			`${sync.stdout || ''}${sync.stderr || ''}`.slice(-400),
		);
	}
	const res = spawnSync('npx svelte-check --tsconfig ./tsconfig.json --output human', {
		encoding: 'utf8',
		shell: true,
		maxBuffer: 32 * 1024 * 1024,
	});
	if (res.error) inconnu('`svelte-check` n\'a pas pu être lancé', res.error.message);
	const sortie = `${res.stdout || ''}${res.stderr || ''}`.replace(motifAnsi(), '');
	//  🔴 CAS ZÉRO — une sortie qui ne ressemble pas à un rapport rendrait
	//  « aucun défaut » sans avoir rien lu.
	const bilan = /svelte-check found (\d+) errors? and (\d+) warnings?/.exec(sortie);
	if (!bilan) {
		inconnu('sortie de `svelte-check` non reconnue', sortie.slice(-400));
	}
	const lignes = sortie.split('\n');

	//  🔴 CAS ZÉRO, SECOND ÉTAGE — le rapport ANNONCE un nombre d'avertissements ;
	//  si on n'arrive pas à les lire, on ne dit pas « aucun ».
	//
	//  Trouvé le 28/08/2026, et c'était un faux vert en production. En intégration
	//  continue, `lint:css-orphelin` et `lint:libelles` rendaient « aucun » — non
	//  parce que le dépôt était conforme, mais parce que RIEN n'était extrait de la
	//  sortie. Sur le poste (terminal interactif) le format est bloc par bloc ;
	//  ailleurs il peut différer, et le premier étage ci-dessus ne voyait rien : la
	//  ligne de bilan, elle, était bien là.
	//
	//  Les deux contrôles ne pouvaient PAS s'en apercevoir : leur relevé légitime
	//  est vide, et « rien lu » y ressemble trait pour trait. C'est `lint:a11y`,
	//  qui porte une exception à servir, qui l'a révélé — il a cru l'écran devenu
	//  conforme. Un contrôle dont le résultat attendu est « zéro » a besoin d'un
	//  témoin extérieur ; celui-ci est le compte que l'outil annonce lui-même.
	const annonces = Number(bilan[2]);
	const lus = lignes.filter((l) => /\bWarn:/.test(l)).length;
	if (annonces > 0 && lus === 0) {
		inconnu(
			`\`svelte-check\` annonce ${annonces} avertissement(s) et aucun n'a pu être lu`,
			`Le format du rapport ne correspond plus au motif de lecture (\`Warn:\`).\n` +
				`   Extrait :\n${sortie.slice(-600)}`,
		);
	}
	return lignes;
}

/**
 * Le motif des codes de couleur ANSI, construit À L'EXÉCUTION.
 *
 * ⚠️ Écrire le caractère d'échappement en clair dans un littéral régulier y met
 * un CARACTÈRE DE CONTRÔLE INVISIBLE — c'est le défaut trouvé dans
 * `check-workflow-envoye.mjs` (un U+0008 au milieu d'un motif, qui le rendait
 * inerte). ESLint le refuse, à raison.
 */
export function motifAnsi() {
	return new RegExp(String.fromCharCode(27) + '\\[[0-9;]*m', 'g');
}

/**
 * Les avertissements dont la ligne contient `marqueur`, avec leur emplacement.
 *
 * ⚠️ **L'emplacement est sur la ligne non vide qui PRÉCÈDE le message**, pas sur
 * la même. Un motif qui les chercherait sur une seule ligne ne trouverait aucun
 * fichier et rapporterait tout en « ? » — vert de forme, muet sur le fond.
 *
 * ⚠️ `indice` est rendu parce que le rapport est MULTILIGNE : le message tient sur
 * la ligne `Warn:`, mais le code stable de la règle (`a11y_no_static_…`) est sur
 * la ligne SUIVANTE, dans l'URL de documentation. Un contrôle qui veut trier par
 * code doit pouvoir lire autour — sinon il recopierait ce tuyau pour deux lignes,
 * et c'est exactement ce que ce module existe pour empêcher (#561).
 *
 * @param lignes   la sortie découpée
 * @param marqueur le texte qui identifie la famille (ex. `Unused CSS selector`)
 * @returns `[{ fichier, ligne, message, indice }]`, chemins normalisés en `/`
 */
export function avertissements(lignes, marqueur) {
	const trouves = [];
	for (let i = 0; i < lignes.length; i++) {
		if (!lignes[i].includes(marqueur)) continue;
		let j = i - 1;
		while (j >= 0 && !lignes[j].trim()) j--;
		const emplacement = /front[\\/](src[^\s:]+)[":\s]+(\d+)/.exec(lignes[j] ?? '');
		trouves.push({
			fichier: emplacement ? emplacement[1].replace(/\\/g, '/').replace(/"$/, '') : '?',
			ligne: emplacement ? emplacement[2] : '?',
			message: lignes[i].trim(),
			indice: i,
		});
	}
	return trouves;
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop())) {
	if (process.argv.includes('--selftest')) {
		let fail = 0;
		const verifier = (nom, obtenu, attendu) => {
			const a = JSON.stringify(attendu);
			const o = JSON.stringify(obtenu);
			if (o === a) console.log(`PASS  ${nom}`);
			else { console.error(`FAIL  ${nom}\n      attendu ${a}\n      obtenu  ${o}`); fail = 1; }
		};

		//  Un extrait RÉEL de la sortie, forme comprise : l'emplacement une ligne
		//  au-dessus, une ligne vide entre deux entrées. Un exemple réécrit de
		//  mémoire porterait les hypothèses de celui qui l'invente.
		const rapport = [
			'C:/Dev/5hostachy/front/src/routes/(app)/faq/+page.svelte:104:5',
			'Warn: Unused CSS selector ".faq-q" (svelte)',
			'',
			'C:/Dev/5hostachy/front/src/lib/components/Nav.svelte:12:2',
			'Warn: A form label must be associated with a control (svelte)',
			'',
			'svelte-check found 0 errors and 2 warnings',
		];
		verifier(
			'la famille demandée, et elle seule',
			avertissements(rapport, 'Unused CSS selector').map((a) => a.fichier),
			['src/routes/(app)/faq/+page.svelte'],
		);
		verifier(
			"l'emplacement vient de la ligne PRÉCÉDENTE",
			avertissements(rapport, 'form label')[0],
			{
				fichier: 'src/lib/components/Nav.svelte',
				ligne: '12',
				message: 'Warn: A form label must be associated with a control (svelte)',
				//  `indice` est rendu depuis #561 : le rapport est MULTILIGNE, et le code
				//  stable d'une règle a11y vit sur la ligne SUIVANTE. Ce cas-ci a refusé
				//  l'ajout tant qu'il n'était pas déclaré — c'est ce qu'on lui demande.
				indice: 4,
			},
		);
		//  Cas zéro de l'appelant : une famille absente ne doit rien inventer.
		verifier('famille absente → liste vide', avertissements(rapport, 'jamais vu').length, 0);
		//  Un message sans emplacement lisible doit se DIRE inconnu, pas s'attribuer
		//  au fichier précédent — qui n'a rien à voir.
		verifier(
			'emplacement illisible → « ? », jamais un fichier au hasard',
			avertissements(['(pas un chemin)', 'Warn: Unused CSS selector ".x" (svelte)'], 'Unused CSS')[0].fichier,
			'?',
		);
		//  Les couleurs se retirent sans laisser de caractère de contrôle.
		const colore = String.fromCharCode(27) + '[31mWarn' + String.fromCharCode(27) + '[0m';
		verifier('les codes ANSI sont retirés', colore.replace(motifAnsi(), ''), 'Warn');

		//  🔴 Le cas zéro du SECOND étage (28/08/2026) : un rapport qui ANNONCE des
		//  avertissements dont aucun n'est lisible. C'était un faux vert réel — en
		//  intégration continue, deux contrôles rendaient « aucun » sans rien avoir
		//  extrait. On éprouve ici la DÉCISION (les deux comptes divergent), pas le
		//  `process.exit` qui la suit.
		const divergent = (annonces, lignes) => annonces > 0 && lignes.filter((l) => /\bWarn:/.test(l)).length === 0;
		verifier('bilan annoncé mais rien de lisible → anomalie', divergent(2, ['svelte-check found 0 errors and 2 warnings']), true);
		verifier('bilan annoncé ET lisible → normal', divergent(2, rapport), false);
		verifier('aucun avertissement annoncé → normal, pas une anomalie', divergent(0, ['svelte-check found 0 errors and 0 warnings']), false);

		if (fail) { console.error('\n✗ lib-svelte-check --selftest : des cas échouent.'); process.exit(1); }
		console.log('✓ lib-svelte-check --selftest : le rapport se lit comme on croit.');
	}
}
