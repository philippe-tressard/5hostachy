#!/usr/bin/env node
/**
 * Garde-fou — **un libellé nomme quelque chose, ou il ne nomme rien du tout.**
 *
 * ## Pourquoi (#561, 28/08/2026)
 *
 * `svelte-check` signalait **quinze** `A form label must be associated with a
 * control`, dans six écrans. Toujours le même motif : un `<label>` qui nomme un
 * **groupe** de contrôles — des pastilles, des cases à cocher, un éditeur riche —
 * ce qu'un `<label>` ne sait pas faire.
 *
 * ```svelte
 * <label>Périmètre *</label>            <!-- ❌ n'associe rien -->
 * <PerimetrePicker … />
 * ```
 *
 * 🔴 **Un lecteur d'écran n'annonçait rien** en entrant dans ces groupes. Et le
 * projet CONNAISSAIT la règle : `ux-patterns` §9 septies l'écrit noir sur blanc —
 * *« les pastilles et l'éditeur riche ne sont PAS labelables : un `for` posé
 * dessus n'associe rien, ET LE FAIT EN SILENCE »*. Elle est écrite à trois
 * endroits, et rien ne l'appliquait.
 *
 * ## Le remède, qui existait déjà
 *
 * `<span class="libelle-groupe" id="…">` + `role="group" aria-labelledby="…"` —
 * exactement ce que `SectionFormulaire` fait, et ce que `RichEditor` attendait par
 * sa prop `ariaLabelledby`, **exposée depuis toujours et employée par aucun des
 * six appels**. Aucun mécanisme n'a été inventé : ils étaient là.
 *
 * ## Pourquoi ce contrôle peut être bloquant, lui
 *
 * Parce que la famille est à **zéro**. C'est la méthode de `check-css-orphelin`
 * (#557) : prendre UNE famille d'avertissements, la ramener à zéro, puis la rendre
 * bloquante — elle seule. Les 30 « clics sans clavier » de #561 restent des
 * avertissements, parce qu'ils ne sont pas encore soldés et qu'un job rouge en
 * permanence est un job désarmé (#419).
 *
 * ⚠️ Le tuyau — lancer `svelte-check`, retirer les couleurs, reconnaître un
 * rapport valide, apparier chaque message à son emplacement — vit dans
 * `lib-svelte-check.mjs`. Il n'est PAS recopié ici : quatre gestes délicats dont
 * deux ont déjà coûté un défaut à ce dépôt.
 *
 * Usage : `npm run lint:libelles`
 *   exit 0 = aucun libellé orphelin hors exception
 *   exit 1 = libellé orphelin, ou exception devenue inutile
 *   exit 2 = INCONNU (`svelte-check` n'a pas pu être mesuré)
 */
import { avertissements, lignesDuRapport } from './lib-svelte-check.mjs';

/**
 * Libellés non associés TOLÉRÉS, par `fichier:ligne`, avec leur raison.
 *
 * ⚠️ Une entrée qui ne sert plus FAIT ÉCHOUER le contrôle. La liste ne peut que
 * décroître.
 *
 * Elle est vide, et c'est le but : les quinze ont été réparés AVANT que ce
 * contrôle ne devienne bloquant. Un garde-fou posé sur une dette non soldée est
 * un job rouge en permanence, donc un job désarmé.
 */
const TOLERANCES = {};

const MARQUEUR = 'A form label must be associated with a control';

const trouves = avertissements(lignesDuRapport(), MARQUEUR);
const cle = (a) => `${a.fichier}:${a.ligne}`;

const fautifs = trouves.filter((a) => !(cle(a) in TOLERANCES));
const inutiles = Object.keys(TOLERANCES).filter((k) => !trouves.some((a) => cle(a) === k));

if (fautifs.length || inutiles.length) {
	console.error(`\n✗ ${fautifs.length} libellé(s) qui ne nomment rien\n`);
	for (const a of fautifs) console.error(`   ${a.fichier}:${a.ligne}`);
	for (const k of inutiles) {
		console.error(`   ✗ tolérance « ${k} » devenue inutile : la retirer de TOLERANCES`);
	}
	console.error(
		'\n  Un `<label>` ne sait nommer QU\'UN contrôle, et un seul. Posé devant un\n' +
			'  groupe — pastilles, cases à cocher, éditeur riche — il n\'associe rien,\n' +
			'  ET IL LE FAIT EN SILENCE : le lecteur d\'écran n\'annonce pas le champ.\n\n' +
			'  Deux remèdes, tous deux DÉJÀ en service dans ce dépôt :\n\n' +
			'   • contrôle labelable (`input`, `select`, `textarea`) →\n' +
			'       <label for="x">…</label> <input id="x" …>\n\n' +
			'   • GROUPE (pastilles, cases, `RichEditor`, `PerimetrePicker`) →\n' +
			'       <span class="libelle-groupe" id="x-titre">…</span>\n' +
			'       <div role="group" aria-labelledby="x-titre"> … </div>\n\n' +
			'     `RichEditor` expose `ariaLabelledby`, et `SectionFormulaire` `idTitre` :\n' +
			'     s\'en servir plutôt que d\'inventer un second mécanisme.\n\n' +
			'  ⚠️ `.libelle-groupe` vit dans `styles/composants.css`, PAS dans la page :\n' +
			'     une notion partagée écrite dans un écran est nue partout ailleurs (#562).\n',
	);
	process.exit(1);
}

console.log(
	`✓ Libellés : aucun libellé sans contrôle associé (${Object.keys(TOLERANCES).length} toléré(s) et déclaré(s)).`,
);
