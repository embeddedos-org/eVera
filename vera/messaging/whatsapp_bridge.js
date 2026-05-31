/**
 * eVera WhatsApp Bridge (whatsapp-web.js)
 * ========================================
 * Runs as a local Node.js server on port 8766.
 * eVera's Python backend communicates with this bridge via HTTP.
 *
 * Install: npm install whatsapp-web.js qrcode-terminal express
 * Run:     node whatsapp_bridge.js
 *
 * On first run, scan the QR code with your WhatsApp mobile app.
 * After that, the session is saved and auto-reconnects.
 */

const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const express = require("express");

const PORT = process.env.WWEBJS_PORT || 8766;
const EVERA_CALLBACK_URL = process.env.EVERA_URL || "http://localhost:8765";

const app = express();
app.use(express.json());

// ── WhatsApp client ────────────────────────────────────────────────────────
const client = new Client({
  authStrategy: new LocalAuth({ dataPath: "./.wwebjs_auth" }),
  puppeteer: {
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-accelerated-2d-canvas",
      "--no-first-run",
      "--no-zygote",
      "--disable-gpu",
    ],
  },
});

let qrData = null;
let isReady = false;
let phoneNumber = null;
let batteryLevel = null;

client.on("qr", (qr) => {
  qrData = qr;
  console.log("[WhatsApp Bridge] Scan this QR code:");
  qrcode.generate(qr, { small: true });
});

client.on("ready", async () => {
  isReady = true;
  qrData = null;
  const info = client.info;
  phoneNumber = info?.wid?.user || null;
  console.log(`[WhatsApp Bridge] Connected as ${phoneNumber}`);
});

client.on("disconnected", (reason) => {
  isReady = false;
  console.log("[WhatsApp Bridge] Disconnected:", reason);
});

client.on("message", async (msg) => {
  if (msg.fromMe) return; // ignore own messages
  const from = msg.from.replace("@c.us", "");
  const body = msg.body;
  const hasMedia = msg.hasMedia;

  console.log(`[WhatsApp Bridge] Message from ${from}: ${body.slice(0, 80)}`);

  // Forward to eVera backend
  try {
    const payload = {
      platform: "whatsapp",
      provider: "wwebjs",
      from,
      message: body,
      has_media: hasMedia,
      timestamp: Date.now(),
    };

    const resp = await fetch(`${EVERA_CALLBACK_URL}/webhooks/whatsapp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (resp.ok) {
      const data = await resp.json();
      if (data.reply) {
        await msg.reply(data.reply);
      }
    }
  } catch (err) {
    console.error("[WhatsApp Bridge] Failed to forward to eVera:", err.message);
  }
});

// ── HTTP API ───────────────────────────────────────────────────────────────

// Status
app.get("/status", (req, res) => {
  res.json({
    connected: isReady,
    phone: phoneNumber,
    battery: batteryLevel,
    has_qr: !!qrData,
  });
});

// QR code
app.get("/qr", (req, res) => {
  if (isReady) {
    return res.json({ connected: true, qr: null });
  }
  if (!qrData) {
    return res.status(404).json({ error: "No QR code available yet" });
  }
  res.json({ qr: qrData });
});

// Send message
app.post("/send", async (req, res) => {
  const { to, message } = req.body;
  if (!to || !message) {
    return res.status(400).json({ error: "to and message are required" });
  }
  if (!isReady) {
    return res.status(503).json({ error: "WhatsApp not connected" });
  }
  try {
    const chatId = to.includes("@c.us") ? to : `${to}@c.us`;
    await client.sendMessage(chatId, message);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Send to group
app.post("/send-group", async (req, res) => {
  const { groupId, message } = req.body;
  if (!groupId || !message) {
    return res.status(400).json({ error: "groupId and message are required" });
  }
  if (!isReady) {
    return res.status(503).json({ error: "WhatsApp not connected" });
  }
  try {
    await client.sendMessage(groupId, message);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// List chats
app.get("/chats", async (req, res) => {
  if (!isReady) {
    return res.status(503).json({ error: "WhatsApp not connected" });
  }
  try {
    const chats = await client.getChats();
    res.json(
      chats.slice(0, 50).map((c) => ({
        id: c.id._serialized,
        name: c.name,
        isGroup: c.isGroup,
        unread: c.unreadCount,
        lastMessage: c.lastMessage?.body?.slice(0, 100),
      }))
    );
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Start ──────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`[WhatsApp Bridge] HTTP API listening on port ${PORT}`);
  console.log(`[WhatsApp Bridge] Forwarding messages to ${EVERA_CALLBACK_URL}`);
  client.initialize();
});
