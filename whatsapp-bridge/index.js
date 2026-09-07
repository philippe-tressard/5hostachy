/**
 * WhatsApp Bridge — Minimal Baileys service for 5Hostachy.
 *
 * Endpoints:
 *   GET  /status        → connection state
 *   GET  /qr            → QR code as PNG image (for pairing)
 *   POST /send          → send a message  { number, text, imageBase64?, imageUrl? }
 *   GET  /groups        → list groups the account is in
 *   POST /restart       → reconnect
 *
 * Auth: header `x-api-key` must match WA_API_KEY env var.
 */

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} = require("baileys");
const express = require("express");
const QRCode = require("qrcode");
const pino = require("pino");
const path = require("path");
const crypto = require("crypto");
const fs = require("fs");

const PORT = parseInt(process.env.WA_PORT || "8090", 10);
const API_KEY = process.env.WA_API_KEY || "";
const AUTH_DIR = process.env.WA_AUTH_DIR || path.join(__dirname, "auth_state");

const logger = pino({ level: process.env.WA_LOG_LEVEL || "warn" });
const app = express();
app.use(express.json());

let sock = null;
let qrCode = null;       // latest QR string (null when connected)
let connectionState = "disconnected"; // disconnected | connecting | open

// ── Reconnect supervision ────────────────────────────────────────────
// Incident 2026-07-24 : après une bascule, le bridge est resté bloqué
// hors état "open" pendant 2h23 sans aucune tentative de reconnexion —
// une reconnexion planifiée avait rejeté une promesse non interceptée
// (startBaileys() est async, appelé nu dans un setTimeout), ce qui a
// tué la chaîne de reconnexion silencieusement. Cf. CLAUDE.md.
let starting = false;          // anti-concurrence : un seul startBaileys() à la fois
let reconnectTimer = null;     // timer de reconnexion déjà programmé
let reconnectAttempt = 0;      // pour le backoff exponentiel
const RECONNECT_BASE_MS = 5_000;
const RECONNECT_MAX_MS = 60_000;
const WATCHDOG_INTERVAL_MS = 60_000;

function scheduleReconnect() {
  if (reconnectTimer) return; // déjà programmé
  const delay = Math.min(RECONNECT_BASE_MS * 2 ** reconnectAttempt, RECONNECT_MAX_MS);
  reconnectAttempt += 1;
  logger.warn({ delay, attempt: reconnectAttempt }, "Reconnexion programmée");
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    startBaileys().catch((err) => {
      logger.warn({ err: err.message }, "startBaileys() a échoué — nouvelle tentative programmée");
      scheduleReconnect();
    });
  }, delay);
}

// ── ACK tracking (ghost session detection) ──────────────────────────
const ACK_TIMEOUT_MS = 15_000;
const pendingAcks = new Map(); // msgId → { resolve, reject, timer }

function waitForAck(msgId) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      if (pendingAcks.delete(msgId)) {
        reject(new Error(`ACK timeout after ${ACK_TIMEOUT_MS}ms — ghost session suspected`));
      }
    }, ACK_TIMEOUT_MS);
    pendingAcks.set(msgId, { resolve, reject, timer });
  });
}

function rejectAllPendingAcks(reason) {
  for (const [id, { reject: rej, timer }] of pendingAcks) {
    clearTimeout(timer);
    rej(new Error(reason));
    pendingAcks.delete(id);
  }
}

// ── Auth middleware ──────────────────────────────────────────────────
function authMiddleware(req, res, next) {
  if (!API_KEY) return next(); // no key configured = open (dev only)
  const provided = req.headers["x-api-key"] || req.query.apikey || "";
  if (crypto.timingSafeEqual(Buffer.from(provided.padEnd(64)), Buffer.from(API_KEY.padEnd(64)))) {
    return next();
  }
  return res.status(401).json({ error: "Unauthorized" });
}
app.use(authMiddleware);

// ── Baileys connection ──────────────────────────────────────────────
async function startBaileys() {
  if (starting) {
    logger.warn("startBaileys() déjà en cours — appel ignoré (anti-concurrence)");
    return;
  }
  starting = true;
  try {
    await startBaileysInner();
  } finally {
    starting = false;
  }
}

