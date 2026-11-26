"""Build the hand-signal arm in Blender (4.x) for MSFS 2024.

Run:  blender --background --python build_arm.py -- --side left --out hsig_arm.blend
  or open Blender > Scripting > open this file > Run Script (edit SIDE below).

What it makes
  - A rigid-segment arm: flight-suit sleeve + sage flight glove with leather fingertips.
  - A chain of empties, one rotation axis each, matching arm/ik.py exactly:
      HSIG_root > HSIG_sh_yaw(Z) > HSIG_sh_pitch(X) > HSIG_sh_roll(Z) > upper arm
        > HSIG_elbow(X) > forearm > HSIG_fore_roll(Z) > HSIG_wr_pitch(Y) > HSIG_wr_yaw(X) > hand
  - One animation per channel in channels.json, frames 0..100 = min..max degrees, LINEAR.
    Each animation is an NLA track named HSIG_<channel>. Tracks with the same name on different
    objects (e.g. the 3 joints of a finger) are merged into one glTF animation when you export with
    Animation mode = "NLA Tracks".
Axes: Blender x = right, y = forward (aircraft nose), z = up. Origin = shoulder joint.
Export with the MSFS 2024 Blender exporter to hsig_arm.gltf (+ .bin), then run ../msfs/make_package.py.
"""
import json
import math
import os
import sys

import bpy

SIDE = "left"
FACE_NEG_Y = False                   # set True (or pass --face-neg-y) if the arm comes out facing backwards in the sim
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = None
for i, a in enumerate(argv):
    if a == "--side":
        SIDE = argv[i + 1]
    if a == "--out":
        OUT = argv[i + 1]
    if a == "--face-neg-y":
        FACE_NEG_Y = True

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else bpy.path.abspath("//")
ARM_DIR = os.path.normpath(os.path.join(HERE, ".."))
CHANNELS = {c["id"]: c for c in json.load(open(os.path.join(ARM_DIR, "channels.json")))["channels"]}
AC = json.load(open(os.path.join(ARM_DIR, "aircraft.json")))["hawk_t2"]
L1, L2 = AC["upper_arm"], AC["forearm"]
S = 1 if SIDE == "left" else -1      # palm faces +x (inboard) for a left arm, -x for a right arm
CURL_SIGN = -S                       # fingers curl toward the palm

# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 0, 100


def material(name, rgb, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    return m


NOMEX = material("HSIG_Glove_Nomex", (0.11, 0.12, 0.075), 0.9)
LEATHER = material("HSIG_Glove_Leather", (0.33, 0.21, 0.10), 0.55)
SUIT = material("HSIG_FlightSuit", (0.09, 0.10, 0.06), 0.85)


def empty(name, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.03
    e.rotation_mode = "XYZ"
    scene.collection.objects.link(e)
    e.parent = parent
    e.location = loc
    return e


def mesh(kind, name, parent, size, loc, mat, rot=(0, 0, 0)):
    if kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=size[0], depth=size[1], location=(0, 0, 0))
    elif kind == "cone":  # size = (radius at the -z end, radius at the +z end, length)
        bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=size[0], radius2=size[1], depth=size[2], location=(0, 0, 0))
    elif kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=18, ring_count=12, radius=size[0], location=(0, 0, 0))
    else:  # rounded box
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
        o = bpy.context.object
        o.scale = size
        bpy.ops.object.transform_apply(scale=True)
        bev = o.modifiers.new("bevel", "BEVEL")
        bev.width, bev.segments = 0.008, 3
    o = bpy.context.object
    o.name = name
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    o.parent = parent
    o.location = loc
    o.rotation_euler = rot
    return o


# ---------------------------------------------------------------- arm chain
root = empty("HSIG_root")
if FACE_NEG_Y:
    root.rotation_euler[2] = math.pi
sh_yaw = empty("HSIG_sh_yaw", root)
sh_pitch = empty("HSIG_sh_pitch", sh_yaw)
sh_roll = empty("HSIG_sh_roll", sh_pitch)
mesh("sphere", "HSIG_shoulder_mesh", sh_roll, (0.055,), (0, 0, 0), SUIT)
mesh("cone", "HSIG_upperarm_mesh", sh_roll, (0.042, 0.052, L1), (0, 0, -L1 / 2), SUIT)
elbow = empty("HSIG_elbow", sh_roll, (0, 0, -L1))
mesh("sphere", "HSIG_elbow_mesh", elbow, (0.044,), (0, 0, 0), SUIT)
mesh("cone", "HSIG_forearm_mesh", elbow, (0.034, 0.042, L2 * 0.7), (0, 0, -L2 * 0.35), SUIT)
mesh("cone", "HSIG_cuff_mesh", elbow, (0.036, 0.048, L2 * 0.32), (0, 0, -L2 * 0.84), NOMEX)   # glove gauntlet
fore_roll = empty("HSIG_fore_roll", elbow, (0, 0, -L2))
wr_pitch = empty("HSIG_wr_pitch", fore_roll)
wr_yaw = empty("HSIG_wr_yaw", wr_pitch)

