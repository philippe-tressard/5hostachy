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

function normalizePageConfig(id: string, parsed: PageConfig, defaults: PageConfig): PageConfig {
	const next: PageConfig = {
		...parsed,
		descriptif: decodeEscapedHtml(parsed.descriptif ?? ''),
		onglets: parsed.onglets ? { ...parsed.onglets } : undefined,
	};

	if (next.onglets) {
		for (const [k, v] of Object.entries(next.onglets)) {
			if (typeof v === 'string') {
				(next.onglets as any)[k] = { label: v, descriptif: decodeEscapedHtml((defaults.onglets as any)?.[k]?.descriptif ?? '') };
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
			delete (next.onglets as Record<string, { label: string; descriptif: string }>).consommation;
		}
		if (!next.onglets?.devis && defaults.onglets?.devis) {
			next.onglets = { ...(next.onglets ?? {}), devis: defaults.onglets.devis };
		}
	}

	if (id === 'espace-cs') {
		if (!next.onglets?.tickets && defaults.onglets?.tickets) {
			next.onglets = { ...(next.onglets ?? {}), tickets: defaults.onglets.tickets };
		}
		if (next.onglets?.validations?.label === '✅ Validations') {
			next.onglets.validations.label = defaults.onglets?.validations?.label ?? next.onglets.validations.label;
		}
		if (next.onglets?.validations?.descriptif === 'Comptes en attente de validation et demandes d\'accès à traiter.') {
			next.onglets.validations.descriptif = defaults.onglets?.validations?.descriptif ?? next.onglets.validations.descriptif;
		}
	}

	return next;
}

// ── Store global alimenté depuis l'API ──────────────────────────────────────
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
export function getPageConfig(raw: Record<string, string>, id: string, defaults: PageConfig): PageConfig {
	try {
		const s = raw[`page_config_${id}`];
		if (s) {
			const parsed = normalizePageConfig(id, JSON.parse(s), defaults);
			return { ...defaults, ...parsed };
		}
	} catch { /* ignore */ }
	return defaults;
}

/** Compat backward — retourne la valeur synchrone du store. */
export function getSiteNom(): string {
	return get(siteNomStore);
}
