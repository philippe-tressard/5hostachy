/**
 * **Lire un texte d'écran** — les portes, le blanchiment, et ce qui s'y cherche.
 *
 * Extrait de `check-vocabulaire-ecran.mjs` le 21/09/2026 (#1123) : le contrôle
 * passait 500 lignes en gagnant la porte du TEXTE AFFICHÉ, et la modularité se
 * règle au fil de l'eau — on découpe le fichier quand on y touche.
 *
 * Ce module ne connaît ni les entités, ni les exceptions, ni le répertoire à
 * balayer : il reçoit une source et des mots, il rend des fautes. C'est ce qui
 * le rend éprouvable seul — `lib-vocabulaire.selftest.mjs` l'exerce sur des
 * chaînes, sans toucher au dépôt.
 */
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

/**
 * Les **portes** par lesquelles un texte devient visible.
 *
 * ⚠️ On ne cherche pas le mot dans tout le fichier : `{#each tickets as ticket}`
 * est du code, et le confondre avec un libellé ferait crier le contrôle sur du
 * légitime — un contrôle qui crie sur du légitime finit désarmé (leçon de C16).
 * Chaque motif capture ce qui sera **lu**.
 */
const PORTES = [
	{ nom: 'titre de boîte', re: /titreBoite\s*=\s*([^;\n]+)/g },
	{ nom: 'bouton de création', re: /libelle="([^"]+)"/g },
	{ nom: 'titre', re: /\btitre="([^"]+)"/g },
	//  🔴 Un `aria-label` EST un libellé : il est lu, par un lecteur d'écran. Le
	//  contrôle l'ignorait, et trois boutons disaient donc encore « Commenter »
	//  à ceux qui ne voient pas l'icône (21/09/2026).
	{ nom: 'nom accessible', re: /aria-label="([^"]+)"/g },
	{ nom: 'nom de l’objet copié', re: /quoi="([^"]+)"/g },
	{ nom: 'nom d’objet passé en prop', re: /\bobjet\s*=\s*'([^']+)'/g },
	{ nom: 'notification', re: /toast\(\s*'[a-z]+'\s*,\s*['"`]([^'"`]+)/g },
	//  🔴 Un libellé DÉCLARÉ dans une table TypeScript est lu comme les autres —
	//  et c'est par là que « Tickets » est resté sur la vignette de navigation
	//  (`lib/raccourcis.ts`) jusqu'au 21/09/2026, signalé à l'écran. Les portes
	//  ne cherchaient que des attributs de balisage : une table `.ts` qui nomme
	//  un objet n'était regardée par personne.
	{
		nom: 'libellé déclaré',
		re: /(?:libelle|navLabel|nom|titre|descriptif|label)\s*:\s*'([^']+)'/g,
	},
	{ nom: 'confirmation', re: /confirm\(\s*['"`]([^'"`]+)/g },
];

/**
 * Le vocabulaire déclaré, LU dans `entites/` — jamais recopié.
 *
 * @returns `[{ fichier, libelle, motDeCode, libelleNouveau, libelleModifier }]`
 */
export function vocabulaireDeclare(sources) {
	const champ = (s, nom) => {
		const m = new RegExp(`\\b${nom}:\\s*(?:'([^']*)'|"([^"]*)")`).exec(s);
		return m ? (m[1] ?? m[2]) : undefined;
	};
	return sources
		.map(({ fichier, source }) => ({
			fichier,
			libelle: champ(source, 'libelle'),
			motDeCode: champ(source, 'motDeCode'),
			libelleNouveau: champ(source, 'libelleNouveau'),
			libelleModifier: champ(source, 'libelleModifier'),
		}))
		.filter((e) => e.libelle);
}

/** La source se contredit-elle ? (points 2 et 3 de l'en-tête) */
export function incoherencesDeclaration(entites) {
	const fautes = [];
	for (const e of entites) {
		const attendu = (e.libelle ?? '').toLowerCase();
		if (e.motDeCode && attendu.includes(e.motDeCode.toLowerCase())) {
			fautes.push(
				`${e.fichier} : \`libelle: '${e.libelle}'\` porte son propre mot de code « ${e.motDeCode} »`,
			);
		}
		for (const clef of ['libelleNouveau', 'libelleModifier']) {
			const v = e[clef];
			if (v === undefined) {
				fautes.push(`${e.fichier} : \`${clef}\` manque`);
				continue;
			}
			//  🔴 L'inclusion n'est exigée que des entités RENOMMÉES, et c'est
			//  mesuré : « Déposer une annonce » ne contient pas « Petite annonce »,
			//  « Nouveau contrat » pas « Contrat d'entretien » — un nom formel et un
			//  nom d'usage, et les deux sont justes. Exiger l'inclusion partout
			//  faisait crier le contrôle sur ces deux-là, et un contrôle qui crie
			//  sur du légitime finit désarmé (leçon de C16).
			//
			//  Là où le mot de code existe, en revanche, l'enjeu est précisément
			//  que le libellé d'action NOMME la chose : « Signaler un problème » ne
			//  nommait rien, « Nouvelle publication » nommait le modèle. C'est le
			//  défaut #1107, et il ne se produit que sur ces entités-là.
			if (e.motDeCode && !v.toLowerCase().includes(attendu)) {
				fautes.push(`${e.fichier} : \`${clef}: '${v}'\` ne nomme pas « ${e.libelle} »`);
			}
			if (!e.motDeCode && !v.trim()) {
				fautes.push(`${e.fichier} : \`${clef}\` est vide`);
			}
		}
	}
	return fautes;
}

/**
 *  Ne garder que ce qui est du TEXTE LITTÉRAL.
 *
 *  Ce qu'une porte capture n'est pas toujours une chaîne : `titreBoite` prend
 *  une expression, et un toast une interpolation. Or `${TICKET.libelle}` et
 *  `PUBLICATION.libelleNouveau` contiennent le mot du modèle et rendent
 *  pourtant « Affaire » et « Nouvelle actualité » — c'est précisément la forme
 *  CORRIGÉE. Les signaler reviendrait à refuser le correctif que ce contrôle
 *  existe pour imposer.
 *
 *  Deux choses partent donc : les interpolations (`${…}`, et les accolades
 *  Svelte `{…}` qui sont la même chose dans le balisage) et les identifiants en
 *  MAJUSCULES, qui sont les constantes d'entité. Le contenu est remplacé par
 *  des espaces — jamais supprimé —, même parade que `lib-commentaires` : les
 *  numéros de ligne restent justes.
 */
function blanchir(t) {
	return t
		.replace(/\$\{[^}]*\}/g, (m) => ' '.repeat(m.length))
		.replace(/\{[^{}]*\}/g, (m) => ' '.repeat(m.length))
		.replace(/\b[A-Z][A-Z0-9_]{2,}\b(\.[A-Za-z][\w$]*)*/g, (m) => ' '.repeat(m.length));
}

/**
 * Le **texte du balisage** — la porte que les motifs ci-dessus ne voyaient pas.
 *
 * ## 🔴 Pourquoi elle manquait, et ce que ça a coûté (#1123, 21/09/2026)
 *
 * `PORTES` ne lit que des **attributs**. Le mot du modèle posé dans un `<span>`
 * ou un `<p>` lui était donc invisible — et c'est là qu'il y en avait le plus :
 * l'avertissement légal des affaires s'intitulait encore « Tickets de type
 * Urgence », et c'est l'ŒIL qui l'a trouvé, aucun contrôle ne le regardant.
 *
 * ⚠️ Un contrôle qui ne couvre qu'une partie des chemins rend un vert exact sur
 * ce qu'il mesure et faux sur la question posée. C'est la même famille que
 * `test_vocabulaire_affaire.py`, qui **déclare** ne pas lire les `.svelte` :
 * cette porte-ci est la moitié qui manquait.
 *
 * On blanchit, dans cet ordre : les blocs `<script>` et `<style>` (du code, pas
 * du texte), les commentaires HTML, puis les balises — leurs attributs relèvent
 * des portes ci-dessus. Ce qui reste est ce qu'un œil lit.
 */
export function texteVisible(source) {
	const espaces = (m) => m.replace(/[^\n]/g, ' ');
	const sansBlocs = source
		.replace(/<script[\s\S]*?<\/script>/gi, espaces)
		.replace(/<style[\s\S]*?<\/style>/gi, espaces)
		.replace(/<!--[\s\S]*?-->/g, espaces);

	//  🔴 Les balises ne se retirent PAS par `/<[^>]*>/`. Une balise de composant
	//  s'étend sur plusieurs lignes et porte des `>` dans ses attributs —
	//  `{a > b}`, `on:click={() => …}` —, et le motif naïf s'y arrête : la fin de
	//  la balise repasse alors pour du texte affiché. C'est ainsi que
	//  `idPrefixe="ticket"` est remonté comme un libellé lisible.
	//
	//  On avance donc caractère par caractère, en ignorant les `>` qui sont dans
	//  une chaîne ou dans une accolade Svelte. Le contenu est blanchi, jamais
	//  supprimé : les numéros de ligne restent justes.
	let sortie = '';
	let i = 0;
	while (i < sansBlocs.length) {
		const c = sansBlocs[i];
		if (c !== '<' || !/[a-zA-Z/!]/.test(sansBlocs[i + 1] ?? '')) {
			sortie += c;
			i += 1;
			continue;
		}
		let j = i + 1;
		let quote = '';
		let accolades = 0;
		while (j < sansBlocs.length) {
			const d = sansBlocs[j];
			if (quote) {
				if (d === quote) quote = '';
			} else if (d === '"' || d === "'" || d === '`') quote = d;
			else if (d === '{') accolades += 1;
			else if (d === '}') accolades = Math.max(0, accolades - 1);
			else if (d === '>' && accolades === 0) break;
			j += 1;
		}
		sortie += espaces(sansBlocs.slice(i, Math.min(j + 1, sansBlocs.length)));
		i = j + 1;
	}
	return sortie;
}

/** Les textes de balisage d'un fichier qui portent l'un des mots de code. */
export function texteVisibleFautif(source, motsDeCode, exceptions = []) {
	if (!motsDeCode.length) return [];
	const motif = new RegExp(`\\b(${motsDeCode.join('|')})s?\\b`, 'i');
	const fautes = [];
	texteVisible(source)
		.split('\n')
		.forEach((ligne, i) => {
			const texte = blanchir(ligne).trim();
			if (!texte || !motif.test(texte)) return;
			if (exceptions.some((e) => ligne.includes(e.texte ?? e))) return;
			fautes.push({ ligne: i + 1, porte: 'texte affiché', texte: texte.slice(0, 80) });
		});
	return fautes;
}

/** Les libellés visibles d'un fichier qui portent l'un des mots de code. */
export function libellesFautifs(source, motsDeCode, exceptions = []) {
	if (!motsDeCode.length) return [];
	const propre = sansCommentaires(source);
	const motif = new RegExp(`\\b(${motsDeCode.join('|')})s?\\b`, 'i');
	const fautes = [];
	propre.split('\n').forEach((ligne, i) => {
		for (const { nom, re } of PORTES) {
			re.lastIndex = 0;
			let m;
			while ((m = re.exec(ligne))) {
				const texte = (m[1] ?? '').trim();
				if (!motif.test(blanchir(texte))) continue;
				if (exceptions.some((e) => texte.includes(e.texte ?? e))) continue;
				fautes.push({ ligne: i + 1, porte: nom, texte: texte.slice(0, 80) });
			}
		}
	});
	return fautes;
}
