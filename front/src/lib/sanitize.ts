/**
 * Sanitisation HTML — défense contre les attaques XSS.
 * Client : DOMPurify (DOM natif du navigateur — gold standard).
 * Serveur : nettoyage regex allow-list (pas de jsdom, léger et compatible Node 22).
 */

// Chargement async fire-and-forget côté client uniquement.
// SSR et premier rendu client utilisent le fallback regex.
// Dès que DOMPurify est chargé (quelques ms), il prend le relais.
let _purify: { sanitize: (html: string, cfg: object) => string } | null = null;

if (typeof window !== 'undefined') {
	import('dompurify').then(mod => { _purify = mod.default; });
}

const ALLOWED_TAGS = [
	'p', 'br', 'b', 'i', 'u', 's', 'strong', 'em',
	'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
	'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
	'a', 'img', 'hr', 'span', 'div',
];

const ALLOWED_ATTR = ['href', 'src', 'alt', 'title', 'class', 'target', 'rel'];

const _allowedTagSet = new Set(ALLOWED_TAGS);
const _allowedAttrSet = new Set(ALLOWED_ATTR);

/** Nettoyage regex basique pour le SSR (les clients ré-hydrateront avec DOMPurify). */
function _serverSanitize(input: string): string {
	return input
		.replace(/<script[\s>][\s\S]*?<\/script>/gi, '')
		.replace(/<style[\s>][\s\S]*?<\/style>/gi, '')
		.replace(/on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, '')
		.replace(/<\/?([a-z][a-z0-9]*)\b([^>]*)>/gi, (match, tag, attrs) => {
			const tagLower = tag.toLowerCase();
			if (!_allowedTagSet.has(tagLower)) return '';
			const cleanAttrs = (attrs || '').replace(
				/\s([a-z][a-z-]*)(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*))?/gi,
				(_: string, attrName: string) =>
					_allowedAttrSet.has(attrName.toLowerCase()) ? _ : ''
			);
			return match.startsWith('</') ? `</${tagLower}>` : `<${tagLower}${cleanAttrs}>`;
		});
}

/**
 * Sanitise une chaîne HTML et retourne la version sûre.
 * Si l'entrée est vide/nulle, retourne ''.
 */
export function safeHtml(input: string | null | undefined): string {
	if (!input) return '';
	if (_purify) {
		return _purify.sanitize(input, {
			ALLOWED_TAGS,
			ALLOWED_ATTR,
			ALLOW_DATA_ATTR: false,
		});
	}
	return _serverSanitize(input);
}

/**
 * Rend un contenu stocké soit en HTML riche, soit en texte simple.
 * - HTML : sanitise et conserve la structure.
 * - Texte : sanitise puis remplace les retours ligne par des <br>.
 */
export function safeRichContent(input: string | null | undefined): string {
	if (!input) return '';
	const value = input.trim();
	const looksLikeHtml = /<\/?[a-z][\s\S]*>/i.test(value);
	if (looksLikeHtml) return safeHtml(value);
	return safeHtml(value).replace(/\n/g, '<br>');
}
