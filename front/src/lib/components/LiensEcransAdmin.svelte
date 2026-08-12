<!--
	Les écrans d'administration qui vivent sur leur PROPRE route, par opposition
	aux onglets internes d'`admin/+page.svelte`.

	Extrait le 12/08/2026 en reliant `copropriete` et `sauvegardes` (#307) :
	`admin/+page.svelte` est à 2259 lignes et le garde-fou de modularité — rang 1,
	sans exception — refuse qu'un fichier de plus de 500 lignes grossisse.

	⚠️ Les adresses restent écrites EN TOUTES LETTRES, une par lien. Les produire
	par un `{#each}` sur un tableau de routes ferait disparaître le littéral
	`/admin/…`, et `scripts/check-routes-atteignables.mjs` — le contrôle né de
	#307, qui cherche exactement ce littéral — déclarerait alors ces six écrans
	orphelins. Un raccourci d'écriture qui aveugle son propre garde-fou coûte plus
	qu'il ne rapporte.
-->
<a href="/admin/lots-import" class="tab-btn" style="text-decoration:none">Import Lots</a>
<a href="/admin/telecommandes-import" class="tab-btn" style="text-decoration:none">Import TC</a>
<a href="/admin/vigiks-import" class="tab-btn" style="text-decoration:none">Import Vigik</a>
<a href="/admin/audit-lots" class="tab-btn" style="text-decoration:none">Audit lots</a>
<a href="/admin/copropriete" class="tab-btn" style="text-decoration:none">Fiche copropriété</a>
<a href="/admin/sauvegardes" class="tab-btn" style="text-decoration:none">Sauvegardes</a>
