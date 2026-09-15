# Latent Forge M11 — Remote serving and operator docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kim can run Latent Forge himself, locally or remotely: a dependency-free Node server serves the built app, proxies the render server and enforces HTTP Basic auth; the RUNBOOK tells him exactly how to start, expose, verify and stop it; the temporary review stack is retired.

**Architecture:** `latent-forge/serve/server.mjs` exports `createForgeServer({distDir, upstream, user, pass})` (static `dist/` with SPA fallback + streaming reverse proxy for the render server's route prefixes + Basic auth compared in constant time) and runs it when executed directly. The Cloudflare quick tunnel points at it. No npm dependencies.

**Tech Stack:** Node 26 (`node:http`, `node:test`), Vite build output, `~/.local/bin/cloudflared`.

**Spec:** §2.3, §3, §12 M11. **Depends on:** M9 (the app in `latent-forge/` builds), M2 (`/forge` routes).

## Global Constraints

- Worktree `/home/kim/Projects/sa3-studio-review`, branch `latent-forge`; commits via `Misc/agent_commit.sh WINTERMUTE -m "..."`; explicit `git add` paths. Push only when Kim asks.
- Password only from the environment variable `LATENT_FORGE_PASS`; user `LATENT_FORGE_USER` (default `kim`); port `LATENT_FORGE_PORT` (default `5180`); upstream `LATENT_FORGE_UPSTREAM` (default `http://127.0.0.1:8056`); dist `LATENT_FORGE_DIST` (default `latent-forge/dist`). Bind `127.0.0.1` only.
- Never write the password, the tunnel URL or hostnames into any file, commit, WORKLOG or dialogue post.
- Proxied prefixes exactly: `/info /status /ckpts /presets /slots /roots /models /audio /generate /a2a_track /a2a_mix /longform /decode /bend /schedule /ab /crops /meta /player_status /source /mix /steer /forge` (each matches itself and `<prefix>/...`).
- The `Authorization` header is not forwarded upstream.
- WORKLOG/dialogue entries written 08:00–17:00 Helsinki do not name Kim.

## File Structure

| File | Responsibility |
|---|---|
| `latent-forge/serve/server.mjs` | static + proxy + auth server |
| `latent-forge/serve/server.test.mjs` | node:test suite |
| `latent-forge/package.json` (modify) | `serve`, `test:serve` scripts |
| `latent-forge/README.md` (rewrite) | what the app is, dev vs served, where the spec is |
| `RUNBOOK.md` (modify, on this branch) | new section `## 17. Latent Forge` |
| `ARCHITECTURE.md` (modify, on this branch) | one reuse-index line |

---

### Task 1: The serve module

**Files:**
- Create: `latent-forge/serve/server.mjs`, `latent-forge/serve/server.test.mjs`
- Modify: `latent-forge/package.json`

**Interfaces:**
- Produces: `PROXY_PREFIXES: string[]`, `isProxied(pathname) -> boolean`, `checkAuth(header, user, pass) -> boolean`, `createForgeServer({distDir, upstream, user, pass}) -> http.Server`.

- [ ] **Step 1: Write the failing test**

`latent-forge/serve/server.test.mjs`:
```js
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createForgeServer, isProxied, checkAuth } from "./server.mjs";

const AUTH = "Basic " + Buffer.from("kim:s3cret").toString("base64");
let upstream, forge, base, seen;

function listen(server) {
  return new Promise((res) => server.listen(0, "127.0.0.1", () => res(server.address().port)));
}

before(async () => {
  const dist = mkdtempSync(join(tmpdir(), "forge-dist-"));
  writeFileSync(join(dist, "index.html"), "<!doctype html><title>Latent Forge</title>");
  mkdirSync(join(dist, "assets"));
  writeFileSync(join(dist, "assets", "app.js"), "console.log(1)");
  upstream = http.createServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      seen = { method: req.method, url: req.url, auth: req.headers.authorization, body };
      res.writeHead(202, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, echo: body }));
    });
  });
  const upPort = await listen(upstream);
  forge = createForgeServer({ distDir: dist, upstream: `http://127.0.0.1:${upPort}`, user: "kim", pass: "s3cret" });
  base = `http://127.0.0.1:${await listen(forge)}`;
});

after(() => {
  forge.close();
  upstream.close();
});

test("prefix matching", () => {
  assert.equal(isProxied("/forge/jobs"), true);
  assert.equal(isProxied("/forge"), true);
  assert.equal(isProxied("/status"), true);
  assert.equal(isProxied("/forgery"), false);
  assert.equal(isProxied("/assets/app.js"), false);
});

