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
import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

/** Le processus existe-t-il encore ? `kill(pid, 0)` interroge sans rien envoyer. */
function vivant(pid: number): boolean {
	try {
		process.kill(pid, 0);
		return true;
	} catch {
		return false;
	}
}

/*
 *  ## 🔴 Un serveur À SOI, sur un port à soi (#1150, 25/09/2026)
 *
 *  Le port était 5173 — celui de `npm run dev` — avec `reuseExistingServer:
 *  true`. Toute exécution trouvant quelque chose sur ce port s'y branchait sans
 *  un mot : le serveur de développement du poste, ou celui d'une AUTRE session,
 *  dans un autre worktree. Deux conséquences, mesurées :
 *
 *  1. **L'intermittence.** Deux exécutions qui se chevauchent : la seconde
 *     réutilise le serveur de la première, qui l'arrête en finissant — et la
 *     seconde tombe en `ERR_CONNECTION_REFUSED` sur un test différent à chaque
 *     fois (squelette, message-erreur-401, etoile-requis : les trois du ticket).
 *     Reproduit à coup sûr ; jamais en isolé, jamais en CI — c'est ce qui l'a
 *     fait prendre pour une affaire de charge.
 *  2. **Le faux vert**, plus grave : un serveur réutilisé sert le code de
 *     CELUI QUI L'A LANCÉ. Le rejeu de la CI pouvait donc valider l'arbre d'un
 *     autre worktree, et `rejouer-ci.sh` dire vert sur ce qu'il n'avait pas lu.
 *
 *  D'où : un port par exécution, dérivé du processus principal et transmis aux
 *  workers par l'environnement (ils relisent ce fichier, et héritent de
 *  `process.env` — un tirage au sort ici donnerait un port par worker). Jamais
 *  de réutilisation : un port déjà pris est une ERREUR explicite, pas un
 *  serveur qu'on emprunte. `--strictPort` empêche Vite de se replier en
 *  silence sur un port voisin pendant que Playwright interroge le premier.
 *
 *  ⚠️ Le port ne protège qu'ENTRE deux dossiers. Dans le MÊME, deux exécutions
 *  partagent aussi `test-results/`, que Playwright vide en démarrant : la
 *  seconde effaçait les traces que la première écrivait (`ENOENT … .trace`,
 *  mesuré le même jour). La seconde est donc REFUSÉE, avec le pid de la
 *  première — un verrou posé par le seul processus principal, puisque lui seul
 *  n'a pas encore de port. Un verrou dont le processus est mort ne retient rien.
 */
if (!process.env.E2E_PORT) {
	const verrou = fileURLToPath(new URL('.e2e-en-cours', import.meta.url));
	const tenant = existsSync(verrou) ? Number(readFileSync(verrou, 'utf8')) : 0;
	if (tenant && tenant !== process.pid && vivant(tenant)) {
		throw new Error(
			`Une exécution e2e tourne déjà dans ce dossier (pid ${tenant}). ` +
				`Deux exécutions ici partagent test-results/ et s'effacent l'une l'autre : attendre la fin.`,
		);
	}
	writeFileSync(verrou, String(process.pid));
	process.on('exit', () => {
		if (existsSync(verrou) && readFileSync(verrou, 'utf8') === String(process.pid)) rmSync(verrou);
	});
	process.env.E2E_PORT = String(5300 + (process.pid % 600));
}
const PORT = Number(process.env.E2E_PORT);
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
		command: `npm run dev -- --port ${PORT} --strictPort`,
		url: BASE,
		reuseExistingServer: false,
		timeout: 120_000,
	},
});
