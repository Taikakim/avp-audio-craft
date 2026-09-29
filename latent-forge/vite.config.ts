import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// The render server (avp-audio-craft/eval/explorer_render_server.py) defaults
// to :8056 and has no CORS headers of its own -- proxy through vite in dev so
// the browser only ever talks to one origin. Override with SA3_RENDER_SERVER
// if it's running elsewhere (e.g. tunnelled from the Arch box).
const RENDER_SERVER = process.env.SA3_RENDER_SERVER || "http://localhost:8056";

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      // Every route the server exposes (see docs/sa3-studio/ORIENTATION.md §2)
      // is under one of these prefixes or exact paths -- list them explicitly
      // rather than proxying "/" so vite's own asset serving is untouched.
      "/info": RENDER_SERVER,
      "/status": RENDER_SERVER,
      "/ckpts": RENDER_SERVER,
      "/presets": RENDER_SERVER,
      "/slots": RENDER_SERVER,
      "/roots": RENDER_SERVER,
      "/models": RENDER_SERVER,
      "/audio": RENDER_SERVER,
      "/generate": RENDER_SERVER,
      "/a2a_track": RENDER_SERVER,
      "/a2a_mix": RENDER_SERVER,
      "/longform": RENDER_SERVER,
      "/decode": RENDER_SERVER,
      "/bend": RENDER_SERVER,
      "/schedule": RENDER_SERVER,
      "/ab": RENDER_SERVER,
      "/crops": RENDER_SERVER,
      "/meta": RENDER_SERVER,
      "/player_status": RENDER_SERVER,
      "/source": RENDER_SERVER,
      "/mix": RENDER_SERVER,
      "/steer": RENDER_SERVER,
    },
  },
});
