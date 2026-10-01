/*
 *  **Le bilan des durées d'hydratation d'un passage e2e (#1475, 01/10/2026).**
 *
 *  Deux rejeux complets sur trois avaient échoué le 30/09 sur un délai
 *  d'hydratation dépassé (10 s), jamais la même spec, toujours en mobile — et
 *  jamais reproduit au repos (médiane 1,3 s, maximum 2,4 s). La mesure qui
 *  manquait : la durée d'hydratation PENDANT un rejeu complet, tests verts
 *  compris. La sortie du rejeu ne garde que celle des étapes en échec.
 *
 *  Chaque appel d'`attendreHydratation` (`e2e/aides.ts`) annote son test de sa
 *  durée ; ce rapporteur en fait, à la fin du passage :
 *  - une ligne dans la sortie — gardée en entier par le rejeu quand l'étape
 *    échoue (`rejeu-ci-echecs/`), donc là où l'on diagnostique ;
 *  - `test-results/hydratation.json`, toutes les mesures, conservé jusqu'au
 *    passage suivant.
 *
 *  ⚠️ Aucune mesure = INCONNU, jamais un bilan vide lu comme « rien de lent ».
 */
import { writeFileSync, mkdirSync } from 'node:fs';
import type { Reporter, TestCase, TestResult } from '@playwright/test/reporter';
import { TYPE_HYDRATATION } from './aides';

/** Au-delà, la mesure est citée : la moitié du délai d'échec, quatre fois le maximum au repos. */
const SEUIL_LENTE_MS = 5000;

type Mesure = { test: string; projet: string; ms: number; statut: string };

export default class RapportHydratation implements Reporter {
	private mesures: Mesure[] = [];

	onTestEnd(test: TestCase, resultat: TestResult): void {
		for (const a of resultat.annotations) {
			if (a.type !== TYPE_HYDRATATION) continue;
			this.mesures.push({
				test: test.titlePath().slice(2).join(' › '),
				projet: test.parent.project()?.name ?? '?',
				ms: Number(a.description),
				statut: resultat.status,
			});
		}
	}

	onEnd(): void {
		const m = [...this.mesures].sort((a, b) => a.ms - b.ms);
		if (m.length === 0) {
			console.log('⏱ hydratation : INCONNU — aucune mesure (aucun test ne l’a attendue)');
			return;
		}
		mkdirSync('test-results', { recursive: true });
		writeFileSync('test-results/hydratation.json', JSON.stringify(m, null, '\t'));
		const s = (ms: number) => `${(ms / 1000).toFixed(1).replace('.', ',')} s`;
		const max = m[m.length - 1];
		console.log(
			`⏱ hydratation : ${m.length} mesure${m.length > 1 ? 's' : ''} — médiane ${s(m[Math.floor(m.length / 2)].ms)}, ` +
				`max ${s(max.ms)} (${max.test} [${max.projet}])`,
		);
		for (const l of m.filter((x) => x.ms > SEUIL_LENTE_MS).reverse())
			console.log(`  ⚠️ ${s(l.ms)} — ${l.test} [${l.projet}] (${l.statut})`);
	}
}
