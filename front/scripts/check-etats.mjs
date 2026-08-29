/**
 * Garde-fou R4 — **une divergence entre deux états se déclare, avec son motif.**
 *
 * ## Pourquoi (cadre #430, lot #431, 17/08/2026)
 *
 * Le relevé des 42 couples menu/entité a mesuré que **13 éditions sur 23**
 * réinventaient un motif que la création portait déjà, et que **5 seulement**
 * portaient une raison écrite. Les cinq étaient dans `FormulaireTicket`, en
 * commentaires — donc invisibles à tout contrôle, et libres de mentir dès le lot
 * suivant. C'est exactement ce qui est arrivé le 17/08 au matin : le commentaire
 * disait « l'état se change depuis le fil, pour qu'il y laisse une trace », un
 * motif (`trace`) que le cadre n'a jamais reconnu.
 *
 * R4 est la clé de voûte du cadre, et la seule règle que l'utilisateur n'avait
 * pas demandée : **sans elle, les cinq autres s'érodent en silence.**
 *
 * ## Ce que ce contrôle REFUSE
 *
 *   1. une entité dont les sections ne sont pas **les neuf, dans l'ordre** ;
 *   2. une section qui ne dit ni ce qu'elle porte (`objet`) ni pourquoi l'entité
 *      ne la porte pas (`sansObjet`) ;
 *   3. **une divergence sans motif**, ou avec un motif hors des trois admis ;
 *   4. **un motif `api` sans ticket** — c'est un marqueur de dette, pas un choix
 *      de conception : il doit citer l'issue qui la fera tomber ;
 *   5. une section rendue **hors déclaration** : dans un écran qui consomme une
 *      entité, `avecPerimetre`, `avecPhotos`… doivent être gouvernés par
 *      `sectionPresente(…)` et par rien d'autre. Une condition en dur
 *      (`{!modeEdition}`) rouvre très exactement la divergence silencieuse que
 *      le cadre supprime ;
 *   6. un **intitulé de section** qui n'est ni le libellé de la section ni celui
 *      que la déclaration annonce (`titreEcran`) — R3 : le même libellé d'un
 *      formulaire à l'autre.
 *
 *   7. **une prop d'`EvolForm` qui ouvre une section hors déclaration** — l'état
 *      `evolution`, ajouté le 28/08/2026 (#463). Voir `lib-etats-evolution.mjs`.
 *
 * ## Ce que ce paragraphe disait, et qui était devenu FAUX
 *
 * Il annonçait : *« `EvolForm.svelte` n'est pas un consommateur (…) l'état
 * `evolution` est donc déclaré et vérifié en tant que déclaration, pas encore
 * confronté à son rendu »*. C'était exact quand il a été écrit — et c'est resté
 * là après que six entités eurent déclaré l'état, sans que rien ne le confronte.
 *
 * 🔴 La portée du contrôle était plus étroite que la règle qu'il défend, et il
 * rendait **vert**. Même faiblesse que #562, à l'autre bout du dépôt
 * (`standards/05` §9 et §9 ter). Le relevé a trouvé **onze** props hors
 * déclaration dans **six** écrans, dont un écart que personne ne voyait : l'espace
 * CS ne propose aucune diffusion sur un commentaire de ticket là où la carte de
 * ticket la propose au même utilisateur.
 *
 * ⚠️ R5 interdisant de brancher les cinq écrans d'un coup, le relevé est **figé
 * en tolérances nommées** : il vit dans le code, ne peut que décroître, et le
 * contrôle échoue dès qu'une entrée cesse de servir. Le message de succès **dit**
 * ce qui reste — un contrôle qui tait sa dette se lit « tout est branché ».
 *
 * Le contrôle s'auto-contrôle : plus de types, plus d'entité, plus de
 * consommateur, une entité que personne ne consomme, un littéral qu'il n'arrive
 * pas à lire → il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';
import { analyserEvolForm, tolerancesMortes, EVOLFORM_TOLEREES } from './lib-etats-evolution.mjs';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const DOSSIER_ENTITES = join(RACINE, 'lib', 'entites');
const TYPES = join(DOSSIER_ENTITES, 'types.ts');

const MOTIFS_ADMIS = ['geste', 'hérité', 'api'];

/**  Les six sections que `ChampsCommuns` sait rendre, et le nom de la prop qui
 *   les ouvre. Ce sont elles qui doivent passer par `sectionPresente`. */
