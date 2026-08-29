/**
 * Auto-test de `$lib/init-prestataires.ts` — le pré-remplissage du kanban.
 *
 * 🔴 POURQUOI il existe (#605, 28/08/2026). Cette décision vivait dans
 * `calendrier/+page.svelte`, en deux boucles quasi identiques, et **rien ne
 * l'éprouvait** : le front n'a pas de lanceur de tests, et `annualFreq` /
 * `spreadMonth` sont précisément les fonctions dont une erreur produit des
 * cartes au mauvais mois — ce qui ne se voit qu'en regardant le kanban, donc
 * jamais. C'est le motif de `check-reliability` (11/08/2026) : une logique de
 * décision qu'aucun contrôle ne touche peut devenir muette sans que personne ne
 * le sache.
 *
 * Le pattern est celui des scripts d'infra — fonction PURE + `--selftest` — et
 * il s'applique ici au TypeScript du front : Node lit les `.ts` nativement, donc
 * le module testé est **celui que le site embarque**, pas une copie.
 *
 * Usage : node --experimental-strip-types scripts/check-init-prestataires.mjs --selftest
 *
 * ⚠️ Le drapeau est passé explicitement : il est sans effet sur Node 24 (le
 * poste) et nécessaire sur les Node 22 antérieurs à 22.18. La CI épingle
 * `node-version: '22'`, qui résout la dernière 22.x — mais un contrôle ne doit
 * pas dépendre de la version que résout un jour un gestionnaire de versions.
 */
import {
	OCCURRENCES_MAX_AN,
	clePlanifiee,
	frequenceAnnuelle,
	moisOccurrence,
	planifier,
	resumePlan,
	titreBase,
	titreOccurrence,
} from '../src/lib/init-prestataires.ts';

const echecs = [];
//  Compté, jamais écrit en dur : un nombre recopié dans le message de succès
//  devient faux au premier cas ajouté, et un contrôle qui se décrit faux se lit
//  mal — on croit couvrir vingt-cinq cas alors qu'on en couvre douze.
let cas = 0;
const verifier = (nom, obtenu, attendu) => {
	cas++;
	const a = JSON.stringify(attendu);
	const o = JSON.stringify(obtenu);
	if (o !== a) echecs.push(`${nom}\n      attendu ${a}\n      obtenu  ${o}`);
};

const source = (over) => ({
	titre: 'Otis — Ascenseur A',
	frequence_type: 'fois_par_an',
	frequence_valeur: 2,
	prestataire_id: 7,
	perimetre: 'batiment-a',
	description: null,
	...over,
});

// ── Fréquence : les trois unités, et le cas zéro ────────────────────────────

verifier('frequenceAnnuelle : fois_par_an', frequenceAnnuelle('fois_par_an', 4), 4);
verifier('frequenceAnnuelle : tous les 3 mois', frequenceAnnuelle('mois', 3), 4);
verifier('frequenceAnnuelle : toutes les 26 semaines', frequenceAnnuelle('semaines', 26), 2);
verifier('frequenceAnnuelle : type inconnu', frequenceAnnuelle('lunes', 2), 0);
verifier('frequenceAnnuelle : type absent', frequenceAnnuelle(null, 2), 0);
//  🔴 Le cas qui tenait par accident : `12 / 0` vaut Infinity, qui passe le test
//  « > 0 » et n'était écarté que par le plafond. Un garde qui tient par hasard
//  tient jusqu'au jour où le plafond bouge.
verifier('frequenceAnnuelle : valeur nulle ne rend PAS Infinity', frequenceAnnuelle('mois', 0), 0);
verifier('frequenceAnnuelle : valeur négative', frequenceAnnuelle('mois', -3), 0);

// ── Répartition dans l'année ────────────────────────────────────────────────

verifier(
	'moisOccurrence : 4 visites tombent en janvier, avril, juillet, octobre',
	[0, 1, 2, 3].map((i) => moisOccurrence(4, i)),
	[1, 4, 7, 10],
);
verifier('moisOccurrence : une visite unique tombe en janvier', moisOccurrence(1, 0), 1);
verifier('moisOccurrence : cas zéro ne divise pas par zéro', moisOccurrence(0, 0), 1);

// ── Numéro d'occurrence — le cœur du lot ────────────────────────────────────

verifier(
	'titreOccurrence : une visite unique ne porte PAS de numéro',
	titreOccurrence('Otis — Ascenseur A', 0, 1),
	'Otis — Ascenseur A',
);
//  🔴 LA FRONTIÈRE, et elle a failli manquer. Les deux cas ci-dessus (1 et 4)
//  passaient encore après avoir remplacé `>= 2` par `>= 3` dans le module — le
//  test ne touchait pas la règle qu'il prétendait poser. Vérifié en cassant,
//  pas en relisant : c'est la seule façon de savoir qu'un cas mord.
verifier(
	'titreOccurrence : DEUX occurrences sont numérotées — c’est la frontière',
	[0, 1].map((i) => titreOccurrence('Otis — Ascenseur A', i, 2)),
	['Otis — Ascenseur A (1/2)', 'Otis — Ascenseur A (2/2)'],
);
verifier(
	'titreOccurrence : à partir de deux, le numéro distingue les cartes',
	[0, 1, 2, 3].map((i) => titreOccurrence('Otis — Ascenseur A', i, 4)),
	[
		'Otis — Ascenseur A (1/4)',
		'Otis — Ascenseur A (2/4)',
		'Otis — Ascenseur A (3/4)',
		'Otis — Ascenseur A (4/4)',
	],
);

