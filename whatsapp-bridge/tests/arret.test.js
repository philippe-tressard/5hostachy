/**
 * Arrêt du bridge — la décision « où en est l'arrêt », sans processus ni signal
 * (#1590). `arret.js` est pur : tout ce qu'il touche (socket, minuteur, sortie)
 * lui est injecté, et c'est ce qui permet de le tester ici.
 *
 * Lancé par la CI avec le reste (`npm test`, dans `whatsapp-bridge/`).
 */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { creerArret, creerSuiviEcritures } = require("../arret");

const attendre = (ms) => new Promise((ok) => setTimeout(ok, ms));

// Un minuteur injecté : il ne tire que si le test le décide.
function faussesMinuteries() {
  const posees = [];
  return {
    posees,
    planifier: (fn, ms) => {
      const t = { fn, ms, annule: false };
      posees.push(t);
      return t;
    },
    annuler: (t) => {
      t.annule = true;
    },
  };
}

test("suivi des écritures : la valeur rendue est celle de la fonction suivie", async () => {
  const suivi = creerSuiviEcritures();
  const ecrire = suivi.suivre(async (x) => x * 2);
  assert.equal(await ecrire(21), 42);
});

test("suivi des écritures : une écriture en cours se voit, puis plus", async () => {
  const suivi = creerSuiviEcritures();
  let fin;
  const ecrire = suivi.suivre(
    () =>
      new Promise((ok) => {
        fin = ok;
      })
  );
  assert.equal(suivi.enCours(), 0);
  const p = ecrire();
  assert.equal(suivi.enCours(), 1);
  fin();
  await p;
  assert.equal(suivi.enCours(), 0);
});

test("suivi des écritures : un échec reste l'échec de l'appelant et ne reste pas « en cours »", async () => {
  const suivi = creerSuiviEcritures();
  const ecrire = suivi.suivre(async () => {
    throw new Error("disque plein");
  });
  await assert.rejects(ecrire(), /disque plein/);
  assert.equal(suivi.enCours(), 0);
  await suivi.attendre(); // ne lève pas
});

test("suivi des écritures : une écriture synchrone qui lève lève chez l'appelant", () => {
  const suivi = creerSuiviEcritures();
  const ecrire = suivi.suivre(() => {
    throw new Error("immédiat");
  });
  assert.throws(() => ecrire(), /immédiat/);
  assert.equal(suivi.enCours(), 0);
});

test("suivi des écritures : attendre() couvre aussi une écriture lancée PENDANT l'attente", async () => {
  const suivi = creerSuiviEcritures();
  const ecrire = suivi.suivre(() => attendre(30));
  ecrire();
  const attente = suivi.attendre();
  setTimeout(() => ecrire(), 10); // lancée après `attendre()`
  await attente;
  assert.equal(suivi.enCours(), 0);
});

test("arrêt : ferme le socket, attend l'écriture en cours, puis sort en 0", async () => {
  const journal = [];
  const suivi = creerSuiviEcritures();
  const ecrire = suivi.suivre(async () => {
    await attendre(40);
    journal.push("ecriture-fin");
  });
  ecrire();
  const m = faussesMinuteries();
  const arret = creerArret({
    fermer: () => journal.push("socket-ferme"),
    attendreEcritures: () => suivi.attendre(),
    quitter: (code) => journal.push(`sortie-${code}`),
    planifier: m.planifier,
    annuler: m.annuler,
    delaiMs: 8000,
  });
  assert.equal(arret.enCours(), false);
  await arret.demander("SIGTERM");
  assert.deepEqual(journal, ["socket-ferme", "ecriture-fin", "sortie-0"]);
  assert.equal(arret.enCours(), true);
  assert.equal(m.posees.length, 1);
  assert.equal(m.posees[0].ms, 8000);
  assert.equal(m.posees[0].annule, true, "le minuteur de sécurité est annulé quand tout s'est terminé");
});

test("arrêt : un second signal ne relance rien (idempotent)", async () => {
  let fermetures = 0;
  const sorties = [];
  const m = faussesMinuteries();
  const arret = creerArret({
    fermer: () => {
      fermetures += 1;
    },
    attendreEcritures: () => attendre(20),
    quitter: (code) => sorties.push(code),
    planifier: m.planifier,
    annuler: m.annuler,
    delaiMs: 8000,
  });
  const premier = arret.demander("SIGTERM");
  const second = arret.demander("SIGINT");
  assert.equal(second, premier, "le même arrêt, pas un second");
  await Promise.all([premier, second]);
  await arret.demander("SIGTERM");
  assert.equal(fermetures, 1);
  assert.deepEqual(sorties, [0]);
  assert.equal(m.posees.length, 1);
});

test("arrêt : une écriture qui ne finit jamais est coupée par le minuteur, en 0", async () => {
  const sorties = [];
  const m = faussesMinuteries();
  const arret = creerArret({
    fermer: () => {},
    attendreEcritures: () => new Promise(() => {}), // ne se termine jamais
    quitter: (code) => sorties.push(code),
    planifier: m.planifier,
    annuler: m.annuler,
    delaiMs: 8000,
  });
  arret.demander("SIGTERM");
  await attendre(10);
  assert.deepEqual(sorties, [], "rien ne sort avant l'échéance");
  m.posees[0].fn(); // le minuteur tire
  assert.deepEqual(sorties, [0]);
});

test("arrêt : un socket qui refuse de se fermer n'empêche ni l'attente ni la sortie", async () => {
  const journal = [];
  const m = faussesMinuteries();
  const arret = creerArret({
    fermer: () => {
      throw new Error("socket déjà mort");
    },
    attendreEcritures: async () => {
      journal.push("attente");
    },
    quitter: (code) => journal.push(`sortie-${code}`),
    planifier: m.planifier,
    annuler: m.annuler,
    delaiMs: 8000,
  });
  await arret.demander("SIGTERM");
  assert.deepEqual(journal, ["attente", "sortie-0"]);
});

test("arrêt : une attente qui lève sort quand même en 0", async () => {
  const sorties = [];
  const m = faussesMinuteries();
  const arret = creerArret({
    fermer: () => {},
    attendreEcritures: async () => {
      throw new Error("boum");
    },
    quitter: (code) => sorties.push(code),
    planifier: m.planifier,
    annuler: m.annuler,
    delaiMs: 8000,
  });
  await arret.demander("SIGTERM");
  assert.deepEqual(sorties, [0]);
});
