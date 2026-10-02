/**
 * Arrêt propre du bridge — la décision, sans processus ni signal (#1590).
 *
 * Pourquoi : `docker compose stop` (bascule de 02:00, chaque déploiement)
 * envoie SIGTERM. Node en PID 1 n'y réagit pas sans écouteur : après 10 s,
 * SIGKILL (exit 137) — au risque de couper une écriture de `creds.json` ou d'un
 * fichier de clé Baileys, état d'authentification multi-fichiers qui ne se
 * déchire pas (incident du 24/07/2026, `standards/06` §1).
 *
 * Ce module ne touche à rien : socket, minuteur et sortie lui sont INJECTÉS par
 * `index.js`, ce qui permet de tester l'enchaînement sans signal ni Baileys
 * (`tests/arret.test.js`).
 */

/**
 * Suivi des écritures d'état en cours. `suivre(fn)` rend une fonction qui fait
 * EXACTEMENT ce que faisait `fn` (mêmes arguments, même valeur, même échec) et
 * note la promesse tant qu'elle n'est pas réglée.
 */
function creerSuiviEcritures() {
  const enCours = new Set();

  function suivre(fn) {
    return function (...args) {
      const resultat = fn.apply(this, args);
      if (resultat && typeof resultat.then === "function") {
        enCours.add(resultat);
        // Réglée, bien ou mal : elle n'est plus « en cours ». Le rejet reste
        // celui de l'appelant — ici on ne fait que le regarder passer.
        const oublier = () => enCours.delete(resultat);
        resultat.then(oublier, oublier);
      }
      return resultat;
    };
  }

  // Attend que plus rien ne soit en cours — y compris ce qui démarre PENDANT
  // l'attente. Ne lève jamais : un échec d'écriture est l'affaire de l'appelant.
  async function attendre() {
    while (enCours.size > 0) {
      await Promise.allSettled([...enCours]);
    }
  }

  return { suivre, attendre, enCours: () => enCours.size };
}

/**
 * L'arrêt : une seule fois, quel que soit le nombre de signaux.
 *
 *   fermer()            ferme le socket (peut lever : l'arrêt continue)
 *   attendreEcritures() promesse réglée quand les écritures d'état sont finies
 *   quitter(code)       process.exit
 *   delaiMs             minuteur de sécurité : passé ce délai, on sort quand
 *                       même — un arrêt ne doit jamais rester suspendu à une
 *                       écriture qui ne finit pas
 *
 * On sort toujours en 0 : un arrêt demandé n'est pas une panne.
 */
function creerArret({
  fermer,
  attendreEcritures,
  quitter,
  delaiMs,
  planifier = setTimeout,
  annuler = clearTimeout,
  journal = () => {},
}) {
  let arret = null;
  // Levé AVANT tout le reste : `fermer()` s'exécute avant que `arret` soit
  // affecté, et la fermeture du socket provoque un `close` que `index.js` doit
  // déjà reconnaître comme voulu.
  let demande = false;

  function demander(signal) {
    // Idempotent : un second signal rend le même arrêt, sans rien relancer.
    if (demande) return arret;
    demande = true;
    journal(`Signal ${signal} reçu — arrêt propre`);
    const minuteur = planifier(() => {
      journal(`Arrêt non terminé après ${delaiMs} ms — sortie forcée`);
      quitter(0);
    }, delaiMs);

    arret = (async () => {
      try {
        fermer();
      } catch (err) {
        journal(`Fermeture du socket : ${err && err.message}`);
      }
      try {
        // Un tour de boucle : les écritures que la fermeture provoque
        // (dernier `creds.update`) doivent être notées avant qu'on compte.
        await new Promise((ok) => setImmediate(ok));
        await attendreEcritures();
      } catch (err) {
        journal(`Attente des écritures : ${err && err.message}`);
      }
      annuler(minuteur);
      quitter(0);
    })();
    return arret;
  }

  return { demander, enCours: () => demande };
}

module.exports = { creerArret, creerSuiviEcritures };
