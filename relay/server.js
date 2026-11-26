// Formation relay: serves the web app and forwards hand data between pilots in the same room.
// Zero dependencies — just Node 18+.   Run:  node relay/server.js   (PORT env var optional, default 8080)
const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const PORT = +process.env.PORT || 8080;
const WEB = path.join(__dirname, "..", "web");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml" };
const MAX_MSG = 64 * 1024;

const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const file = path.normalize(path.join(WEB, p === "/" ? "index.html" : p));
  if (!file.startsWith(WEB)) { res.writeHead(403).end(); return; }
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404).end("Not found"); return; }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" }).end(buf);
  });
});

// ---- minimal WebSocket (RFC 6455) ----
const rooms = new Map(); // room -> Set<socket>

function frame(str) {
  const data = Buffer.from(str);
  const n = data.length;
  const head = n < 126 ? Buffer.from([0x81, n])
    : n < 65536 ? Buffer.from([0x81, 126, n >> 8, n & 255])
    : (() => { const b = Buffer.alloc(10); b[0] = 0x81; b[1] = 127; b.writeBigUInt64BE(BigInt(n), 2); return b; })();
  return Buffer.concat([head, data]);
}

server.on("upgrade", (req, sock) => {
  const url = new URL(req.url, "http://x");
  const key = req.headers["sec-websocket-key"];
  if (url.pathname !== "/ws" || !key) { sock.destroy(); return; }
  const accept = crypto.createHash("sha1").update(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
  sock.write("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n");
  sock.setNoDelay(true);

  const room = (url.searchParams.get("room") || "FLIGHT1").slice(0, 40);
  if (!rooms.has(room)) rooms.set(room, new Set());
  const peers = rooms.get(room);
  peers.add(sock);
  log(`+ join ${room} (${peers.size})`);

  let buf = Buffer.alloc(0);
  sock.on("data", chunk => {
    buf = Buffer.concat([buf, chunk]);
    while (buf.length >= 2) {
      const op = buf[0] & 15, masked = buf[1] & 128;
      let len = buf[1] & 127, off = 2;
      if (len === 126) { if (buf.length < 4) return; len = buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { if (buf.length < 10) return; len = Number(buf.readBigUInt64BE(2)); off = 10; }
      if (len > MAX_MSG) { sock.destroy(); return; }
      const total = off + (masked ? 4 : 0) + len;
      if (buf.length < total) return;
      let payload = buf.subarray(off + (masked ? 4 : 0), total);
      if (masked) {
        const m = buf.subarray(off, off + 4);
        payload = Buffer.from(payload.map((b, i) => b ^ m[i & 3]));
      }
      buf = buf.subarray(total);
      if (op === 8) { sock.end(Buffer.from([0x88, 0])); return; }        // close
      if (op === 9) { sock.write(Buffer.concat([Buffer.from([0x8a, payload.length]), payload])); continue; } // ping→pong
      if (op !== 1) continue;                                           // text only
      const out = frame(payload.toString());
      for (const p of peers) if (p !== sock && p.writable) p.write(out);
    }
  });
  const leave = () => {
    if (!peers.delete(sock)) return;
    if (!peers.size) rooms.delete(room);
    log(`- leave ${room} (${peers.size})`);
  };
  sock.on("close", leave);
  sock.on("error", leave);
});

function log(s) { console.log(new Date().toISOString().slice(11, 19), s); }

server.listen(PORT, () => {
  const ips = Object.values(require("os").networkInterfaces()).flat().filter(i => i.family === "IPv4" && !i.internal).map(i => i.address);
  console.log(`Relay running.
  Tracker:  http://localhost:${PORT}/            (camera works on localhost; phones need HTTPS — see README)
  Viewer:   http://localhost:${PORT}/viewer.html
  On your network: ${ips.map(ip => `http://${ip}:${PORT}`).join("  ") || "n/a"}`);
});
