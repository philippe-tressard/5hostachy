//  L'ADMINISTRATION : comptes et validations, délégations d'aidant, réglages du
//  site. Ce que seuls l'administrateur et le conseil syndical appellent.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '$lib/api'` du front ne changent pas d'une ligne.
import { api, buildQuery } from './client';

export const annuaireAdmin = {
	getCS: () => api.get<any>('/admin/annuaire/cs'),
	putCS: (data: unknown) => api.put<any>('/admin/annuaire/cs', data),
	getSyndic: () => api.get<any>('/admin/annuaire/syndic'),
	putSyndic: (data: unknown) => api.put<any>('/admin/annuaire/syndic', data),
};

export const delegations = {
	list: () => api.get<any[]>('/delegations'),
	create: (data: { mandant_id: number; aidant_id: number; motif?: string; date_fin?: string }) =>
		api.post<any>('/delegations', data),
	update: (id: number, data: { motif?: string; date_fin?: string }) =>
		api.patch<any>(`/delegations/${id}`, data),
	accepter: (id: number) => api.post<any>(`/delegations/${id}/accepter`),
	revoquer: (id: number) => api.post<any>(`/delegations/${id}/revoquer`),
	mesMandants: () => api.get<any[]>('/delegations/mes-mandants'),
};

export const admin = {
	// Comptes
	comptesEnAttente: () => api.get<any[]>('/admin/comptes-en-attente'),
	//  🔴 `pendingAccounts` A ÉTÉ SUPPRIMÉE ICI le 06/09/2026 (#801) : même route,
	//  même corps, même retour que `comptesEnAttente` juste au-dessus — un doublon
	//  exact, à une ligne d'écart, dans un fichier qu'on relit rarement en entier.
	//  Elle figurait au relevé des « clients sans appelant » ; le tri a montré
	//  qu'elle n'était ni un manque ni une avance, mais une COPIE. Elle était aussi
	//  la seule des deux dont le nom fût en anglais.
	traiterCompte: (id: number, data: { action: string; motif?: string }) =>
		//  🔴 `<any>` EXPLICITE, et c'est le fond du sujet : sans argument de type,
		//  `api.post` rend `{}`, et l'écran qui lit `res.auto_match.…` ne compile
		//  pas. C'est exactement ce qui l'avait fait réécrire l'appel en dur avec
		//  son propre `<any>` — une méthode trop pauvre ne fait pas contourner un
		//  peu, elle fait recopier la route en entier (#801).
		api.post<any>(`/admin/comptes/${id}/traiter`, data),
	// Commandes accès
	commandesAccesEnAttente: () => api.get<any[]>('/admin/commandes-acces'),
	traiterCommandeAcces: (id: number, data: { action: string; motif_refus?: string }) =>
		api.post(`/admin/commandes-acces/${id}/traiter`, data),
	// Sauvegardes
	backupConfig: () => api.get<any>('/admin/sauvegardes/config'),
	updateBackupConfig: (data: unknown) => api.put<any>('/admin/sauvegardes/config', data),
	// Modèles e-mail
	emailTemplates: () => api.get<any[]>('/admin/modeles-email'),
	//  L'historique des envois — il manquait au client, et l'écran l'appelait en
	//  dur juste à côté de `emailTemplates` (#801). Deux routes du même écran, une
	//  déclarée et l'autre non : c'est ainsi qu'un client se vide de son sens.
	emailsHistorique: () => api.get<any[]>('/admin/emails/historique'),
	updateEmailTemplate: (id: number, data: unknown) => api.patch(`/admin/modeles-email/${id}`, data),
	resetEmailTemplates: () => api.post<{ message: string }>('/admin/modeles-email/reinitialiser'),
	// Utilisateurs & rôles
	utilisateurs: () => api.get<any[]>('/admin/utilisateurs'),
	//  🔴 Les trois rendent l'utilisateur MIS À JOUR, et le type le dit depuis le
	//  06/09/2026 (#801). Sans argument de type, `api.post` rend `{}` : l'écran
	//  qui fait `{ ...u, ...updated }` ne compilait pas, et il a donc réécrit
	//  l'appel en dur — avec son propre `<any>` et une URL construite dans un
	//  ternaire, invisible à toute recherche par route. Une méthode trop pauvre
	//  ne fait pas contourner un peu : elle fait recopier la route en entier.
	changerRole: (id: number, role: string) =>
		api.post<any>(`/admin/utilisateurs/${id}/changer-role`, { role }),
	ajouterRole: (id: number, role: string) =>
		api.post<any>(`/admin/utilisateurs/${id}/ajouter-role`, { role }),
	retirerRole: (id: number, role: string) =>
		api.post<any>(`/admin/utilisateurs/${id}/retirer-role`, { role }),
	// Demandes de modification de profil
	demandesProfil: () => api.get<any[]>('/admin/demandes-profil'),
	//  ⚠️ `motif_refus` accepte `null` et pas seulement `undefined` : l'écran
	//  envoie `refusDemande[id] || null`, donc un null EXPLICITE. Resserrer le
	//  type aurait obligé l'écran à changer ce qu'il transmet — le client suit le
	//  contrat réel, il ne le réécrit pas (#801).
	traiterDemandeProfil: (id: number, data: { action: string; motif_refus?: string | null }) =>
		api.post(`/admin/demandes-profil/${id}/traiter`, data),
	// Baux locatifs
	baux: () => api.get<any[]>('/admin/baux'),
	lierLocataire: (bail_id: number, user_id: number) =>
		api.post(`/admin/baux/${bail_id}/lier-locataire/${user_id}`, {}),
	// Audit associations user-lot
	auditUserLots: () => api.get<any[]>('/admin/audit/user-lots'),
	supprimerUserLot: (id: number) => api.delete(`/admin/user-lots/${id}`),
	// Télémétrie
	//  🔴 `scope` a été AJOUTÉ ici plutôt que dans l'écran (#801) : `OngletTelemetrie`
	//  écrivait `/telemetry/dashboard?scope=${…}` en dur parce que la méthode ne
	//  savait pas le porter. Une méthode trop pauvre ne fait pas contourner un peu,
	//  elle fait recopier la route en entier — et la route recopiée ne suit plus.
	telemetryDashboard: (scope?: 'jour' | 'mois' | 'annee') =>
		api.get<any>(`/telemetry/dashboard${buildQuery({ scope })}`),
	telemetryUsersActive: () => api.get<any[]>('/telemetry/users-active'),
	telemetryAgreger: () => api.post('/admin/telemetry/agreger'),
	telemetryHistorique: () => api.get<any[]>('/admin/telemetry/historique'),

	//  Le relevé CSP — agrégé côté serveur et PERSISTÉ dans `ConfigSite`, donc il
	//  survit aux redémarrages. Il existait sans aucun lecteur : la donnée était
	//  collectée depuis des semaines et personne ne pouvait la voir (#536).
	cspViolations: () => api.get<CspReleve>('/admin/csp-violations'),

	//  ── Gestes sur un utilisateur — ajoutés le 06/09/2026 (#801) ───────────────
	//
	//  Les six vivaient EN DUR dans `admin/+page.svelte`, et l'un d'eux —
	//  `accueilArrivant` — était recopié à l'identique dans `espace-cs`. Deux
	//  écrans, une route, aucun lien entre eux : le jour où elle change, l'un des
	//  deux suit et l'autre part en 404 sans que rien ne lève.
	modifierUtilisateur: (id: number, data: unknown) =>
		api.patch<any>(`/admin/utilisateurs/${id}`, data),
	supprimerUtilisateur: (id: number) => api.delete(`/admin/utilisateurs/${id}`),
	autoMatchUtilisateur: (id: number) => api.post<any>(`/admin/utilisateurs/${id}/auto-match`),
	/**
	 *  Les actions d'accueil d'un nouvel arrivant — bienvenue, consignes,
	 *  demandes au syndic et au CS.
	 *
	 *  🔴 Cet appel était écrit TROIS fois, avec le même corps : deux dans
	 *  `admin/+page.svelte` (validation de compte, puis geste d'accueil isolé) et
	 *  une dans `espace-cs`. Trois copies d'un envoi qui déclenche des e-mails —
	 *  ajouter un champ au corps en aurait laissé deux en arrière, et rien
	 *  n'aurait levé : le message serait simplement parti incomplet.
	 */
	accueilArrivant: (
		id: number,
		data: { batiment?: string | null; ancien_resident?: string | null },
	) => api.post<any>(`/admin/utilisateurs/${id}/accueil-arrivant`, data),
	banCommunaute: (id: number, data: unknown) =>
		api.patch<any>(`/admin/utilisateurs/${id}/ban-communaute`, data),
	//  ⚠️ Route DISTINCTE de `comptesEnAttente` : `/enrichis` rend les mêmes
	//  comptes avec le rapprochement de lots déjà calculé. Deux endpoints, deux
	//  méthodes — les confondre sous un drapeau donnerait une méthode dont le
	//  retour change de forme selon l'argument.
	comptesEnAttenteEnrichis: () => api.get<any[]>('/admin/comptes-en-attente/enrichis'),

	//  ── Intégrité de la base (`IntegriteReferentielle`) ────────────────────────
	clesEtrangeres: () => api.get<ReleveOrphelins>('/admin/db/cles-etrangeres'),
	/**  Ce qui PARTIRAIT — l'endpoint ne supprime rien sans `confirmer=true`. */
	simulerPurgeOrphelins: () =>
		api.post<{ seraient_supprimees?: number; seraient_deliees?: number }>(
			'/admin/db/purger-orphelins',
		),
	/**
	 *  🔴 La purge RÉELLE, et elle est irréversible.
	 *
	 *  Deux méthodes plutôt qu'un drapeau `confirmer: boolean`, délibérément :
	 *  une signature où un booléen décide entre « compter » et « détruire » se
	 *  lit mal sur la ligne d'appel, et un défaut de valeur y devient une
	 *  destruction par omission. Ici, le nom dit ce qui se passe.
	 */
	purgerOrphelins: () =>
		api.post<{ supprimees: number; deliees: number }>('/admin/db/purger-orphelins?confirmer=true'),

	/** L'état des tâches planifiées — lu par `TachesPlanifiees`. */
	santeMaintenance: () => api.get<any>('/admin/maintenance/sante'),

	/**
	 *  L'historique d'une tâche planifiée.
	 *
	 *  🔴 Deux tâches ont leur PROPRE table d'historique, les autres partagent
	 *  celle de la maintenance : c'est le repli ci-dessous, et il vivait dans
	 *  l'écran sous forme d'une table `SOURCE` de routes littérales. Deux de ces
	 *  routes — `/admin/telemetry/historique` et `/admin/telemetry/agreger` —
	 *  étaient DÉJÀ déclarées ici et figuraient au relevé des méthodes « sans
	 *  appelant » (#801). Elles en avaient un ; il passait par une table, donc
	 *  aucune recherche par nom de méthode ne pouvait le voir.
	 *
	 *  ⚠️ Une route rangée dans une table de l'écran reste une route recopiée.
	 *  C'est la forme la plus discrète du contournement, et la plus difficile à
	 *  relever — elle ne ressemble plus à un appel.
	 */
	historiqueTache: (tache: string, limite = 10) => {
		const propre: Record<string, () => Promise<any[]>> = {
			backup: () => api.get<any[]>('/admin/sauvegardes/historique'),
			telemetrie: () => api.get<any[]>('/admin/telemetry/historique'),
		};
		return (
			propre[tache]?.() ??
			api.get<any[]>(
				`/admin/maintenance/historique${buildQuery({ tache, limite: String(limite) })}`,
			)
		);
	},

	/**
	 *  Lance une tâche planifiée à la demande. Rend un 202 : c'est la PRISE EN
	 *  COMPTE qui est confirmée, pas l'exécution.
	 *
	 *  ⚠️ `maintenance` n'exécute PAS `maintenance.sh` — seulement
	 *  `run_maintenance` dans le process de l'API (purges + VACUUM), sur le seul
	 *  nœud qui répond. L'hygiène locale du standby n'est déclenchée par personne
	 *  ici ; l'écran le dit à l'utilisateur, et ce commentaire le rappelle à qui
	 *  ajouterait un appelant.
	 *
	 *  Rend `null` pour une tâche qui ne se lance pas à la main — l'écran ne
	 *  montre alors aucun bouton.
	 */
	lancerTache: (tache: string): Promise<any> | null => {
		const route = ROUTES_LANCEMENT[tache];
		return route ? api.post<any>(route) : null;
	},
	/**
	 *  « Cette tâche se lance-t-elle à la main ? » — l'écran y conditionne son
	 *  bouton.
	 *
	 *  ⚠️ Elle interroge `ROUTES_LANCEMENT`, elle ne REDIT pas la liste : une
	 *  seconde énumération des mêmes clés se désaccorderait de la première au
	 *  premier ajout, et l'écran afficherait un bouton qui ne lance rien — ou
	 *  masquerait une tâche qui se lance.
	 */
	tacheLancable: (tache: string) => tache in ROUTES_LANCEMENT,
};

