<!--
  Jauge de robustesse d'un mot de passe, affichée sous le champ de saisie par
  `ChampMotDePasse.svelte` (prop `robustesse`).

  Deux corrections le 15/08/2026 (issue #344) :
  — la liste des critères existait en DEUX exemplaires dans ce fichier, une
    constante `criteria` que plus rien ne lisait et un tableau recopié dans le
    `{#each}` ; c'est exactement l'orphelin décrit par `standards/02` §5, et il
    aurait divergé au premier critère ajouté. Une seule liste désormais ;
  — l'apparition était sèche et sans hiérarchie : le bloc pousse maintenant le
    reste du formulaire en s'ouvrant, et se présente comme une carte rattachée
    au champ plutôt que comme du texte flottant.
-->
<script lang="ts">
	export let password: string = '';

	$: hasLength  = password.length >= 8;
	$: hasUpper   = /[A-Z]/.test(password);
	$: hasDigit   = /\d/.test(password);
	$: hasSpecial = /[@$!%*?&#._\-+]/.test(password);

	$: score = [hasLength, hasUpper, hasDigit, hasSpecial].filter(Boolean).length;

	/* Deux teintes par niveau, et ce n'est pas un oubli de factorisation : un
	   aplat de 4 px ne se lit pas comme du texte de 12 px. Les barres gardent la
	   couleur vive, le libellé prend la variante foncée qui atteint le rapport
	   de contraste AA de 4,5:1 (`standards/11` §13.2) — #16a34a et #d97706 y
	   échouaient sur fond clair. */
	$: jaugeCouleur =
		score === 4 ? '#16a34a' :
		score === 3 ? '#d97706' :
		score >= 1  ? '#dc2626' :
		'transparent';

	$: libelleCouleur =
		score === 4 ? '#15803d' :
		score === 3 ? '#b45309' :
		score >= 1  ? '#b91c1c' :
		'inherit';

	$: gaugeLabel =
		score === 4 ? 'Fort' :
		score === 3 ? 'Moyen' :
		score >= 1  ? 'Faible' :
		'';

	// La seule et unique liste des critères.
	$: criteres = [
		{ label: '8 caractères minimum',                ok: hasLength  },
		{ label: 'Une lettre majuscule',                ok: hasUpper   },
		{ label: 'Un chiffre',                          ok: hasDigit   },
		{ label: 'Un caractère spécial (@$!%*?&#._-+)', ok: hasSpecial },
	];
</script>

<!-- La région `status` reste montée en permanence : une zone d'annonce créée en
     même temps que son contenu n'est pas annoncée par tous les lecteurs d'écran. -->
<div class="pwd-strength" class:ouvert={password.length > 0}>
	<div class="pwd-inner" role="status" aria-live="polite" aria-label="Force du mot de passe : {gaugeLabel}">
		{#if password.length > 0}
			<div class="pwd-carte">
				<div class="gauge">
					{#each [0, 1, 2, 3] as i}
						<div class="gauge-bar" style={score > i ? `background:${jaugeCouleur}` : ''}></div>
					{/each}
					{#if gaugeLabel}
						<span class="gauge-label" style="color:{libelleCouleur}">{gaugeLabel}</span>
					{/if}
				</div>
				<ul class="criteria-list">
					{#each criteres as c}
						<li class:ok={c.ok}>
							<span class="check-icon">{c.ok ? '✓' : '○'}</span>
							{c.label}
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	</div>
</div>

<style>
	/* Ouverture par `grid-template-rows: 0fr → 1fr` : la hauteur du contenu n'a
	   pas à être connue à l'avance, et là où la propriété n'est pas animable le
	   bloc apparaît d'un coup — le comportement d'avant, jamais pire. */
	.pwd-strength {
		display: grid;
		grid-template-rows: 0fr;
		margin-top: 0;
		opacity: 0;
		transition: grid-template-rows .18s ease, opacity .18s ease, margin-top .18s ease;
	}
	.pwd-strength.ouvert {
		grid-template-rows: 1fr;
		margin-top: .5rem;
		opacity: 1;
	}
	.pwd-inner { overflow: hidden; min-height: 0; }

	@media (prefers-reduced-motion: reduce) {
		.pwd-strength { transition: none; }
	}

	.pwd-carte {
		padding: .55rem .7rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
	}

	.gauge { display: flex; align-items: center; gap: .25rem; margin-bottom: .45rem; }
	.gauge-bar {
		flex: 1;
		height: 4px;
		border-radius: 2px;
		background: var(--color-border, #e5e7eb);
		transition: background .2s ease;
	}
	.gauge-label {
		font-size: .75rem;
		font-weight: 600;
		min-width: 3rem;
		text-align: right;
		transition: color .2s ease;
	}

	.criteria-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: .2rem;
	}
	.criteria-list li {
		display: flex;
		align-items: center;
		gap: .35rem;
		font-size: .8rem;
		color: var(--color-text-muted, #6b7280);
		transition: color .15s ease;
	}
	.criteria-list li.ok { color: #15803d; }
	.check-icon { width: 1rem; text-align: center; font-size: .85rem; flex-shrink: 0; }
</style>
