#!/usr/bin/env python3
"""Hand-signal arm bridge for MSFS 2024.

Runs on each pilot's PC next to the sim:
  1. Receives YOUR tracked hand from the relay (sent by the phone/webcam tracker with your callsign).
  2. Solves arm IK (ik.py) and writes L:HSIG_0_* so the arm attached in your aircraft moves.
  3. Sends your arm pose + aircraft position to the relay.
  4. For every wingman, spawns an arm SimObject ("HSIG Arm Slot N"), keeps it on their cockpit
     every frame, and writes L:HSIG_N_* to pose it.

Usage:
  python bridge.py --relay ws://localhost:8080 --room FLIGHT1 --callsign LEAD
  python bridge.py ... --dry-run      (no sim: prints the arm angles; good for testing the tracker)
  python bridge.py ... --calibrate    (prints pitch/bank so you can check the sign settings)

Needs Python 3.9+ and, for the sim, the same SimConnect package vASW uses (pip install SimConnect,
or copy vASW's SimConnect folder next to this file). No other dependencies.
"""
import argparse
import base64
import ctypes
import json
import math
import os
import socket
import ssl
import struct
import sys
import threading
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik  # noqa: E402

EARTH_R_FT = 20902231.0
CHANNELS = ik.load_channels()
IDS = [c["id"] for c in CHANNELS]
REST_DEG = {c["id"]: 0.0 for c in CHANNELS}   # arm hanging, hand relaxed
REST_DEG.update({"curl_index": 20, "curl_middle": 25, "curl_ring": 30, "curl_pinky": 30, "curl_thumb": 15})
WRAP = {c["id"] for c in CHANNELS if c["max"] - c["min"] >= 360}


