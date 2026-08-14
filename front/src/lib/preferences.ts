/**
 * Les deux clés des préférences de notification par e-mail.
 *
 * Elles doivent rester identiques à celles de `api/app/utils/preferences_mail.py`,
 * qui fait autorité : c'est lui qui décide d'envoyer ou non. Une clé recopiée de
 * travers ici ne produirait aucune erreur — l'écran cocherait une case que le
 * serveur ne lirait jamais, et le résident croirait avoir réglé quelque chose.
 *
 * `api/tests/test_preferences_mail.py` vérifie que les deux côtés emploient les
 * mêmes noms et les mêmes valeurs par défaut.
 */
export const MON_BATIMENT = 'mon_batiment_mail';
export const AUTRES_BATIMENTS = 'autres_batiments_mail';

/** Coché pour son propre bâtiment, décoché pour les autres : personne n'a
 *  jamais consenti à recevoir les e-mails d'ailleurs. */
export const DEFAUTS_NOTIFS: Record<string, boolean> = {
	[MON_BATIMENT]: true,
	[AUTRES_BATIMENTS]: false,
};
