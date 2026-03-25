/**
 * Sanitisation HTML — défense contre les attaques XSS.
 * Utilise isomorphic-dompurify (JSDOM côté SSR, DOM natif côté client).
 */
import DOMPurify from 'isomorphic-dompurify';

const ALLOWED_TAGS = [
	'p', 'br', 'b', 'i', 'u', 's', 'strong', 'em',
	'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
	'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
	'a', 'img', 'hr', 'span', 'div',
];

const ALLOWED_ATTR = ['href', 'src', 'alt', 'title', 'class', 'target', 'rel'];

/**
 * Sanitise une chaîne HTML et retourne la version sûre.
 * Si l'entrée est vide/nulle, retourne ''.
 */
export function safeHtml(input: string | null | undefined): string {
	if (!input) return '';
	return DOMPurify.sanitize(input, {
		ALLOWED_TAGS,
		ALLOWED_ATTR,
		ALLOW_DATA_ATTR: false,
	});
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
