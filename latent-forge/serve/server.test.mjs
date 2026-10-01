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
