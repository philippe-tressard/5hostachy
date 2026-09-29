<!--
  Un encart d'avertissement : fond et filet de la teinte d'avertissement, le
  texte restant en couleur de texte — `--color-warning` ne sert jamais au texte
  (charte, `ux-patterns` §18).

  Créé le 29/09/2026 (#779) : le profil l'écrivait deux fois (`.info-banner
  .info-yellow`), et le découper en deux fichiers aurait recopié la règle. La
  notion est écrite une douzaine de fois ailleurs, chacune avec sa marge et son
  rayon : leur migration est un ticket à part, pas ce lot.
-->
<div class="encart-avertissement"><slot /></div>

<style>
	.encart-avertissement {
		padding: 0.6rem 0.9rem;
		border-radius: var(--radius);
		font-size: var(--fs-md);
		background: var(--color-warning-fond);
		border: 1px solid var(--color-warning-bordure);
	}
</style>
