/**
 * Baileys SIMULÉ — préchargé par `node -r` avant `index.js`.
 *
 * Le bridge ne peut pas se tester contre WhatsApp : aucune CI ne tient une
 * session, et en ouvrir une depuis un test serait un appareil de plus sur le
 * compte. Ce qu'on peut vérifier sans lui, c'est tout ce qu'`index.js` fait
 * AUTOUR de Baileys — clé d'API, plafond du corps, codes de réponse, accusé du
 * serveur — et c'est précisément ce qu'une montée d'express peut casser.
 *
 * Né le 27/09/2026 avec la montée d'express 4 → 5 (PR Dependabot #1289) : le
 * banc qui l'a précédé a trouvé un `POST /send` sans corps JSON passé de 400 à
 * 500, que rien d'autre n'aurait vu avant la production.
 */
const Module = require("module");
const { EventEmitter } = require("events");

const simule = {
  default: () => {
    const ev = new EventEmitter();
    setTimeout(() => ev.emit("connection.update", { connection: "open" }), 20);
    return {
      ev,
      end() {},
      groupFetchAllParticipating: async () => ({
        g1: { id: "g1", subject: "Hall", participants: [{}, {}] },
      }),
      sendMessage: async () => {
        const id = `M${Date.now()}`;
        // L'accusé du serveur (statut ≥ 2) arrive après l'envoi, comme en vrai.
        setTimeout(() => ev.emit("messages.update", [{ key: { id }, update: { status: 2 } }]), 10);
        return { key: { id } };
      },
    };
  },
  useMultiFileAuthState: async () => ({ state: { creds: {}, keys: {} }, saveCreds() {} }),
  DisconnectReason: { loggedOut: 401 },
  fetchLatestBaileysVersion: async () => ({ version: [2, 3000, 0] }),
  makeCacheableSignalKeyStore: (cles) => cles,
};

const chargerOrigine = Module._load;
Module._load = function (demande, ...reste) {
  if (demande === "baileys") return simule;
  return chargerOrigine.call(this, demande, ...reste);
};