//  🔴 LE cas qui protège la production. Sans normalisation, l'arrivée du numéro
//  aurait fait échouer TOUTES les correspondances d'un coup, et le premier clic
//  après la mise en production aurait recréé l'exercice entier en double.
verifier(
	'titreBase : un titre déjà numéroté retrouve sa base',
	titreBase('Otis — Ascenseur A (2/4)'),
	'Otis — Ascenseur A',
);
verifier(
	'titreBase : un titre sans numéro ne bouge pas',
	titreBase('Otis — Ascenseur A'),
	'Otis — Ascenseur A',
);
verifier(
	'clePlanifiee : un ancien titre NON numéroté et le nouveau donnent la MÊME clé',
	clePlanifiee('Otis — Ascenseur A', 3),
	clePlanifiee('Otis — Ascenseur A (2/4)', 3),
);

// ── Le plan ─────────────────────────────────────────────────────────────────

const planNeuf = planifier([source({ frequence_valeur: 4 })], new Set(), 2027);
verifier('planifier : quatre occurrences pour une fréquence 4/an', planNeuf.aCreer.length, 4);
verifier(
	'planifier : la date porte l’exercice demandé et le 15 du mois',
	planNeuf.aCreer.map((e) => e.debut),
	['2027-01-15T09:00', '2027-04-15T09:00', '2027-07-15T09:00', '2027-10-15T09:00'],
);
verifier(
	'planifier : le périmètre de la source est repris tel quel',
	[...new Set(planNeuf.aCreer.map((e) => e.perimetre))],
	['batiment-a'],
);
verifier(
	'planifier : les événements naissent dans la colonne Prestataire, non affichables',
	[planNeuf.aCreer[0].statut_kanban, planNeuf.aCreer[0].affichable],
	['fournisseur', false],
);

//  Ce qui existe déjà n'est pas recréé — y compris quand l'existant porte
//  l'ANCIEN titre, sans numéro. C'est la rétro-compatibilité, vérifiée.
const dejaLa = new Set([clePlanifiee('Otis — Ascenseur A', 0)]);
const planPartiel = planifier([source({ frequence_valeur: 4 })], dejaLa, 2027);
verifier('planifier : l’occurrence existante est ignorée', planPartiel.ignores, 1);
verifier('planifier : les trois autres restent à créer', planPartiel.aCreer.length, 3);

//  🔴 Le plafond ne se tait plus : c'est le défaut nommé par #605.
const planTropFrequent = planifier(
	[source({ titre: 'Veolia — Chaufferie', frequence_type: 'mois', frequence_valeur: 1 })],
	new Set(),
	2027,
);
verifier('planifier : au-delà du plafond, rien n’est créé', planTropFrequent.aCreer.length, 0);
verifier(
	'planifier : … mais la source écartée est NOMMÉE, avec sa fréquence',
	planTropFrequent.horsPlafond,
	[{ titre: 'Veolia — Chaufferie', parAn: 12 }],
);
verifier(
	'resumePlan : le message dit ce qui a été écarté, au lieu de « aucune source »',
	resumePlan(planTropFrequent, 2027).includes('Veolia — Chaufferie (12/an)'),
	true,
);
verifier(
	'resumePlan : … et il nomme le plafond appliqué',
	resumePlan(planTropFrequent, 2027).includes(`au-delà de ${OCCURRENCES_MAX_AN}/an`),
	true,
);

//  Une source sans fréquence n'est pas une source écartée : elle n'en est pas une.
const planSansFreq = planifier(
	[source({ frequence_type: null, frequence_valeur: null })],
	new Set(),
	2027,
);
verifier('planifier : sans fréquence, comptée à part', planSansFreq.sansFrequence, 1);
verifier('planifier : sans fréquence, rien à créer', planSansFreq.aCreer.length, 0);

//  Cas zéro de l'appelant : aucune source ne doit rien inventer, et le message
//  doit le dire sans laisser croire qu'on a écarté quelque chose.
const planVide = planifier([], new Set(), 2027);
verifier('planifier : cas zéro', [planVide.aCreer.length, planVide.horsPlafond.length], [0, 0]);
verifier(
	'resumePlan : cas zéro dit « aucune source », pas « rien à créer »',
	resumePlan(planVide, 2027),
	'Aucune source de maintenance récurrente pour 2027.',
);

if (echecs.length) {
	console.error(`\n✗ check-init-prestataires : ${echecs.length} cas en échec\n`);
	for (const e of echecs) console.error(`   ${e}\n`);
	process.exit(1);
}
console.log(
	`✓ check-init-prestataires — ${cas} cas : fréquences, répartition, numéro d’occurrence ` +
		'(et sa rétro-compatibilité), plafond parlant, cas zéro.',
);