test("checkAuth", () => {
  assert.equal(checkAuth(AUTH, "kim", "s3cret"), true);
  assert.equal(checkAuth("Basic " + Buffer.from("kim:nope").toString("base64"), "kim", "s3cret"), false);
  assert.equal(checkAuth("Basic " + Buffer.from("kimonly").toString("base64"), "kim", "s3cret"), false);
  assert.equal(checkAuth(undefined, "kim", "s3cret"), false);
});

test("401 without auth", async () => {
  const r = await fetch(base + "/");
  assert.equal(r.status, 401);
  assert.match(r.headers.get("www-authenticate"), /Latent Forge/);
});

test("static index, asset, SPA fallback", async () => {
  const h = { headers: { authorization: AUTH } };
  const index = await fetch(base + "/", h);
  assert.equal(index.status, 200);
  assert.match(await index.text(), /Latent Forge/);
  const js = await fetch(base + "/assets/app.js", h);
  assert.equal(js.headers.get("content-type"), "text/javascript");
  const spa = await fetch(base + "/some/client/route", h);
  assert.match(await spa.text(), /Latent Forge/);
});

test("traversal never escapes dist", async () => {
  const r = await fetch(base + "/%2e%2e/%2e%2e/%2e%2e/etc/passwd", { headers: { authorization: AUTH } });
  const text = await r.text();
  assert.doesNotMatch(text, /root:/);
});

test("proxy streams body, keeps status, strips authorization", async () => {
  const r = await fetch(base + "/forge/jobs?x=1", {
    method: "POST", headers: { authorization: AUTH, "content-type": "application/json" },
    body: JSON.stringify({ op: "generate" }),
  });
  assert.equal(r.status, 202);
  assert.deepEqual(await r.json(), { ok: true, echo: '{"op":"generate"}' });
  assert.equal(seen.url, "/forge/jobs?x=1");
  assert.equal(seen.auth, undefined);
});

