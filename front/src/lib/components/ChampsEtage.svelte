<!--
  Les DEUX étages du profil, et ce qui les distingue (#835).

  🔴 Ils ne se ressemblent qu'en surface : `Utilisateur.etage` dit où la personne
  VIT, `Lot.etage` décrit un BIEN. Un bailleur a un lot au 4ᵉ et habite ailleurs.
  Les afficher côte à côte sans le dire, c'est inviter à écrire l'un à la place de
  l'autre — l'écran doit dire lequel est lequel, et c'est la raison d'être de ce
  composant : les deux champs se lisent ensemble ou pas du tout.

  Extrait de `profil/+page.svelte` le 09/09/2026, la page ayant franchi son
  plafond de modularité en les recevant. La coupe suit la notion, pas
  l'arithmétique.

  ⚠️ Le bloc « par logement » n'apparaît qu'à partir de DEUX logements : avec un
  seul, `etageParDefaut` propose déjà son étage au champ personnel, et afficher
  deux fois le même chiffre inviterait à les désaccorder.
-->
<script lang="ts">
	import { lots as lotsApi } from '$lib/api';
	import { ETAGE_MAX, ETAGE_MIN, lotTypeLabel } from '$lib/utils';

	/**  L'étage où la personne HABITE. */
	export let etage: number | null = null;
	/**  L'étage de CHAQUE lot, par identifiant — donnée de patrimoine. */
	export let etagesLot: Record<number, number | null> = {};
	export let lots: any[] = [];

	/**  Enregistre les étages de lots MODIFIÉS, et rend la liste à jour.
	 *
	 *   L'écriture vit ici plutôt que dans la page : `Lot.etage` est une autre
	 *   table, une autre règle d'accès (le lot doit m'être rattaché) et une autre
	 *   route que `Utilisateur.etage`. Le composant qui saisit une donnée est
	 *   celui qui sait comment elle s'enregistre.
	 *
	 *   ⚠️ Seuls les lots CHANGÉS partent : réécrire les autres poserait un
	 *   `modifie_le` sur des lignes que personne n'a touchées. */
	export async function enregistrerEtagesDeLots(): Promise<any[]> {
		const changes = lots.filter((l) => (l.etage ?? null) !== (etagesLot[l.id] ?? null));
		const majs = await Promise.all(
			changes.map((l) => lotsApi.majEtage(l.id, etagesLot[l.id] ?? null)),
		);
		const parId = new Map(majs.map((m: any) => [m.id, m]));
		lots = lots.map((l) => parId.get(l.id) ?? l);
		return lots;
	}
</script>

<!--  ⚠️ L'indication dit à quoi il SERT, comme à l'inscription : un champ
      facultatif dont on ignore l'usage ne se remplit pas. Les bornes sont les
      mêmes des deux côtés — et elles sont AUSSI vérifiées par l'API, un champ
      borné côté client se postant directement. -->
<div class="field">
	<label for="p-etage">Étage</label>
	<input
		id="p-etage"
		type="number"
		bind:value={etage}
		min={ETAGE_MIN}
		max={ETAGE_MAX}
		placeholder="Ex. 3"
	/>
	<p class="field-hint">
		Facultatif. L’étage où vous habitez — il sert à vous situer auprès de vos voisins.
	</p>
</div>
{#if lots.length > 1}
	<div class="field">
		<!--  `.libelle-groupe` + `role="group"` : un `<label>` ne sait pas nommer un
		      groupe de contrôles — posé dessus, il n'associe rien, ET IL LE FAIT EN
		      SILENCE (`champs.css`, #561). -->
		<span class="libelle-groupe" id="p-etages-lots">Étage de chacun de mes logements</span>
		<div class="etages-lots" role="group" aria-labelledby="p-etages-lots">
			{#each lots as lot (lot.id)}
				<div class="etage-lot">
					<label for={`p-etage-lot-${lot.id}`}>
						{#if lot.batiment_nom}{lot.batiment_nom} —
						{/if}N° {lot.numero}
						<span class="etage-lot-type">{lotTypeLabel(lot.type)}</span>
					</label>
					<input
						id={`p-etage-lot-${lot.id}`}
						type="number"
						bind:value={etagesLot[lot.id]}
						min={ETAGE_MIN}
						max={ETAGE_MAX}
						placeholder="Ex. 3"
					/>
				</div>
			{/each}
		</div>
		<p class="field-hint">
			Facultatif. L’étage du bien lui-même — il apparaît sur les fiches et les affiches de la
			copropriété.
		</p>
	</div>
{/if}

<style>
	/*  Un logement par ligne : son identité à gauche, son étage à droite. La
	    grille tient sur un téléphone parce que la colonne du champ est FIXE et
	    celle du libellé élastique — l'inverse aurait écrasé le libellé sur les
	    numéros longs (« Bât. 3 — N° 412 · appartement »). */
	.etages-lots {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.etage-lot {
		display: grid;
		grid-template-columns: 1fr 6rem;
		align-items: center;
		gap: 0.5rem 0.75rem;
	}
	.etage-lot label {
		font-weight: 400;
		color: var(--color-text-muted);
	}
	.etage-lot-type {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}
	/*  44 px : une cible tactile est une taille PHYSIQUE, celle d'un pouce — elle
	    ne suit pas la typographie (#839, où `2.75rem` avait rendu 33 px, la racine
	    valant 12 px en émulation mobile). */
	.etage-lot input {
		min-height: 44px;
	}
	/*  Sous 480 px, la grille à deux colonnes serre le champ : on empile. */
	@media (max-width: 480px) {
		.etage-lot {
			grid-template-columns: 1fr;
		}
	}
</style>
