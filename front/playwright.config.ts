/*
 *  **Playwright — la vérification de l'écran, enfin exécutable.**
 *
 *  ## Pourquoi (06/09/2026)
 *
 *  Le projet n'avait AUCUN test de navigateur : `api/tests/` couvre le serveur,
 *  les linters lisent la source, `svelte-check` lit les types. Tout ce qui ne se
 *  voit qu'à l'écran — un lien d'évitement qui prend le focus, une carte qui se
 *  replie, un titre qui disparaît sur téléphone — n'était vérifiable que par un
 *  coup d'oeil humain. C'est ce que dit le post-check P7, et c'est la raison
 *  pour laquelle plusieurs défauts d'interface ont été trouvés par l'utilisateur
 *  et non par un contrôle (#787, #802, la vignette du calendrier).
 *
 *  ## Ce que ces tests peuvent voir, et ce qu'ils ne peuvent pas
 *
 *  🔴 **Le site est derrière une connexion.** Sans session, seuls `/auth/*` et le
 *  squelette sont atteignables — c'est le périmètre de ce premier lot. Couvrir
 *  les écrans applicatifs demande un compte de test et une décision sur l'endroit
 *  où vivent ses identifiants : cela ne s'improvise pas dans un fichier versionné
 *  (`standards/03` §2). Voir `e2e/README.md`.
 *
 *  ⚠️ `vite dev` proxifie `/api` vers `localhost:8000`. Sans API lancée, les
 *  appels échouent — les tests d'ici n'en font aucun, et un test qui en ferait
 *  devrait le déclarer plutôt que d'attendre un serveur qui n'est pas là.
 */
import { defineConfig, devices } from '@playwright/test';

const PORT = 5173;
const BASE = `http://localhost:${PORT}`;

export default defineConfig({
	testDir: './e2e',
	//  Pas de test « flaky » toléré en silence : un test d'interface qui échoue
	//  une fois sur deux ne dit rien, et on finit par ne plus le lire.
	retries: 0,
	//  ⚠️ Le rapport HTML ne s'ouvre PAS tout seul : en session non interactive il
	//  bloquerait sur un serveur qui attend une touche.
	reporter: [['list'], ['html', { open: 'never', outputFolder: 'e2e-rapport' }]],
	use: {
		baseURL: BASE,
		//  La trace n'est gardée que sur échec : c'est là qu'elle sert, et elle
		//  pèse quelques mégaoctets par test.
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
	},
	projects: [
		{ name: 'bureau', use: { ...devices['Desktop Chrome'] } },
		//  🔴 Le mobile n'est PAS une option. La responsivité est une exigence
		//  permanente (`standards/11` §10), et c'est sur téléphone que le titre des
		//  cartes disparaissait (#453, `EnteteCarte`).
		{ name: 'mobile', use: { ...devices['Pixel 5'] } },
	],
	webServer: {
		command: 'npm run dev -- --port ' + PORT,
		url: BASE,
		reuseExistingServer: true,
		timeout: 120_000,
	},
});
