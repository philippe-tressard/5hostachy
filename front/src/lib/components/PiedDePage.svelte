<!--
  LE pied de page de l'application : celui du squelette `(app)`, et son aperçu
  dans Admin › Site. Un seul rendu pour les deux, si bien que l'aperçu montre ce
  que le site affichera (08/10/2026).

  Les éléments et ceux qui se masquent sont dans `$lib/piedDePage`.

  La version s'affiche courte (« v2.118.1 · RPi1 »). L'empreinte du build et sa
  date passent dans l'infobulle : elles servent toujours au diagnostic, par
  exemple pour voir un onglet PWA resté sur une version en cache. P3 lit la
  version dans le bundle, pas ici (`check-version-servie.mjs`).
-->
<script lang="ts">
	import pkg from '../../../package.json';
	import { env } from '$env/dynamic/public';
	import { configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { lienSource, NOM_PLATEFORME } from '$lib/plateforme';
	import { elementsAffiches, mentionAnnee, type ReglagePied } from '$lib/piedDePage';

	/** Le réglage, déjà lu (`lireReglagePied`). */
	export let reglage: ReglagePied;

	const empreinte = import.meta.env.VITE_GIT_HASH ?? 'dev';
	//  Le nœud se lit à l'EXÉCUTION (`PUBLIC_INSTANCE_ID`, docker-compose) : une
	//  image construite par la CI sert les deux nœuds (#1758).
	const serveur = env.PUBLIC_INSTANCE_ID || '';
	const version = `v${pkg.version}`;
	const build = [version, empreinte, import.meta.env.VITE_BUILD_DATE].filter(Boolean).join(' · ');
	const anneeCourante = new Date().getFullYear();

	$: siteUrl = $configStore['site_url'] ?? '';
	//  Sans identifiant de nœud (poste de développement), il n'y a rien à dire.
	$: affiches = elementsAffiches(reglage).filter((c) => c !== 'serveur' || serveur);
</script>

<footer class="app-footer">
	<!--  Le séparateur est tracé par la feuille de style, entre deux éléments :
	      écrit dans le balisage, il héritait des blancs du gabarit d'un seul côté. -->
	{#each affiches as code (code)}
		<span class="element"
			>{#if code === 'annee'}{mentionAnnee(
					reglage.anneeDebut,
					anneeCourante,
				)}{:else if code === 'texte'}{reglage.texte}{:else if code === 'residence'}{#if reglage.prefixeNom}{reglage.prefixeNom}&nbsp;{/if}<a
					href={siteUrl}
					target="_blank"
					rel="noopener noreferrer">{$siteNomStore}</a
				>{:else if code === 'version'}<span title={build}>{version}</span
				>{:else if code === 'serveur'}RPi{serveur}{:else if code === 'source'}<a
					href={lienSource(empreinte)}
					target="_blank"
					rel="noopener noreferrer"
					title="Le code source de la version en service">{NOM_PLATEFORME}</a
				>{:else if code === 'mentions'}<a href="/mentions-legales">Mentions légales</a
				>{:else if code === 'confidentialite'}<a href="/politique-de-confidentialite"
					>Politique de confidentialité</a
				>{/if}</span
		>
	{/each}
</footer>

<style>
	.app-footer {
		text-align: center;
		padding: 0.75rem 1rem;
		font-size: var(--fs-2xs);
		color: var(--color-text-muted);
		border-top: 1px solid var(--color-border);
		letter-spacing: 0.02em;
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
	}
	.element:not(:last-child)::after {
		/*  Un point de lecture, pas un mot : le texte de remplacement est vide.
		    Accroché à l'élément qui PRÉCÈDE, il reste en fin de ligne quand le
		    pied de page passe à la ligne, au lieu d'en ouvrir une. */
		content: '·' / '';
		margin: 0 0.4em;
	}
</style>
