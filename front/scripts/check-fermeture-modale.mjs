/**
 * Garde-fou : une modale qui contient une SAISIE ne se ferme pas au clic sur le fond.
 *
 * ## Le défaut (#640, 30/08/2026)
 *
 * `Modale.svelte` offrait deux moyens de protéger une saisie d'un clic à côté :
 * `fermetureAuFond={false}` et, depuis le même jour, `edition`. Les deux sont des
 * **déclarations** — il faut y penser.
 *
 * 🔴 Relevé sur l'écran d'administration : **trois** modales portant
 * respectivement **8, 3 et 2 champs de saisie**, et **aucune des trois** ne
 * déclarait quoi que ce soit. Un clic à côté effaçait la saisie, sans
 * confirmation et sans moyen de la retrouver.
 *
 * Trois sur trois, ce n'est pas de l'inattention : une protection qui dépend d'un
 * geste qu'on peut oublier ne protège que ceux qui y ont pensé. C'est la leçon de
 * la prop `marge` d'`EntetePage` — *tant que le mécanisme d'exception existe,
 * l'exception se reproduit.*
 *
 * La protection est donc passée **dans le composant**, qui constate son propre
 * contenu (`querySelector` sur la boîte rendue) au lieu d'attendre qu'on le lui
 * dise. Ce fichier éprouve la décision qui en résulte.
 *
 * ## Ce qu'il couvre, et ce qu'il ne couvre pas
 *
 * ⚠️ Il porte sur la **décision** (`fondFermant`), pas sur la **détection** : le
 * `querySelector` demande un navigateur, et c'est P7 qui l'exerce. La séparation
 * est délibérée — *l'autotest couvre la décision, jamais l'entrée/sortie qui
 * l'alimente* (`standards/04` §11). D'où les deux contrôles de portée en fin de
 * fichier : sans eux, ce test éprouverait sa propre copie de la règle pendant que
 * le composant ferait autre chose.
 *
 * Usage : node scripts/check-fermeture-modale.mjs --selftest
 */
import { readFileSync } from 'node:fs';

const MODALE = new URL('../src/lib/components/Modale.svelte', import.meta.url).pathname.replace(
	/^\/([A-Za-z]:)/,
	'$1',
);

/**
 * La règle, recopiée depuis `Modale.svelte`.
 *
 * ⚠️ Une recopie diverge — c'est la règle du dépôt, et elle vaut pour ce fichier
 * comme pour les autres. Le contrôle de portée ci-dessous vérifie donc que la
 * ligne du composant est **littéralement** celle-ci.
 */
const fondFermant = (fermetureAuFond, edition, contientSaisie) =>
	fermetureAuFond && !edition && !contientSaisie;

const CAS = [
	// [fermetureAuFond, edition, contientSaisie, attendu, libellé]
	[true, false, false, true, 'confirmation sans saisie : le fond ferme, comme avant'],
	//  🔴 LE cas de l'écran d'administration : trois modales à saisie qui ne
	//  déclaraient rien. Il doit passer au vert sans que l'écran écrive quoi que
	//  ce soit — c'est tout l'objet du correctif.
	[true, false, true, false, 'saisie constatée, RIEN déclaré : le fond ne ferme plus'],
	[true, true, false, false, 'édition déclarée : le fond ne ferme pas'],
	[false, false, false, false, 'fermetureAuFond={false} explicite : respecté'],
	[true, true, true, false, 'édition ET saisie : ne ferme pas'],
	[false, false, true, false, 'les deux raisons de ne pas fermer se cumulent'],
];

let echecs = 0;
for (const [f, e, s, attendu, libelle] of CAS) {
	const obtenu = fondFermant(f, e, s);
	if (obtenu === attendu) console.log(`PASS  ${libelle}`);
	else {
		console.error(`FAIL  ${libelle} — attendu ${attendu}, obtenu ${obtenu}`);
		echecs++;
	}
}

// ── Portée : la règle testée est-elle celle que le composant applique ? ───────
const source = readFileSync(MODALE, 'utf8');

const ATTENDU = 'fermetureAuFond && !edition && !contientSaisie';
if (source.includes(`$: fondFermant = ${ATTENDU};`)) {
	console.log('PASS  la règle testée est bien celle que le composant applique');
} else {
	console.error(
		`FAIL  Modale.svelte n'applique plus « ${ATTENDU} » — ce test éprouve une règle morte.`,
	);
	echecs++;
}

//  Cas zéro : si la détection disparaît, `contientSaisie` reste faux pour
//  toujours. La règle ci-dessus resterait juste — et ne protégerait plus rien.
//  C'est exactement le vert qu'on ne doit pas pouvoir obtenir sans mesurer.
if (/querySelector\(['"]input, textarea, select['"]\)/.test(source)) {
	console.log('PASS  la détection des champs de saisie est en place');
} else {
	console.error(
		'FAIL  la détection des champs a disparu de Modale.svelte — `contientSaisie` ne peut plus ' +
			'devenir vrai, et la protection ne joue plus pour personne.',
	);
	echecs++;
}

if (echecs > 0) {
	console.error(`\n✗ ${echecs} échec(s).`);
	process.exit(1);
}
console.log(`\n✓ Fermeture au fond : ${CAS.length} cas + 2 contrôles de portée.`);
