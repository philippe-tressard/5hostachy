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
	cleSource,
	clesDesEvenements,
	frequenceAnnuelle,
	moisOccurrence,
	planifier,
	resumePlan,
	titreBase,
	titreOccurrence,
	sourcesDesContrats,
	sourcesDesEvenements,
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
	contrat_id: 42,
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

// ── La clé par SOURCE, et sa rétro-compatibilité ────────────────────────────
//
//  🔴 C'est ici que se joue le même risque que `titreBase` en son temps : les
//  visites créées AVANT le 01/09/2026 ne portent aucun `contrat_id`. Rapprocher
//  uniquement par la source ferait recréer l'exercice entier au premier clic —
//  le défaut qu'on corrige, en pire.

verifier(
	'cleSource : deux contrats différents ne se confondent pas',
	cleSource(42, 0) === cleSource(43, 0),
	false,
);
verifier(
	'cleSource : deux occurrences du même contrat non plus',
	cleSource(42, 0) === cleSource(42, 1),
	false,
);

//  Une visite existante reconnue par sa SOURCE : le titre a beau avoir changé —
//  contrat renommé, prestataire renommé — elle n'est pas recréée. C'est tout
//  l'objet de ce lot.
const titreChange = planifier(
	[source({ titre: 'AUTRE NOM COMPLÈTEMENT', frequence_valeur: 2 })],
	new Set([cleSource(42, 0), cleSource(42, 1)]),
	2027,
);
verifier('planifier : le contrat renommé ne recrée RIEN', titreChange.aCreer.length, 0);
verifier('planifier : … et le dit', titreChange.ignores, 2);

//  Le repli par titre reste actif pour l'existant sans `contrat_id`.
const ancienStyle = planifier(
	[source({ frequence_valeur: 2 })],
	new Set([clePlanifiee('Otis — Ascenseur A', 0), clePlanifiee('Otis — Ascenseur A', 6)]),
	2027,
);
verifier(
	'planifier : les visites d’avant la migration restent reconnues',
	ancienStyle.aCreer.length,
	0,
);

//  🔴 Le cas que le mois ne savait pas traiter : la fréquence passe de 2 à 3.
//  Par titre + mois, les deux anciennes ne correspondent plus (les mois ont
//  bougé) et l'on obtient TROIS nouvelles, soit cinq visites. Par source, les
//  index 0 et 1 correspondent et seule la troisième est créée.
const frequenceChangee = planifier(
	[source({ frequence_valeur: 3 })],
	new Set([cleSource(42, 0), cleSource(42, 1)]),
	2027,
);
verifier(
	'planifier : de 2 à 3 par an, une seule visite ajoutée',
	frequenceChangee.aCreer.length,
	1,
);

//  Une source SANS contrat — un événement de maintenance saisi à la main — ne
//  doit pas planter, ni se rapprocher d'une clé de contrat.
const sansContrat = planifier(
	[source({ contrat_id: null, frequence_valeur: 1 })],
	new Set([cleSource(42, 0)]),
	2027,
);
verifier(
	'planifier : une source sans contrat ignore la clé de source',
	sansContrat.aCreer.length,
	1,
);

//  L'événement fabriqué PORTE son contrat : sans cela la clé de source serait
//  écrite mais jamais relue, et le lot suivant recréerait tout.
verifier(
	'planifier : l’événement créé porte son contrat_id',
	planifier([source({ frequence_valeur: 1 })], new Set(), 2027).aCreer[0].contrat_id,
	42,
);

// ── Les clés des visites DÉJÀ posées ────────────────────────────────────────
//
//  Cette fonction vivait dans l'écran, où rien ne l'éprouvait — et c'est elle qui
//  décide si le clic recrée ou non l'exercice entier.

const visite = (over) => ({
	titre: 'Otis — Ascenseur A',
	debut: '2027-03-15T09:00',
	type: 'maintenance_recurrente',
	archivee: false,
	contrat_id: 42,
	...over,
});

verifier(
	'clesDesEvenements : une visite avec contrat rend DEUX clés',
	clesDesEvenements([visite()], 2027).size,
	2,
);
verifier(
	'clesDesEvenements : une visite d’avant la migration n’en rend qu’une',
	clesDesEvenements([visite({ contrat_id: null })], 2027).size,
	1,
);
//  L'index se déduit du RANG par date, pas de l'ordre du tableau : l'API rend
//  les événements dans un ordre qui n'est pas garanti.
verifier(
	'clesDesEvenements : l’index suit la DATE, pas l’ordre reçu',
	[
		...clesDesEvenements(
			[visite({ debut: '2027-09-15T09:00' }), visite({ debut: '2027-03-15T09:00' })],
			2027,
		),
	].includes(cleSource(42, 0)),
	true,
);
//  Les trois filtres, chacun pour lui-même : un archivé, un autre type, un autre
//  exercice ne doivent RIEN produire — sinon le pré-remplissage se croirait déjà
//  fait et n'écrirait rien du tout.
verifier(
	'clesDesEvenements : une visite archivée est ignorée',
	clesDesEvenements([visite({ archivee: true })], 2027).size,
	0,
);
verifier(
	'clesDesEvenements : un autre type est ignoré',
	clesDesEvenements([visite({ type: 'maintenance' })], 2027).size,
	0,
);
verifier(
	'clesDesEvenements : un autre exercice est ignoré',
	clesDesEvenements([visite({ debut: '2026-03-15T09:00' })], 2027).size,
	0,
);
//  Le cas zéro : aucune visite, aucune clé — et surtout pas une erreur.
verifier('clesDesEvenements : liste vide', clesDesEvenements([], 2027).size, 0);

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

