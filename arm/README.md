# In-sim arm (MSFS 2024) — PC setup checklist

Your tracked hand drives a gloved arm in the cockpit, posed by inverse kinematics (IK), and it can be seen from outside the aircraft. Every pilot running this also sees their wingmen's arms on their aircraft.

```
phone tracker ──hand──▶ relay ◀──arm pose + position──▶ bridge.py (each pilot's PC)
                                                         ├─ L:HSIG_0_*  → your arm (SimAttachment on your Hawk)
                                                         └─ L:HSIG_N_*  → wingman N's arm (spawned object kept on their cockpit)
```

| File | Job |
|---|---|
| `ik.py` | Two-bone arm IK + wrist and finger angles. Tested: wrist error < 0.001 mm over 2,000 random poses. |
| `bridge.py` | Runs next to the sim. Relay ↔ SimConnect, using the same raw calls as vASW. |
| `channels.json` | The 14 joint channels and their angle ranges. Shared by the bridge and Blender. |
| `aircraft.json` | Hawk T2 preset: arm lengths, where your hand sits relative to the shoulder, seat position. |
| `blender/build_arm.py` | Builds the arm model with one animation per channel. |
| `msfs/make_package.py` | Writes the SimAttachment, wingman SimObjects and the `attached_objects.cfg` snippet. |

## Steps at the PC

1. **Try the bridge without the sim.** Start the relay (`node relay/server.js`), open the tracker on your phone, connect with callsign `LEAD`, then run:
   ```
   python arm/bridge.py --relay ws://localhost:8080 --callsign LEAD --dry-run
   ```
   You should see `TRACKING` and the shoulder and elbow angles change as you move your hand.
2. **Build the model.** Run `blender --background --python arm/blender/build_arm.py -- --side left --out hsig_arm.blend`. Open `hsig_arm.blend` and export with the MSFS 2024 exporter to `hsig_arm.gltf`, with **Animation mode: NLA Tracks**. This merges the per-joint tracks into one animation per channel.
3. **Make the package files** with `python arm/msfs/make_package.py --gltf path/to/hsig_arm.gltf`. In the Project Editor, add `out/hsig-arm/` to a package: SimAttachment + SimObjects asset groups. Build it and put it in Community.
4. **Attach it to the Hawk.** Paste `attached_objects_snippet.cfg` into the Hawk T2's `attached_objects.cfg`. Set `attach_to_node` to an exterior node near the front seat, then nudge `attach_offset` until the shoulder sits on the pilot's left shoulder.
5. **Fly.** Install SimConnect for Python (`pip install SimConnect`, or copy vASW's `SimConnect` folder into `arm/`). Then run:
   ```
   python arm/bridge.py --relay <relay> --room FLIGHT1 --callsign LEAD
   ```
   The arm appears while your hand is tracked and hides when it isn't.
6. **Calibrate once.** Run `python arm/bridge.py --callsign LEAD --calibrate` and pitch up / bank right. If either number reads negative, set that sign to −1 in `aircraft.json` → `"attitude_signs": {"pitch": -1, "bank": -1}` (the default). If it reads positive, set it to +1. This only affects where wingmen's arms are placed.

## Tuning
- **Hand too high, low or far:** `signal_box` in `aircraft.json` sets where your hand sits relative to the shoulder (metres; x right, y up, z forward).
- **Elbow pointing the wrong way:** `elbow_pole`.
- **Wingmen's arms trail behind their cockpit:** raise `--lead-ms` (try 50–150). Placing a wingman's arm needs that pilot's own position from the relay, so some lag at speed is expected.
- **Arm faces backwards in the sim:** rebuild with `--face-neg-y`, or set `attach_pbh = 0,180,0`.
- **Wrong hand picked:** the tracker labels left and right as if the image were mirrored. `"swap_handedness": true` (the default) corrects that for a front camera.

## Known limits (check these first if something's off)
- **Extra arm:** the Hawk's own pilot model keeps its left arm. If the pilot model is yours, hide its left arm while `(L:HSIG_0_active)` is 1.
- **Your arm showing on other Hawks:** your attached arm is hidden on other players' Hawks using `(A:IS USER SIM)`. Some MSFS 2024 builds report that wrongly for multiplayer aircraft. If your arm shows up on other Hawks, that's the cause.
- **Unconfirmed `sim.cfg` category:** the wingman arm objects use `category = "SimpleObject"`. If the bridge says it can't spawn them, compare `sim.cfg` with a simple SimObject sample from the SDK.
- **Not tested in the sim yet:** the Blender script and MSFS files were written against the 2024 SDK docs. Expect the first build to need small fixes.
