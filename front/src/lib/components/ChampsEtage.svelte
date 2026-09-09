<!--
  L'étage de chacun de mes LOGEMENTS (#835).

  🔴 Le champ « Étage » PERSONNEL (`Utilisateur.etage`) vivait ici, juste au-dessus
  — il a été retiré le 09/09/2026, sur arbitrage de Philippe, à l'écran : deux
  champs « Étage » à trois lignes d'écart, dont le premier ne disait rien que le
  second ne dise mieux. Il reste saisi à l'inscription, et la colonne garde sa
  valeur ; ce qui disparaît, c'est sa saisie ici.

  ⚠️ Un bailleur ne peut donc plus déclarer depuis son profil l'étage où il HABITE
  quand ce n'est pas celui d'un de ses lots. C'est le coût du choix, dit une fois :
  l'écran gagne en clarté ce que ce cas précis perd en précision.

  🔴 SEULS LES LOGEMENTS sont listés — pas les caves ni les parkings. « Étage de
  chacun de mes logements » énumérait « N° 417 Cave » et « N° 450 Parking », qui
  n'en sont pas : un titre qui ment sur son contenu se corrige par le contenu,
  pas par le titre (arbitrage à l'écran, 09/09/2026). Leur étage se règle depuis
  l'administration du patrimoine, comme avant.
-->
<script lang="ts">
	import { lots as lotsApi } from '$lib/api';
	import { ETAGE_MAX, ETAGE_MIN, lotTypeLabel } from '$lib/utils';

	/**  L'étage de CHAQUE logement, par identifiant — donnée de patrimoine. */
	export let etagesLot: Record<number, number | null> = {};
	export let lots: any[] = [];

	/**  Les LOGEMENTS seuls : une cave et un parking ont un niveau, pas un étage
	 *   d'habitation, et les lister sous « mes logements » était faux. Le filtre
	 *   porte sur le type, jamais sur une liste de types à exclure — un type
	 *   ajouté demain serait alors inclus par défaut, ce qui est le mauvais sens. */
	$: logements = lots.filter((l) => l.type === 'appartement');

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
		const changes = logements.filter((l) => (l.etage ?? null) !== (etagesLot[l.id] ?? null));
		const majs = await Promise.all(
			changes.map((l) => lotsApi.majEtage(l.id, etagesLot[l.id] ?? null)),
		);
		const parId = new Map(majs.map((m: any) => [m.id, m]));
		lots = lots.map((l) => parId.get(l.id) ?? l);
		return lots;
	}
</script>

{#if logements.length > 0}
	<div class="field">
		<!--  `.libelle-groupe` + `role="group"` : un `<label>` ne sait pas nommer un
		      groupe de contrôles — posé dessus, il n'associe rien, ET IL LE FAIT EN
		      SILENCE (`champs.css`, #561). -->
		<span class="libelle-groupe" id="p-etages-lots">Étage de chacun de mes logements</span>
		<div class="etages-lots" role="group" aria-labelledby="p-etages-lots">
			{#each logements as lot (lot.id)}
				<div class="etage-lot">
					<label for={`p-etage-lot-${lot.id}`}>
						<!--  Les deux espaces autour du tiret sont INSÉCABLES : écrites en
						      blanc elles disparaissaient au reformatage, et `&#32;` était
						      recollée par le navigateur — le libellé rendait « Bât. 4 —N° 15 ».
						      Une espace insécable ne se réduit ni ne se replie. -->
						{#if lot.batiment_nom}{lot.batiment_nom}&nbsp;—&nbsp;{/if}N° {lot.numero}
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
