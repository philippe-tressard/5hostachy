/**
 * Contrat HTTP du bridge — ce que l'API reçoit, quelle que soit la version
 * d'express ou de pino installée.
 *
 * Lancé par la CI (job « Build SvelteKit ») : `npm test`, dans `whatsapp-bridge/`.
 * `index.js` tourne tel quel dans un processus enfant, Baileys simulé
 * (`baileys-simule.js`) — aucun appel ne quitte la machine.
 *
 * ⚠️ Ce test ne dit RIEN de Baileys lui-même : une montée de `baileys` se juge
 * toujours sur un envoi réel constaté (`.github/dependabot.yml`).
 */
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const path = require("node:path");

const PORT = 18090 + Math.floor(Math.random() * 500);
const BASE = `http://127.0.0.1:${PORT}`;
const CLE = "cle-de-test";
const JSON_CLE = { "x-api-key": CLE, "content-type": "application/json" };

let bridge;

before(async () => {
  bridge = spawn(process.execPath, ["-r", "./tests/baileys-simule.js", "index.js"], {
    cwd: path.join(__dirname, ".."),
    env: { ...process.env, WA_PORT: String(PORT), WA_API_KEY: CLE, WA_LOG_LEVEL: "silent" },
    stdio: "ignore",
  });
  // Attendre que le bridge écoute ET que la connexion simulée soit ouverte.
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch(`${BASE}/status`, { headers: { "x-api-key": CLE } });
      if ((await r.json()).state === "open") return;
    } catch (_) {}
    await new Promise((ok) => setTimeout(ok, 50));
  }
  throw new Error("le bridge n'a pas démarré");
});

after(() => bridge?.kill());

async function appel(chemin, options = {}) {
  const r = await fetch(BASE + chemin, options);
  const texte = await r.text();
  let corps = null;
  try { corps = JSON.parse(texte); } catch (_) {}
  return { statut: r.status, corps };
}

test("sans clé d'API : 401", async () => {
  assert.equal((await appel("/status")).statut, 401);
});

test("clé en paramètre de requête : acceptée", async () => {
  const r = await appel(`/status?apikey=${CLE}`);
  assert.equal(r.statut, 200);
  assert.equal(r.corps.state, "open");
});

test("envoi d'un texte : 200 avec l'identifiant du message", async () => {
  const r = await appel("/send", {
    method: "POST", headers: JSON_CLE, body: JSON.stringify({ number: "33600000000", text: "t" }),
  });
  assert.equal(r.statut, 200);
  assert.equal(r.corps.ok, true);
  assert.equal(r.corps.jid, "33600000000@s.whatsapp.net");
});

test("envoi avec photo en base64 : 200", async () => {
  const r = await appel("/send", {
    method: "POST", headers: JSON_CLE,
    body: JSON.stringify({ number: "33600000000", text: "t", imageBase64: "AAAA" }),
  });
  assert.equal(r.statut, 200);
});

test("champs manquants : 400 en JSON", async () => {
  const r = await appel("/send", { method: "POST", headers: JSON_CLE, body: "{}" });
  assert.equal(r.statut, 400);
  assert.match(r.corps.error, /required/);
});

// Express 5 : sans corps JSON, `req.body` vaut `undefined` — c'était un 500.
test("corps non JSON : 400, pas 500", async () => {
  const r = await appel("/send", { method: "POST", headers: { "x-api-key": CLE }, body: "x" });
  assert.equal(r.statut, 400);
});

// #1057 : le plafond d'express rejetait toute photo, et en HTML.
test("corps au-delà du plafond : 413 en JSON, avec le plafond", async () => {
  const r = await appel("/send", {
    method: "POST", headers: JSON_CLE,
    body: JSON.stringify({ number: "1", text: "x".repeat(900 * 1024) }),
  });
  assert.equal(r.statut, 413);
  assert.equal(r.corps.limitKo, 800);
});

test("corps d'une photo ordinaire (≈ 500 kio) : accepté", async () => {
  const r = await appel("/send", {
    method: "POST", headers: JSON_CLE,
    body: JSON.stringify({ number: "1", text: "t", imageBase64: "A".repeat(500 * 1024) }),
  });
  assert.equal(r.statut, 200);
});

test("liste des groupes : 200", async () => {
  const r = await appel("/groups", { headers: { "x-api-key": CLE } });
  assert.equal(r.statut, 200);
  assert.deepEqual(r.corps, [{ id: "g1", subject: "Hall", participants: 2 }]);
});

test("QR alors que connecté : 200, « Already connected »", async () => {
  const r = await appel("/qr", { headers: { "x-api-key": CLE } });
  assert.equal(r.statut, 200);
  assert.equal(r.corps.state, "open");
});
