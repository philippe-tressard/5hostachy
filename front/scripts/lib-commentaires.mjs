/**
 * Neutraliser les commentaires avant d'analyser un fichier — **une seule fois**.
 *
 * ## Pourquoi ce module existe
 *
 * Le 20/08/2026, **trois** garde-fous du front ont refusé un lot à cause d'un
 * COMMENTAIRE qui citait ce qu'ils interdisent :
 *
 * | Contrôle | Ce qu'il a refusé |
 * |---|---|
 * | `check-html` | un commentaire expliquant pourquoi le composant n'emploie PAS `{@html}` |
 * | `check-charge-utile` | une virgule dans une phrase, qui coupait son propre découpage |
 * | `check-libelles-taches` | un commentaire nommant « Sauvegarde quotidienne » |
 *
 * 🔴 **Un contrôle qui interdit d'en parler oblige à taire la raison — et c'est
 * la raison qui se perd en premier.** Le fichier qui explique une règle est
 * précisément celui qui la cite le plus.
 *
 * Chacun a d'abord été corrigé chez lui. Quatre copies de la même parade en ont
 * résulté, écrites dans la même journée : c'est la duplication que
 * `standards/02` interdit, commise en réparant des contrôles.
 *
 * ## 🔴 La détection LINE-LOCALE ne suffit pas
 *
 * La forme naïve — « la portion de ligne avant l'occurrence contient-elle `//`,
 * `*` ou `<!--` ? » — ne voit qu'un commentaire ouvert sur la MÊME ligne. Un
 * commentaire Svelte de plusieurs lignes la traverse sans être vu, et c'est
 * exactement ce qui s'est produit trois fois.
 *
 * ## Le contenu est remplacé par des ESPACES, jamais supprimé
 *
 * Les index et les numéros de ligne des occurrences RÉELLES doivent rester
 * justes : un contrôle qui désigne la mauvaise ligne se fait ignorer.
 *
 * Test : node front/scripts/lib-commentaires.mjs --selftest
 */
import { pathToFileURL } from 'node:url';

/**
 * Remplace le contenu des commentaires par des espaces, en conservant la
 * longueur du fichier.
 *
 * Trois formes, dont deux peuvent s'étendre sur plusieurs lignes : le
 * commentaire HTML/Svelte `<!-- … -->`, le commentaire de bloc `/* … *\/`, et le
 * commentaire de fin de ligne `// …`.
 *
 * ⚠️ Le `//` d'une URL (`https://…`) n'est PAS un commentaire. Le motif exige
 * donc que le caractère précédent ne soit pas `:` — sans quoi une ligne
 * contenant une URL serait tronquée, et ce qui la suit deviendrait invisible.
 */
export function neutraliserCommentaires(source) {
	return source
		.replace(/<!--[\s\S]*?-->|\/\*[\s\S]*?\*\//g, (bloc) => bloc.replace(/[^\n]/g, ' '))
		.replace(/(^|[^:])\/\/[^\n]*/g, (bloc, avant) => avant + ' '.repeat(bloc.length - avant.length));
}

function selftest() {
	let ko = 0;

	//  🔴 On éprouve des PROPRIÉTÉS, pas des chaînes recopiées.
	//
	//  La première version de ce self-test comparait le résultat à un attendu
	//  écrit à la main — et deux cas sur sept échouaient, à UN espace près. La
	//  fonction était juste, mes attendus étaient faux. Un test qu'on ajuste
	//  jusqu'à ce qu'il passe ne prouve plus rien : il finit par décrire le
	//  comportement observé, quel qu'il soit.
	//
	//  Les trois propriétés ci-dessous sont, elles, indiscutables — et ce sont
	//  exactement celles dont dépendent les contrôles qui emploient ce module.
	const t = (libelle, source, marqueur) => {
		const obtenu = neutraliserCommentaires(source);
		const soucis = [];
		if (obtenu.length !== source.length) {
			soucis.push(`longueur ${obtenu.length} au lieu de ${source.length} — les positions se décalent`);
		}
		if ((obtenu.match(/\n/g) || []).length !== (source.match(/\n/g) || []).length) {
			soucis.push('sauts de ligne perdus — les numéros de ligne deviennent faux');
		}
		if (marqueur !== null && obtenu.includes(marqueur)) {
			soucis.push(`« ${marqueur} » subsiste alors qu'il est en commentaire`);
		}
		if (marqueur === null && obtenu !== source) {
			soucis.push('le contenu HORS commentaire a été modifié');
		}
		if (!soucis.length) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — ${soucis.join(' ; ')}`);
			ko = 1;
		}
	};

	t('commentaire de ligne', 'const a = 1; // interdit', 'interdit');
	t('commentaire de bloc', 'const a = 1; /* interdit */ const b = 2;', 'interdit');
	t('commentaire Svelte', '<!-- interdit -->\n<p>ok</p>', 'interdit');
	//  🔴 Le cas que la détection line-locale ne voit pas — celui qui a fait
	//  refuser trois lots le 20/08/2026.
	t('commentaire Svelte multi-lignes',
		'<!--  ligne un\n      ligne deux : interdit\n-->\n<p>ok</p>', 'interdit');
	t('commentaire de bloc multi-lignes', '/*\n interdit\n*/\nconst a = 1;', 'interdit');
	//  ⚠️ Ce qui n'est PAS un commentaire doit rester intact, au caractère près.
	t('URL avec double barre', "const u = 'https://exemple.fr/a';", null);
	t('code sans commentaire', 'const a = 1;\nconst b = 2;', null);
	t('barre oblique simple', 'const r = a / b;', null);

	console.log(
		ko === 0
			? '\n✓ Autotest : commentaires neutralisés, longueurs et lignes conservées, code intact.'
			: '\n✗ Autotest en échec',
	);
	return ko;
}

//  Ne s'exécute QUE si le fichier est lancé, jamais s'il est importé — sans quoi
//  un module qu'on ne peut pas importer est un module qu'on ne peut pas éprouver.
const _lance = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === _lance) process.exit(selftest());
