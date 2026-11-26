// Formation signal engine based on AFPAM 11-205 (9 Aug 2018), day hand signals.
// Works on MediaPipe hand landmarks: hand SHAPE per frame + MOVEMENT over the last ~1.5 s
// + short SEQUENCES (fist → fingers = HEFOE, change lead → position, digits).
// Plain script: defines window.SignalEngine (and module.exports for tests).
(function (root) {
  "use strict";

  // key: [default label, how to make it (shown on the page)]
  var SIGNALS = {
    GEAR_UP:          ["GEAR UP",            "Fist, thumb up, move hand up"],
    GEAR_DOWN:        ["GEAR DOWN",          "Fist, thumb down, move hand down"],
    LAND_IMMEDIATELY: ["I MUST LAND IMMEDIATELY", "Fist, thumb down, pump arm up and down rapidly"],
    FLAPS_DOWN:       ["FLAPS DOWN",         "Flat hand, fingers forward, bend down at the wrist"],
    FLAPS_UP:         ["FLAPS UP",           "Flat hand, fingers forward, bend up at the wrist"],
    SPEED_BRAKES:     ["SPEED BRAKES",       "Biting motion: fingers and thumb open and close"],
    AFTERBURNER:      ["AFTERBURNER IN/OUT", "Clenched fist moved inboard or outboard"],
    JETTISON:         ["JETTISON STORES",    "Fist at top of canopy, several pumping motions"],
    DESCEND:          ["DESCEND / DESIRE TO LAND", "Flat hand, palm down, moved forward and down"],
    LOOSEN:           ["LOOSEN FORMATION",   "Open hand pushed sideways toward the wingman"],
    PITCHOUT:         ["PITCHOUT / RUN UP",  "Index finger up, circular motion"],
    START_ENGINES:    ["START ENGINES",      "Open hand making a circular motion"],
    CHANGE_LEAD:      ["CHANGE LEAD",        "Point forward several times, then show wingman's position (fingers)"],
    ECHELON_TURN:     ["ECHELON TURN",       "Fist with index and little finger up"],
    BDA_CHECK:        ["BDA CHECK",          "Fist with index finger and thumb extended"],
    LANYARD_CHECK:    ["LANYARD CHECK",      "Hooked index finger"],
    FUEL_CHECK:       ["FUEL CHECK",         "Fist, thumb out sideways (drinking motion to mask)"],
    OXYGEN_CHECK:     ["OXYGEN CHECK / OK",  "OK sign: thumb and index form a circle"],
    HEFOE:            ["SYSTEM FAILURE",     "Fist held still, then 1 Hyd · 2 Elec · 3 Fuel · 4 Oxy · 5 Engine"],
    NUMBERS:          ["NUMBERS",            "Fingers up = 1–5, sideways = 6–9, fist = 0; drop hand between digits (fuel, frequency)"],
    BAILOUT:          ["EJECTING",           "Both fists pulled down across the face"],
    TX_FAIL:          ["RADIO: TRANSMITTER FAILED", "Open palm in front of face, moved up and down"],
    RX_FAIL:          ["RADIO: RECEIVER FAILED",    "Open palm by the ear, moved toward/away from camera"]
  };
  // Signals in the pamphlet a hand camera cannot see (aircraft, head or light signals)
  var NOT_DETECTABLE = [
    "Attention (rock wings)", "Echelon right/left (dip wing)", "Reform/tighten (rock wings slowly)",
    "Tactical formation (manoeuvres)", "Ready for takeoff (head nod)", "Start takeoff roll (head back)",
    "I must land on your wing (pat shoulder)", "Approach-end cable, electrical-failure and radio-inop landings (flown)",
    "Intercept signals (wing rock)", "All night signals (flashlight / landing light)"
  ];
  var HEFOE_NAMES = ["", "HYDRAULIC", "ELECTRICAL", "FUEL", "OXYGEN", "ENGINE"];

  // ---------- geometry ----------
  function d3(a, b) { return Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0)); }
  function d2(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }
  function angleAt(a, b, c) { // angle between a→b and b→c (0 = straight)
    var ux = b.x - a.x, uy = b.y - a.y, uz = (b.z || 0) - (a.z || 0);
    var vx = c.x - b.x, vy = c.y - b.y, vz = (c.z || 0) - (b.z || 0);
    var dot = (ux * vx + uy * vy + uz * vz) / (Math.hypot(ux, uy, uz) * Math.hypot(vx, vy, vz) || 1);
    return Math.acos(Math.max(-1, Math.min(1, dot))) * 180 / Math.PI;
  }

  // Hand shape from one frame. w = world landmarks (metres), img = image landmarks (0–1, y down)
  function shapeOf(w, img) {
    var palm = d3(w[0], w[9]);
    var ext = function (tip, pip) { return d3(w[0], w[tip]) > d3(w[0], w[pip]) * 1.15; };
    var f = [ext(8, 6), ext(12, 10), ext(16, 14), ext(20, 18)];
    var thumb = d3(w[4], w[5]) > palm * 0.5 && d3(w[0], w[4]) > d3(w[0], w[3]);
    var n = f.filter(Boolean).length;
    var pinch = d3(w[4], w[8]) / palm;
    // which way the extended fingers point on screen
    var pairs = [[5, 8], [9, 12], [13, 16], [17, 20]], dx = 0, dy = 0;
    pairs.forEach(function (p, i) { if (f[i] || !n) { dx += img[p[1]].x - img[p[0]].x; dy += img[p[1]].y - img[p[0]].y; } });
    var vertical = Math.abs(dy) >= Math.abs(dx);
    var indexBend = angleAt(w[5], w[6], w[8]);
    var shape, count = n + (thumb ? 1 : 0);

    if (!f[1] && !f[2] && !f[3] && !thumb && indexBend > 45 && indexBend < 130 && d3(w[8], w[5]) > palm * 0.55) shape = "HOOK";
    else if (pinch < 0.35 && f[1] && f[2] && f[3]) shape = "OK";
    else if (!n && !thumb) shape = "FIST";
    else if (!n && thumb) {
      var tx = img[4].x - img[2].x, ty = img[4].y - img[2].y;
      shape = Math.abs(ty) > Math.abs(tx) ? (ty < 0 ? "THUMB_UP" : "THUMB_DOWN") : "THUMB_SIDE";
    }
    else if (thumb && f[0] && !f[1] && !f[2] && !f[3]) shape = "BDA";
    else if (f[0] && f[3] && !f[1] && !f[2]) shape = "HORNS";
    else if (thumb && n === 4) shape = "OPEN";
    else shape = "FINGERS";
    return { shape: shape, count: count, vertical: vertical, up: dy < 0, pinch: pinch, flat: n >= 4 };
  }

  // ---------- motion helpers ----------
  function swings(v, thr) { // number of direction reversals bigger than thr
    if (!v.length) return 0;
    var dir = 0, ext = v[0], n = 0;
    for (var i = 0; i < v.length; i++) {
      var x = v[i];
      if (dir === 0) { if (x - ext > thr) { dir = 1; ext = x; } else if (ext - x > thr) { dir = -1; ext = x; } }
      else if (dir === 1) { if (x > ext) ext = x; else if (ext - x > thr) { dir = -1; ext = x; n++; } }
      else { if (x < ext) ext = x; else if (x - ext > thr) { dir = 1; ext = x; n++; } }
    }
    return n;
  }
  function circleTurns(xs, ys) { // how many full turns the path makes around its centre, and its radius
    var cx = 0, cy = 0, k = xs.length; if (k < 6) return { turns: 0, r: 0 };
    for (var i = 0; i < k; i++) { cx += xs[i]; cy += ys[i]; } cx /= k; cy /= k;
    var sum = 0, r = 0, prev = Math.atan2(ys[0] - cy, xs[0] - cx);
    for (i = 0; i < k; i++) {
      var a = Math.atan2(ys[i] - cy, xs[i] - cx), da = a - prev;
      if (da > Math.PI) da -= 2 * Math.PI; if (da < -Math.PI) da += 2 * Math.PI;
      sum += da; prev = a; r += Math.hypot(xs[i] - cx, ys[i] - cy);
    }
    return { turns: Math.abs(sum) / (2 * Math.PI), r: r / k };
  }
  function median(v) { var s = v.slice().sort(function (a, b) { return a - b; }); return s[s.length >> 1] || 0; }

  // ---------- engine ----------
  function SignalEngine() {
    this.buf = [];        // recent frames
    this.cool = 0;        // no new motion signal until this time
    this.lock = null;     // static shape already reported (wait for change)
    this.missingSince = 0;
    this.digits = []; this.lastDigit = 0;
    this.stillCool = 0; this.lastKey = null; this.lastT = 0;
    this.pending = null;  // {type:"HEFOE"|"CHANGE_LEAD", t}
  }
  SignalEngine.SIGNALS = SIGNALS;
  SignalEngine.NOT_DETECTABLE = NOT_DETECTABLE;
  SignalEngine.shapeOf = shapeOf;

  // hands: [{w, img}] (first = primary). t: ms. Returns {key, label} or null.
  SignalEngine.prototype.update = function (hands, t) {
    var B = this.buf;
    if (!hands.length) {
      if (!this.missingSince) this.missingSince = t;
      if (t - this.missingSince > 250) this.lock = null; // hand dropped out of sight: next digit can be the same
      B.length = 0;
      return null;
    }
    this.missingSince = 0;
    var h = hands[0], s = shapeOf(h.w, h.img), size = d2(h.img[0], h.img[9]);
    var second = hands[1] ? { shape: shapeOf(hands[1].w, hands[1].img).shape, y: hands[1].img[0].y } : null;
    B.push({ t: t, s: s, x: h.img[0].x, y: h.img[0].y, ix: h.img[8].x, iy: h.img[8].y, size: size,
             tip: (h.img[12].y - h.img[0].y) / size, mx: h.img[12].x, my: h.img[12].y, second: second });
    while (B.length && t - B[0].t > 1600) B.shift();
    if (this.digits.length && t - this.lastDigit > 4000) this.digits = [];
    if (this.pending && t - this.pending.t > 4000) this.pending = null;
    if (t < this.stillCool) return null;
    var m = t >= this.cool && this.motion(t);
    if (m === true) return null;
    return m || this.still(t);
  };

  SignalEngine.prototype.fire = function (key, t, label) {
    this.cool = t + 1200; this.stillCool = t + 400; this.buf.length = 0;
    this.lock = "__motion";
    var repeat = this.lastKey === key && t - this.lastT < 2500; // same movement still going on: don't re-announce
    this.lastKey = key; this.lastT = t;
    return repeat ? null : { key: key, label: label || SIGNALS[key][0] };
  };

  SignalEngine.prototype.motion = function (t) {
    var B = this.buf, self = this;
    var win = function (dt) { return B.filter(function (e) { return t - e.t <= dt; }); };
    var frac = function (W, pred) { return W.length ? W.filter(pred).length / W.length : 0; };
    var is = function () { var names = [].slice.call(arguments); return function (e) { return names.indexOf(e.s.shape) >= 0; }; };
    var flatHand = function (e) { return e.s.flat; };
    var col = function (W, k) { return W.map(function (e) { return e[k]; }); };

    var L = win(1500); if (L.length < 8 || L[L.length - 1].t - L[0].t < 500) return null;
    var size = median(col(L, "size")), thr = 0.35 * size;
    var ys = col(L, "y"), xs = col(L, "x"), sizes = col(L, "size");

    // both fists pulled down together → ejecting
    var S = win(800);
    if (frac(S, function (e) { return e.s.shape === "FIST" && e.second && e.second.shape === "FIST"; }) > 0.6 &&
        S[S.length - 1].y - S[0].y > 1.2 * size) return this.fire("BAILOUT", t);

    // repeated movements (≥3 reversals)
    var vy = swings(ys, thr), vx = swings(xs, thr), vz = swings(sizes, 0.18 * size);
    var bite = swings(L.map(function (e) { return e.s.pinch; }), 0.45);
    if (bite >= 3 && vy < 2) return this.fire("SPEED_BRAKES", t);
    if (frac(L, is("THUMB_DOWN")) > 0.6 && vy >= 3) return this.fire("LAND_IMMEDIATELY", t);
    if (frac(L, is("FIST")) > 0.6 && vy >= 3) return this.fire("JETTISON", t);
    if (frac(L, flatHand) > 0.6 && vy >= 3) return this.fire("TX_FAIL", t);
    if (frac(L, flatHand) > 0.6 && vz >= 3 && vy < 2 && vx < 2) return this.fire("RX_FAIL", t);

    // circles
    var pointUp = function (e) { return e.s.shape === "FINGERS" && e.s.count === 1 && e.s.vertical && e.s.up; };
    if (frac(L, pointUp) > 0.6) {
      var c = circleTurns(col(L, "ix"), col(L, "iy"));
      if (c.turns > 0.8 && c.r > 0.3 * size) return this.fire("PITCHOUT", t);
    }
    if (frac(L, flatHand) > 0.6) {
      var c2 = circleTurns(xs, ys);
      if (c2.turns > 0.8 && c2.r > 0.3 * size) return this.fire("START_ENGINES", t);
    }
    // forward pointing jabs → change lead, then position number
    var pointFwd = function (e) { return e.s.shape === "FINGERS" && e.s.count === 1 && !e.s.vertical; };
    if (frac(L, pointFwd) > 0.6 && (vz >= 2 || vx >= 2)) {
      var ev = this.fire("CHANGE_LEAD", t, SIGNALS.CHANGE_LEAD[0] + " →");
      this.pending = { type: "CHANGE_LEAD", t: t };
      return ev || true; // true = handled (repeat jab), stop other checks
    }

    // single strokes over the last 0.6 s
    var M = win(600); if (M.length < 5) return null;
    var dy = M[M.length - 1].y - M[0].y, dx = M[M.length - 1].x - M[0].x;
    var hold = function (pred) { return frac(M, pred) > 0.7; };
    if (hold(is("THUMB_UP")) && dy < -0.9 * size) return this.fire("GEAR_UP", t);
    if (hold(is("THUMB_DOWN")) && dy > 0.9 * size) return this.fire("GEAR_DOWN", t);
    if (hold(is("FIST")) && Math.abs(dx) > 1.0 * size && Math.abs(dy) < 0.6 * size) return this.fire("AFTERBURNER", t);
    if (hold(flatHand)) {
      var dTip = M[M.length - 1].tip - M[0].tip;
      if (Math.abs(dy) < 0.4 * size && dTip > 0.6) return this.fire("FLAPS_DOWN", t);
      if (Math.abs(dy) < 0.4 * size && dTip < -0.6) return this.fire("FLAPS_UP", t);
      if (dy > 0.9 * size && Math.abs(dx) < dy) return this.fire("DESCEND", t);
      if (Math.abs(dx) > 1.1 * size && Math.abs(dy) < 0.5 * size) return this.fire("LOOSEN", t);
    }
    return null;
  };

  SignalEngine.prototype.still = function (t) {
    var B = this.buf, last = B[B.length - 1];
    var W = B.filter(function (e) { return t - e.t <= 450; });
    if (W.length < 4 || t - W[0].t < 350) return null;
    var k = function (e) { return e.s.shape + ":" + e.s.count + ":" + (e.s.vertical ? "v" : "h"); };
    var key = k(last);
    if (!W.every(function (e) { return k(e) === key; })) return null;
    var size = median(W.map(function (e) { return e.size; }));
    var range = function (k) { var v = W.map(function (e) { return e[k]; }); return Math.max.apply(null, v) - Math.min.apply(null, v); };
    if (range("x") > 0.3 * size || range("y") > 0.3 * size || range("mx") > 0.4 * size || range("my") > 0.4 * size) return null;
    if (this.lock === key) return null;
    var afterMotion = this.lock === "__motion";
    this.lock = key;
    if (afterMotion && !this.pending) return null; // pose left over from a movement signal, not a new signal

    var s = last.s, self = this;
    var simple = { OK: "OXYGEN_CHECK", BDA: "BDA_CHECK", HORNS: "ECHELON_TURN", HOOK: "LANYARD_CHECK", THUMB_SIDE: "FUEL_CHECK" };
    if (simple[s.shape]) return { key: simple[s.shape], label: SIGNALS[simple[s.shape]][0] };

    var digit = null;
    if (s.shape === "FIST") {
      if (this.digits.length && t - this.lastDigit < 4000) digit = 0;
      else { this.pending = { type: "HEFOE", t: t }; return null; }
    }
    if (s.shape === "FINGERS" || s.shape === "OPEN") digit = s.vertical ? s.count : (s.count <= 4 ? s.count + 5 : null);
    if (digit === null) return null;

    var p = this.pending;
    if (p && p.type === "HEFOE" && s.vertical && digit >= 1 && digit <= 5) {
      this.pending = null;
      return { key: "HEFOE", label: SIGNALS.HEFOE[0] + ": " + HEFOE_NAMES[digit] };
    }
    if (p && p.type === "CHANGE_LEAD" && s.vertical && digit >= 1 && digit <= 5) {
      this.pending = null;
      return { key: "CHANGE_LEAD", label: SIGNALS.CHANGE_LEAD[0] + ": #" + digit + " TAKES LEAD" };
    }
    this.digits.push(digit); this.lastDigit = t;
    return { key: "NUMBERS", label: SIGNALS.NUMBERS[0] + ": " + self.digits.join(" ") };
  };

  root.SignalEngine = SignalEngine;
  if (typeof module !== "undefined") module.exports = SignalEngine;
})(typeof window !== "undefined" ? window : globalThis);
