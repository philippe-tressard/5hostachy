/**
 * La PLATEFORME — le logiciel qui sert la résidence, et non la résidence (#1725).
 *
 * Deux noms, et les confondre est le défaut que ce module ferme :
 *
 * | | Ce qu'il nomme | Où il se lit |
 * |---|---|---|
 * | la résidence | celle qu'on habite | `site_nom`, en base — `siteNomStore` |
 * | la plateforme | le logiciel, le même pour toutes | ICI, et nulle part ailleurs |
 *
 * Arbitrage du 07/10/2026 (`specs/architecture/multi-coproprietes.md`, D9) : la
 * plateforme s'appelle CoproConnect.
 *
 * 🔴 L'API porte la MÊME déclaration (`api/app/utils/plateforme.py`) : les
 * contextes de build `./api` et `./front` ne partagent aucun fichier.
 * `api/tests/test_plateforme.py` échoue si les deux divergent.
 *
 * ⚠️ La licence est celle EN VIGUEUR : son passage à l'AGPL-3.0-or-later est un
 * lot séparé (#1726), qui ne changera que les deux constantes de licence.
 */

/** Le nom du logiciel — l'attribution et le lien vers le source. */
export const NOM_PLATEFORME = 'CoproConnect';

/** Le dépôt public du code source. Son nom est historique : le logiciel est né
 *  pour une seule résidence (source déclarée de `lint:nom-residence`). */
export const DEPOT_SOURCE = 'https://github.com/philippe-tressard/5hostachy';

/** La licence en vigueur, telle qu'on la nomme et qu'on la lie. */
export const LICENCE_NOM = 'Licence 5Hostachy';
export const LICENCE_URL = `${DEPOT_SOURCE}/blob/main/LICENSE-5Hostachy.md`;

/**
 * Le code source de la version qui TOURNE — l'AGPLv3 §13 vise celle-là, pas la
 * dernière du dépôt. L'empreinte est celle du build (`VITE_GIT_HASH`) ; sans
 * elle (poste de développement), le dépôt lui-même.
 */
export function lienSource(empreinte?: string | null): string {
	const propre = (empreinte ?? '').trim();
	return !propre || propre === 'dev' ? DEPOT_SOURCE : `${DEPOT_SOURCE}/tree/${propre}`;
}
