# Hand-signal project — context for Claude Code

The owner flies MSFS 2024 formation (multiplayer) and wants camera hand tracking → formation hand signals → a visible arm in the cockpit. Windows PC. They also have Quest 3 and Tobii Eye Tracker 5, and an older repo **vASW** (Python + vendored `SimConnect` package; `bridge.py` reuses its raw-DLL call style).

## What exists (all working/tested unless noted)
- `web/index.html`: phone/webcam tracker (MediaPipe Hand Landmarker + three.js flight-glove hand in its own centred view, camera as corner window). Sends `{type:"hand", callsign, hands:[{side, w:63 world floats, p:[x,y,size]}], label}` to the relay ~15 Hz. Live at https://datderpywastaken.github.io/hand-signal-test/ (GitHub Pages from `main`).
- `web/signals.js`: AFPAM 11-205 signal engine (shape + motion + sequences such as HEFOE, change lead and digits). Tests: `node test/signals.test.js` (23 synthetic cases).
- `web/viewer.js` / `viewer.html`, `msfs-panel/`: 2D wingman viewer + toolbar panel.
- `relay/server.js`: zero-dependency Node WebSocket relay with rooms (`/ws?room=`). Serves `web/`.
- `arm/`: in-sim IK arm for MSFS 2024. Read `arm/README.md`.
  - `ik.py`: two-bone IK. Frame: x right, y forward, z up (Blender). Tested in `test/test_ik.py`.
  - `bridge.py`: relay ↔ SimConnect. Own arm via `L:HSIG_0_*`. Wingmen via spawned `HSIG Arm Slot N` SimObjects moved every frame plus `L:HSIG_N_*`. `--dry-run`, `--calibrate`. Tested in `test/test_bridge_math.py`.
  - `blender/build_arm.py`, `msfs/make_package.py`: **untested** (no Blender/MSFS in the cloud session).
  - `aircraft.json` → `hawk_t2` preset. Shoulder offset, seat node and signal box are **placeholders**. The owner's own Hawk T2 aircraft project is the test bed, but it isn't in this repo yet.

## Open item (where we stopped)
Wingmen's arms lag behind their aircraft because they're separate objects positioned from outside the sim. Agreed direction, not yet built:
1. **Now:** position wingman arms from the multiplayer aircraft as rendered in the local sim (SimConnect data on multiplayer SimObjects, every visual frame) plus velocity prediction, instead of the relay-sent position.
2. **Test for zero lag:** put wingman arms inside the Hawk model as attachments driven by per-instance scoped L:vars (`L:1:`). Needs a dev-mode check of whether the Hawk's model behaviours/WASM run for other players' aircraft and can match an instance to a callsign by position. If yes, it replaces 1.

## First things to do on the PC
1. `node relay/server.js`, open the tracker on the phone, then `python arm/bridge.py --callsign LEAD --dry-run`.
2. Get the Hawk T2 project path from the owner. Fill in `attach_to_node` / `attach_offset` / `shoulder_offset`.
3. Run Blender + make_package, build in the Project Editor, and fix whatever the first build reports.

Commit messages end with the Co-Authored-By / Claude-Session lines already used in this repo's history.
