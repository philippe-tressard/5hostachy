<script lang="ts">
	export let password: string = '';

	$: hasLength  = password.length >= 8;
	$: hasUpper   = /[A-Z]/.test(password);
	$: hasDigit   = /\d/.test(password);
	$: hasSpecial = /[@$!%*?&#._\-+]/.test(password);

	$: score = [hasLength, hasUpper, hasDigit, hasSpecial].filter(Boolean).length;

	$: gaugeColor =
		score === 4 ? '#16a34a' :
		score === 3 ? '#d97706' :
		score >= 1  ? '#dc2626' :
		'transparent';

	$: gaugeLabel =
		score === 4 ? 'Fort' :
		score === 3 ? 'Moyen' :
		score >= 1  ? 'Faible' :
		'';

	const criteria = [
		{ label: '8 caractères minimum',          ok: () => hasLength  },
		{ label: 'Une lettre majuscule',           ok: () => hasUpper   },
		{ label: 'Un chiffre',                     ok: () => hasDigit   },
		{ label: 'Un caractère spécial (@$!%*?&#._-+)', ok: () => hasSpecial },
	];
</script>

{#if password.length > 0}
<div class="pwd-strength" role="status" aria-live="polite" aria-label="Force du mot de passe : {gaugeLabel}">
	<div class="gauge">
		{#each [0, 1, 2, 3] as i}
			<div
				class="gauge-bar"
				style={score > i ? `background:${gaugeColor}` : ''}
			></div>
		{/each}
		{#if gaugeLabel}
			<span class="gauge-label" style="color:{gaugeColor}">{gaugeLabel}</span>
		{/if}
	</div>
	<ul class="criteria-list">
		{#each [
			{ label: '8 caractères minimum',               ok: hasLength  },
			{ label: 'Une lettre majuscule',               ok: hasUpper   },
			{ label: 'Un chiffre',                         ok: hasDigit   },
			{ label: 'Un caractère spécial (@$!%*?&#._-+)', ok: hasSpecial },
		] as c}
			<li class:ok={c.ok}>
				<span class="check-icon">{c.ok ? '✓' : '○'}</span>
				{c.label}
			</li>
		{/each}
	</ul>
</div>
{/if}

<style>
	.pwd-strength { margin-top: .5rem; }

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
	.criteria-list li.ok { color: #16a34a; }
	.check-icon { width: 1rem; text-align: center; font-size: .85rem; flex-shrink: 0; }
</style>
