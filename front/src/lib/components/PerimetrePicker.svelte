<script lang="ts">
	import Pastille from '$lib/components/Pastille.svelte';
	import { perimetresStore } from '$lib/stores/perimetres';
	import { SEPARATEUR_ELEMENT, perimetreParDefaut, type Perimetre } from '$lib/perimetres';

	/** Valeurs sélectionnées — tableau de codes. Ex : ['résidence'] ou ['bat:1','parking'] */
	export let value: string[] = [];

	/** Exclusif (une seule valeur) ou multiple. Par défaut : multiple.
	    Ne change QUE le comportement de sélection : le rendu est le même —
	    des pastilles — dans les deux cas, comme partout ailleurs sur le site. */
	export let mode: 'multi' | 'single' = 'multi';

	/** Intitulé du champ. Il était écrit par CHAQUE page appelante, et elles
	    avaient divergé : « Périmètre * », « Périmètre » sans astérisque sur les
	    tickets, « Périmètre d'affichage * » sur l'espace CS (16/08/2026). Le
	    porter ici rend toute évolution héritée. Surcharger uniquement pour une
	    vraie spécificité d'écran — c'est le point d'héritage. */
	export let titre = 'Périmètre';

	/** Ajoute l'astérisque des champs requis. */
	export let requis = true;

	import { createEventDispatcher } from 'svelte';
	const dispatch = createEventDispatcher<{ change: string[] }>();

	//  L'arborescence vient de la base : une entrée ajoutée depuis
	//  `/admin/patrimoine` apparaît ici sans qu'on touche à ce fichier. C'est tout
	//  l'objet du lot — la table de sept clés qui vivait dans `lib/utils.ts` ne
	//  pouvait pas décrire une copropriété sans AFUL, ni un cinquième bâtiment.
	$: actifs = $perimetresStore.filter((n) => n.actif);
	$: parCode = new Map(actifs.map((n) => [n.code, n]));
	$: defaut = perimetreParDefaut();

	//  Un nœud de premier niveau est soit une racine sélectionnable, soit l'enfant
	//  d'un REGROUPEMENT racine (« Bâtiments » n'est pas une cible : on choisit un
	//  bâtiment). Cela remonte les bâtiments dans la première rangée, là où
	//  l'utilisateur les cherche, sans inventer de niveau dans les données.
	function estGroupeRacine(n: Perimetre | undefined): boolean {
		return !!n && n.parent === null && !n.selectionnable;
	}
	$: niveau1 = actifs.filter(
		(n) =>
			n.selectionnable &&
			n.code !== defaut &&
			(n.parent === null || estGroupeRacine(parCode.get(n.parent!))),
	);

	const codesNiveau1 = (liste: Perimetre[]) => new Set(liste.map((n) => n.code));

	/** Le nœud de premier niveau dont dépend une valeur sélectionnée, s'il y en a un. */
	function racineDe(code: string, n1: Set<string>): string | null {
		let courant = parCode.get(code);
		const vus = new Set<string>();
		while (courant && !vus.has(courant.code)) {
			if (n1.has(courant.code)) return courant.code;
			vus.add(courant.code);
			courant = courant.parent ? parCode.get(courant.parent) : undefined;
		}
		return null;
	}

	//  Le second niveau ne s'affiche que pour UN parent à la fois : proposer les
	//  espaces de quatre bâtiments simultanément produirait une rangée illisible,
	//  et le geste attendu est « je précise dans celui-ci ».
	$: n1 = codesNiveau1(niveau1);
	//  Rien n'indiquait qu'un bâtiment cachait neuf espaces : il fallait cliquer
	//  pour le découvrir, et personne ne cliquait (signalé le 12/08/2026). Le
	//  chevron dit qu'il y a un second niveau, sans l'imposer.
	$: aDesEnfants = new Set(
		actifs.filter((n) => n.selectionnable && n.parent && n1.has(n.parent)).map((n) => n.parent!),
	);
	//  🔴 Le second niveau suit le DERNIER nœud touché, pas le premier de la
	//  sélection (18/08/2026, signalé à l'écran).
	//
	//  `value.map(racineDe).find(Boolean)` retenait la PREMIÈRE valeur qui a une
	//  racine. Après « Bât. 3 › Caves, Toit » puis un clic sur « Bât. 4 », la
	//  sélection vaut ['caves:3','toit:3','bat:4'] : la première a pour racine le
	//  bâtiment 3, et la rangée de précision restait donc bloquée sur lui — on
	//  cliquait sur un bâtiment et on voyait les espaces d'un autre.
	//
	//  ⚠️ L'état est nécessaire : `value` ne dit pas dans quel ORDRE on a cliqué.
	//  Il reste dérivé quand personne n'a encore touché la rangée — à l'ouverture
	//  d'un formulaire d'édition, le second niveau s'ouvre sur ce qui est
	//  enregistré.
	let parentTouche: string | null = null;
	$: parentOuvert =
		parentTouche && aDesEnfants.has(parentTouche)
			? parentTouche
			: (value.map((v) => racineDe(v, n1)).find(Boolean) ?? null);
	$: niveau2 = parentOuvert
		? actifs.filter((n) => n.parent === parentOuvert && n.selectionnable)
		: [];

	//  Ce qu'un nœud de premier niveau porte de sélectionné en second niveau.
	//  Sert à le CONTRACTER quand sa rangée se referme : sans cela, choisir un
	//  autre bâtiment faisait disparaître « Caves, Toit » de l'écran alors qu'ils
	//  restent sélectionnés — la valeur était juste, l'écran mentait.
	$: enfantsChoisis = (code: string) =>
		actifs.filter((n) => n.parent === code && selection.has(n.code));

	$: noeudDefaut = defaut ? parCode.get(defaut) : undefined;
	$: estDefaut = value.length === 0 || (value.length === 1 && value[0] === defaut);
	$: selection = new Set(value);

	//  Aide contextuelle : la description du nœud choisi. C'est ce qui manquait
	//  entièrement — un résident n'avait nulle part l'information qu'AFUL notifie
	//  tout le conseil syndical.
	$: descriptionActive = value.length === 1 ? (parCode.get(value[0])?.description ?? '') : '';

	function choisirDefaut() {
		//  🔴 La rangée de précision se referme AUSSI (18/08/2026, signalé à
		//  l'écran) : revenir à « Copropriété entière » vidait bien toutes les
		//  pastilles, mais laissait « Préciser dans Bâtiment 1 » affiché sous elles,
		//  avec ses espaces devenus sans objet. On proposait de préciser dans un
		//  bâtiment qui n'était plus retenu.
		//
		//  ⚠️ C'est le pendant exact du défaut corrigé juste au-dessus : là,
		//  `parentTouche` survivait au geste qui le rendait faux. Un état qu'on pose
		//  se remet à zéro dans TOUS les chemins qui le contredisent — ici il n'y en
		//  a qu'un, et il avait été oublié.
		parentTouche = null;
		value = defaut ? [defaut] : [];
		dispatch('change', value);
	}

	/**
	 * 🔴 **L'ALGORITHME, REMIS À PLAT** (18/08/2026, demandé à l'écran : *« le
	 * périmètre ne fonctionne pas ; peux-tu remettre à plat l'algorithme »*).
	 *
	 * ## Ce qui n'allait pas, et qu'aucune rustine ne pouvait réparer
	 *
	 * **Une même pastille portait DEUX gestes** — « ouvrir pour préciser » et
	 * « choisir tout le bâtiment » — et il fallait deviner lequel partirait. D'où
	 * une série de symptômes qui semblaient sans rapport :
	 *
	 *   • rouvrir « Bât. 3 » pour vérifier son toit **effaçait** ce toit (le clic
	 *     était compris comme « je veux tout le bâtiment ») ;
	 *   • ou, la veille encore, **ajoutait** le bâtiment entier par-dessus son
	 *     toit — « Toit · Toit · Bâtiment 3 » ;
	 *   • et affecter un toit à deux bâtiments de suite devenait un jeu d'adresse.
	 *
	 * Chaque correctif déplaçait le défaut d'un cas à l'autre, parce que le
	 * problème n'était pas dans le calcul : **deux intentions ne tiennent pas dans
	 * un seul geste.**
	 *
	 * ## La règle, en entier — cinq lignes, aucun cas implicite
	 *
	 * | Clic sur | Sélection | Rangée |
	 * |---|---|---|
	 * | un nœud de 1ᵉʳ niveau **qui a des espaces retenus** | *inchangée* | s'ouvre |
	 * | un nœud de 1ᵉʳ niveau sans espace retenu, non retenu | il est **ajouté** | s'ouvre |
	 * | un nœud de 1ᵉʳ niveau **retenu lui-même** | il est **retiré** | se ferme |
	 * | un **espace** | il est basculé ; son bâtiment entier est retiré | reste ouverte |
	 * | « toute la copropriété » | tout est vidé | se ferme |
	 *
	 * **La première ligne est la clé** : quand un bâtiment porte déjà des espaces
	 * précisés, le clic sur lui ne veut plus dire « je choisis tout le bâtiment »,
	 * il veut dire « montre-moi ce que j'y ai mis ». On peut donc rouvrir, vérifier,
	 * ajouter un second espace, sans jamais rien perdre.
	 *
	 * ⚠️ **Comment choisir « tout le bâtiment » quand on a déjà des espaces ?** En
	 * les retirant. Ce n'est pas une lacune : « tout le bâtiment 3 » et « le toit du
	 * bâtiment 3 » sont deux cibles **exclusives**, et l'écran ne doit pas laisser
	 * croire qu'on peut les cumuler. Les retirer un à un EST la façon de dire qu'on
	 * élargit.
	 *
	 * ⚠️ **Aucune règle ne dépend de l'ordre des clics.** C'est ce qui manquait :
	 * une règle asymétrique donne un résultat différent selon le chemin suivi, et
	 * rien ne rattrape un chemin qu'on n'avait pas prévu.
	 */
	function basculer(code: string) {
		const racine = racineDe(code, n1);
		const estNiveau1 = racine === code;

		if (mode === 'single') {
			parentTouche = racine;
			value = [code];
			dispatch('change', value);
			return;
		}

		const s = new Set(value.filter((v) => v !== defaut));
		const espacesRetenus = [...s].filter((v) => v !== code && racineDe(v, n1) === code);

		if (estNiveau1 && espacesRetenus.length > 0 && !s.has(code)) {
			//  1. Le nœud porte des espaces précisés : on vient les REVOIR, pas les
			//     remplacer. La sélection ne bouge pas d'un iota.
			parentTouche = code;
			return;
		}

		if (s.has(code)) {
			//  2 & 3. Retirer ce qui était retenu. Retirer le nœud de premier niveau
			//     referme sa rangée ; retirer un espace la laisse ouverte — on en
			//     précise souvent plusieurs à la suite, et refermer sous le doigt
			//     obligerait à rouvrir.
			s.delete(code);
			if (estNiveau1) parentTouche = null;
		} else {
			parentTouche = racine;
			//  4. Un espace remplace son bâtiment : « Bât. 2 › Hall » veut dire le
			//     hall, pas les deux. Le cas inverse — un bâtiment par-dessus ses
			//     espaces — ne peut plus se produire : il est intercepté en 1.
			if (!estNiveau1 && racine) s.delete(racine);
			s.add(code);
		}

		value = s.size > 0 ? [...s] : defaut ? [defaut] : [];
		dispatch('change', value);
	}

