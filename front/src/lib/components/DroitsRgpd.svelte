<!--
  Le pavé **RGPD** du profil : les droits du résident, et le réglage de
  télémétrie qui les met en pratique.

  Extrait de `routes/(app)/profil/+page.svelte` le 22/09/2026, au fil de l'eau :
  la page faisait 619 lignes et le garde-fou de modularité (rang 1) a refusé
  qu'elle grossisse en recevant la mention « réglage par défaut » (#1147).

  🔴 Ce bloc, et pas un autre : il ne partage **aucun état** avec le reste de la
  page — ni chargement, ni enregistrement, ni message. Il se lit seul, donc il
  se déplace seul. Les trois cartes qui restent (identité, résidence, lots)
  partagent toutes `user`, `saving` et les mêmes gestes de sauvegarde : les
  sortir demanderait de remonter cet état, c'est-à-dire d'en faire une notion de
  plus plutôt qu'une de moins.

  ⚠️ La carte porte ses couleurs en ligne, comme avant l'extraction. Elles ne
  sont PAS de la charte (un ambre qui n'existe nulle part ailleurs) — c'est une
  dérive à traiter avec les 206 couleurs en dur déjà relevées (#1055), pas au
  détour d'un déplacement de fichier qui la ferait passer pour une décision.
-->
<script lang="ts">
	import TelemetrieRGPD from '$lib/components/TelemetrieRGPD.svelte';
</script>

<!-- ── RGPD ─────────────────────────────────────────────────────────────── -->
<section class="card" style="border-color:#fde68a;background:#fffbeb">
	<h2 style="font-size:.95rem;font-weight:600;margin-bottom:.5rem">Vos droits (RGPD)</h2>
	<p style="font-size:.8rem;line-height:1.55;color:var(--color-text-muted)">
		Conformément au RGPD, vous pouvez exercer vos droits d'accès, rectification, portabilité et
		effacement en contactant le responsable de traitement à l'adresse indiquée dans la
		<a href="/politique-de-confidentialite" style="color:var(--color-primary)"
			>politique de confidentialité</a
		>.
	</p>

	<TelemetrieRGPD />
</section>