// ── Les contrats ÉCHUS, et ce que « échu » veut dire ────────────────────────
//
//  🔴 Ces vingt lignes vivaient dans `calendrier/+page.svelte`, où RIEN ne les
//  éprouvait — le point 4 de #605 reprochait exactement cela aux fonctions de
//  calcul avant leur extraction, et le filtre `echu` a été ajouté au même
//  endroit aveugle le 01/09/2026.

const ctx = {
	nomPrestataire: (id) => (id === 7 ? 'Chauffagiste' : 'Prestataire'),
	perimetreDuBatiment: (id) => (id ? `bat:${id}` : 'résidence'),
};

const contrat = (extra = {}) => ({
	id: 1,
	libelle: 'Chaudière',
	prestataire_id: 7,
	batiment_id: 2,
	frequence_type: 'fois_par_an',
	frequence_valeur: 2,
	notes: null,
	echu: false,
	...extra,
});

const courant = sourcesDesContrats([contrat()], ctx);
verifier('sourcesDesContrats : un contrat courant devient une source', courant.sources.length, 1);
verifier('sourcesDesContrats : aucun échu à signaler', courant.echus, 0);
verifier(
	'sourcesDesContrats : le titre porte le nom du prestataire',
	courant.sources[0].titre,
	'Chauffagiste — Chaudière',
);
verifier(
	'sourcesDesContrats : le périmètre vient du bâtiment',
	courant.sources[0].perimetre,
	'bat:2',
);
verifier('sourcesDesContrats : la source porte son contrat', courant.sources[0].contrat_id, 1);

const echu = sourcesDesContrats([contrat({ echu: true })], ctx);
verifier('sourcesDesContrats : un contrat échu ne devient pas une source', echu.sources.length, 0);
verifier('sourcesDesContrats : et il est COMPTÉ, pas tu', echu.echus, 1);

//  🔴 Le cas qui distingue « échu » de « expiré », et qui est le cœur de la
//  réponse à la question du 28/08/2026. Un contrat d'entretien sous reconduction
//  tacite n'est JAMAIS `echu` — le serveur reporte son terme d'un an tant qu'il
//  est passé. Il continue donc de générer ses visites, et c'est juste : un
//  contrat qu'on n'a pas dénoncé court. Le geste qui l'arrête est l'archivage.
const vieuxMaisReconduit = sourcesDesContrats([contrat({ echu: false })], ctx);
verifier(
	'sourcesDesContrats : reconduit tacitement ⇒ toujours une source',
	vieuxMaisReconduit.sources.length,
	1,
);

//  Le compte remonte jusqu'au message : une décision qui écarte silencieusement
//  se lit comme une absence de matière.
const planAvecEchus = planifier([], new Set(), 2027, 3);
verifier('planifier : le compte des échus est transmis', planAvecEchus.echus, 3);
verifier(
	'resumePlan : les échus sont NOMMÉS dans le message',
	resumePlan(planAvecEchus, 2027),
	'Rien à créer pour 2027 — 3 contrat(s) échu(s) écarté(s).',
);

// ── Les événements de maintenance saisis à la main ──────────────────────────
const evenement = (extra = {}) => ({
	type: 'maintenance',
	titre: 'Ramonage',
	prestataire_id: 9,
	batiment_id: 3,
	perimetre: null,
	frequence_type: 'fois_par_an',
	frequence_valeur: 1,
	description: null,
	...extra,
});

verifier(
	'sourcesDesEvenements : un autre type est ignoré',
	sourcesDesEvenements([evenement({ type: 'travaux' })], ctx).length,
	0,
);
verifier(
	'sourcesDesEvenements : sans prestataire, ignoré',
	sourcesDesEvenements([evenement({ prestataire_id: null })], ctx).length,
	0,
);
verifier(
	'sourcesDesEvenements : archivé, ignoré',
	sourcesDesEvenements([evenement({ archivee: true })], ctx).length,
	0,
);
//  🔴 LE CORRECTIF DE #605, ÉPINGLÉ. Cette branche posait `ev.perimetre ?? ''`,
//  donc une chaîne VIDE quand l'événement n'en portait pas, là où la branche des
//  contrats calculait celui du bâtiment.
verifier(
	'sourcesDesEvenements : sans périmètre, celui du bâtiment',
	sourcesDesEvenements([evenement()], ctx)[0].perimetre,
	'bat:3',
);
verifier(
	'sourcesDesEvenements : avec périmètre, on garde le sien',
	sourcesDesEvenements([evenement({ perimetre: 'parking' })], ctx)[0].perimetre,
	'parking',
);
//  Un événement saisi à la main n'a pas de contrat : sa clé anti-doublon reste
//  le titre, et c'est le repli que `planifier` documente.
verifier(
	'sourcesDesEvenements : aucun contrat_id',
	sourcesDesEvenements([evenement()], ctx)[0].contrat_id,
	null,
);

if (echecs.length) {
	console.error(`\n✗ check-init-prestataires : ${echecs.length} cas en échec\n`);
	for (const e of echecs) console.error(`   ${e}\n`);
	process.exit(1);
}
console.log(
	`✓ check-init-prestataires — ${cas} cas : fréquences, répartition, numéro d’occurrence ` +
		'(et sa rétro-compatibilité), clé par SOURCE et son repli, plafond parlant, ' +
		'contrats échus écartés ET comptés, normalisation des deux sources, cas zéro.',
);