test("502 when upstream is down", async () => {
  const dead = createForgeServer({ distDir: tmpdir(), upstream: "http://127.0.0.1:9", user: "kim", pass: "s3cret" });
  const port = await listen(dead);
  const r = await fetch(`http://127.0.0.1:${port}/status`, { headers: { authorization: AUTH } });
  assert.equal(r.status, 502);
  dead.close();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/sa3-studio-review/latent-forge && node --test serve/`
Expected: FAIL — `Cannot find module './server.mjs'`.

- [ ] **Step 3: Implement `latent-forge/serve/server.mjs`**

```js
// Latent Forge production server: built app + reverse proxy to the render server + HTTP Basic auth.
// No dependencies. Password comes only from LATENT_FORGE_PASS. Binds 127.0.0.1; expose it with a tunnel.
import http from "node:http";
import { createReadStream, statSync } from "node:fs";
import { extname, join, normalize, resolve, sep } from "node:path";
import { createHash, timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";

export const PROXY_PREFIXES = [
  "/info", "/status", "/ckpts", "/presets", "/slots", "/roots", "/models", "/audio", "/generate",
  "/a2a_track", "/a2a_mix", "/longform", "/decode", "/bend", "/schedule", "/ab", "/crops", "/meta",
  "/player_status", "/source", "/mix", "/steer", "/forge",
];

const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2",
  ".ico": "image/x-icon", ".map": "application/json", ".wav": "audio/wav",
};

export function isProxied(pathname) {
  return PROXY_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

const digest = (s) => createHash("sha256").update(String(s)).digest();

export function checkAuth(header, user, pass) {
  if (!header || !header.startsWith("Basic ")) return false;
  const decoded = Buffer.from(header.slice(6), "base64").toString("utf8");
  const i = decoded.indexOf(":");
  if (i < 0) return false;
  const userOk = timingSafeEqual(digest(decoded.slice(0, i)), digest(user));
  const passOk = timingSafeEqual(digest(decoded.slice(i + 1)), digest(pass));
  return userOk && passOk;
}

export function createForgeServer({ distDir, upstream, user, pass }) {
  const root = resolve(distDir);
  const up = new URL(upstream);
  return http.createServer((req, res) => {
    if (!checkAuth(req.headers.authorization, user, pass)) {
      res.writeHead(401, { "WWW-Authenticate": 'Basic realm="Latent Forge"', "Content-Type": "text/plain" });
      res.end("Auth required");
      return;
    }
    const url = new URL(req.url, "http://local");
    if (isProxied(url.pathname)) {
      const headers = { ...req.headers, host: up.host };
      delete headers.authorization;
      const preq = http.request(
        { hostname: up.hostname, port: up.port, method: req.method, path: url.pathname + url.search, headers },
        (pres) => {
          res.writeHead(pres.statusCode ?? 502, pres.headers);
          pres.pipe(res);
        },
      );
      preq.on("error", (e) => {
        if (!res.headersSent) res.writeHead(502, { "Content-Type": "text/plain" });
        res.end(`render server unreachable: ${e.message}`);
      });
      req.pipe(preq);
      return;
    }
    if (req.method !== "GET" && req.method !== "HEAD") {
      res.writeHead(405);
      res.end();
      return;
    }
    let rel;
    try {
      rel = decodeURIComponent(url.pathname);
    } catch {
      res.writeHead(400);
      res.end();
      return;
    }
    let file = resolve(join(root, normalize(rel)));
    if (file !== root && !file.startsWith(root + sep)) file = join(root, "index.html");
    let st;
    try {
      st = statSync(file);
      if (st.isDirectory()) {
        file = join(file, "index.html");
        st = statSync(file);
      }
    } catch {
      file = join(root, "index.html");
      try {
        st = statSync(file);
      } catch {
        res.writeHead(404, { "Content-Type": "text/plain" });
        res.end("dist not built — run npm run build");
        return;
      }
    }
    res.writeHead(200, {
      "Content-Type": MIME[extname(file)] ?? "application/octet-stream",
      "Content-Length": st.size,
      "Cache-Control": extname(file) === ".html" ? "no-cache" : "public, max-age=3600",
    });
    if (req.method === "HEAD") {
      res.end();
      return;
    }
    createReadStream(file).pipe(res);
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const pass = process.env.LATENT_FORGE_PASS;
  if (!pass) {
    console.error("LATENT_FORGE_PASS is not set");
    process.exit(1);
  }
  const upstreamUrl = process.env.LATENT_FORGE_UPSTREAM ?? "http://127.0.0.1:8056";
  const port = Number(process.env.LATENT_FORGE_PORT ?? 5180);
  const server = createForgeServer({
    distDir: process.env.LATENT_FORGE_DIST ?? fileURLToPath(new URL("../dist", import.meta.url)),
    upstream: upstreamUrl,
    user: process.env.LATENT_FORGE_USER ?? "kim",
    pass,
  });
  server.listen(port, "127.0.0.1", () => console.log(`[latent-forge] http://127.0.0.1:${port} -> ${upstreamUrl}`));
}
```

In `latent-forge/package.json` `"scripts"` add:
```json
    "serve": "node serve/server.mjs",
    "test:serve": "node --test serve/"
```

- [ ] **Step 4: Run tests**

Run: `cd latent-forge && npm run test:serve`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add latent-forge/serve/server.mjs latent-forge/serve/server.test.mjs latent-forge/package.json
Misc/agent_commit.sh WINTERMUTE -m "latent-forge: dependency-free serve (static + proxy + basic auth)"
```

---

### Task 2: Operator docs

**Files:**
- Modify: `RUNBOOK.md` (append section 17), `ARCHITECTURE.md` (one line)
- Rewrite: `latent-forge/README.md`

- [ ] **Step 1: Append to `RUNBOOK.md`**

```markdown
## 17. Latent Forge (the arrangement / render app)

Two processes: the render server on **:8056** (the only model process) and the Latent Forge
server on **:5180** (built app + proxy + password). Until the `latent-forge` branch is merged,
every path below is the worktree `/home/kim/Projects/sa3-studio-review`; after the merge,
substitute `/home/kim/Projects/SAO`.

**Start the render server** (takes the GPU lock as `KIND=server`, ~40 s to ready):

    cd /home/kim/Projects/sa3-studio-review
    eval/forge/dev_server.sh start

**Build and serve the app** (~20 s build):

    cd /home/kim/Projects/sa3-studio-review/latent-forge
    npm ci && npm run build
    export LATENT_FORGE_PASS='<pick one; do not write it down in the repo>'
    npm run serve            # leave running; Ctrl+C stops it

**Remote access** (a second shell; prints an https://…trycloudflare.com URL — share it only with yourself):

    ~/.local/bin/cloudflared tunnel --url http://127.0.0.1:5180

VERIFY:
- `curl -s -o /dev/null -w '%{http_code}\n' localhost:5180/` prints `401`.
- `curl -s -u kim:"$LATENT_FORGE_PASS" localhost:5180/forge/backbone` prints JSON with `"ok": true`.
- In the browser, the top bar reads `LATENT FORGE` and the MODEL select lists the backbones.
- Long renders keep going past 100 s through the tunnel: RENDER/MIXDOWN are background jobs, the page polls.

**Stop:** Ctrl+C the tunnel and the serve process, then `eval/forge/dev_server.sh stop`
(releases the GPU lock). `eval/forge/dev_server.sh status` shows what is still running.

**Local-only work** skips the password and tunnel: `npm run dev` in `latent-forge/` (Vite on :5173
proxies to :8056).
```

- [ ] **Step 2: Add the ARCHITECTURE reuse-index line**

In `ARCHITECTURE.md`, in the reuse index next to the render server entry, add:
```markdown
- **Latent Forge** — `latent-forge/` (Svelte 5 app) + `eval/forge_api.py` / `eval/forge/` (the `/forge/*` API: async jobs, uploads, sessions/presets, chroma, stretch, stats, schedule shapes, per-lane commit pipeline). Spec `docs/superpowers/specs/2026-09-15-latent-forge-design.md`; operate via RUNBOOK §17.
```

- [ ] **Step 3: Rewrite `latent-forge/README.md`**

```markdown
# Latent Forge

A four-lane arrangement workspace for Stable Audio 3: place, stretch and align clips on an audio
timeline, audition renders before they touch the arrangement, then MIXDOWN — each lane is encoded,
steered through its own chain (LatCH / FiLM / LoRA / Bungee), overlaps are inpainted, lanes are
mixed in latent space and the master chain runs before one decode.

- **Spec:** `docs/superpowers/specs/2026-09-15-latent-forge-design.md`
- **Backend:** the resident render server `eval/explorer_render_server.py` (:8056) and its
  `/forge/*` routes (`eval/forge_api.py`).
- **Run it:** RUNBOOK §17. Development: `npm run dev` (Vite :5173, proxies to :8056).
- **Tests:** `npm test` (vitest), `npm run test:serve` (serve module), Playwright layout checks
  against the fixture mock (`docs/latent-forge/contract/fixtures/`).

The timeline is audio; renders land in the preview container and enter the timeline only when
dragged there; MIXDOWN is the only thing that commits the arrangement.
```

- [ ] **Step 4: Commit**

```bash
git add RUNBOOK.md ARCHITECTURE.md latent-forge/README.md
Misc/agent_commit.sh WINTERMUTE -m "docs(latent-forge): RUNBOOK §17, ARCHITECTURE entry, app README"
```

---

### Task 3: End-to-end remote check and retiring the review stack

- [ ] **Step 1: Retire the temporary review stack** (it predates Latent Forge and holds an old password)

```bash
pkill -f "cloudflared tunnel --url http://127.0.0.1:5180" || true
pkill -f "sa3-studio-review/auth-proxy/server.js" || true
pkill -f "sa3-studio-review/sa3-studio/node_modules/.bin/vite" || true
cd /home/kim/Projects/sa3-studio-review && git status --short auth-proxy
```
Expected: `auth-proxy/` shows as untracked (`??`). Remove it: `rm -r auth-proxy`. It was never committed.

- [ ] **Step 2: Follow RUNBOOK §17 exactly** — start the render server, build, serve with a freshly generated password (`python3 -c 'import secrets; print(secrets.token_urlsafe(18))'`, kept in the shell only), start the tunnel.

- [ ] **Step 3: Verify through the tunnel** (substitute the printed URL in the shell only)

```bash
U='<tunnel url>'
curl -s -o /dev/null -w '%{http_code}\n' "$U/"                                     # 401
curl -s -u kim:"$LATENT_FORGE_PASS" -o /dev/null -w '%{http_code}\n' "$U/"         # 200
curl -s -u kim:"$LATENT_FORGE_PASS" "$U/forge/backbone" | head -c 120; echo       # {"ok":true,...
```
Then submit a 60 s generate job through the tunnel and poll it to `done` — proves async rendering survives the 100 s edge timeout:
```bash
J=$(curl -s -u kim:"$LATENT_FORGE_PASS" -H 'Content-Type: application/json' -X POST "$U/forge/jobs" \
     -d '{"op":"generate","payload":{"prompt":"slow evolving pad","duration":60,"steps":24,"seed":3}}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')
until curl -s -u kim:"$LATENT_FORGE_PASS" "$U/forge/jobs/$J" | grep -q '"state": *"\(done\|error\)"'; do sleep 5; done
curl -s -u kim:"$LATENT_FORGE_PASS" "$U/forge/jobs/$J" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["state"], d["result"]["timings"]["total_sec"] if d["result"] else d["error"])'
```
Expected: `done <seconds>`.

- [ ] **Step 4: WORKLOG line** (public: no URL, no password, no hostnames; impersonal wording during 08:00–17:00 Helsinki)

```bash
cd /home/kim/Projects/SAO && Misc/worklog_note.sh WINTERMUTE "Latent Forge M11: served build + /forge API verified end-to-end through the tunnel (auth 401/200, 60 s async render done). Operator steps in RUNBOOK §17 on branch latent-forge."
```

- [ ] **Step 5: Tell Kim the tunnel URL and password in chat only**, then stop the tunnel if he does not want it kept up.