const PROPS_SECTION = {
	avecPerimetre: 'perimetre',
	avecDestinataires: 'destinataires',
	avecDescription: 'description',
	avecPhotos: 'photos',
	avecDocuments: 'documents',
	avecDiffusion: 'diffusion',
};

const erreurs = [];
const echec = (m) => erreurs.push(m);

/** Sortie de cas zéro : on dit AUSSI ce qu'on avait déjà relevé, sinon le
 *  diagnostic s'arrête au symptôme (« 0 section lue ») sans sa cause. */
function casZero(message) {
	console.error(`✗ Cas zéro : ${message}`);
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error("Le contrôle n'a rien pu établir ; ne pas lire ceci comme un succès.");
	process.exit(1);
}

//  ── Lecture d'un littéral TypeScript ────────────────────────────────────────
//
//  Node ne sait pas importer un `.ts`. Plutôt que de relire la déclaration à
//  coups d'expressions régulières — ce qui reviendrait à en tenir une seconde
//  lecture, libre de diverger —, on EXTRAIT le littéral et on l'évalue tel quel.
//  Le scanner saute chaînes et commentaires : une accolade dans un texte
//  d'explication ne doit pas fermer l'objet.
function litteralApres(source, index) {
	//  Le littéral commence à la PREMIÈRE des deux ouvertures possibles : chercher
	//  `{` puis se rabattre sur `[` ferait ouvrir un tableau sur l'accolade d'une
	//  déclaration suivante, à des centaines de lignes de là.
	const candidats = [source.indexOf('{', index), source.indexOf('[', index)].filter((n) => n >= 0);
	if (candidats.length === 0) return null;
	let i = Math.min(...candidats);
	const ouvrants = { '{': '}', '[': ']' };
	const pile = [ouvrants[source[i]]];
	const debut = i;
	i += 1;
	while (i < source.length && pile.length) {
		const c = source[i];
		if (c === '/' && source[i + 1] === '/') {
			i = source.indexOf('\n', i);
			if (i < 0) return null;
			continue;
		}
		if (c === '/' && source[i + 1] === '*') {
			i = source.indexOf('*/', i);
			if (i < 0) return null;
			i += 2;
			continue;
		}
		if (c === "'" || c === '"' || c === '`') {
			i += 1;
			while (i < source.length && source[i] !== c) {
				if (source[i] === '\\') i += 1;
				i += 1;
			}
			i += 1;
			continue;
		}
		if (c === '{' || c === '[') pile.push(ouvrants[c]);
		else if (c === '}' || c === ']') {
			if (c !== pile[pile.length - 1]) return null;
			pile.pop();
		}
		i += 1;
	}
	return pile.length ? null : source.slice(debut, i);
}

/** Constantes de chaîne du fichier — `const DETTE_API = '#431';` et consorts. */
function prelude(source) {
	const lignes = [];
	const re = /^const\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*('[^']*'|"[^"]*")\s*;/gm;
	let m;
	while ((m = re.exec(source))) lignes.push(`const ${m[1]} = ${m[2]};`);
	return lignes.join('\n');
}

function evaluer(source, nom, litteral, chemin) {
	try {
		return new Function(`${prelude(source)}\nreturn (${litteral});`)();
	} catch (e) {
		echec(`${chemin} — impossible de lire le littéral \`${nom}\` : ${e.message}`);
		return null;
	}
}

function extraire(source, nom, chemin) {
	const ancre = source.search(new RegExp(`export\\s+const\\s+${nom}\\b`));
	if (ancre < 0) {
		echec(`${chemin} — \`${nom}\` est introuvable.`);
		return null;
	}
	//  ⚠️ On part de l'`=`, pas de l'ancre : une annotation de type porte des
	//  crochets (`readonly IdSection[]`), et démarrer avant elle faisait lire un
	//  tableau VIDE — un cas zéro qui se serait présenté comme « 0 section lue ».
	const affectation = source.slice(ancre).search(/=(?![=>])/);
	if (affectation < 0) {
		echec(`${chemin} — \`${nom}\` n'est pas une affectation.`);
		return null;
	}
	const litteral = litteralApres(source, ancre + affectation);
	if (!litteral) {
		echec(`${chemin} — le littéral de \`${nom}\` n'est pas équilibré.`);
		return null;
	}
	return evaluer(source, nom, litteral, chemin);
}

