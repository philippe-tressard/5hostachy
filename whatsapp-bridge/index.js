/**
 * WhatsApp Bridge — Minimal Baileys service for 5Hostachy.
 *
 * Endpoints:
 *   GET  /status        → connection state
 *   GET  /qr            → QR code as PNG image (for pairing)
 *   POST /send          → send a message  { number, text, imageUrl? }
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
      logger.info("WhatsApp connected ✓");
    }

    if (connection === "close") {
      connectionState = "disconnected";
      rejectAllPendingAcks("Connection closed");
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      logger.warn({ statusCode, shouldReconnect }, "Connection closed");
      if (shouldReconnect) {
        setTimeout(startBaileys, 5_000);
      } else {
        logger.warn("Logged out — delete auth_state and restart to re-pair");
      }
    }
  });
}

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
  const { number, text, imageUrl } = req.body;
  if (!number || !text) {
    return res.status(400).json({ error: "number and text are required" });
  }
  try {
    const jid = number.includes("@") ? number : `${number}@s.whatsapp.net`;
    let sentMsg;
    if (imageUrl) {
      sentMsg = await sock.sendMessage(jid, { image: { url: imageUrl }, caption: text });
    } else {
      sentMsg = await sock.sendMessage(jid, { text });
    }

    // Wait for SERVER_ACK to confirm the message actually reached WhatsApp servers.
    // If no ACK within ACK_TIMEOUT_MS, the session is likely a ghost (connected
    // in appearance but silently rejected by WhatsApp). Reconnect automatically.
    const msgId = sentMsg?.key?.id;
    if (msgId) {
      await waitForAck(msgId);
    }

    res.json({ ok: true, jid });
  } catch (err) {
    logger.error(err, "Send failed");
    if (err.message.includes("ghost session") || err.message.includes("ACK timeout")) {
      logger.warn("Ghost session detected — triggering reconnect");
      try { if (sock) sock.end(); } catch (_) {}
      setTimeout(startBaileys, 2_000);
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
  setTimeout(startBaileys, 1_000);
  res.json({ ok: true, message: "Restarting..." });
});

// ── Start ───────────────────────────────────────────────────────────
app.listen(PORT, "0.0.0.0", () => {
  logger.info(`WhatsApp Bridge listening on port ${PORT}`);
  startBaileys();
});