async function startBaileysInner() {
  // Ferme proprement le socket précédent avant d'en ouvrir un nouveau —
  // sans ça, un ancien socket encore vivant peut se battre avec le nouveau
  // pour la même session (source probable des tempêtes "conflict: replaced").
  if (sock) {
    try { sock.end(undefined); } catch (_) {}
    sock = null;
  }

  connectionState = "connecting";
  qrCode = null;

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    logger,
    printQRInTerminal: true,
    connectTimeoutMs: 60_000,
    defaultQueryTimeoutMs: 60_000,
    browser: ["5Hostachy", "Chrome", "1.0.0"],
  });

  sock.ev.on("creds.update", saveCreds);

  // Resolve pending ACKs when WhatsApp server acknowledges receipt
  sock.ev.on("messages.update", (updates) => {
    for (const { key, update } of updates) {
      const pending = pendingAcks.get(key?.id);
      if (pending && (update?.status ?? 0) >= 2) { // SERVER_ACK or better
        clearTimeout(pending.timer);
        pendingAcks.delete(key.id);
        pending.resolve(update.status);
      }
    }
  });

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      qrCode = qr;
      connectionState = "waiting_qr";
      logger.info("New QR code generated — scan it to connect");
    }

    if (connection === "open") {
      connectionState = "open";
      qrCode = null;
      reconnectAttempt = 0; // reset du backoff après une connexion réussie
      logger.warn("WhatsApp connected ✓");
    }

    if (connection === "close") {
      connectionState = "disconnected";
      rejectAllPendingAcks("Connection closed");
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      logger.warn({ statusCode, shouldReconnect }, "Connection closed");
      if (shouldReconnect) {
        scheduleReconnect();
      } else {
        logger.warn("Logged out — delete auth_state and restart to re-pair");
      }
    }
  });
}

// Filet de sécurité : si plus aucune reconnexion n'est en cours ni programmée
// alors que l'état n'est pas "open", on en relance une. Couvre tout scénario
// où la chaîne de reconnexion s'arrêterait pour une raison non anticipée
// (cf. incident du 2026-07-24 : 2h23 sans la moindre tentative).
setInterval(() => {
  if (connectionState !== "open" && connectionState !== "connecting" && connectionState !== "waiting_qr" && !reconnectTimer && !starting) {
    logger.warn("Watchdog : aucune reconnexion en cours/programmée — relance forcée");
    scheduleReconnect();
  }
}, WATCHDOG_INTERVAL_MS);

// ── Routes ──────────────────────────────────────────────────────────
app.get("/status", (_req, res) => {
  res.json({ state: connectionState, hasQR: !!qrCode });
});

app.get("/qr", async (req, res) => {
  if (connectionState === "open") {
    return res.json({ message: "Already connected", state: "open" });
  }
  if (!qrCode) {
    return res.status(503).json({ message: "No QR code available yet, wait a few seconds", state: connectionState });
  }
  const format = req.query.format || "png";
  if (format === "raw") {
    return res.json({ qr: qrCode, state: connectionState });
  }
  // Return PNG image
  res.setHeader("Content-Type", "image/png");
  QRCode.toFileStream(res, qrCode, { width: 300, margin: 2 });
});