//  ── Cas zéro : de quoi ce contrôle a besoin pour contrôler quoi que ce soit ──
if (!existsSync(TYPES)) {
	casZero(`${TYPES} est introuvable — le cadre n'a plus de types, contrôle inopérant.`);
}
const srcTypes = readFileSync(TYPES, 'utf8');
for (const fonction of ['sectionPresente', 'sectionsDe']) {
	if (!new RegExp(`export function ${fonction}\\b`).test(srcTypes)) {
		casZero(
			`\`${fonction}\` n'est plus exportée par types.ts. Le contrat a changé — ` +
				'mettre ce contrôle à jour, sinon il laisse passer les sections rendues hors déclaration.',
		);
	}
}

const ORDRE = extraire(srcTypes, 'SECTIONS_ORDRE', relative(RACINE, TYPES));
const LIBELLES = extraire(srcTypes, 'SECTIONS_LIBELLE', relative(RACINE, TYPES));
if (!Array.isArray(ORDRE) || ORDRE.length !== 9) {
	casZero(`SECTIONS_ORDRE devrait porter les NEUF sections (${ORDRE?.length ?? 0} lue(s)).`);
}
if (!LIBELLES || ORDRE.some((id) => !LIBELLES[id])) {
	casZero('SECTIONS_LIBELLE ne nomme pas les neuf sections.');
}

const fichiersEntites = existsSync(DOSSIER_ENTITES)
	? readdirSync(DOSSIER_ENTITES).filter((n) => n.endsWith('.ts') && n !== 'types.ts')
	: [];
if (fichiersEntites.length === 0) {
	casZero(`aucune entité déclarée dans ${DOSSIER_ENTITES}. Ce contrôle n'a rien à garder.`);
}

//  ── Les déclarations ────────────────────────────────────────────────────────
const entites = [];
for (const nomFichier of fichiersEntites) {
	const chemin = join(DOSSIER_ENTITES, nomFichier);
	const source = readFileSync(chemin, 'utf8');
	const court = relative(RACINE, chemin);
	const m = source.match(/export\s+const\s+([A-Z][A-Z0-9_]*)\s*:\s*EntiteDeclaree\b/);
	if (!m) {
		echec(`${court} — aucune \`export const <NOM>: EntiteDeclaree\` : entité illisible.`);
		continue;
	}
	const nom = m[1];
	const decl = extraire(source, nom, court);
	if (!decl) continue;
	entites.push({ nom, decl, court });

	const ids = (decl.sections ?? []).map((s) => s.id);
	if (ids.length !== ORDRE.length || ids.some((id, i) => id !== ORDRE[i])) {
		echec(
			`${court} (${nom}) — les sections ne sont pas les neuf dans l'ordre de SECTIONS_ORDRE.\n` +
				`      déclarées : ${ids.join(' · ') || '(aucune)'}\n` +
				`      attendues : ${ORDRE.join(' · ')}`,
		);
		continue;
	}

	for (const s of decl.sections) {
		const ou = `${court} (${nom} › ${s.id})`;
		if (!s.objet && !s.sansObjet) {
			echec(`${ou} — ni \`objet\` ni \`sansObjet\` : on ne sait pas ce que porte la section.`);
		}
		if (s.sansObjet && s.absente) {
			echec(
				`${ou} — \`sansObjet\` ET \`absente\` : une notion que l'entité n'a pas ne diverge de rien. ` +
					'Choisir.',
			);
		}
		for (const [etat, div] of Object.entries(s.absente ?? {})) {
			if (!div || typeof div !== 'object') {
				echec(`${ou} — divergence illisible pour l'état « ${etat} ».`);
				continue;
			}
			if (!div.motif) {
				echec(
					`${ou} — ABSENTE en « ${etat} » SANS MOTIF. R4 : toute divergence entre deux états ` +
						`se déclare avec son motif (${MOTIFS_ADMIS.join(' · ')}).`,
				);
				continue;
			}
			if (!MOTIFS_ADMIS.includes(div.motif)) {
				echec(
					`${ou} — motif « ${div.motif} » inconnu pour l'état « ${etat} ». ` +
						`Trois motifs, trois seulement : ${MOTIFS_ADMIS.join(' · ')}.`,
				);
			}
			if (!div.explication || !String(div.explication).trim()) {
				echec(
					`${ou} — divergence en « ${etat} » sans \`explication\` : un motif nu ne se relit pas.`,
				);
			}
			if (div.motif === 'api' && !/^#\d+$/.test(String(div.ticket ?? ''))) {
				echec(
					`${ou} — motif \`api\` en « ${etat} » SANS TICKET. C'est un marqueur de DETTE, jamais ` +
						"de conception : il doit citer l'issue qui la fera tomber (forme « #431 »).",
				);
			}
		}
	}
}