/**  Les tâches qu'on peut déclencher à la demande, et par quelle route. Table
 *   déplacée de `TachesPlanifiees.svelte` le 06/09/2026 (#801) : une table de
 *   routes est un morceau de client, où qu'elle soit écrite. */
const ROUTES_LANCEMENT: Record<string, string> = {
	maintenance: '/admin/maintenance/lancer',
	backup: '/admin/sauvegardes/maintenant',
	telemetrie: '/admin/telemetry/agreger',
};

export const config = {
	get: (): Promise<Record<string, string>> => api.get<Record<string, string>>('/config'),
	save: (data: Record<string, string>): Promise<void> => api.put('/config', data),

	//  ── Réglages d'administration et bancs d'essai (#801) ──────────────────────
	//
	//  Sept routes que trois écrans écrivaient en dur. Elles rejoignent `config`
	//  parce que c'est ce qu'elles sont — la configuration du site et les essais
	//  qui la valident — et non un objet `whatsapp` de plus : un objet par écran
	//  redonnerait le découpage que le client existe pour éviter.
	admin: (): Promise<Record<string, string>> => api.get<Record<string, string>>('/config/admin'),
	testerSmtp: (email: string) => api.post<any>('/config/smtp-test', { email }),
	testerImap: () => api.post<any>('/config/imap-test', {}),

	whatsappStatut: () => api.get<any>('/config/whatsapp-status'),
	whatsappJournaux: () => api.get<any>('/config/whatsapp-logs'),
	whatsappPlanifies: () => api.get<any>('/config/whatsapp-scheduled'),
	modifierWhatsappPlanifie: (id: number, data: unknown) =>
		api.put<any>(`/config/whatsapp-scheduled/${id}`, data),
	testerWhatsapp: (message: string) => api.post<any>('/config/whatsapp-test', { message }),
};

