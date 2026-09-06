/**
 * Comment un **rôle** et un **statut** s'écrivent — jumeau front de
 * `api/app/utils/roles_libelles.py`.
 *
 * ## 🔴 Pourquoi ce fichier (#801, 06/09/2026)
 *
 * La même notion était écrite **six fois** — trois côté serveur, trois ici — et
 * les six avaient dérivé :
 *
 * | Où | `conseil_syndical` | `copropriétaire_résident` |
 * |---|---|---|
 * | API `ajouter_role` | « Membre du Conseil Syndical » | — |
 * | API `retirer_role` | « Conseil Syndical » | — |
 * | API `changer_role` | « Membre du Conseil Syndical » | — |
 * | front `admin` | « Conseil syndical » | « Copropriétaire **R**ésident » |
 * | front `profil` | « Conseil syndical » | « Copropriétaire **R**ésident » |
 * | front `tableau-de-bord` | « Conseil syndical » | « Copropriétaire **r**ésident » |
 *
 * Le même rôle s'annonçait donc autrement selon qu'on l'attribuait ou qu'on le
 * retirait — dans deux notifications que **la même personne** reçoit — et le
 * même statut changeait de casse d'un écran à l'autre. Aucune écriture n'était
 * fausse ; c'est l'ensemble qui n'avait pas de logique.
 *
 * ⚠️ **Aucun garde-fou ne pouvait le voir**, et c'est ce qui l'a laissé passer :
 * six tables cohérentes chacune avec elle-même. Deux tables d'accord entre elles
 * ne prouvent rien (`standards/02` §3 bis) — il fallait les comparer à une
 * référence, et il n'y en avait pas.
 *
 * ## Ce qui est tranché
 *
 * « **Conseil syndical** » et « **Copropriétaire résident** » : l'orthographe
 * française ne met pas de capitale au second terme d'un nom commun composé, et
 * c'était déjà la forme majoritaire. « Membre du Conseil Syndical » disait la
 * même chose en plus long, dans une phrase qui portait déjà le mot « rôle ».
 *
 * ## La duplication front ⇄ API est inévitable — d'où le test
 *
 * Les contextes de build sont `./api` et `./front` : rien de la racine n'entre
 * dans les images (mémoire `project_partage_front_api_impossible`). Le seul
 * motif viable est **copie + concordance exécutée**, celui de `noms.ts`.
 *
 * 🔒 `api/tests/test_roles_libelles.py` lit CE fichier et vérifie que les deux
 * tables portent exactement les mêmes chaînes.
 *
 * ## Rôle ≠ statut, et le produit distingue les deux
 *
 * Le **rôle** dit ce qu'un compte a le droit de faire ; le **statut** dit ce
 * qu'une personne est dans la copropriété. Un copropriétaire bailleur peut être
 * membre du conseil syndical : deux tables, jamais une.
 */

/**  Les rôles — `RoleUtilisateur` côté serveur. */
export const LIBELLES_ROLE: Record<string, string> = {
	résident: 'Résident',
	propriétaire: 'Propriétaire',
	conseil_syndical: 'Conseil syndical',
	admin: 'Admin',
	externe: 'Externe',
};

/**  Les statuts — `StatutUtilisateur` côté serveur. */
export const LIBELLES_STATUT: Record<string, string> = {
	copropriétaire_résident: 'Copropriétaire résident',
	copropriétaire_bailleur: 'Copropriétaire bailleur',
	locataire: 'Locataire',
	syndic: 'Syndic',
	mandataire: 'Mandataire',
	aidant: 'Aidant (proche)',
	admin_technique: 'Compte technique',
};

/**
 *  Anciennes clés encore présentes en base ou dans des réponses d'API.
 *
 *  ⚠️ Elles sont **à part**, et pas mêlées aux deux tables ci-dessus : celles-ci
 *  décrivent les énumérations actuelles et sont vérifiées contre le serveur.
 *  Fondre l'ancien dans le nouveau ferait échouer la concordance — ou, pire,
 *  obligerait à ajouter ces clés côté serveur pour faire passer le test, donc à
 *  ressusciter ce qu'on est en train de retirer.
 */
const LIBELLES_HERITES: Record<string, string> = {
	bailleur: 'Copropriétaire bailleur',
};

/** « conseil_syndical » → « Conseil syndical ». Une clé inconnue est rendue
 *  **telle quelle** : un libellé manquant doit se voir, pas s'effacer. */
export function libelleRole(role: string | null | undefined): string {
	if (!role) return '';
	return LIBELLES_ROLE[role] ?? LIBELLES_HERITES[role] ?? LIBELLES_STATUT[role] ?? role;
}

/** « copropriétaire_résident » → « Copropriétaire résident ». */
export function libelleStatut(statut: string | null | undefined): string {
	if (!statut) return '';
	return LIBELLES_STATUT[statut] ?? LIBELLES_HERITES[statut] ?? LIBELLES_ROLE[statut] ?? statut;
}
