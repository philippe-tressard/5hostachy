/**
 * Comment le nom d'une personne S'AFFICHE — jumeau front de `app/utils/noms.py`.
 *
 * ## La règle, arbitrée à l'écran le 31/08/2026
 *
 * > *« L'affichage devrait être Prénom NOM => Nom en majuscule »*
 *
 * Signalé sur une carte du fil qui rendait **« Jean-Sébastien CourT »** : la
 * casse telle qu'elle avait été tapée, avec un « T » final resté majuscule. Le
 * prénom garde sa casse, le nom passe en capitales — c'est l'usage administratif
 * français, et surtout c'est ce qui rend la lecture homogène quand la saisie ne
 * l'est pas.
 *
 * ## 🔴 Pourquoi une fonction et pas un `{u.prenom} {u.nom}` de plus
 *
 * Le motif était écrit **34 fois dans 16 fichiers** côté front, et 31 fois côté
 * API. Chaque occurrence est correcte ; toutes ensemble forment la seule chose
 * qu'on ne peut pas corriger — une règle d'affichage qui n'existe nulle part.
 * C'est `standards/02` §2 sur la notion la plus banale du site.
 *
 * ## La duplication front ⇄ API est INÉVITABLE, et c'est pour ça qu'il y a un test
 *
 * Les contextes de build sont `./api` et `./front` : rien de la racine n'entre
 * dans les images (mémoire `project_partage_front_api_impossible`). Le seul motif
 * viable est *copie + concordance exécutée* — celui de `perimetreLabel`, dont la
 * règle a été corrigée d'un seul côté le 18/08/2026 et a mis neuf jours à se voir.
 *
 * 🔒 `npm run lint:noms` transpile ce fichier, l'exécute, et vérifie que le test
 * Python attend **la même chaîne**.
 *
 * ⚠️ **Ne pas confondre avec `_nom_presentable`** (`api/app/utils/destinataires.py`),
 * qui fait l'INVERSE : « DUPONT » → « Dupont ». Elle sert à s'ADRESSER à
 * quelqu'un — « Madame Dupont » dans un courriel — où la capitale crierait. Ici
 * on IDENTIFIE une personne dans une liste. Deux besoins opposés, deux fonctions.
 *
 * ## Ce que la fonction ne fait pas
 *
 * Elle ne touche **ni à la donnée, ni au prénom**. Le nom reste enregistré tel
 * qu'il a été saisi : c'est un rendu, pas une normalisation.
 */

/** Ce dont on a besoin pour afficher quelqu'un — et rien de plus. */
export interface Nommable {
	prenom?: string | null;
	nom?: string | null;
}

/**
 * « Jean-Sébastien », « CourT » → « Jean-Sébastien COURT ».
 *
 * Tolère l'absence de l'un ou de l'autre : une personne dont on ne connaît que
 * le nom doit s'afficher quand même, et sans espace en trop. Rend `''` quand on
 * ne connaît ni l'un ni l'autre — jamais `undefined`, que l'écran afficherait.
 */
export function nomAffiche(personne: Nommable | null | undefined): string;
export function nomAffiche(
	prenom: string | null | undefined,
	nom: string | null | undefined,
): string;
export function nomAffiche(a: Nommable | string | null | undefined, b?: string | null): string {
	//  Deux appels possibles, parce que les deux existent à l'écran : un objet
	//  (`nomAffiche(u)`) et deux champs (`nomAffiche(t.auteur_prenom, t.auteur_nom)`),
	//  ces derniers venant d'API qui aplatissent leur porteur.
	const prenom = (typeof a === 'string' || a == null ? a : a.prenom) ?? '';
	const nom = (typeof a === 'string' || a == null ? b : a.nom) ?? '';
	return [prenom.trim(), nom.trim().toUpperCase()].filter(Boolean).join(' ');
}

/**
 * **Comment on CLASSE des personnes** — par le nom de famille, puis le prénom.
 *
 * ## 🔴 Pourquoi ici (15/09/2026)
 *
 * Signalé à l'écran :
 *
 * > « Le classement des badges & télécommandes par Nom doit se faire sur le nom
 * >   et pas le prénom. »
 *
 * La table triait sur `porteur_nom`, qui vaut « **Alain** GARCIA » : la chaîne
 * commence par le prénom, donc le classement aussi. Et `FormulaireTicket`
 * comparait littéralement `` `${prenom} ${nom}` ``.
 *
 * ⚠️ **La règle juste existait déjà, écrite trois fois** — `admin`, `annuaire`,
 * `espace-cs`, plus `utils/annuaire.py` côté serveur. C'est la règle la plus
 * déployée ; ces deux écrans-là ne la suivaient pas. Elle est donc reprise ici
 * telle quelle, et c'est elle qui s'applique partout.
 *
 * ## Les trois décisions qu'elle porte
 *
 * 1. **Le nom d'abord** — c'est ainsi qu'on cherche quelqu'un dans une liste ;
 * 2. **le prénom en départage** — deux GARCIA se rangent entre eux, sinon leur
 *    ordre dépendrait de l'ordre d'arrivée en base, donc de rien ;
 * 3. **`'fr'` et `sensitivity: 'base'`** — « Ébert » se range après « Dupont » et
 *    non en fin de liste, et « MOREL » vaut « Morel ». La casse ne doit pas
 *    classer : `nomAffiche` met justement le nom en capitales.
 *
 * ⚠️ Un nom absent se range **à la fin** plutôt qu'au début : une ligne
 * incomplète n'a pas à ouvrir la liste.
 */
export function comparerParNom(
	a: Nommable | null | undefined,
	b: Nommable | null | undefined,
): number {
	const nomA = (a?.nom ?? '').trim();
	const nomB = (b?.nom ?? '').trim();
	//  Sans nom → à la fin, dans les deux sens de tri : c'est le seul rang où une
	//  ligne incomplète ne prétend pas être la première.
	if (!nomA !== !nomB) return nomA ? -1 : 1;
	const parNom = nomA.localeCompare(nomB, 'fr', { sensitivity: 'base' });
	if (parNom !== 0) return parNom;
	return (a?.prenom ?? '').localeCompare(b?.prenom ?? '', 'fr', { sensitivity: 'base' });
}
