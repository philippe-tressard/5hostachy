<!--
  L'onglet **Paramétrage site** de l'administration.

  ## Pourquoi il existe (#513)

  Sept onglets d'administration étaient déjà des composants ; celui-ci vivait
  encore dans `admin/+page.svelte`. Le garde-fou de modularité a refusé d'y
  ajouter le second délai d'archivage — et il disait vrai : une page de 1 500
  lignes qui porte encore un onglet entier n'a pas un problème de taille, elle a
  un problème de découpage (#453).

  ## Ce qui reste chez le parent

  `siteConfig` est LIÉ et `saveSiteConfig` arrive en callback : c'est la page qui
  parle à l'API et qui met à jour le `configStore`. Dupliquer l'appel ici
  donnerait deux vérités sur la configuration du site.
-->
<script lang="ts">
	import { nomAffiche } from '$lib/noms';
	import Icon from '$lib/components/Icon.svelte';

	/** Lié : la page porte l'état et l'enregistre. */
	export let siteConfig: any;
	export let siteSaving = false;
	export let siteManagerUsers: any[] = [];
	export let saveSiteConfig: () => void;
</script>

<section class="card config-section">
	<h2 class="config-section-title"><Icon name="settings" size={17} />Paramètres généraux</h2>
	<div class="form-grid largeur-saisie">
		<label class="field">
			Nom de la plateforme
			<input type="text" bind:value={siteConfig.nom} placeholder="5Hostachy" />
			<span class="field-hint">Affiché sur la page de connexion et dans le menu.</span>
		</label>
		<label class="field">
			URL publique
			<input type="url" bind:value={siteConfig.url} placeholder="https://..." />
		</label>
		<label class="field" style="grid-column:span 2">
			E-mail administrateur
			<input type="email" bind:value={siteConfig.email_admin} placeholder="admin@example.com" />
			<span class="field-hint"
				>Adresse de secours utilisée si aucun utilisateur gestionnaire du site n'est sélectionné.</span
			>
		</label>
		<label class="field" style="grid-column:span 2">
			Gestionnaire du site (utilisateur)
			<select bind:value={siteConfig.site_manager_user_id}>
				<option value="">Aucun (utiliser l'e-mail administrateur)</option>
				{#each siteManagerUsers as u (u.id)}
					<option value={String(u.id)}>{nomAffiche(u)} — {u.email}</option>
				{/each}
			</select>
			<span class="field-hint"
				>Cet utilisateur est considéré comme gestionnaire du site dans l'administration et reçoit
				les notifications e-mail « Bug » si l'option est activée.</span
			>
		</label>
		<label class="field" style="grid-column:span 2">
			Sous-titre de la page de connexion
			<input
				type="text"
				bind:value={siteConfig.login_sous_titre}
				placeholder="Votre espace numérique de résidence"
			/>
			<span class="field-hint">Affiché sous le nom du site sur la page de connexion.</span>
		</label>
		<!--  🔴 UN SEUL délai, pour tout le site (#515). Il y en avait TROIS : deux
          affichés ici — dont un qui ne concernait plus qu'un statut devenu
          inatteignable — et un troisième CODÉ EN DUR dans `annonces.py`, que
          l'écran n'a jamais montré. C'est le mélange qui a fait dire « je
          croyais qu'il était de 30 » (#513).

          ⚠️ Ce champ gouverne SEPT objets, pas seulement les actualités : le
          texte d'aide doit le dire, sinon on croira régler une seule page. -->
		<label class="field champ-court" style="grid-column:span 2">
			Délai d'archivage automatique (jours)
			<input
				type="number"
				bind:value={siteConfig.archivage_delai_jours}
				min="1"
				max="365"
				placeholder="30"
			/>
			<span class="field-hint"
				>Un contenu terminé quitte les listes actives et bascule dans les <strong>Archives</strong>
				après ce délai (défaut : 30 jours). Il s'applique à <strong>tout le site</strong> :
				actualités, tickets résolus, petites annonces vendues ou données, idées décidées, sondages
				clôturés, événements passés et affiches de hall envoyées. Un contenu <strong>annulé</strong> est
				archivé immédiatement, sans attendre — et le bouton 📦 archive à la main, quel que soit ce réglage.</span
			>
		</label>
		<label class="field champ-court" style="grid-column:span 2">
			Délai de relance syndic (jours)
			<input
				type="number"
				bind:value={siteConfig.relance_syndic_delai_jours}
				min="1"
				max="365"
				placeholder="30"
			/>
			<span class="field-hint"
				>Nombre de jours sans mise à jour d'un ticket destinataire-syndic avant qu'il apparaisse
				dans la liste de relance de l'Espace CS (défaut : 30 jours).</span
			>
		</label>
		<label class="field" style="grid-column:span 2">
			<span class="case">
				<input type="checkbox" bind:checked={siteConfig.notify_ticket_bug_email} />
				Notifier si un bug (Tickets)
			</span>
			<span class="field-hint"
				>Envoie un e-mail au gestionnaire du site sélectionné (ou à l'adresse administrateur de
				secours) uniquement pour les tickets de catégorie « Bug ». Les tickets « Urgence » ne
				déclenchent pas cette notification.</span
			>
		</label>
		<label class="field" style="grid-column:span 2">
			<span class="case">
				<input type="checkbox" bind:checked={siteConfig.notify_new_user_created_email} />
				Notifier si un nouvel utilisateur est créé
			</span>
			<span class="field-hint"
				>Envoie un e-mail au gestionnaire du site sélectionné (ou à l'adresse administrateur de
				secours) lorsqu'un nouveau compte est créé et mis en attente de validation.</span
			>
		</label>
	</div>
	<div class="form-actions largeur-saisie">
		<button class="btn btn-primary" on:click={saveSiteConfig} disabled={siteSaving}>
			{siteSaving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</section>
