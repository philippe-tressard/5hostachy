/**
 * Le paramétrage du site — la correspondance entre la configuration stockée
 * (des chaînes, à plat) et le formulaire de l'administration (des types).
 *
 * ## Pourquoi ce fichier (#515)
 *
 * La même liste de clés était écrite **trois fois** dans `admin/+page.svelte` :
 * une fois pour lire, une fois pour envoyer à l'API, une fois pour rafraîchir
 * `configStore` — trois objets littéraux de treize entrées, sur une seule ligne
 * chacun.
 *
 * 🔴 **Et les trois avaient déjà divergé.** La mise à jour du store omettait
 * `relance_syndic_delai_jours`, `whatsapp_footer`, `email_footer` et
 * `reference_copro` : après une sauvegarde, le store affichait encore les
 * anciennes valeurs de ces quatre réglages, jusqu'au rechargement de la page.
 * Personne ne l'avait vu, parce que le défaut ne se voit qu'en comparant deux
 * lignes de 900 caractères.
 *
 * Une seule fonction produit désormais le payload, et les deux appels l'utilisent.
 *
 * ⚠️ Ce module ne connaît **que** l'onglet « Site ». Les pages
 * (`page_config_*`), WhatsApp et les mentions légales ont leurs propres chemins,
 * et `mentions_legales` / `politique_confidentialite` se lisent par un endpoint
 * séparé (`/config/legal`) — c'est pourquoi `lireConfigSite` les reçoit à part.
 */
import { delaiArchivageJours } from '$lib/archivage';

export interface ConfigSite {
	nom: string;
	url: string;
	email_admin: string;
	login_sous_titre: string;
	mentions_legales: string;
	politique_confidentialite: string;
	archivage_delai_jours: number;
	relance_syndic_delai_jours: number;
	notify_ticket_bug_email: boolean;
	notify_new_user_created_email: boolean;
	site_manager_user_id: string;
	whatsapp_footer: string;
	email_footer: string;
	reference_copro: string;
}

/** L'état initial du formulaire, avant tout chargement. */
export const CONFIG_SITE_DEFAUT: ConfigSite = {
	nom: '5Hostachy',
	url: '',
	email_admin: '',
	login_sous_titre: 'Votre espace numérique de résidence',
	mentions_legales: '',
	politique_confidentialite: '',
	archivage_delai_jours: 30,
	relance_syndic_delai_jours: 30,
	notify_ticket_bug_email: false,
	notify_new_user_created_email: false,
	site_manager_user_id: '',
	whatsapp_footer: '— Le Conseil Syndical',
	email_footer: '— Envoyé depuis 5hostachy.fr',
	reference_copro: '',
};

/** Configuration stockée → formulaire. */
export function lireConfigSite(
	cfg: Record<string, string>,
	legal: { mentions_legales?: string; politique_confidentialite?: string } = {},
): ConfigSite {
	return {
		nom: cfg['site_nom'] ?? CONFIG_SITE_DEFAUT.nom,
		url: cfg['site_url'] ?? '',
		email_admin: cfg['site_email'] ?? '',
		login_sous_titre: cfg['login_sous_titre'] ?? CONFIG_SITE_DEFAUT.login_sous_titre,
		mentions_legales: legal.mentions_legales ?? '',
		politique_confidentialite: legal.politique_confidentialite ?? '',
		//  Le réglage unique et son repli vivent dans `$lib/archivage` : les
		//  recopier ici rouvrirait exactement la divergence que #515 referme.
		archivage_delai_jours: delaiArchivageJours(cfg),
		relance_syndic_delai_jours: parseInt(cfg['relance_syndic_delai_jours'] ?? '30') || 30,
		notify_ticket_bug_email: cfg['notify_ticket_bug_email'] === '1',
		notify_new_user_created_email: cfg['notify_new_user_created_email'] === '1',
		site_manager_user_id: cfg['site_manager_user_id'] ?? '',
		whatsapp_footer: cfg['whatsapp_footer'] ?? CONFIG_SITE_DEFAUT.whatsapp_footer,
		email_footer: cfg['email_footer'] ?? CONFIG_SITE_DEFAUT.email_footer,
		reference_copro: cfg['reference_copro'] ?? '',
	};
}

/**
 * Formulaire → configuration stockée.
 *
 * 🔴 **Un seul producteur, deux consommateurs** : l'appel d'enregistrement et la
 * mise à jour du store. C'est ce partage qui empêche le store de conserver des
 * valeurs périmées — le défaut que ce module a mis au jour.
 */
export function ecrireConfigSite(c: ConfigSite): Record<string, string> {
	return {
		site_nom: c.nom,
		site_url: c.url,
		site_email: c.email_admin,
		login_sous_titre: c.login_sous_titre,
		mentions_legales: c.mentions_legales,
		politique_confidentialite: c.politique_confidentialite,
		archivage_delai_jours: String(
			c.archivage_delai_jours || CONFIG_SITE_DEFAUT.archivage_delai_jours,
		),
		relance_syndic_delai_jours: String(c.relance_syndic_delai_jours),
		notify_ticket_bug_email: c.notify_ticket_bug_email ? '1' : '0',
		notify_new_user_created_email: c.notify_new_user_created_email ? '1' : '0',
		site_manager_user_id: c.site_manager_user_id || '',
		whatsapp_footer: c.whatsapp_footer,
		email_footer: c.email_footer,
		reference_copro: c.reference_copro,
	};
}
