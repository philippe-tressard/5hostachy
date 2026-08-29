import { writable, derived, get } from 'svelte/store';
import { browser } from '$app/environment';

export interface PageConfig {
	titre: string;
	descriptif: string;
	navLabel: string;
	icone?: string;
	onglets?: Record<string, { label: string; descriptif: string }>;
}

function decodeEscapedHtml(input: string): string {
	if (!input) return '';
	return input
		.replace(/&lt;/gi, '<')
		.replace(/&gt;/gi, '>')
		.replace(/&quot;/gi, '"')
		.replace(/&#39;|&#x27;/gi, "'")
		.replace(/&nbsp;/gi, ' ')
		.replace(/&amp;/gi, '&');
}

/**  Ôte la clé d'un onglet d'une configuration ENREGISTRÉE.
 *
 *   Un onglet retiré du code laisse sa clé dans `page_config_<id>` chez tous ceux
 *   qui ont ouvert la page avant : sans ce retrait, « Descriptif pages »
 *   continuerait d'en proposer le libellé et le descriptif — une case à remplir
 *   qui ne commande plus rien.
 *
 *   ⚠️ Écrite une fois pour les TROIS appels ci-dessous (`consommation` renommé,
 *   `tickets` retiré le 28/08/2026, `devis` retiré avec les prestations
 *   ponctuelles). Le cast verbeux était recopié à chaque fois : au troisième, il
 *   valait mieux le nommer. Un quatrième onglet retiré n'ajoutera qu'une ligne.
 */
function oterOnglet(config: PageConfig, cle: string): void {
	if (config.onglets?.[cle]) {
		delete (config.onglets as Record<string, { label: string; descriptif: string }>)[cle];
	}
}

function normalizePageConfig(id: string, parsed: PageConfig, defaults: PageConfig): PageConfig {
	const next: PageConfig = {
		...parsed,
		descriptif: decodeEscapedHtml(parsed.descriptif ?? ''),
		onglets: parsed.onglets ? { ...parsed.onglets } : undefined,
	};

	if (next.onglets) {
		for (const [k, v] of Object.entries(next.onglets)) {
			if (typeof v === 'string') {
				(next.onglets as any)[k] = {
					label: v,
					descriptif: decodeEscapedHtml((defaults.onglets as any)?.[k]?.descriptif ?? ''),
				};
			} else if (v && typeof v === 'object') {
				(next.onglets as any)[k] = {
					...v,
					descriptif: decodeEscapedHtml((v as { descriptif?: string }).descriptif ?? ''),
				};
			}
		}
	}

	if (id === 'prestataires') {
		if (next.onglets?.consommation && !next.onglets?.consommations) {
			next.onglets.consommations = next.onglets.consommation;
			oterOnglet(next, 'consommation');
		}
		//  L'onglet « Prestations ponctuelles » a disparu avec l'objet qu'il
		//  rendait : le rattrapage inverse — qui le RÉINJECTAIT depuis les défauts —
		//  aurait ressuscité sa clé à chaque ouverture de la page.
		oterOnglet(next, 'devis');
	}

	if (id === 'espace-cs') {
		//  L'onglet « Tickets résidence » a été retiré le 28/08/2026, redondant avec
		//  la page /tickets — même raison que les deux retraits ci-dessus.
		oterOnglet(next, 'tickets');
		if (next.onglets?.validations?.label === '✅ Validations') {
			next.onglets.validations.label =
				defaults.onglets?.validations?.label ?? next.onglets.validations.label;
		}
		if (
			next.onglets?.validations?.descriptif ===
			"Comptes en attente de validation et demandes d'accès à traiter."
		) {
			next.onglets.validations.descriptif =
				defaults.onglets?.validations?.descriptif ?? next.onglets.validations.descriptif;
		}
	}

	return next;
}

// ── Store global alimenté depuis l'API ──────────────────────────────────────
//  Ré-export : `getPageConfig` et `defautsDePage` sont les deux moitiés d'un même
//  geste — « lis la configuration, avec ces défauts-là » — et `check-pages.mjs`
//  impose déjà de les écrire ensemble. Une page ouvrait pourtant DEUX imports
//  pour cela, ce qui faisait grossir d'une ligne dix fichiers déjà au-dessus du
//  plafond de 500 lignes : le garde-fou de modularité l'a refusé, à raison. La
//  table reste la source (`lib/pages.ts` expose toujours ces fonctions, ce que
//  vérifie le cas zéro de `check-pages.mjs`) ; c'est la PORTE qui est unifiée.
//  L'import de `pages.ts` vers ce fichier est un `import type`, effacé à la
//  compilation : aucun cycle à l'exécution.
export { defautsDePage, configDepuisPage } from '$lib/pages';

export const configStore = writable<Record<string, string>>({});

// Nom du site réactif
export const siteNomStore = derived(configStore, ($c) => $c['site_nom'] ?? '5Hostachy');

let _configLoaded = false;

/**
 * Charge la configuration depuis l'API et peuple le store.
 * Idempotente : ne refait pas appel réseau si déjà chargée.
 */
export async function loadSiteConfig(): Promise<void> {
	if (!browser || _configLoaded) return;
	// Store déjà alimenté depuis le SSR root layout → pas besoin de refetch
	if (Object.keys(get(configStore)).length > 0) {
		_configLoaded = true;
		return;
	}
	_configLoaded = true;
	try {
		const r = await fetch('/api/config');
		if (r.ok) {
			const data = await r.json();
			configStore.set(data);
		}
	} catch {
		_configLoaded = false; // autoriser retry si erreur réseau
	}
}

/**
 * Retourne la config d'une page à partir du store brut (réactif via $configStore).
 * Utiliser : $: _pc = getPageConfig($configStore, 'id', defaults)
 */
export function getPageConfig(
	raw: Record<string, string>,
	id: string,
	defaults: PageConfig,
): PageConfig {
	try {
		const s = raw[`page_config_${id}`];
		if (s) {
			const parsed = normalizePageConfig(id, JSON.parse(s), defaults);
			return { ...defaults, ...parsed };
		}
	} catch {
		/* ignore */
	}
	return defaults;
}

/** Compat backward — retourne la valeur synchrone du store. */
export function getSiteNom(): string {
	return get(siteNomStore);
}
