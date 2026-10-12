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
