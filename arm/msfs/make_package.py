#!/usr/bin/env python3
"""Generate the MSFS 2024 source files for the hand-signal arm.

  python make_package.py [--slots 4] [--gltf path/to/hsig_arm.gltf]

Writes ./out/hsig-arm/ containing
  SimAttachments/HSIG_Arm/model/       your own arm, attached to your aircraft (reads L:HSIG_0_*)
  SimObjects/Misc/HSIG_Arm_Slot_N/     one spawnable arm per wingman (reads L:HSIG_N_*)
  attached_objects_snippet.cfg         paste into your Hawk T2's attached_objects.cfg
Add these to a package in the MSFS 2024 Project Editor and build it (see the README).
If --gltf is given, the exported glTF + .bin are copied next to every model XML.
"""
import argparse
import json
import os
import shutil
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
CHANNELS = [c["id"] for c in json.load(open(os.path.join(HERE, "..", "channels.json")))["channels"]]


def model_xml(prefix, gltf_name, own_aircraft):
    anims = "\n".join(f"""      <UseTemplate Name="ASOBO_GT_Anim_Code">
        <ANIM_NAME>HSIG_{c}</ANIM_NAME>
        <ANIM_CODE>(L:{prefix}{c})</ANIM_CODE>
        <ANIM_LENGTH>100</ANIM_LENGTH>
      </UseTemplate>""" for c in CHANNELS)
    # Own arm: only on your own aircraft (not on other players' copies of it), and only while tracking.
    vis = f"(L:{prefix}active) (A:IS USER SIM, Bool) and" if own_aircraft else f"(L:{prefix}active)"
    guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, "hsig-arm-" + prefix)) + "}"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!-- Hand-signal arm. Animations HSIG_<channel> run 0..100, driven by bridge.py through L:{prefix}<channel>. -->
<ModelInfo guid="{guid}" version="1.1">
  <LODS>
    <LOD minSize="0" ModelFile="{gltf_name}"/>
  </LODS>
  <Behaviors>
    <Include ModelBehaviorFile="Asobo\\Common.xml"/>
    <Component ID="HSIG_ARM">
{anims}
      <UseTemplate Name="ASOBO_GT_Visibility_Code">
        <NODE_ID>HSIG_root</NODE_ID>
        <VISIBILITY_CODE>{vis}</VISIBILITY_CODE>
      </UseTemplate>
    </Component>
  </Behaviors>
</ModelInfo>
"""


def slot_sim_cfg(n):
    return f"""; Spawnable wingman arm, slot {n}. bridge.py spawns it by this title and moves it every frame.
; If spawning fails, compare this file with a simple SimObject from the MSFS 2024 SDK samples.
[VERSION]
major = 1
minor = 0

[fltsim.0]
title = "HSIG Arm Slot {n}"
model = ""

[General]
category = "SimpleObject"
"""


SNIPPET = r"""; ---- Hand-signal arm: paste into the Hawk T2's attached_objects.cfg ----
; Pick an exterior node near the front seat for attach_to_node (look in the SimObject Editor's
; node list), then move the arm's shoulder onto the pilot's LEFT shoulder with attach_offset (metres)
; and turn it with attach_pbh if it faces backwards (try 0,180,0).
[SIM_ATTACHMENT.N]
attachment_root = "SimAttachments\HSIG_Arm\"
attachment_file = "model\HSIG_Arm.xml"
attach_to_model = "exterior"
attach_to_node = "REPLACE_WITH_SEAT_NODE"
attach_offset = -0.24, 0.85, 0.0
attach_pbh = 0, 0, 0
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", type=int, default=4)
    ap.add_argument("--gltf", help="exported hsig_arm.gltf (its .bin must sit beside it)")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "hsig-arm"))
    a = ap.parse_args()

    gltf_name = os.path.basename(a.gltf) if a.gltf else "hsig_arm.gltf"
    model_dirs = []

    own = os.path.join(a.out, "SimAttachments", "HSIG_Arm", "model")
    os.makedirs(own, exist_ok=True)
    open(os.path.join(own, "HSIG_Arm.xml"), "w").write(model_xml("HSIG_0_", gltf_name, True))
    model_dirs.append(own)

    for n in range(1, a.slots + 1):
        d = os.path.join(a.out, "SimObjects", "Misc", f"HSIG_Arm_Slot_{n}")
        m = os.path.join(d, "model")
        os.makedirs(m, exist_ok=True)
        open(os.path.join(d, "sim.cfg"), "w").write(slot_sim_cfg(n))
        open(os.path.join(m, "model.cfg"), "w").write(f"[models]\nnormal = HSIG_Arm_Slot_{n}.xml\n")
        open(os.path.join(m, f"HSIG_Arm_Slot_{n}.xml"), "w").write(model_xml(f"HSIG_{n}_", gltf_name, False))
        model_dirs.append(m)

    open(os.path.join(a.out, "attached_objects_snippet.cfg"), "w").write(SNIPPET)

    if a.gltf:
        src_bin = os.path.splitext(a.gltf)[0] + ".bin"
        for d in model_dirs:
            shutil.copy(a.gltf, d)
            if os.path.exists(src_bin):
                shutil.copy(src_bin, d)
    print(f"Wrote {len(model_dirs)} models ({a.slots} wingman slots) to {a.out}"
          + ("" if a.gltf else "  -- no glTF copied yet; rerun with --gltf after exporting from Blender"))


if __name__ == "__main__":
    main()
