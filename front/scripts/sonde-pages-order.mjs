/**
 *  Sonde : l'ordre du menu que la PRODUCTION sert (`pages_order`) ne cite que
 *  des pages que le code connaît (#1114).
 *
 *  `pages_order` est une DONNÉE — une clé de `ConfigSite` que l'administration
 *  réordonne —, pas du code : aucun contrôle de CI ne peut la voir. Le 21/09/2026
 *  elle portait `acces-badges`, page fondue dans « Mes lots & accès » le 12/09 ;
 *  le 24/09, aussi `actualites` et `calendrier`, disparues avec la v2.0.0. Le
 *  menu les écarte en silence (`ordonnerPages`) — et c'est pourquoi personne ne
 *  les voyait. La CI vérifie le code, cette sonde vérifie la donnée : deux
 *  sondes indépendantes (`standards/04` §10), comme le point 19 pour les liens
 *  des courriels.
 *
 *  Verdicts :
 *    OK      — chaque identifiant servi est une page connue, une seule fois ;
 *    ECART   — un fantôme, sans effet : à nettoyer, pas à bloquer ;
 *    FAIL    — un identifiant RÉPÉTÉ : l'écran figé du 16/09 (`each_key_duplicate`) ;
 *    INCONNU — rien de lisible : ni la production, ni la table du code.
 *
 *  Usage : node front/scripts/sonde-pages-order.mjs --site https://5hostachy.fr
 *          node front/scripts/sonde-pages-order.mjs --selftest
 *  Sortie : « VERDICT<TAB>détail » sur une ligne — lue par le point 20 du pré-check.
 */
import { idsDePages } from './lib-pages.mjs';

/** Décision PURE : `servi` = liste lue en production (ou null), `connus` = ids du code. */
export function verdictPagesOrder(servi, connus) {
	if (!Array.isArray(servi))
		return ['INCONNU', 'pages_order illisible dans la configuration servie'];
	//  Cas zéro : une table du code vide rendrait tout « fantôme » — ou, pire,
	//  une liste servie vide rendrait « OK » sans rien avoir comparé.
	if (connus.length < 5) return ['INCONNU', `table du code quasi vide (${connus.length} page(s))`];
	if (servi.length === 0) return ['OK', "aucun ordre enregistré — le menu suit l'ordre du code"];
	const repetes = [...new Set(servi.filter((id, i) => servi.indexOf(id) !== i))];
	if (repetes.length) return ['FAIL', `identifiant(s) répété(s) : ${repetes.join(', ')}`];
	const fantomes = servi.filter((id) => !connus.includes(id));
	if (fantomes.length)
		return ['ECART', `identifiant(s) sans page : ${fantomes.join(', ')} — à retirer`];
	return ['OK', `${servi.length} identifiant(s), tous connus`];
}

async function sonder(site) {
	let servi;
	try {
		const reponse = await fetch(`${site.replace(/\/$/, '')}/api/config`);
		const config = await reponse.json();
		servi =
			typeof config.pages_order === 'string' ? JSON.parse(config.pages_order) : config.pages_order;
	} catch {
		servi = null;
	}
	return verdictPagesOrder(servi, idsDePages());
}

function selftest() {
	const connus = ['a', 'b', 'c', 'd', 'e'];
	const cas = [
		[['a', 'b'], 'OK'],
		[[], 'OK'],
		[['a', 'fantome'], 'ECART'],
		[['a', 'b', 'a'], 'FAIL'],
		//  Une répétition l'emporte sur un fantôme : c'est elle qui fige l'écran.
		[['a', 'a', 'fantome'], 'FAIL'],
		[null, 'INCONNU'],
		['pas une liste', 'INCONNU'],
	];
	let echecs = 0;
	for (const [servi, attendu] of cas) {
		const [obtenu] = verdictPagesOrder(servi, connus);
		if (obtenu !== attendu) {
			console.error(`✗ ${JSON.stringify(servi)} : attendu ${attendu}, obtenu ${obtenu}`);
			echecs++;
		}
	}
	if (verdictPagesOrder(['a'], ['a'])[0] !== 'INCONNU') {
		console.error('✗ cas zéro : une table du code quasi vide doit rendre INCONNU');
		echecs++;
	}
	//  La lecture du code elle-même : sans elle, la sonde comparerait à du vide.
	if (idsDePages().length < 5) {
		console.error(`✗ idsDePages() ne lit que ${idsDePages().length} page(s) dans le code`);
		echecs++;
	}
	if (echecs) process.exit(1);
	console.log(
		`✓ verdictPagesOrder : ${cas.length + 1} cas, et ${idsDePages().length} pages lues dans le code.`,
	);
}

const args = process.argv.slice(2);
if (args[0] === '--selftest') selftest();
else if (args[0] === '--site' && args[1]) {
	const [verdict, detail] = await sonder(args[1]);
	console.log(`${verdict}\t${detail}`);
} else {
	console.error('usage : sonde-pages-order.mjs --site <url> | --selftest');
	process.exit(2);
}
