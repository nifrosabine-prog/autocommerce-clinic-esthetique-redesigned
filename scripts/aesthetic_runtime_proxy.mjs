import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { URL } from "node:url";

const PORT = Number(process.env.PORT || 8180);
const API_PORT = 8100;
const STATIC_ROOT = "/home/ubuntu/aesthetic_runtime_audit/autocommerce-app/dist/public";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2" };

function proxyApi(req, res) {
  const upstream = http.request({ host: "127.0.0.1", port: API_PORT, method: req.method, path: req.url, headers: { ...req.headers, host: `127.0.0.1:${API_PORT}` } }, (response) => {
    res.writeHead(response.statusCode ?? 502, response.headers);
    response.pipe(res);
  });
  upstream.on("error", (error) => { res.writeHead(502, { "content-type": "application/json" }); res.end(JSON.stringify({ error: "API upstream unavailable", detail: error.message })); });
  req.pipe(upstream);
}

function serveStatic(req, res) {
  const requestUrl = new URL(req.url ?? "/", "http://aesthetic.local");
  let relative = decodeURIComponent(requestUrl.pathname);
  if (relative === "/") relative = "/index.html";
  const root = path.resolve(STATIC_ROOT);
  const candidate = path.resolve(root, `.${relative}`);
  const filePath = candidate.startsWith(root) && fs.existsSync(candidate) && fs.statSync(candidate).isFile() ? candidate : path.join(root, "index.html");
  res.writeHead(200, { "content-type": MIME[path.extname(filePath)] ?? "application/octet-stream" });
  fs.createReadStream(filePath).pipe(res);
}

http.createServer((req, res) => {
  if ((req.url ?? "/").startsWith("/api/")) return proxyApi(req, res);
  if (req.method !== "GET" && req.method !== "HEAD") { res.writeHead(405); return res.end("Method Not Allowed"); }
  return serveStatic(req, res);
}).listen(PORT, "0.0.0.0", () => console.log(`Aesthetic runtime proxy listening on ${PORT}`));