# ---------------------------------------------------------------- relay (minimal WebSocket client)
class Relay:
    def __init__(self, url, room):
        u = urlparse(url)
        port = u.port or (443 if u.scheme == "wss" else 80)
        raw = socket.create_connection((u.hostname, port), timeout=10)
        self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=u.hostname) if u.scheme == "wss" else raw
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path.rstrip("/") or "") + "/ws?room=" + room
        self.sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {u.hostname}:{port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("relay closed during handshake")
            head += chunk
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise ConnectionError("relay refused WebSocket: " + head.split(b"\r\n")[0].decode())
        self.buf = head.split(b"\r\n\r\n", 1)[1]
        self.sock.settimeout(None)
        self.lock = threading.Lock()

    def _frame(self, op, data):
        mask = os.urandom(4)
        n = len(data)
        head = bytes([0x80 | op]) + (bytes([0x80 | n]) if n < 126 else
                                     bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else
                                     bytes([0x80 | 127]) + struct.pack(">Q", n))
        return head + mask + bytes(b ^ mask[i & 3] for i, b in enumerate(data))

    def send(self, obj):
        with self.lock:
            self.sock.sendall(self._frame(1, json.dumps(obj, separators=(",", ":")).encode()))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("relay closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        while True:
            b0, b1 = self._read(2)
            op, n = b0 & 15, b1 & 127
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            data = self._read(n)
            if op == 1:
                return data.decode("utf-8", "replace")
            if op == 8:
                raise ConnectionError("relay closed")
            if op == 9:
                with self.lock:
                    self.sock.sendall(self._frame(10, data))


# ---------------------------------------------------------------- sim output
class Sim:
    """Thin wrapper over the SimConnect package, using the same raw calls as vASW."""

    def __init__(self):
        from SimConnect import SimConnect, AircraftRequests
        from SimConnect.Constants import SIMCONNECT_UNUSED, SIMCONNECT_OBJECT_ID_USER
        from SimConnect.Enum import SIMCONNECT_DATATYPE, SIMCONNECT_DATA_INITPOSITION
        self.UNUSED, self.USER = SIMCONNECT_UNUSED, SIMCONNECT_OBJECT_ID_USER
        self.DT, self.INIT = SIMCONNECT_DATATYPE, SIMCONNECT_DATA_INITPOSITION
        self.sm = SimConnect()
        self.aq = AircraftRequests(self.sm, _time=20)
        self.defs = {}
        self.pos_def = self.sm.new_def_id()
        self.sm.dll.AddToDataDefinition(self.sm.hSimConnect, self.pos_def.value, b"Initial Position", b"",
                                        self.DT.SIMCONNECT_DATATYPE_INITPOSITION, 0, self.UNUSED)

    def _lvar_def(self, prefix):
        if prefix not in self.defs:
            d = self.sm.new_def_id()
            for name in IDS + ["active"]:
                self.sm.dll.AddToDataDefinition(self.sm.hSimConnect, d.value, f"L:{prefix}{name}".encode(), b"number",
                                                self.DT.SIMCONNECT_DATATYPE_FLOAT64, 0, self.UNUSED)
            self.defs[prefix] = d
        return self.defs[prefix]

    def set_lvars(self, prefix, anim, active):
        d = self._lvar_def(prefix)
        arr = (ctypes.c_double * (len(IDS) + 1))(*([anim[i] for i in IDS] + [1.0 if active else 0.0]))
        self.sm.dll.SetDataOnSimObject(self.sm.hSimConnect, d.value, self.USER, 0, 0,
                                       ctypes.sizeof(arr), ctypes.cast(arr, ctypes.c_void_p))

    def own_state(self):
        g = self.aq.get
        try:
            return {"lat": g("PLANE_LATITUDE"), "lon": g("PLANE_LONGITUDE"), "alt": g("PLANE_ALTITUDE"),
                    "pitch": math.degrees(g("PLANE_PITCH_DEGREES")), "bank": math.degrees(g("PLANE_BANK_DEGREES")),
                    "hdg": math.degrees(g("PLANE_HEADING_DEGREES_TRUE")),
                    "ve": g("VELOCITY_WORLD_X"), "vn": g("VELOCITY_WORLD_Z"), "vu": g("VELOCITY_WORLD_Y")}
        except TypeError:  # a value came back None (sim loading)
            return None

    def _init(self, p):
        s = self.INIT()
        s.Latitude, s.Longitude, s.Altitude = p["lat"], p["lon"], p["alt"]
        s.Pitch, s.Bank, s.Heading = p["pitch"], p["bank"], p["hdg"]
        s.OnGround, s.Airspeed = 0, 0
        return s

    def spawn(self, title, p):
        os.environ.pop("SIMCONNECT_OBJECT_ID", None)
        self.sm.dll.AICreateSimulatedObject(self.sm.hSimConnect, title.encode(), self._init(p), self.sm.new_request_id().value)
        for _ in range(40):
            oid = os.environ.get("SIMCONNECT_OBJECT_ID")
            if oid:
                return int(oid)
            time.sleep(0.025)
        return None

    def move(self, oid, p):
        s = self._init(p)
        self.sm.dll.SetDataOnSimObject(self.sm.hSimConnect, self.pos_def.value, ctypes.c_uint32(oid), 0, 0,
                                       ctypes.sizeof(s), ctypes.pointer(s))

    def remove(self, oid):
        self.sm.dll.AIRemoveObject(self.sm.hSimConnect, ctypes.c_uint32(oid), self.sm.new_request_id().value)


# ---------------------------------------------------------------- maths helpers
def smooth(prev, new, alpha):
    out = {}
    for k in IDS:
        a, b = prev.get(k, new[k]), new[k]
        if k in WRAP:
            b = a + ((b - a + 180) % 360 - 180)
            v = a + (b - a) * alpha
            out[k] = (v + 180) % 360 - 180
        else:
            out[k] = a + (b - a) * alpha
    return out


def body_to_world(state, off, signs):
    """Place a body-frame offset (right, up, forward, metres) on the aircraft. Returns sim lat/lon/alt/pbh."""
    pu = state["pitch"] * signs["pitch"]          # nose-up positive
    br = state["bank"] * signs["bank"]            # right-wing-down positive
    h, p, b = map(math.radians, (state["hdg"], pu, br))
    r, u, f = (v * 3.28084 for v in off)          # to feet
    e, n, up = r * math.cos(b) + u * math.sin(b), f, -r * math.sin(b) + u * math.cos(b)
    n, up = n * math.cos(p) - up * math.sin(p), n * math.sin(p) + up * math.cos(p)
    e, n = e * math.cos(h) + n * math.sin(h), -e * math.sin(h) + n * math.cos(h)
    lat = state["lat"] + math.degrees(n / EARTH_R_FT)
    lon = state["lon"] + math.degrees(e / (EARTH_R_FT * math.cos(math.radians(state["lat"]))))
    return {"lat": lat, "lon": lon, "alt": state["alt"] + up, "pitch": state["pitch"], "bank": state["bank"], "hdg": state["hdg"]}


def predict(state, dt):
    s = dict(state)
    s["lat"] += math.degrees(state["vn"] * dt / EARTH_R_FT)
    s["lon"] += math.degrees(state["ve"] * dt / (EARTH_R_FT * math.cos(math.radians(state["lat"]))))
    s["alt"] += state["vu"] * dt
    return s


def pick_hand(hands, side, swap):
    if not hands:
        return None
    want = side.capitalize()
    for h in hands:
        label = h.get("side", "")
        actual = {"Left": "Right", "Right": "Left"}.get(label, label) if swap else label
        if actual == want and "p" in h:
            return h
    return next((h for h in hands if "p" in h), None)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--relay", default="ws://localhost:8080")
    ap.add_argument("--room", default="FLIGHT1")
    ap.add_argument("--callsign", required=True, help="must match the callsign in the tracker page")
    ap.add_argument("--aircraft", default="hawk_t2", help="entry in aircraft.json")
    ap.add_argument("--slots", type=int, default=4, help="how many wingman arm objects exist (HSIG Arm Slot 1..N)")
    ap.add_argument("--lead-ms", type=float, default=0.0, help="extra prediction for wingman arms; tune if they trail")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()

    cfg = ik.load_aircraft(a.aircraft)
    signs = cfg.get("attitude_signs", {"pitch": -1, "bank": -1})
    me = a.callsign.upper()
    sim = None if a.dry_run else Sim()

    if a.calibrate:
        print("Pitch the nose UP and bank RIGHT. If a number goes negative, set its sign to -1 in aircraft.json "
              "'attitude_signs' (else +1).")
        while True:
            s = sim.own_state()
            if s:
                print(f"raw pitch {s['pitch']:+7.1f}   raw bank {s['bank']:+7.1f}   hdg {s['hdg']:6.1f}", end="\r")
            time.sleep(0.2)

    relay = Relay(a.relay, a.room)
    print(f"Connected to relay {a.relay} room {a.room} as {me}. Aircraft config: {a.aircraft}.")
    lock = threading.Lock()
    own = {"hand": None, "t": 0.0}
    remotes = {}  # callsign -> {"anim", "state", "t_state", "t", "slot", "oid"}

    def reader():
        while True:
            try:
                m = json.loads(relay.recv())
            except ConnectionError as e:
                print("Relay connection lost:", e)
                os._exit(1)
            except ValueError:
                continue
            cs = str(m.get("callsign", "")).upper()[:12]
            with lock:
                if m.get("type") == "hand" and cs == me:
                    own["hand"] = pick_hand(m.get("hands") or [], cfg.get("side", "left"), cfg.get("swap_handedness", True))
                    if own["hand"]:
                        own["t"] = time.time()
                elif m.get("type") == "arm" and cs and cs != me and len(m.get("a", [])) == len(IDS):
                    r = remotes.setdefault(cs, {"slot": None, "oid": None})
                    r["anim"] = dict(zip(IDS, m["a"]))
                    r["t"] = time.time()
                    if m.get("s"):
                        r["state"], r["t_state"] = dict(zip(["lat", "lon", "alt", "pitch", "bank", "hdg", "ve", "vn", "vu"], m["s"])), time.time()
    threading.Thread(target=reader, daemon=True).start()

    deg = dict(REST_DEG)
    last_send = last_print = 0.0
    free_slots = list(range(1, a.slots + 1))
    while True:
        t0 = time.time()
        with lock:
            hand, age = own["hand"], t0 - own["t"]
        target = ik.hand_to_channels(hand, cfg) if hand and age < 0.5 else REST_DEG
        deg = smooth(deg, {k: target.get(k, REST_DEG[k]) for k in IDS}, 0.35 if target is not REST_DEG else 0.08)
        anim = ik.to_anim(deg, CHANNELS)
        active = target is not REST_DEG
        state = sim.own_state() if sim else None
        if sim:
            sim.set_lvars("HSIG_0_", anim, active)
        if t0 - last_send > 0.05:
            msg = {"type": "arm", "callsign": me, "a": [round(anim[i], 2) for i in IDS]}
            if state:
                msg["s"] = [state[k] for k in ("lat", "lon", "alt", "pitch", "bank", "hdg", "ve", "vn", "vu")]
            relay.send(msg)
            last_send = t0

        with lock:
            for cs, r in list(remotes.items()):
                if t0 - r["t"] > 10:  # wingman gone
                    if sim and r["oid"]:
                        sim.remove(r["oid"])
                    if r["slot"]:
                        free_slots.append(r["slot"])
                    del remotes[cs]
                    print(f"{cs} left; slot freed")
                    continue
                if r["slot"] is None:
                    if not free_slots:
                        continue
                    r["slot"] = free_slots.pop(0)
                    print(f"{cs} -> arm slot {r['slot']}")
                if sim and r.get("state"):
                    s = predict(r["state"], t0 - r["t_state"] + a.lead_ms / 1000)
                    where = body_to_world(s, cfg["shoulder_offset"], signs)
                    if r["oid"] is None and t0 - r.get("spawn_t", 0) > 5:  # retry a failed spawn every 5 s
                        r["spawn_t"] = t0
                        r["oid"] = sim.spawn(f"HSIG Arm Slot {r['slot']}", where)
                        if r["oid"] is None:
                            print(f"Could not spawn 'HSIG Arm Slot {r['slot']}' - is the arm package in Community?")
                    elif r["oid"]:
                        sim.move(r["oid"], where)
                    sim.set_lvars(f"HSIG_{r['slot']}_", r["anim"], t0 - r["t"] < 1)

        if a.dry_run and t0 - last_print > 0.5:
            show = " ".join(f"{k}={deg[k]:6.1f}" for k in ("sh_yaw", "sh_pitch", "sh_roll", "elbow", "wr_pitch", "curl_index"))
            print(("TRACKING " if active else "rest     ") + show + f" | wingmen: {', '.join(remotes) or '-'}", flush=True)
            last_print = t0
        time.sleep(max(0.0, 1 / 30 - (time.time() - t0)))


if __name__ == "__main__":
    main()
