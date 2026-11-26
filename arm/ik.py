"""Arm inverse kinematics: tracked hand -> arm/hand joint angles (degrees).

Internal frame "B" (same as Blender): x = right, y = forward, z = up, origin at the shoulder.
Config files use cockpit order (x right, y up, z forward) and are converted on load.

Joint chain (must match blender/build_arm.py):
  shoulder: Rz(sh_yaw) * Rx(sh_pitch) * Rz(sh_roll)   rest = arm hanging straight down (-z)
  elbow:    Rx(elbow)                                  bends toward the upper arm's local +y
  wrist:    Rz(fore_roll) * Ry(wr_pitch) * Rx(wr_yaw)  forearm roll, flexion, deviation
Rest hand: fingers down (-z), index knuckle forward of pinky knuckle (+y).
Pure Python, no dependencies.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------- tiny vector / matrix helpers (3x3 as list of rows) ----------
def add(a, b): return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
def sub(a, b): return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
def mul(a, s): return [a[0] * s, a[1] * s, a[2] * s]
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def norm(a): return math.sqrt(dot(a, a))
def unit(a):
    n = norm(a)
    return [a[0] / n, a[1] / n, a[2] / n] if n > 1e-9 else [0.0, 0.0, 0.0]
def col(M, j): return [M[0][j], M[1][j], M[2][j]]
def from_cols(x, y, z): return [[x[0], y[0], z[0]], [x[1], y[1], z[1]], [x[2], y[2], z[2]]]
def mm(A, B): return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def mv(A, v): return [dot(A[0], v), dot(A[1], v), dot(A[2], v)]
def tr(A): return [[A[j][i] for j in range(3)] for i in range(3)]
def Rx(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]
def Ry(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
def Rz(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]
def angle_between(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(a), unit(b))))))
def clamp(x, lo, hi): return lo if x < lo else hi if x > hi else x


def cockpit_to_b(v):  # (right, up, forward) -> (right, forward, up)
    return [v[0], v[2], v[1]]


def camera_to_b(p):
    """MediaPipe camera coords (x image-right, y image-down, z away from camera), camera facing the pilot."""
    return [-p[0], -p[2], -p[1]]


# ---------- config ----------
def load_channels():
    with open(os.path.join(HERE, "channels.json")) as f:
        return json.load(f)["channels"]


def load_aircraft(name):
    with open(os.path.join(HERE, "aircraft.json")) as f:
        cfg = json.load(f)[name]
    cfg = dict(cfg)
    cfg["box_center_b"] = cockpit_to_b(cfg["signal_box"]["center"])
    s = cfg["signal_box"]["size"]
    cfg["box_size_b"] = [s[0], s[2], s[1]]  # width, depth, height
    cfg["pole_b"] = unit(cockpit_to_b(cfg["elbow_pole"]))
    cfg.setdefault("size_ref", 0.12)
    return cfg


# ---------- forward kinematics (for tests and debugging) ----------
def forward(ch, cfg):
    """Return (elbow, wrist, hand_frame) in B for a set of channel angles."""
    U = mm(mm(Rz(ch["sh_yaw"]), Rx(ch["sh_pitch"])), Rz(ch["sh_roll"]))
    elbow = mv(U, [0, 0, -cfg["upper_arm"]])
    F = mm(U, Rx(ch["elbow"]))
    wrist = add(elbow, mv(F, [0, 0, -cfg["forearm"]]))
    H = mm(F, mm(mm(Rz(ch["fore_roll"]), Ry(ch["wr_pitch"])), Rx(ch["wr_yaw"])))
    return elbow, wrist, H


# ---------- inverse kinematics ----------
def solve_arm(target, hand_frame, cfg):
    """Two-bone IK to put the wrist at target (B, relative to shoulder) and orient the hand."""
    L1, L2 = cfg["upper_arm"], cfg["forearm"]
    dist = norm(target)
    t = unit(target) if dist > 1e-6 else [0, 0, -1]
    dist = clamp(dist, abs(L1 - L2) + 1e-3, L1 + L2 - 1e-3)
    T = mul(t, dist)
    # elbow direction: rotate from the target line toward the pole
    pole = cfg["pole_b"]
    n = sub(pole, mul(t, dot(pole, t)))
    if norm(n) < 1e-6:
        n = sub([0, 0, -1], mul(t, -t[2]))
    n = unit(n)
    cos_b = clamp((L1 * L1 + dist * dist - L2 * L2) / (2 * L1 * dist), -1, 1)
    b = math.acos(cos_b)
    d = unit(add(mul(t, math.cos(b)), mul(n, math.sin(b))))  # upper arm direction
    elbow = mul(d, L1)
    f = unit(sub(T, elbow))                                    # forearm direction

    pitch = math.degrees(math.acos(clamp(-d[2], -1, 1)))
    yaw = math.degrees(math.atan2(-d[0], d[1])) if pitch > 1e-3 else 0.0
    A = mm(Rz(yaw), Rx(pitch))
    bend = sub(f, mul(d, dot(f, d)))
    if norm(bend) > 1e-6:
        bend = unit(bend)
        roll = math.degrees(math.atan2(-dot(bend, col(A, 0)), dot(bend, col(A, 1))))
    else:
        roll = 0.0
    elbow_deg = angle_between(d, f)

    U = mm(A, Rz(roll))
    F = mm(U, Rx(elbow_deg))
    rel = mm(tr(F), hand_frame)                                # = Rz(r) Ry(p) Rx(y)
    wp = math.degrees(math.asin(clamp(-rel[2][0], -1, 1)))
    wy = math.degrees(math.atan2(rel[2][1], rel[2][2]))
    wr = math.degrees(math.atan2(rel[1][0], rel[0][0]))
    return {"sh_yaw": yaw, "sh_pitch": pitch, "sh_roll": roll, "elbow": elbow_deg,
            "fore_roll": wr, "wr_pitch": wp, "wr_yaw": wy}


def hand_frame_from_landmarks(wb):
    """Hand orientation from world landmarks already in B. Columns = hand x, y, z."""
    hz = mul(unit(sub(wb[9], wb[0])), -1)           # fingers point along -z
    across = sub(wb[5], wb[17])                     # pinky knuckle -> index knuckle = +y
    hy = unit(sub(across, mul(hz, dot(across, hz))))
    hx = cross(hy, hz)
    return from_cols(hx, hy, hz)


def finger_angles(wb):
    def bend(a, b, c): return angle_between(sub(b, a), sub(c, b))
    out = {}
    for name, (m, p, d, tip) in {"index": (5, 6, 7, 8), "middle": (9, 10, 11, 12),
                                 "ring": (13, 14, 15, 16), "pinky": (17, 18, 19, 20)}.items():
        out["curl_" + name] = (bend(wb[0], wb[m], wb[p]) + bend(wb[m], wb[p], wb[d]) + bend(wb[p], wb[d], wb[tip])) / 3
    out["curl_thumb"] = (bend(wb[1], wb[2], wb[3]) + bend(wb[2], wb[3], wb[4])) / 2
    out["thumb_opp"] = angle_between(sub(wb[2], wb[1]), sub(wb[5], wb[0]))
    out["spread"] = angle_between(sub(wb[6], wb[5]), sub(wb[18], wb[17])) / 2
    return out


def target_from_image(p, cfg):
    """p = [x, y, size] of the wrist in the camera image (0-1) -> wrist target in B."""
    cx, cy, cz = cfg["box_center_b"]
    w, depth, h = cfg["box_size_b"]
    x, y, size = p
    fwd = clamp((size - cfg["size_ref"]) / cfg["size_ref"], -1, 1) * depth / 2
    return [cx + (0.5 - x) * w, cy + fwd, cz + (0.5 - y) * h]


def hand_to_channels(hand, cfg):
    """hand = {"w": 63 floats (MediaPipe world landmarks), "p": [x, y, size]} -> degrees per channel."""
    w = hand["w"]
    wb = [camera_to_b(w[i * 3:i * 3 + 3]) for i in range(21)]
    ch = solve_arm(target_from_image(hand["p"], cfg), hand_frame_from_landmarks(wb), cfg)
    ch.update(finger_angles(wb))
    return ch


def to_anim(ch_deg, channels):
    """Degrees -> 0..100 animation positions."""
    out = {}
    for c in channels:
        v = ch_deg.get(c["id"], 0.0)
        out[c["id"]] = clamp((v - c["min"]) / (c["max"] - c["min"]) * 100.0, 0.0, 100.0)
    return out
