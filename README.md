# Hand Tracking → Formation Hand Signals

Your phone's camera tracks your hand, a 3D virtual hand copies it live, and the app recognises formation signals. Your wingmen see your hand and signal in an MSFS toolbar panel, or in a browser window on a second screen.

```
 Phone / webcam            Relay (your PC)            Wingman's MSFS
 ┌──────────────┐  wss    ┌───────────────┐   ws/wss   ┌────────────────────┐
 │ web/index.html│ ─────▶ │ relay/server.js│ ────────▶ │ Toolbar panel       │
 │ MediaPipe hand│        │ rooms per flight│           │ (or viewer.html)    │
 │ + 3D hand     │        └───────────────┘            └────────────────────┘
 └──────────────┘
```

| Folder | What it is |
|---|---|
| `web/index.html` | The tracker. Uses the camera and MediaPipe Hand Landmarker (21 points per hand, up to 2 hands), shows a 3D hand (three.js) and recognises signals. |
| `web/viewer.html` + `viewer.js` | The wingman view. Draws everyone else's hand and their current signal. |
| `relay/server.js` | A small server with no dependencies. It serves the web app and passes hand data between pilots in the same "room" (flight). |
| `msfs-panel/` | Files for the MSFS toolbar panel (it reuses `viewer.js`). |

You need **Node.js 18 or newer** on the PC that runs the relay. The tracker page loads MediaPipe and three.js from public CDNs, so the phone needs internet.

---

## 1. Try it on your PC (2 minutes)

```bash
node relay/server.js
```
Open `http://localhost:8080` in Chrome and press **Start camera**. Webcams work here because `localhost` counts as a secure origin. Then open `http://localhost:8080/viewer.html` in a second tab, connect both to room `FLIGHT1`, and the viewer will show your hand.

## 2. Run it on your phone

Browsers only allow the camera on **HTTPS** pages. Opening the PC's plain `http://192.168.x.x:8080` address on your phone loads the page, but the camera is blocked. The easiest fix is a free tunnel, which also gives you a `wss://` address for the relay:

```bash
node relay/server.js
# in a second terminal (Cloudflare's free tunnel, no account needed):
cloudflared tunnel --url http://localhost:8080
```
Open the `https://….trycloudflare.com` address it prints on your phone. The relay address is filled in for you. Press **Start camera**, then **Connect**. `ngrok http 8080` works the same way.

If you only want to test tracking without the relay, put the `web/` folder on any HTTPS host (GitHub Pages, Netlify) and open it on the phone.

Tips: prop the phone up facing you, light your hand from the front, and keep it 30–60 cm from the lens. **Flip camera** switches to the back camera.

## 3. Signals

A signal counts once it has been held steady for about 0.35 s. The defaults are placeholders. Edit them under **Signal meanings** on the page so they match what your flight briefs:

| Gesture | Key | Default meaning |
|---|---|---|
| Open palm | `OPEN_PALM` | HOLD / STANDBY |
| Fist | `FIST` | SPEEDBRAKES |
| Thumb up | `THUMBS_UP` | READY / AFFIRM |
| Thumb down | `THUMBS_DOWN` | NEGATIVE / PROBLEM |
| 1–4 fingers (thumb in) | `ONE`…`FOUR` | 1…4 (position / channel) |
| Thumb + little finger | `THUMB_PINKY` | REJOIN |

To add a gesture, add a rule to `classify()` in `web/index.html` and a matching key to the meanings.

## 4. Getting it into MSFS

**How it works:** MSFS multiplayer doesn't carry custom data between aircraft, so the relay does that job. Each pilot connects to the same relay room, and the toolbar panel shows the other pilots' hands and signals. **The hand does not appear on the other aircraft's 3D model.** That would need a separate WASM/SimObject add-on, and standard multiplayer wouldn't sync it anyway.

**Quickest option (no SDK needed):** open `http://<relay-address>/viewer.html?room=FLIGHT1&me=YOURCALLSIGN&auto=1` in a browser on a second monitor, or pin it over the sim with any always-on-top browser or overlay tool.

**In-game toolbar panel (MSFS SDK):**
1. Install the MSFS SDK (Dev Mode → Help → SDK Installer).
2. Open the SDK's **InGamePanels** sample project in the Project Editor and save a copy as `hand-signals-panel`.
3. Replace the sample's HTML/JS with the files in `msfs-panel/html_ui/InGamePanels/HandSignalsPanel/`, and its panel XML with `msfs-panel/InGamePanels/hand-signals-panel.xml`. If your SDK's sample HTML wrapper looks different from ours, keep the sample's `<ingame-ui>` wrapper and paste in our content block and scripts.
4. Add a toolbar icon SVG named `ICON_TOOLBAR_HAND_SIGNALS.svg` under `html_ui/Textures/Menu/toolbar/` (copy the sample's icon to start).
5. Build the package, then copy it from `Packages/` into your MSFS **Community** folder. Give the built package to your wingmen too.
6. In the sim, open **Hand Signals** from the toolbar, enter the relay address and room, and press Connect.

Relay address for the panel: use `ws://localhost:8080` if the relay runs on your own PC. For wingmen elsewhere, use the tunnel's `wss://…trycloudflare.com` address. A quick tunnel's address changes each time you restart it. For a fixed one, use a named Cloudflare tunnel or host `relay/server.js` on a small VPS.

The panel was written for the MSFS 2020 SDK sample layout and hasn't been tested inside the sim. MSFS 2024 uses the same HTML toolbar-panel system, but check the wrapper against your SDK's sample.

## Tuning

- Signals not detected: lower the `1.15` finger-extension threshold in `classify()`, or improve the lighting.
- Signals flickering: raise `HOLD_MS`.
- Network usage: the tracker sends about 15 updates a second (~1 KB each). To change it, edit `now - lastSend > 66` (66 ms ≈ 15 Hz).

## Next steps worth doing
- Swap the joint-and-bone hand for a rigged glTF hand model (drive its bones from the same landmarks).
- Moving signals (e.g. circling, a pat on the head for a lead change) by tracking landmark paths over ~1 s.
- An audio cue in the panel when a wingman's signal changes.
