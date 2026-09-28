<!--
  Le journal des messages relevés dans la boîte des réponses (#1447).

  🔴 Le 28/09/2026, un message a été ignoré sans qu'on puisse dire pourquoi :
  la relève ne gardait que des totaux, dans un journal de conteneur effacé à
  chaque MEP. Chaque verdict a désormais sa ligne — y compris « ignoré », qui
  était muet par construction —, et elle se lit ici, sous le réglage qui la
  produit. Jamais le texte du message : il est dans l'affaire ou dans la boîte.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { config as configApi, type CourrielReleve } from '$lib/api';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import JournalVerdicts, {
		type EntreeJournal,
		type TonVerdict,
	} from '$lib/components/JournalVerdicts.svelte';
	import { lienTicket } from '$lib/tickets';

	//  La gravité, pas le nom : un refus est orange — le conseil a été prévenu,
	//  rien n'est cassé —, un message ignoré est gris.
	const VERDICTS: Record<CourrielReleve['decision'], { libelle: string; ton: TonVerdict }> = {
		accepte: { libelle: 'Ajouté au fil', ton: 'succes' },
		relance: { libelle: 'Transmis au conseil', ton: 'info' },
		refuse: { libelle: 'Refusé', ton: 'attention' },
		ignore: { libelle: 'Ignoré', ton: 'neutre' },
	};

	let releves: CourrielReleve[] = [];
	let chargement = true;
	let erreur = '';

	async function charger() {
		chargement = true;
		erreur = '';
		try {
			releves = await configApi.relevesCourriel();
		} catch (e: any) {
			erreur = e?.message ?? 'Chargement impossible';
		} finally {
			chargement = false;
		}
	}

	$: entrees = releves.map((r): EntreeJournal => ({
		cle: r.id,
		titre: r.objet || '(sans objet)',
		sousTitre: r.expediteur,
		verdict: VERDICTS[r.decision]?.libelle ?? r.decision,
		ton: VERDICTS[r.decision]?.ton ?? 'neutre',
		date: r.releve_le,
		texte: r.motif,
		lien: r.ticket_id
			? { href: lienTicket(r.ticket_id), libelle: `Affaire #${r.affaire}` }
			: undefined,
	}));

	onMount(charger);
</script>

{#if chargement || erreur}
	<EtatListe {chargement} {erreur} compact />
{:else}
	<JournalVerdicts
		{entrees}
		recharger={charger}
		vide="Aucun message relevé pour l’instant."
		libelleRecharger="Rafraîchir le journal des relèves"
	/>
{/if}