//  ── Les consommateurs : ce qui est rendu doit venir de la déclaration ───────
function svelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...svelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

/** Retire commentaires et balisage commenté : expliquer la règle ne l'enfreint pas. */

const tousSvelte = svelte(RACINE);
if (tousSvelte.length === 0) {
	casZero("aucun composant analysé — l'arborescence a changé.");
}

const nomsEntites = new Set(entites.map((e) => e.nom));
const entitesConsommees = new Set();
let consommateurs = 0;

//  Les intitulés qu'une section peut porter à l'écran : son libellé générique, ou
//  celui que la déclaration annonce quand la section n'a qu'un champ (le titre EST
//  alors le libellé du champ — `SectionFormulaire`).
const titresAdmis = new Set(Object.values(LIBELLES));
for (const { decl } of entites) {
	//  `titreEcran` peut être une LISTE : une section qui groupe plusieurs champs
	//  nommés en porte un par champ (la section 2 du ticket : « Catégorie » et
	//  « Saisi pour »). Une section reste une section — c'est son contenu qui a
	//  plusieurs noms, pas elle qui se scinde.
	for (const s of decl.sections ?? []) {
		for (const t of [s.titreEcran ?? []].flat()) titresAdmis.add(t);
	}
}

for (const chemin of tousSvelte) {
	const brut = readFileSync(chemin, 'utf8');
	//  `import type` ne consomme rien : seul un import de VALEUR fait de ce
	//  fichier un rendu gouverné par la déclaration.
	const importe = [
		...brut.matchAll(/import\s+(?!type\b)\{([^}]*)\}\s+from\s+'\$lib\/entites\/[^']+'/g),
	];
	if (importe.length === 0) continue;
	consommateurs += 1;
	const court = relative(RACINE, chemin);
	const texte = sansCommentaires(brut);

	for (const m of importe) {
		for (const nom of m[1].split(',').map((s) => s.trim())) {
			if (nomsEntites.has(nom)) entitesConsommees.add(nom);
		}
	}

	// 5. les six sections de `ChampsCommuns` passent par `sectionPresente`
	for (const [prop, id] of Object.entries(PROPS_SECTION)) {
		const re = new RegExp(`\\b${prop}\\b(\\s*=\\s*\\{([^}]*)\\})?`, 'g');
		let m;
		while ((m = re.exec(texte))) {
			if (!m[1]) {
				echec(
					`${court} — \`${prop}\` est posée en dur (section toujours rendue). ` +
						`Elle doit être gouvernée par la déclaration : ${prop}={sectionPresente(…, '${id}')}.`,
				);
				continue;
			}
			const expr = m[2];
			if (!expr.includes('sectionPresente(') || !expr.includes(`'${id}'`)) {
				echec(
					`${court} — \`${prop}\` est gouvernée par « ${expr.trim()} », hors déclaration. ` +
						`R4 : la présence d'une section se DÉCLARE, avec son motif — ` +
						`attendu \`sectionPresente(<ENTITE>, <état>, '${id}')\`.`,
				);
			}
		}
	}

	// 7. l'état et la section cités doivent exister
	for (const m of texte.matchAll(
		/sectionPresente\(\s*([A-Za-z_$][\w$]*)\s*,\s*([^,]+),\s*'([^']+)'\s*\)/g,
	)) {
		if (!ORDRE.includes(m[3])) {
			echec(`${court} — \`sectionPresente(…, '${m[3]}')\` : section inconnue du cadre.`);
		}
		if (nomsEntites.size && !nomsEntites.has(m[1])) {
			echec(`${court} — \`sectionPresente(${m[1]}, …)\` : ce n'est pas une entité déclarée.`);
		}
	}

	// 6. les intitulés de section
	for (const m of texte.matchAll(/<Section(?:Formulaire|Lecture)\b[^>]*?\btitre="([^"]*)"/g)) {
		const titre = m[1].trim();
		if (titre && !titresAdmis.has(titre)) {
			echec(
				`${court} — intitulé de section « ${titre} » absent de la déclaration. ` +
					"R3 : le libellé est le même d'un formulaire à l'autre — le nommer dans " +
					'`SECTIONS_LIBELLE` ou dans le `titreEcran` de la section.',
			);
		}
	}
}

