/**
 * Auto-test de `lib-lecture-source.mjs` — la lecture ne dépend PAS de la mise en page.
 *
 * 🔴 Chaque cas est écrit DEUX fois : resserré et reformaté. C'est tout l'objet
 * du module, et un test qui n'éprouverait qu'une forme ne dirait rien — c'est
 * exactement l'angle mort dans lequel les quatre contrôles étaient tombés (#419).
 *
 * Lancer : node scripts/lib-lecture-source.mjs --selftest
 */
import { baliseFermante, corpsDesTables, emploieComposant, valeursDeclarees } from './lib-lecture-source.mjs';

export function selftest() {
	let echecs = 0;
	const verifier = (quoi, attendu, obtenu) => {
		const a = JSON.stringify(attendu);
		const o = JSON.stringify(obtenu);
		if (a === o) return console.log(`  ✓ ${quoi}`);
		echecs++;
		console.error(`  ✗ ${quoi}\n      attendu ${a}\n      obtenu  ${o}`);
	};

	console.log('\nlib-lecture-source — auto-test\n');

	const SERRE = [
		"export const PAGES = [",
		"	{ id: 'tableau-de-bord', href: '/tableau-de-bord', nom: 'Accueil' },",
		"	{ id: 'residence', href: '/residence', nom: 'Résidence' },",
		"];",
	].join('\n');
	const REFORMATE = [
		"export const PAGES = [",
		"	{", "		id: 'tableau-de-bord',", "		href: '/tableau-de-bord',", "		nom: 'Accueil',", "	},",
		"	{", "		id: 'residence',", "		href: '/residence',", "		nom: 'Résidence',", "	},",
		"];",
	].join('\n');

	const IDS = ['tableau-de-bord', 'residence'];
	const opts = { valeur: '[a-z0-9-]+', suivi: 'href' };
	verifier('table serrée — identifiants', IDS, valeursDeclarees(SERRE, 'id', opts));
	verifier('table reformatée — identifiants', IDS, valeursDeclarees(REFORMATE, 'id', opts));

	//  ⚠️ `suivi` n'est pas décoratif : sans lui, tout `id:` du fichier entrerait
	//  dans le relevé — y compris ceux d'objets qui ne sont pas des pages.
	verifier(
		"`suivi` écarte un `id:` qui n'est pas suivi de `href:`",
		[],
		valeursDeclarees("{ id: 'autre-chose', libelle: 'x' }", 'id', opts)
	);

	//  🔴 La lecture par BLOC, et pourquoi elle remplace l'ancre d'indentation :
	//  celle-ci disait à la fois la PROFONDEUR et la mise en page, et seule la
	//  première comptait. Sans le bloc, `couleur:` d'une autre table entrerait.
	const TABLES = [
		"export const LIBELLE_TACHE = {",
		"	backup: 'Sauvegarde',",
		"	vacuum:", "		'Compactage',",
		"};",
		"export const CLASSE_STATUT = {",
		"	ok: 'badge-green',",
		"};",
	].join('\n');
	verifier(
		'seule la table nommée est lue',
		['Sauvegarde', 'Compactage'],
		corpsDesTables(TABLES, /export const (LIBELLE_TACHE)\b/g).flatMap((c) => valeursDeclarees(c, '[a-z_]+'))
	);
	verifier('accolade jamais refermée → aucun bloc', [], corpsDesTables("export const LIBELLE_X = {", /export const (LIBELLE_[A-Z_]+)\b/g));

	verifier('<Modale> sur une ligne', true, emploieComposant('<Modale titre="x">', 'Modale'));
	verifier('<Modale> reformaté', true, emploieComposant('<Modale\n	titre="x"\n>', 'Modale'));
	verifier('<Modale/> auto-fermé', true, emploieComposant('<Modale/>', 'Modale'));
	//  🔴 Sans la frontière, un composant dont le nom COMMENCE par `Modale`
	//  compterait : le contrôle croirait couvert un écran qui ne l'est pas.
	verifier('<ModaleConfirmation> ne compte pas', false, emploieComposant('<ModaleConfirmation>', 'Modale'));

	//  🔴 Prettier coupe la balise FERMANTE quand l'ouvrante déborde.
	verifier('</button> d’un tenant', 19, baliseFermante('<button>Oui</button>', 'button').fin);
	verifier('</button> coupé par le formatage', 20, baliseFermante('<button>Oui</button\n>', 'button').fin);
	verifier('balise jamais refermée → null', null, baliseFermante('<button>Oui', 'button'));

	//  Cas zéro : une source vide ne rend rien, et ne lève pas.
	verifier('source vide → aucun relevé', [], valeursDeclarees('', 'id', opts));
	verifier('source vide → aucun emploi', false, emploieComposant('', 'Modale'));

	console.log(echecs === 0 ? '\n✓ auto-test complet\n' : `\n✗ ${echecs} échec(s)\n`);
	process.exit(echecs === 0 ? 0 : 1);
}
