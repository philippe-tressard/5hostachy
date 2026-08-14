<!--
  Les préférences personnelles du profil : ce que je VOIS, ce que je REÇOIS.

  Extrait de `routes/(app)/profil/+page.svelte` le 14/08/2026 (#339). La page
  dépassait 838 lignes — le contrôle de modularité refuse qu'un fichier déjà
  au-dessus de 500 grossisse, et il fallait y ajouter la case de visibilité.

  Les deux blocs vivent ensemble parce qu'ils répondent à la même question du
  résident — « qu'est-ce que la copropriété m'envoie ? » — mais ils sont
  séparés visuellement, et ce n'est pas cosmétique :

  ⚠️ La case de visibilité est une préférence d'**affichage**, jamais une mesure
  de confidentialité. Le résident se restreint lui-même et peut se déverrouiller
  quand il veut. Ce qui protège réellement — qui a le droit de lire quoi — reste
  le public cible d'une publication et les profils d'accès aux documents, que ce
  lot ne touche pas. L'interface ne doit donc jamais laisser croire que cocher
  cette case cache quelque chose à quelqu'un.
-->
<script lang="ts">
	export let valeurs: Record<string, boolean>;
	export let restreindre = false;
	export let onSave: (valeurs: Record<string, boolean>, restreindre: boolean) => void;

	const LIGNES = [
		{ cle: 'ticket', libelle: 'Mises à jour de mes tickets' },
		{ cle: 'actu', libelle: 'Nouvelles publications / actualités' },
		{ cle: 'doc', libelle: 'Nouveaux documents ajoutés' },
		{ cle: 'communaute', libelle: 'Réponses à mes idées / annonces / sondages' },
	];
</script>

<section class="card" style="margin-bottom:1.5rem">
	<h2 class="section-title">Ce que j'affiche</h2>
	<label class="checkbox-field">
		<input type="checkbox" bind:checked={restreindre} />
		N'afficher que les contenus de mon ou mes bâtiments
	</label>
	<p class="notif-help" style="padding-left:1.55rem">
		Décochée, vous voyez les actualités de toute la copropriété : un chantier, une coupure ou
		une réunion vous concernent souvent sans être « chez vous ». Cochée, vous retrouvez
		l'affichage d'avant — seuls les contenus de votre bâtiment, et de ceux où vous avez un lot.
		Ce réglage ne change rien aux documents et aux sondages, qui restent réservés aux personnes
		concernées.
	</p>

	<h2 class="section-title" style="margin-top:1.5rem">Préférences de notifications</h2>
	<p class="notif-help">Affiner ces réglages vous évite le bruit inutile et vous garantit de recevoir les informations importantes sur le bon canal.</p>
	<div class="notif-matrix-wrap">
		<table class="notif-matrix" aria-label="Préférences de notifications">
			<thead>
				<tr>
					<th>Type d'action</th>
					<th>Dans l'appli</th>
					<th>Par e-mail</th>
				</tr>
			</thead>
			<tbody>
				{#each LIGNES as ligne}
					<tr>
						<td>{ligne.libelle}</td>
						<td><input type="checkbox" bind:checked={valeurs[`${ligne.cle}_app`]} aria-label="{ligne.libelle} — notification dans l'application" /></td>
						<td><input type="checkbox" bind:checked={valeurs[`${ligne.cle}_mail`]} aria-label="{ligne.libelle} — notification par e-mail" /></td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<div class="form-actions">
		<button type="button" class="btn btn-primary" on:click={() => onSave(valeurs, restreindre)}>Enregistrer</button>
	</div>
</section>

<style>
	.notif-help { font-size: .82rem; color: var(--color-text-muted); margin: .35rem 0 .75rem; line-height: 1.5; }
	.notif-matrix-wrap { overflow-x: auto; }
	.notif-matrix { width: 100%; border-collapse: collapse; font-size: .88rem; }
	.notif-matrix th, .notif-matrix td { padding: .45rem .5rem; border-bottom: 1px solid var(--color-border); text-align: left; }
	.notif-matrix th:not(:first-child), .notif-matrix td:not(:first-child) { text-align: center; width: 6.5rem; }
	.checkbox-field { display: flex; align-items: flex-start; gap: .55rem; font-size: .9rem; }
</style>
