// Wingman viewer: connects to the relay and draws every other pilot's hand + current signal.
// Plain script (no modules, no WebGL) so it also runs inside MSFS's in-game panel browser.
(function () {
  var CONN = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],
    [9,13],[13,14],[14,15],[15,16],[13,17],[0,17],[17,18],[18,19],[19,20]];
  var STALE_MS = 3000;

  function HandViewer(opts) {
    this.canvas = opts.canvas;
    this.onStatus = opts.onStatus || function () {};
    this.myCallsign = (opts.myCallsign || "").toUpperCase();
    this.peers = {}; // callsign -> {hands, label, t, changed}
    this.ws = null;
    var self = this;
    (function tick() { self.draw(); requestAnimationFrame(tick); })();
  }

  HandViewer.prototype.connect = function (url, room) {
    var self = this;
    clearTimeout(this.retry);
    if (this.ws) { this.ws.onclose = null; this.ws.close(); }
    var full = url.replace(/\/$/, "") + "/ws?room=" + encodeURIComponent(room || "FLIGHT1");
    try { this.ws = new WebSocket(full); } catch (e) { this.onStatus("Bad address: " + e.message); return; }
    this.ws.onopen = function () { self.onStatus("Connected to " + room); };
    this.ws.onclose = function () {
      self.onStatus("Disconnected — retrying in 3 s");
      self.retry = setTimeout(function () { self.connect(url, room); }, 3000);
    };
    this.ws.onmessage = function (ev) {
      var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.type !== "hand" || !m.callsign) return;
      var cs = String(m.callsign).toUpperCase().slice(0, 12);
      if (cs === self.myCallsign) return;
      var p = self.peers[cs] || (self.peers[cs] = {});
      if (p.label !== m.label && m.label) p.changed = Date.now();
      p.label = m.label; p.hands = m.hands || []; p.t = Date.now();
    };
  };

  HandViewer.prototype.draw = function () {
    var c = this.canvas, x = c.getContext("2d");
    var W = c.clientWidth || c.width, H = c.clientHeight || c.height;
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
    x.clearRect(0, 0, W, H);
    var now = Date.now(), self = this;
    var names = Object.keys(this.peers).filter(function (k) { return now - self.peers[k].t < STALE_MS; });
    if (!names.length) {
      x.fillStyle = "#8a96a3"; x.font = "16px sans-serif"; x.textAlign = "center";
      x.fillText("Waiting for wingmen…", W / 2, H / 2); return;
    }
    var cols = Math.ceil(Math.sqrt(names.length)), rows = Math.ceil(names.length / cols);
    var cw = W / cols, ch = H / rows;
    names.sort().forEach(function (name, i) {
      var p = self.peers[name], ox = (i % cols) * cw, oy = Math.floor(i / cols) * ch;
      var flash = p.changed && now - p.changed < 800;
      x.fillStyle = flash ? "rgba(255,180,0,.25)" : "rgba(255,255,255,.04)";
      x.fillRect(ox + 4, oy + 4, cw - 8, ch - 8);
      x.fillStyle = "#e8edf2"; x.font = "bold 14px sans-serif"; x.textAlign = "left";
      x.fillText(name, ox + 12, oy + 22);
      var s = Math.min(cw, ch) * 3.2;
      (p.hands || []).forEach(function (h, hi) {
        var cx = ox + cw * (p.hands.length > 1 ? (hi ? .7 : .3) : .5), cy = oy + ch * .48;
        var pt = function (k) { return [cx - h.w[k * 3] * s, cy + h.w[k * 3 + 1] * s]; };
        x.strokeStyle = "#ffb400"; x.lineWidth = Math.max(3, s / 60); x.lineCap = "round";
        x.beginPath();
        CONN.forEach(function (e) { var a = pt(e[0]), b = pt(e[1]); x.moveTo(a[0], a[1]); x.lineTo(b[0], b[1]); });
        x.stroke();
        x.fillStyle = "#fff";
        for (var k = 0; k < 21; k++) { var q = pt(k); x.beginPath(); x.arc(q[0], q[1], Math.max(3, s / 90), 0, 7); x.fill(); }
      });
      if (p.label) {
        x.fillStyle = "#ffb400"; x.textAlign = "center";
        x.font = "bold " + Math.round(Math.min(32, cw / 9)) + "px sans-serif";
        x.fillText(p.label, ox + cw / 2, oy + ch - 16);
      }
    });
  };

  window.HandViewer = HandViewer;
})();
