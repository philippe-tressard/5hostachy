<script lang="ts">
	import Pastille from '$lib/components/Pastille.svelte';
	import { perimetresStore } from '$lib/stores/perimetres';
	import { perimetreParDefaut, type Perimetre } from '$lib/perimetres';

	/** Valeurs sélectionnées — tableau de codes. Ex : ['résidence'] ou ['bat:1','parking'] */
	export let value: string[] = [];

	/** Exclusif (une seule valeur) ou multiple. Par défaut : multiple.
	    Ne change QUE le comportement de sélection : le rendu est le même —
	    des pastilles — dans les deux cas, comme partout ailleurs sur le site. */
	export let mode: 'multi' | 'single' = 'multi';

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
	$: parentOuvert = value.map((v) => racineDe(v, n1)).find(Boolean) ?? null;
	$: niveau2 = parentOuvert
		? actifs.filter((n) => n.parent === parentOuvert && n.selectionnable)
		: [];

	$: noeudDefaut = defaut ? parCode.get(defaut) : undefined;
	$: estDefaut = value.length === 0 || (value.length === 1 && value[0] === defaut);
	$: selection = new Set(value);

	//  Aide contextuelle : la description du nœud choisi. C'est ce qui manquait
	//  entièrement — un résident n'avait nulle part l'information qu'AFUL notifie
	//  tout le conseil syndical.
	$: descriptionActive = value.length === 1 ? (parCode.get(value[0])?.description ?? '') : '';

	function choisirDefaut() {
		value = defaut ? [defaut] : [];
		dispatch('change', value);
	}

	function basculer(code: string) {
		if (mode === 'single') {
			value = [code];
			dispatch('change', value);
			return;
		}
		const s = new Set(value.filter((v) => v !== defaut));
		if (s.has(code)) {
			s.delete(code);
		} else {
			//  Choisir un espace remplace son bâtiment : « Bât. 2 » puis
			//  « Bât. 2 › Hall » veut dire le hall, pas les deux.
			const racine = racineDe(code, n1);
			if (racine && racine !== code) s.delete(racine);
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
<div class="perimetre-pills">
	{#if defaut}
		<Pastille active={estDefaut} icone={noeudDefaut?.icone ?? ''} on:click={choisirDefaut}>
			{noeudDefaut?.libelle ?? defaut}
		</Pastille>
	{/if}
	{#each niveau1 as n (n.code)}
		<Pastille active={!estDefaut && selection.has(n.code)} icone={n.icone ?? ''}
			chevron={aDesEnfants.has(n.code)} on:click={() => basculer(n.code)}>{n.libelle}</Pastille>
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
	.perimetre-niveau2 { margin-top: .6rem; padding-left: .1rem; }
	.perimetre-precision { font-size: .8rem; color: var(--color-text-muted); margin: 0 0 .35rem; }
	.perimetre-facultatif { opacity: .75; }
	.perimetre-aide { font-size: .8rem; color: var(--color-text-muted); line-height: 1.5; margin: .6rem 0 0; }
</style>
