/**
 * Garde-fou — **un champ de Workflow qu'on voit et qui ne part pas**.
 *
 * ## Le défaut (#435, trouvé le 17/08/2026, corrigé le 19)
 *
 * `FormulaireTicket` affichait la rangée de pastilles Workflow **en création** :
 * elles se rendaient, se cliquaient, changeaient d'aspect. Et la charge utile du
 * `POST` ne portait pas `statut` — le ticket repartait toujours en « Ouvert ».
 *
 * Le serveur, lui, l'acceptait depuis le 16/08, avec une liste blanche dérivée de
 * l'énumération et réservée au CS. **Rien n'était cassé côté serveur : c'est le
 * front qui ne demandait pas.** Un champ qu'on voit et qui ne fait rien est la
 * même faute que le `200` qui n'écrit rien, dans l'autre sens — il fabrique une
 * confiance qu'il devrait retirer.
 *
 * Le défaut est devenu visible quand le cadre #430 a proposé la section Workflow
 * aux quatre rendus : la même section **fonctionne** sur les publications
 * (`statut` part bien dans le `POST`) et ne faisait rien sur les tickets. Deux
 * entités divergentes sur un champ que le cadre déclare identique.
 *
 * ## Ce que ce contrôle vérifie
 *
 * Dans tout `Formulaire*.svelte` : si `<WorkflowPastilles valeur={X}>` est rendu
 * **modifiable** (pas de `lecture` inconditionnel), alors le nom `X` doit
 * apparaître dans la charge utile construite par le fichier.
 *
 * C'est volontairement une vérification de **présence du nom**, pas une analyse
 * de flot : un contrôle large sur du JavaScript produit des faux positifs, et un
 * contrôle qu'on apprend à ignorer ne garde plus rien (`standards/04`). Il ne
 * prouve pas que la valeur arrive au serveur — il prouve que le formulaire ne
 * l'a pas simplement **oubliée**, ce qui est exactement ce qui s'est produit.
 *
 * ⚠️ La lecture d'un champ (`valeur={objet.statut}` sur une carte d'affichage)
 * n'est pas concernée : seuls les fichiers `Formulaire*` sont examinés.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/** Nombre minimal de rangées de workflow attendues — cas zéro. */
const RANGEES_MINIMALES = 3;

function fichiersSvelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiersSvelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

const fichiers = fichiersSvelte(RACINE).filter((f) => /[\\/]Formulaire[^\\/]*\.svelte$/.test(f));
if (fichiers.length === 0) {
	console.error('✗ Cas zéro : aucun Formulaire*.svelte trouvé — arborescence changée.');
	console.error('Ne pas lire ceci comme un succès.');
	process.exit(1);
}

const erreurs = [];
let rangees = 0;

//  `<WorkflowPastilles … valeur={X} …>` — la balise entière, attributs compris.
const PASTILLES = /<WorkflowPastilles\b([^>]*)>/g;

for (const chemin of fichiers) {
	const relatif = relative(RACINE, chemin).replace(/\\/g, '/');
	const source = readFileSync(chemin, 'utf8');

	//  🔴 Les balises sont collectées d'ABORD, en une passe. Piloter la boucle par
	//  `PASTILLES.exec` tout en réutilisant `PASTILLES` dans un `replace` plus bas
	//  remettait son `lastIndex` à 0 à chaque tour : boucle infinie, contrôle qui
	//  ne rend jamais la main. Un garde-fou qui pend ne dit rien (`standards/04`).
	for (const m of [...source.matchAll(PASTILLES)]) {
		const attributs = m[1];
		const valeur = /\bvaleur=\{([^}]+)\}/.exec(attributs);
		if (!valeur) continue;
		rangees++;

		//  `lecture` sans expression = toujours en lecture : rien à envoyer.
		if (/\blecture(?!=)/.test(attributs)) continue;
		if (/\blecture=\{true\}/.test(attributs)) continue;

		//  Le nom de la variable liée, sans son chemin (`form.statut_kanban` → le
		//  nom complet sert de sonde, `statut` → `statut`).
		const expr = valeur[1]
			.trim()
			.replace(/\s*\?\?.*$/, '')
			.trim();
		const nom = expr.split('.').pop().trim();
		if (!/^[A-Za-z_$][\w$]*$/.test(nom)) continue;

		const ligne = source.slice(0, m.index).split('\n').length;

		//  Apparaît-il ailleurs que dans son propre rendu et sa déclaration ?
		//  Une charge utile l'écrit soit en abrégé (`statut,`), soit nommément
		//  (`statut: x`, `payload.statut = x`, `statut_kanban: …`).
		const dansCharge = new RegExp(`(^|[^\\w$.])${nom}\\s*[,:]|\\.${nom}\\s*=|\\b${nom}:\\s`, 'm');
		//  On retire la balise elle-même et la déclaration `let nom = …` avant de
		//  chercher : sinon le rendu se répondrait à lui-même.
		const sansRendu = source
			.replace(/<WorkflowPastilles[^>]*>/g, '')
			.replace(new RegExp(`\\blet\\s+${nom}\\b[^;\\n]*`, 'g'), '')
			.replace(new RegExp(`\\bexport\\s+let\\s+${nom}\\b[^;\\n]*`, 'g'), '');

		if (!dansCharge.test(sansRendu)) {
			erreurs.push(
				`${relatif}:${ligne} — la rangée Workflow modifie « ${nom} », et ce nom ` +
					"n'apparaît dans AUCUNE charge utile du fichier : les pastilles se cliquent " +
					'et le serveur ne reçoit rien.',
			);
		}
	}
}

if (rangees < RANGEES_MINIMALES) {
	console.error(
		`✗ Cas zéro : ${rangees} rangée(s) Workflow reconnue(s), ${RANGEES_MINIMALES} attendues au minimum.`,
	);
	console.error(
		'Trois formulaires en portaient une le 19/08/2026 (ticket, annonce, événement).\n' +
			"Un relevé qui s'effondre signale que le contrôle a cessé de voir — pas que le\n" +
			'défaut a disparu (`standards/04-fiabilite-des-controles.md` §2).',
	);
	process.exit(1);
}

if (erreurs.length) {
	console.error('✗ Section Workflow décorative — le champ se voit et ne part pas :\n');
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		"\n🔴 Le cadre interdit d'ouvrir un champ que le serveur ne consomme pas ; il\n" +
			"   interdit tout autant d'afficher un champ que le formulaire n'envoie pas.\n" +
			'   Soit la charge utile le porte, soit la rangée passe en `lecture`.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Workflow : ${rangees} rangées modifiables dans ${fichiers.length} formulaires — ` +
		'toutes présentes dans une charge utile.',
);
