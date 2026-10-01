#!/usr/bin/env node
/**
 * Garde-fou : un spec e2e prend `test` (et `expect`) dans `e2e/aides.ts`,
 * jamais directement dans `@playwright/test`.
 *
 * ## 🔴 Le défaut (#1475, 01/10/2026)
 *
 * `deconnexion.spec.ts` tombait au hasard, en CI et au rejeu : « Bonsoir »
 * sans prénom. La cause était une exception — l'API simulée rendait `[]` pour
 * le fil, et `RaccourcisRapides` lisait `undefined.tickets_ouverts`. Elle
 * interrompait la mise à jour Svelte et figeait le titre. Personne ne
 * l'écoutait : deux specs seulement surveillaient `pageerror`, chacun pour
 * lui. En branchant l'écoute sur TOUS les specs, quatre autres ont révélé une
 * exception qu'ils laissaient passer depuis des semaines.
 *
 * ## Ce qui est vérifié
 *
 * Le `test` de `e2e/aides.ts` porte une fixture automatique qui fait échouer
 * tout test dont la page lève une exception. Un spec qui importerait `test` de
 * `@playwright/test` y échapperait sans un mot : c'est ce que ce contrôle
 * refuse. Les imports de TYPES (`import type { Page }`) restent libres.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const E2E = join(dirname(fileURLToPath(import.meta.url)), '..', 'e2e');

/** Un import de VALEURS depuis `@playwright/test` (pas `import type`). */
const IMPORT_VALEURS = /^import\s+(?!type\b)[^;]*?from\s+['"]@playwright\/test['"]/ms;

const fautif = (source) =>
	source
		.split(/(?=^import\s)/m)
		.some((bloc) => IMPORT_VALEURS.test(bloc) && /\b(test|expect)\b/.test(bloc.split('from')[0]));

if (process.argv.includes('--selftest')) {
	//  Le contrôle se prouve sur le cas fautif AVANT de servir (socle 04 §2).
	const fautifs = [
		"import { expect, test } from '@playwright/test';",
		"import { test, type Page } from '@playwright/test';",
		"import {\n\texpect,\n\ttest,\n} from '@playwright/test';",
		'import { test } from "@playwright/test";',
	];
	const licites = [
		"import { expect, test } from './aides';",
		"import type { Page } from '@playwright/test';",
		"import type { Page, Request } from '@playwright/test';\nimport { test } from './aides';",
		"import type { Reporter } from '@playwright/test/reporter';",
	];
	const rates = [
		...fautifs.filter((s) => !fautif(s)).map((s) => `NON REFUSÉ : ${s}`),
		...licites.filter((s) => fautif(s)).map((s) => `REFUSÉ À TORT : ${s}`),
	];
	if (rates.length) {
		console.error('✗ Autotest du garde-fou :\n   ' + rates.join('\n   '));
		process.exit(1);
	}
	console.log(
		`✓ Autotest : ${fautifs.length} cas fautif(s) refusé(s), ${licites.length} licite(s) laissé(s) passer.`,
	);
	process.exit(0);
}

const specs = readdirSync(E2E).filter((n) => n.endsWith('.spec.ts'));
//  Cas zéro : un parcours qui ne trouve rien ne prouve rien (socle 04 §2).
if (specs.length < 30) {
	console.error(`✗ Seulement ${specs.length} spec(s) lus dans e2e/ : le parcours a dérivé.`);
	process.exit(1);
}
const ecarts = specs.filter((n) => fautif(readFileSync(join(E2E, n), 'utf8')));
if (ecarts.length) {
	console.error('\n✗ Spec(s) qui prennent `test` dans `@playwright/test` :\n');
	for (const e of ecarts) console.error(`   e2e/${e}`);
	console.error(
		'\n  Importer `test` et `expect` de `./aides` : son `test` fait échouer une' +
			'\n  exception de la page, que celui de Playwright laisse passer (#1475).\n',
	);
	process.exit(1);
}
console.log(`✓ e2e : ${specs.length} specs prennent \`test\` dans \`./aides\`.`);