# ---------------------------------------------------------------- gloved hand (fingers along -z, index at +y)
PALM_L = 0.095
mesh("box", "HSIG_palm_mesh", wr_yaw, (0.032, 0.085, PALM_L), (0, 0, -PALM_L / 2), NOMEX)
FINGERS = {"index": (0.030, (0.045, 0.026, 0.020)), "middle": (0.010, (0.050, 0.030, 0.022)),
           "ring": (-0.010, (0.046, 0.028, 0.021)), "pinky": (-0.030, (0.036, 0.022, 0.018))}
SPREAD_W = {"index": 1.0, "middle": 0.0, "ring": -0.5, "pinky": -1.0}
drives = {cid: [] for cid in CHANNELS}   # channel -> [(object, axis index, weight)]
drives["sh_yaw"].append((sh_yaw, 2, 1)); drives["sh_pitch"].append((sh_pitch, 0, 1))
drives["sh_roll"].append((sh_roll, 2, 1)); drives["elbow"].append((elbow, 0, 1))
drives["fore_roll"].append((fore_roll, 2, 1)); drives["wr_pitch"].append((wr_pitch, 1, 1))
drives["wr_yaw"].append((wr_yaw, 0, 1))
for name, (y, segs) in FINGERS.items():
    spread = empty(f"HSIG_{name}_spread", wr_yaw, (0, y, -PALM_L))
    drives["spread"].append((spread, 0, SPREAD_W[name]))
    parent = spread
    for j, seg in enumerate(segs):
        joint = empty(f"HSIG_{name}_{j}", parent, (0, 0, 0) if j == 0 else (0, 0, -segs[j - 1]))
        drives["curl_" + name].append((joint, 1, CURL_SIGN))
        mat = LEATHER if j == 2 else NOMEX
        r = 0.0105 - j * 0.001
        mesh("cyl", f"HSIG_{name}_{j}_mesh", joint, (r, seg), (0, 0, -seg / 2), mat)
        mesh("sphere", f"HSIG_{name}_{j}_knuckle", joint, (r * 1.05,), (0, 0, 0), mat)
        parent = joint
    mesh("sphere", f"HSIG_{name}_tip", parent, (0.0095,), (0, 0, -segs[-1]), LEATHER)

thumb_base = empty("HSIG_thumb_base", wr_yaw, (S * 0.012, 0.040, -0.025))
thumb_base.rotation_euler = (math.radians(-35), 0, 0)          # thumb points forward-down at rest
drives["thumb_opp"].append((thumb_base, 2, S))
parent = thumb_base
for j, seg in enumerate((0.042, 0.033, 0.028)):
    joint = empty(f"HSIG_thumb_{j}", parent, (0, 0, 0) if j == 0 else (0, 0, -(0.042, 0.033)[j - 1]))
    drives["curl_thumb"].append((joint, 1, CURL_SIGN))
    mesh("cyl", f"HSIG_thumb_{j}_mesh", joint, (0.012 - j * 0.001, seg), (0, 0, -seg / 2), LEATHER if j == 2 else NOMEX)
    mesh("sphere", f"HSIG_thumb_{j}_knuckle", joint, (0.0125 - j * 0.001,), (0, 0, 0), NOMEX)
    parent = joint

# ---------------------------------------------------------------- animations
for cid, targets in drives.items():
    c = CHANNELS[cid]
    for obj, axis, weight in targets:
        base = obj.rotation_euler[axis]
        obj.animation_data_create()
        act = bpy.data.actions.new(f"HSIG_{cid}__{obj.name}")
        obj.animation_data.action = act
        for frame, deg in ((0, c["min"]), (100, c["max"])):
            obj.rotation_euler[axis] = base + math.radians(deg * weight)
            obj.keyframe_insert("rotation_euler", index=axis, frame=frame)
        for fc in act.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        track = obj.animation_data.nla_tracks.new()
        track.name = f"HSIG_{cid}"
        track.strips.new(track.name, 0, act)
        obj.animation_data.action = None
        obj.rotation_euler[axis] = base

if OUT:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
print("HSIG arm built:", SIDE, "arm,", sum(len(v) for v in drives.values()), "animated joints")