//  ── 8. `EvolForm` — le quatrième état, confronté à son rendu (#463) ─────────
//
//  Ce contrôle ne regardait QUE les six props de `ChampsCommuns`. `EvolForm`
//  compose ses sections avec `SectionFormulaire` directement, et lui échappait
//  ENTIÈREMENT : l'état `evolution` était déclaré par six entités et confronté à
//  son rendu par aucune. La décision et son relevé vivent dans
//  `lib-etats-evolution.mjs`, avec leur `--selftest`.
//
//  ⚠️ La passe est SÉPARÉE de la boucle ci-dessus, et c'est le point : celle-ci
//  ne visite que les fichiers qui importent une déclaration. Trois des cinq
//  écrans qui rendent `EvolForm` n'en importent aucune — les mettre dans la même
//  boucle les aurait laissés hors de portée une seconde fois.
const evolformServies = [];
for (const chemin of tousSvelte) {
	//  Chemin NORMALISÉ : sur ce poste Windows `relative()` rend des `\`, et une
	//  clé de tolérance écrite avec des `/` ne correspondrait alors jamais — le
	//  contrôle serait vert par accident, pas par mérite.
	const court = relative(RACINE, chemin).replace(/\\/g, '/');
	const { ecarts, servies } = analyserEvolForm(
		court,
		sansCommentaires(readFileSync(chemin, 'utf8')),
	);
	for (const e of ecarts) echec(e);
	evolformServies.push(...servies);
}
for (const m of tolerancesMortes(evolformServies)) {
	echec(
		`tolérance \`EVOLFORM_TOLEREES\` devenue inutile : ${m}. La retirer — une dérogation ` +
			"oubliée est une porte qu'on croit fermée, et cette liste ne peut que DÉCROÎTRE.",
	);
}

if (consommateurs === 0) {
	casZero(
		"aucun écran ne consomme une déclaration d'entité. Une déclaration que personne ne lit " +
			'est décorative — et ce contrôle vert ne prouverait rien.',
	);
}
for (const { nom, court } of entites) {
	if (!entitesConsommees.has(nom)) {
		echec(
			`${court} — l'entité \`${nom}\` n'est consommée par aucun écran. Une déclaration ` +
				'que personne ne lit diverge du produit sans que rien ne le dise.',
		);
	}
}

//  ── Verdict ────────────────────────────────────────────────────────────────
if (erreurs.length) {
	console.error("✗ Cadre d'interface (#430) — R4 : une divergence sans motif est refusée.\n");
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		"\nLes trois motifs, et il n'y en a pas d'autre :\n" +
			"  geste  — la section est un ACTE qui n'a pas lieu dans cet état\n" +
			"  hérité — la valeur vient de l'objet porteur\n" +
			'  api    — DETTE, jamais conception : doit citer un ticket\n',
	);
	process.exit(1);
}

console.log(
	`✓ Cadre d'interface : ${entites.length} entité(s) déclarée(s) sur les 9 sections, ` +
		`${consommateurs} écran(s) gouverné(s) par la déclaration, toutes divergences motivées.`,
);
//  🔴 Le vert DIT ce qu'il ne couvre pas encore. Un contrôle qui tait sa dette
//  se lit « tout est branché », et le chantier s'endort — `standards/04` §12.
if (evolformServies.length) {
	console.log(
		`  ⏳ État \`evolution\` : ${new Set(evolformServies).size} prop(s) d'EvolForm encore hors ` +
			`déclaration dans ${Object.keys(EVOLFORM_TOLEREES).length} écran(s), tolérées et suivies en #463.`,
	);
}
