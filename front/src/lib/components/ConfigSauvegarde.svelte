<script lang="ts">
	/**
	 * Réglage de la sauvegarde quotidienne — heure et rétention.
	 *
	 * ## Ce qui vivait avant sur `/admin/sauvegardes`, et ne marchait pas
	 *
	 * Cet écran portait aussi « Sauvegarde immédiate » et « Historique des
	 * sauvegardes », **strictement redondants** avec l'onglet Maintenance : mêmes
	 * points d'accès (`POST /admin/sauvegardes/maintenant`,
	 * `GET /admin/sauvegardes/historique`), déjà appelés par `TachesPlanifiees`
	 * sous la ligne « Sauvegarde quotidienne ». C'était la duplication que #299
	 * avait supprimée dans l'autre sens. **Maintenance est désormais le seul
	 * endroit qui montre et déclenche les tâches planifiées.**
	 *
	 * Surtout, son formulaire n'enregistrait presque rien :
	 * `PUT /admin/sauvegardes/config` applique `if hasattr(cfg, k)`, or il envoyait
	 * `heure` et `nb_versions` quand le modèle porte `heure_execution` et
	 * `nb_versions_conservees` — **les deux champs étaient ignorés en silence**.
	 * Les valeurs affichées venaient de l'initialisation locale, pas du serveur.
	 * Et son option « Désactivée » n'existe pas dans `FrequenceSauvegarde`.
	 *
	 * ## Pourquoi il n'y a plus de choix de fréquence
	 *
	 * `quotidienne` / `hebdomadaire` / `mensuelle` sont EXCLUSIFS : choisir
	 * « hebdomadaire » ne s'ajoute pas au quotidien, il le remplace. Sur une base
	 * de quelques mégaoctets, espacer les sauvegardes n'apporte rien et coûte des
	 * jours de données en cas de perte. Le choix est retiré (13/08/2026) et la
	 * migration `0139` ramène les installations existantes au quotidien.
	 *
	 * À ne pas confondre avec la **Maintenance hebdomadaire** (`maintenance.sh`,
	 * cron du dimanche 3 h : purges, VACUUM, rotation des logs, cache Docker) :
	 * deux tâches distinctes, deux ordonnanceurs — celle-ci tourne dans l'API.
	 */
	import { onMount } from 'svelte';
	import { admin, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';

	//  Les NOMS DU MODÈLE, pas des noms inventés : c'est ce qui manquait.
	let heure_execution = 3;
	let nb_versions_conservees = 7;
	let chargement = true;
	let enregistrement = false;

	onMount(async () => {
		const cfg = await admin.backupConfig().catch(() => null);
		if (cfg) {
			heure_execution = cfg.heure_execution ?? heure_execution;
			nb_versions_conservees = cfg.nb_versions_conservees ?? nb_versions_conservees;
		}
		chargement = false;
	});

	async function enregistrer() {
		enregistrement = true;
		try {
			await admin.updateBackupConfig({
				frequence: 'quotidienne',
				heure_execution: Number(heure_execution),
				nb_versions_conservees: Number(nb_versions_conservees),
			});
			toast('success', 'Réglage enregistré');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur à l’enregistrement');
		} finally {
			enregistrement = false;
		}
	}
</script>

<section class="config-sauvegarde">
	<h3 class="titre">💾 Réglage de la sauvegarde quotidienne</h3>
	<p class="aide">
		La sauvegarde s’exécute <strong>tous les jours</strong>. Son historique et son
		déclenchement manuel sont dans le tableau ci-dessus, avec les autres tâches.
	</p>

	{#if chargement}
		<p class="aide">Chargement…</p>
	{:else}
		<form on:submit|preventDefault={enregistrer} class="grille">
			<label class="field champ-en-ligne">
				<span>Heure d’exécution</span>
				<select bind:value={heure_execution}>
					{#each Array.from({ length: 24 }, (_, h) => h) as h}
						<option value={h}>{String(h).padStart(2, '0')} h 00</option>
					{/each}
				</select>
			</label>
			<label class="field champ-en-ligne">
				<span>Versions conservées</span>
				<input type="number" min="1" max="99" bind:value={nb_versions_conservees} />
			</label>
			<button class="btn-primary" type="submit" disabled={enregistrement}>
				{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</form>
		<p class="aide note">
			Au-delà de {nb_versions_conservees} versions, la plus ancienne est effacée.
		</p>
		{#if heure_execution === 2 || heure_execution === 3}
			<p class="avertissement">
				⚠️ <strong>{String(heure_execution).padStart(2, '0')} h</strong> croise une autre
				tâche : la <strong>bascule</strong> entre les deux Raspberry Pi tourne à 02 h,
				et la <strong>maintenance hebdomadaire</strong> (purge et VACUUM de la base) le
				dimanche à 03 h. Une sauvegarde qui démarre pendant l’une ou l’autre lit une
				base en cours de réorganisation. Préférez une heure creuse — 01 h ou 04 h.
			</p>
		{/if}
	{/if}
</section>

<style>
	.config-sauvegarde { margin-top: 1.5rem; padding-top: 1.25rem; border-top: 1px solid var(--color-border); }
	.titre { font-size: .95rem; margin: 0 0 .35rem; }
	.aide { font-size: .82rem; color: var(--color-text-muted); line-height: 1.5; margin: 0 0 .9rem; }
	.note { margin: .7rem 0 0; }
	.avertissement { font-size: .82rem; line-height: 1.5; margin: .7rem 0 0; padding: .6rem .7rem; border-left: 3px solid var(--color-warning, #d97706); background: var(--color-bg); }
	.grille { display: flex; flex-wrap: wrap; gap: .8rem; align-items: flex-end; }
</style>