</script>

<!--  UN SEUL RENDU pour les deux modes (16/08/2026).
      `mode="single"` rendait ici une LISTE DÉROULANTE là où tout le reste du
      site affiche des pastilles. Le composant était donc bien mutualisé — et
      portait la divergence lui-même : même notion, deux apparences selon un
      attribut, ce que `standards/11` §1 interdit (un pattern par notion).
      Signalé sur l'écran Prestataires, seul utilisateur de ce mode avec le
      formulaire d'édition du même écran.

      Rien n'est perdu à la suppression : l'exclusivité du mode `single` vit
      dans `basculer()` (elle remplace la valeur au lieu de l'ajouter), pas
      dans le `<select>`. Le rendu en pastilles apporte en plus ce que la liste
      déroulante ne pouvait pas donner : les icônes, le second niveau, et la
      description du nœud choisi — l'information qu'AFUL notifie tout le
      conseil syndical, par exemple. -->
{#if titre}
	<!--  Le BADGE dit l'état retenu sans qu'on ait à lire les pastilles : « Toute
	      la résidence » quand rien n'est précisé. Inauguré par le sondage, étendu
	      au standard à la demande de l'utilisateur (skill ux-patterns §9 quater). -->
	<div class="perimetre-titre">
		{titre}{#if requis} *{/if}
		{#if estDefaut && noeudDefaut}<span class="badge badge-green perimetre-badge">{noeudDefaut.libelle}</span>{/if}
	</div>
{/if}
<div class="perimetre-pills">
	{#if defaut}
		<Pastille active={estDefaut} icone={noeudDefaut?.icone ?? ''} on:click={choisirDefaut}>
			{noeudDefaut?.libelle ?? defaut}
		</Pastille>
	{/if}
	<!--  🔴 La pastille se CONTRACTE quand sa rangée se referme (18/08/2026).
	      Choisir un autre bâtiment fait disparaître la rangée de précision du
	      précédent — et avec elle, à l'écran, les espaces qu'on venait d'y
	      cocher. Ils restaient pourtant sélectionnés : la valeur était juste et
	      l'écran mentait. Le nœud porte donc son résumé, « Bât. 3 › Caves · Toit ».

	      Les séparateurs ne sont pas inventés ici : « › » est déjà la marque du
	      second niveau (R3, le chevron des pastilles) et « · » celui du
	      multi-périmètre (`perimetreLabel`). Le chevron final disparaît quand le
	      résumé est là — il annonce « un second niveau existe », ce que le résumé
	      dit déjà, et « Bât. 3 › Caves · Toit › » ne voudrait rien dire.

	      `libelle_court` pour les enfants : la pastille est en `nowrap`, et trois
	      libellés longs la feraient déborder de la largeur du téléphone. -->
	{#each niveau1 as n (n.code)}
		{@const choisis = enfantsChoisis(n.code)}
		<!--  🔴 LE RÉSUMÉ EST PERMANENT (18/08/2026, signalé à l'écran). Il
		      n'apparaissait qu'une fois la rangée refermée : en précisant « Toit »
		      dans le bâtiment 3, on ne voyait donc RIEN changer sur le bâtiment 3
		      lui-même — « le dernier enfant sélectionné, on ne sait pas s'il a été
		      sauvegardé ».

		      Demandé ainsi : « dès qu'on clique sur un enfant, il est sélectionné,
		      mais en plus il est AGRÉGÉ au niveau du parent — ou désagrégé si on le
		      désélectionne ». L'agrégation devient l'accusé de réception du clic, et
		      elle vaut rangée ouverte comme fermée.

		      ⚠️ L'espace se lit alors deux fois quand la rangée est ouverte : dans le
		      résumé et dans la rangée. Ce n'est pas une redite mais un RETOUR — la
		      rangée dit ce qu'on PEUT choisir, le résumé ce qui EST retenu. C'est
		      justement leur écart qui manquait. -->
		{@const contracte = choisis.length > 0}
		<!--  🔴 LA MÈRE RESTE PLEINE dès qu'un de ses espaces est retenu, rangée
		      ouverte ou non (18/08/2026, ARBITRAGE CORRIGÉ PAR L'ÉCRAN).

		      J'avais conditionné cela à `contracte`, en craignant qu'une mère pleine
		      au-dessus d'« Ascenseur » plein se lise « tout le bâtiment ET
		      l'ascenseur ». L'utilisateur a réfuté, capture à l'appui : *« quand on
		      sélectionne une catégorie de niveau 2, la pastille mère se
		      désélectionne : elle ne devrait pas »*.

		      Il a raison, et mon objection portait à faux : une mère creuse ne dit
		      pas « le bâtiment n'est pas concerné », elle donne l'impression d'avoir
		      PERDU le choix qu'on vient de faire — c'est le même défaut que la
		      disparition du résumé, en plus discret. Ce qui lève l'ambiguïté n'est
		      pas de vider la mère, c'est que la rangée ouverte montre lequel de ses
		      espaces est retenu.

		      ⚠️ La VALEUR ne change pas : `basculer()` retire toujours le bâtiment
		      quand on précise un espace (`s.delete(racine)`). C'est bien l'ascenseur
		      qui est ciblé, pas le bâtiment entier — seule la lecture est corrigée. -->
		<Pastille active={!estDefaut && (selection.has(n.code) || choisis.length > 0)}
			icone={n.icone ?? ''}
			chevron={aDesEnfants.has(n.code) && !contracte}
			on:click={() => basculer(n.code)}
			>{n.libelle}{#if contracte}<span class="perimetre-resume"
				> › {choisis
					.map((e) => e.libelle_court || e.libelle)
					.join(SEPARATEUR_ELEMENT)}</span
			>{/if}</Pastille>
	{/each}
</div>

{#if niveau2.length > 0}
	<div class="perimetre-niveau2">
		<p class="perimetre-precision">
			Préciser dans {parCode.get(parentOuvert ?? '')?.libelle ?? ''}
			<span class="perimetre-facultatif">— facultatif</span>
		</p>
		<div class="perimetre-pills">
			{#each niveau2 as espace (espace.code)}
				<Pastille petite active={selection.has(espace.code)}
					on:click={() => basculer(espace.code)}>{espace.libelle}</Pastille>
			{/each}
		</div>
	</div>
{/if}

{#if descriptionActive}
	<p class="perimetre-aide">{descriptionActive}</p>
{/if}

<style>
	/*  La PASTILLE elle-même est un objet — `Pastille.svelte` — qui porte son
	    balisage et son style ensemble : c'est ce qui les empêche de diverger, et
	    ce qui garantit qu'un second écran ne pourra pas hériter de l'un sans
	    l'autre (régression du 16/08/2026, pastilles nues sur les sondages).

	    Le CONTENEUR, lui, reste ici : c'est une mise en page, propre à cet
	    écran — pas une propriété de la pastille. */
	.perimetre-pills { display: flex; flex-wrap: wrap; gap: .4rem; }
	.perimetre-titre { font-size: .875rem; font-weight: 500; color: var(--color-text); margin-bottom: .3rem; }
	.perimetre-badge { font-size: .72rem; margin-left: .4rem; }
	/*  Le résumé d'une pastille contractée : légèrement en retrait pour qu'on lise
	    d'abord le nœud, puis ce qu'il contient. Il est rendu ICI, donc stylé ici —
	    une classe posée sur le contenu d'un slot appartient à l'appelant, jamais
	    au composant qui l'accueille (v2.67.11). */
	.perimetre-resume { opacity: .85; font-weight: 500; }
	.perimetre-niveau2 { margin-top: .6rem; padding-left: .1rem; }
	.perimetre-precision { font-size: .8rem; color: var(--color-text-muted); margin: 0 0 .35rem; }
	.perimetre-facultatif { opacity: .75; }
	.perimetre-aide { font-size: .8rem; color: var(--color-text-muted); line-height: 1.5; margin: .6rem 0 0; }
</style>
