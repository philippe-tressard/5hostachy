<!--
  Saisie de pièces jointes : liste retirable + bouton d'ajout. Les images
  s'affichent en vignettes, les documents en pastilles nommées — c'est `accept`
  qui décide de ce qu'on peut ajouter, pas le rendu.

  ⚠️ Composant UNIQUE de saisie de pièces jointes. `PhotosUpload.svelte` en était
  une seconde copie à ~80 % identique (même mise en page, même compteur, CSS de la
  croix de suppression rigoureusement identique) — et les deux avaient divergé sur
  le point qui compte : celui-ci acceptait `multiple`, l'autre non, alors que son
  en-tête annonçait « sélection multiple ». Résultat, on ne pouvait joindre qu'UNE
  photo aux sondages et à l'espace CS (signalé le 10/08/2026). Fusionné ici : ne
  pas recréer de variante, c'est la divergence qui produit le défaut, pas le code.

  Le téléversement passe par défaut par l'endpoint générique
  (`POST /uploads/fichier`, qui valide le type MIME). Les rubriques qui ont leur
  PROPRE endpoint (photo de résidence, annonces…) passent un callback `upload` —
  et `remove` si la suppression doit être répercutée côté serveur.

  Le fichier est téléversé immédiatement — avant même que l'élément parent
  existe — et l'URL obtenue part dans le `fichiers_urls` de la création. C'est ce
  qui permet à un ticket envoyé au syndic de partir avec ses documents joints,
  ce que le flux « créer puis téléverser » des photos ne permet pas.

  ## Le mode DIFFÉRÉ (`differe`), et pourquoi il existe

  Deux rubriques ne peuvent PAS téléverser à la sélection : les documents d'une
  actualité deviennent des entités `Document` rattachées à `publication_id`, qui
  n'existe pas tant que l'actualité n'est pas créée. Elles utilisaient donc un
  `<input type="file">` nu — d'où deux apparences pour une même notion sur le
  site, signalé le 16/08/2026 (« le libellé fichier n'est pas conforme »).

  En mode différé, le composant RETIENT les `File` sélectionnés au lieu de les
  envoyer : même rendu, même compteur, même bouton, mêmes vignettes (par
  `URL.createObjectURL`). Le parent lit `bind:fichiers` après la création et les
  téléverse alors. L'apparence est identique — c'est tout l'objet.

  ⚠️ Les URLs d'aperçu sont un **état global du navigateur** : elles sont
  révoquées au retrait ET dans `onDestroy` (socle 11 §12 — la fonction de
  libération est appelée depuis chaque sortie, pas seulement la sortie nominale).

  Props :
    - urls     : liste des URLs (bindable) — mode normal
    - fichiers : liste des `File` retenus (bindable) — mode `differe`
    - differe  : ne pas téléverser, retenir les fichiers pour le parent
    - max      : nombre maximum de documents
    - label    : libellé du bouton d'ajout
    - accept   : filtre du sélecteur de fichiers
    - id       : posé sur l'input, pour qu'un `<label for="…">` le désigne
    - disabled : désactive l'ajout
    - readonly : affichage seul (ni ajout ni retrait)
    - upload   : (file) => Promise<url> — remplace l'endpoint générique
    - remove   : (url) => Promise<url[] | void> — suppression serveur ; si elle
                 retourne une liste, elle fait foi
  Events :
    - change(detail: string[]) — après ajout ou retrait (mode normal)
-->
<script lang="ts">
	import { createEventDispatcher, onDestroy } from 'svelte';
	import Vignette from './Vignette.svelte';
	import { fichiersApi } from '$lib/api';
	import { toast } from './Toast.svelte';
	import { ACCEPT_DOCUMENTS, ACCEPT_FICHIERS, ACCEPT_PHOTOS, MAX_FICHIERS, nomFichier, separerFichiers } from '$lib/fichiers';

	export let urls: string[] = [];
	export let max = MAX_FICHIERS;
	/** 'photos' | 'documents' | 'mixte' — porte à la fois le filtre du sélecteur
	 *  et le libellé par défaut : une page n'a ni import ni ligne de plus à écrire
	 *  pour dire « ici, ce sont des photos ». */
	export let mode: 'photos' | 'documents' | 'mixte' = 'documents';
	export let label: string | null = null;
	export let accept: string | null = null;
	$: accepte = accept ?? { photos: ACCEPT_PHOTOS, documents: ACCEPT_DOCUMENTS, mixte: ACCEPT_FICHIERS }[mode];
	$: libelle = label ?? { photos: 'Ajouter des photos', documents: 'Ajouter un document', mixte: 'Ajouter un fichier' }[mode];
	export let id: string | undefined = undefined;
	export let disabled = false;
	export let readonly = false;
	export let upload: ((file: File) => Promise<string>) | null = null;
	export let remove: ((url: string) => Promise<string[] | void>) | null = null;
	/** Côté des vignettes d'image, en px. */
	export let size = 64;

	/** Retenir les fichiers au lieu de les téléverser (voir l'en-tête). */
	export let differe = false;
	/** Les `File` retenus en mode différé — à lier avec `bind:`. */
	export let fichiers: File[] = [];

	/** Intitulé affiché au-dessus du champ. Laisser vide : il est DÉDUIT du mode
	    et de `max`. C'est tout l'objet de cette prop — le libellé vivait dans
	    CHAQUE page appelante, et elles avaient divergé : « Photos » sur les
	    actualités et le calendrier, « Photos (max 5) » sur les tickets ;
	    « Documents (PDF, Word, Excel) » ici, « Documents (PDF, Word, Excel —
	    max 5) » là (signalé le 16/08/2026).

	    Le porter ici rend toute évolution HÉRITÉE : changer la formulation, ou
	    les types acceptés, se répercute partout sans toucher une seule page.
	    Ne le surcharger que pour une vraie spécificité d'écran. */
	export let titre: string | null = null;

	//  Les types annoncés ne sont pas récités à la main : ils DÉCOULENT de
	//  `ACCEPT_DOCUMENTS` (pdf, doc, docx, xls, xlsx). Une extension ajoutée là-bas
	//  se dit ici, au lieu de laisser un libellé mentir.
	//  `mode` sert au rendu (vignettes ou liste). Quand il n'est pas donné, le
	//  libellé se déduit d'`accept` plutôt que du défaut : plusieurs champs de
	//  PHOTOS ne précisaient pas `mode`, et auraient annoncé « Documents » au-dessus
	//  de leurs photos (constaté en relevant les 13 usages, 16/08/2026).
	$: _nature = accept === ACCEPT_PHOTOS ? 'photos'
		: accept === ACCEPT_DOCUMENTS ? 'documents'
		: accept ? 'mixte'
		: mode;
	$: _titre = titre ?? (
		_nature === 'photos'    ? `Photos (max ${max})`
		: _nature === 'documents' ? `Documents (PDF, Word, Excel, texte — max ${max})`
		: `Pièces jointes — photos et documents (max ${max})`
	);

	const dispatch = createEventDispatcher<{ change: string[] }>();

	let envoi = false;

	//  Aperçus des fichiers RETENUS (mode différé). Mémorisés dans une `Map` et
	//  non recalculés : `apercuDe` est appelée depuis un bloc réactif, et créer
	//  une URL d'objet à chaque recalcul fuirait une entrée par frappe clavier.
	const apercus = new Map<File, string>();
	function apercuDe(f: File): string | null {
		if (!f.type.startsWith('image/')) return null;
		let u = apercus.get(f);
		if (!u) {
			u = URL.createObjectURL(f);
			apercus.set(f, u);
		}
		return u;
	}
	function oublier(f: File) {
		const u = apercus.get(f);
		if (u) {
			URL.revokeObjectURL(u);
			apercus.delete(f);
		}
	}
	//  Sortie non nominale : l'utilisateur peut quitter l'écran sans jamais
	//  soumettre ni retirer un fichier (socle 11 §12).
	onDestroy(() => {
		for (const u of apercus.values()) URL.revokeObjectURL(u);
		apercus.clear();
	});

	//  UNE seule liste rendue, quelle que soit l'origine : c'est ce qui garantit
	//  que le mode différé ne peut pas prendre une autre apparence.
	//  `apercu` non nul ⇒ vignette d'image ; nul ⇒ pastille de document.
	type Piece = { cle: string; nom: string; apercu: string | null; fichier: File | null };
	$: pieces = differe
		? fichiers.map((f, i): Piece => ({
			cle: `${i} ${f.name} ${f.size}`,
			nom: f.name,
			apercu: apercuDe(f),
			fichier: f,
		}))
		: (({ photos, documents }) => [
			...photos.map((u): Piece => ({ cle: u, nom: nomFichier(u), apercu: u, fichier: null })),
			...documents.map((u): Piece => ({ cle: u, nom: nomFichier(u), apercu: null, fichier: null })),
		])(separerFichiers(urls));
	$: vignettes = pieces.filter((p) => p.apercu !== null);
	$: pastilles = pieces.filter((p) => p.apercu === null);
	$: nombre = differe ? fichiers.length : urls.length;
	$: complet = nombre >= max;

	async function ajouter(e: Event) {
		const input = e.target as HTMLInputElement;
		const choisis = Array.from(input.files ?? []);
		input.value = '';
		if (!choisis.length || complet) return;
		//  `slice` borne à ce qui reste sous `max`, dans les deux modes.
		const retenus = choisis.slice(0, max - nombre);
		if (differe) {
			fichiers = [...fichiers, ...retenus];
			return;
		}
		envoi = true;
		try {
			// Séquentiel et non parallèle : l'API valide et redimensionne chaque
			// fichier, et un RPi qui reçoit cinq images de 4 Mo en même temps sature
			// sa mémoire.
			for (const file of retenus) {
				urls = [...urls, upload ? await upload(file) : (await fichiersApi.upload(file)).url];
			}
			dispatch('change', urls);
		} catch (err) {
			toast('error', err instanceof Error ? err.message : "Erreur lors de l'envoi du document");
		} finally {
			envoi = false;
		}
	}

	async function retirer(p: Piece) {
		if (p.fichier) {
			oublier(p.fichier);
			fichiers = fichiers.filter((f) => f !== p.fichier);
			return;
		}
		try {
			const maj = remove ? await remove(p.cle) : null;
			urls = Array.isArray(maj) ? maj : urls.filter((u) => u !== p.cle);
			dispatch('change', urls);
		} catch (err) {
			toast('error', err instanceof Error ? err.message : 'Erreur lors de la suppression');
		}
	}
</script>

<div class="fichiers-upload">
	{#if _titre}
		<label class="fichiers-titre" for={id}>{_titre}</label>
	{/if}
	{#if vignettes.length}
		<div class="fichiers-liste">
			{#each vignettes as p (p.cle)}
				<Vignette src={p.apercu ?? ''} alt="" {size} title={p.nom}>
					{#if !readonly}
						<button type="button" class="photo-retirer" title="Retirer cette photo"
							aria-label="Retirer {p.nom}" on:click={() => retirer(p)}>×</button>
					{/if}
				</Vignette>
			{/each}
		</div>
	{/if}
	{#if pastilles.length}
		<div class="fichiers-liste">
			{#each pastilles as p (p.cle)}
				<span class="fichier-chip">
					<span aria-hidden="true">&#x1F4C4;</span>
					<span class="fichier-nom">{p.nom}</span>
					{#if !readonly}
						<button type="button" class="fichier-retirer" title="Retirer ce document"
							aria-label="Retirer {p.nom}" on:click={() => retirer(p)}>×</button>
					{/if}
				</span>
			{/each}
		</div>
	{/if}

	{#if !readonly}
	<label class="btn btn-sm btn-outline fichiers-ajout" class:disabled={complet || envoi || disabled}>
		{envoi ? '⏳ Envoi…' : `\u{1F4CE} ${libelle}`}
		<input {id} type="file" multiple accept={accepte} disabled={complet || envoi || disabled} on:change={ajouter} />
	</label>
	<span class="fichiers-compte">{nombre}/{max}</span>
	{/if}
</div>

<style>
	/*  Mêmes valeurs que `.field label` : l'œil doit lire la même chose qu'un
	    intitulé de champ ordinaire. */
	.fichiers-titre { display: block; font-size: .875rem; font-weight: 500; color: var(--color-text); margin-bottom: .3rem; }
	.fichiers-upload { display: flex; flex-direction: column; gap: .5rem; align-items: flex-start; }
	.fichiers-liste { display: flex; gap: .35rem; flex-wrap: wrap; }
	.fichier-chip {
		display: inline-flex;
		align-items: center;
		gap: .3rem;
		max-width: 100%;
		padding: .2rem .45rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg-alt, #f5f5f5);
		font-size: .8rem;
	}
	.fichier-nom {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 200px;
	}
	.fichier-retirer {
		border: none;
		background: none;
		color: var(--color-danger);
		cursor: pointer;
		font-size: 1rem;
		line-height: 1;
		padding: 0;
	}
	.photo-retirer {
		position: absolute;
		top: 2px;
		right: 2px;
		background: rgba(0, 0, 0, .6);
		color: #fff;
		border: none;
		border-radius: 50%;
		width: 18px;
		height: 18px;
		font-size: .75rem;
		cursor: pointer;
		line-height: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.fichiers-ajout { cursor: pointer; display: inline-flex; align-items: center; gap: .3rem; }
	.fichiers-ajout.disabled { opacity: .5; cursor: default; }
	.fichiers-ajout input { display: none; }
	.fichiers-compte { font-size: .72rem; color: var(--color-text-muted); }
	@media (max-width: 480px) {
		.fichier-nom { max-width: 58vw; }
	}
</style>
