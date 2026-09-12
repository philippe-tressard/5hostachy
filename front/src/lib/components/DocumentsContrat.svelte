<!--
  Les pièces d'un contrat d'entretien — **le rendu des tickets, sans écart**.

  ## Pourquoi (30/08/2026, #453 · #640) puis refait le 12/09/2026

  `prestataires/+page.svelte` rendait ce bloc **deux fois**, dans le formulaire du
  haut et dans l'édition en ligne. Ce composant l'a écrit une fois — mais il l'a
  écrit **à sa manière** : une liste verticale en styles inline, un titre
  « 📄 Documents (N) » qui doublait celui de la section, et un dépôt en deux temps
  (« Choisir un document » puis un bouton « + Document »).

  🔴 Signalé à l'écran le 12/09/2026, capture à l'appui :

  > La section document n'est pas standard en édition — regarde le différentiel
  > avec Documents de Tickets ⇒ adopte le même rendu : **je n'accepte pas de
  > différence** (sauf dans le libellé).

  Le différentiel mesuré, et aucun écart n'était voulu :

  | | Tickets | Contrats (avant) |
  |---|---|---|
  | les pièces | pastilles « PDF: nom × » | liste verticale + 🗑️, styles inline |
  | le titre | celui de la section, une fois | **deux fois** |
  | le dépôt | « Ajouter un document » | « Choisir un document » **+ « + Document »** |
  | le plafond | 10 | 1 |
  | le champ de nom | pleine largeur | étroit, sur sa propre ligne |

  ## Ce qui rendait le dépôt en DEUX temps, et pourquoi il n'a plus lieu d'être

  Un document de ticket est une URL dans une liste ; un document de contrat est
  une entité `Document` rattachée à un `contrat_id`. D'où un envoi séparé — et un
  bouton pour le déclencher.

  Mais **en édition le contrat existe déjà** : son identifiant est connu au
  moment où l'on choisit le fichier. L'envoi peut donc partir tout de suite, par
  le `upload` que `FichiersUpload` accepte depuis toujours, et le second bouton
  disparaît. Le composant du dépôt n'avait pas besoin d'être adapté : **il savait
  déjà faire**, et c'est le troisième « le composant existait déjà » de la semaine.

  ⚠️ La seule différence qui subsiste est celle que l'utilisateur a admise : le
  **libellé** du champ de nommage. Elle est portée par `FichiersUpload`, pas ici.
-->
<script lang="ts">
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import { documents as docsApi } from '$lib/api';

	/** Le contrat dont on montre les pièces. */
	export let contratId: number;
	/** Les documents déjà attachés. */
	export let documents: any[] = [];
	/** Qui sait supprimer — l'écran, qui tient la table. */
	export let onSupprimer: (contratId: number, docId: number) => void;
	/** Qui sait recharger après un ajout. */
	export let onAjoute: (contratId: number) => void;
	/** Identifiant du champ de téléversement — unique par emplacement. */
	export let idChamp: string;

	/**  Le nom de fichier saisi au dépôt. `FichiersUpload` s'en sert pour RENOMMER
	 *   le fichier avant l'envoi — c'est ainsi que les tickets le font, et le
	 *   `titre` du `Document` reçoit ensuite ce même nom. Une seule règle de
	 *   nommage, donc, et non deux qui finiraient par diverger. */
	let libelleFichier = '';

	//  Les pièces sont rendues par leur URL de téléchargement, et `noms` dit
	//  comment les afficher : l'URL `/documents/12/télécharger` ne porte ni le
	//  nom ni l'extension, donc ni le type de la pastille.
	$: urls = (documents ?? []).map((d) => docsApi.downloadUrl(d.id));
	$: noms = Object.fromEntries(
		(documents ?? []).map((d) => [docsApi.downloadUrl(d.id), d.titre || d.fichier_nom]),
	);

	/**  L'envoi part dès que le fichier est choisi — le contrat existe déjà.
	 *
	 *  ⚠️ L'URL rendue n'est PAS conservée : `onAjoute` recharge la table depuis
	 *  l'API, qui seule connaît l'identifiant du document, sa date et son titre
	 *  définitif. Rendre l'URL sert à `FichiersUpload`, qui attend une chaîne. */
	async function envoyer(file: File): Promise<string> {
		const doc = await docsApi.uploadForContrat(file.name, contratId, file);
		onAjoute(contratId);
		return docsApi.downloadUrl(doc.id);
	}

	/**  Retirer une pastille supprime le document. L'écran tient la table : il
	 *   rend la nouvelle liste, et `FichiersUpload` s'y aligne. */
	async function retirer(url: string): Promise<string[]> {
		const doc = (documents ?? []).find((d) => docsApi.downloadUrl(d.id) === url);
		if (doc) onSupprimer(contratId, doc.id);
		return urls.filter((u) => u !== url);
	}
</script>

<FichiersUpload
	id={idChamp}
	mode="documents"
	titre=""
	avecLibelle
	bind:libelleFichier
	{urls}
	{noms}
	upload={envoyer}
	remove={retirer}
/>