app.post("/send", async (req, res) => {
  if (connectionState !== "open") {
    return res.status(503).json({ error: "WhatsApp not connected", state: connectionState });
  }
  const { number, text, imageUrl, imageBase64 } = req.body;
  if (!number || !text) {
    return res.status(400).json({ error: "number and text are required" });
  }
  try {
    const jid = number.includes("@") ? number : `${number}@s.whatsapp.net`;
    // `imageBase64` est la voie normale : l'API a le fichier sous la main et nous
    // l'envoie. `imageUrl` reste accepté par compatibilité, mais il oblige Baileys
    // à retélécharger le fichier PAR L'INTERNET PUBLIC — ce qui suppose que le
    // dossier soit servi en anonyme, et a cassé l'envoi le 10/08/2026 quand les
    // photos de publication ont rejoint le dossier authentifié.
    const media = imageBase64
      ? { image: Buffer.from(imageBase64, "base64"), caption: text }
      : imageUrl
        ? { image: { url: imageUrl }, caption: text }
        : null;

    let sentMsg;
    try {
      sentMsg = await sock.sendMessage(jid, media ?? { text });
    } catch (errMedia) {
      // ⚠️ Un échec sur l'IMAGE ne doit jamais faire perdre le MESSAGE. Le
      // 10/08/2026, un 401 sur la photo a supprimé l'annonce entière du groupe :
      // les résidents n'ont rien reçu du tout, et l'échec n'était visible que
      // dans les logs. Le texte part, l'image est signalée.
      if (!media) throw errMedia;
      logger.warn({ err: errMedia }, "Média refusé — repli sur le texte seul");
      sentMsg = await sock.sendMessage(jid, { text });
    }

    // Wait for SERVER_ACK to confirm the message actually reached WhatsApp servers.
    // If no ACK within ACK_TIMEOUT_MS, the session is likely a ghost (connected
    // in appearance but silently rejected by WhatsApp). Reconnect automatically.
    //
    // 🔴 MAIS L'ABSENCE D'ACCUSÉ N'EST PAS UN ÉCHEC D'ENVOI (19/08/2026).
    // `sendMessage()` a déjà rendu la main : le message est PARTI. Seule la
    // confirmation du serveur manque. Jusqu'ici cette branche tombait dans le
    // `catch` commun et répondait 500 — indistinguable d'un envoi qui n'a jamais
    // eu lieu. L'historique de l'administration affichait donc « incertain —
    // réponse 500 du bridge » sur deux messages que WhatsApp montrait remis,
    // double coche à l'appui. Signalé à l'écran par l'utilisateur.
    //
    // 202 Accepted dit exactement ce qui s'est passé : reçu et traité, résultat
    // non confirmé. L'API le traduit en « incertain », mais avec la bonne raison
    // — et `envoye: true` distingue ce cas de tous les autres.
    const msgId = sentMsg?.key?.id;
    if (msgId) {
      try {
        await waitForAck(msgId);
      } catch (errAck) {
        logger.warn({ err: errAck, msgId }, "Message émis, accusé non observé — reconnexion");
        try { if (sock) sock.end(); } catch (_) {}
        connectionState = "disconnected";
        reconnectAttempt = 0;
        scheduleReconnect();
        return res.status(202).json({
          ok: false,
          envoye: true,
          acquitte: false,
          id: msgId,
          jid,
          error: errAck.message,
        });
      }
    }

    res.json({ ok: true, jid, id: msgId ?? null });
  } catch (err) {
    // Ici, `sendMessage()` lui-même a échoué : RIEN n'est parti, et rejouer est
    // sûr. Le cas « émis sans accusé » est traité plus haut et ne descend pas
    // jusqu'ici — la garde ci-dessous reste par prudence si un autre chemin
    // venait à lever la même erreur.
    logger.error(err, "Send failed");
    if (err.message.includes("ghost session") || err.message.includes("ACK timeout")) {
      logger.warn("Ghost session detected — triggering reconnect");
      try { if (sock) sock.end(); } catch (_) {}
      connectionState = "disconnected";
      reconnectAttempt = 0;
      scheduleReconnect();
    }
    res.status(500).json({ error: err.message });
  }
});

app.get("/groups", async (_req, res) => {
  if (connectionState !== "open") {
    return res.status(503).json({ error: "WhatsApp not connected", state: connectionState });
  }
  try {
    const groups = await sock.groupFetchAllParticipating();
    const list = Object.values(groups).map((g) => ({
      id: g.id,
      subject: g.subject,
      participants: g.participants?.length || 0,
    }));
    res.json(list);
  } catch (err) {
    logger.error(err, "Groups fetch failed");
    res.status(500).json({ error: err.message });
  }
});

app.post("/restart", async (_req, res) => {
  try {
    if (sock) sock.end();
  } catch (_) {}
  connectionState = "disconnected";
  reconnectAttempt = 0;
  scheduleReconnect();
  res.json({ ok: true, message: "Restarting..." });
});

// ── Start ───────────────────────────────────────────────────────────
app.listen(PORT, "0.0.0.0", () => {
  logger.info(`WhatsApp Bridge listening on port ${PORT}`);
  startBaileys().catch((err) => {
    logger.warn({ err: err.message }, "Échec du démarrage initial — nouvelle tentative programmée");
    scheduleReconnect();
  });
});