/**
 *  Le relevé des lignes qui référencent un parent disparu — `admin.clesEtrangeres`.
 *
 *  ⚠️ `inconnu` n'est PAS `ok: false` : « je n'ai pas pu mesurer » et « rien à
 *  signaler » sont deux réponses différentes, et l'écran doit les distinguer
 *  (`standards/04` — un contrôle qui ne peut pas s'exécuter rend INCONNU).
 *  Le type vivait dans `IntegriteReferentielle.svelte` ; il décrit une réponse
 *  d'API, donc sa place est ici, avec la méthode qui la rend (#801).
 */
export interface ReleveOrphelins {
	ok: boolean;
	inconnu: boolean;
	orphelins?: number;
	par_relation?: { table: string; colonne: string; table_parente: string; lignes: number }[];
	erreur?: string;
}

/** Le relevé des violations CSP — voir `admin.cspViolations`. */
export interface CspReleve {
	/** Renseignée quand AUCUN rapport n'est arrivé : un relevé vide ne prouve rien. */
	note: string | null;
	recus: number;
	/** Rapports reçus mais illisibles, ou refusés par le plafond de clés. */
	ignores: number;
	cles_distinctes: number;
	plafond_atteint: boolean;
	violations: { directive: string; bloque: string; compte: number }[];
}
